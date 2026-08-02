"""
fita.backends.hdf5 -- FITA data model stored in HDF5 via h5py.

File layout
-----------
/                           root group
  .attrs                    global attributes (FITA version, pack, nlayers, ...)
  /layers/                  group per layer
    /layers/0001/           one sub-group per layer (zero-padded 4-digit index)
      .attrs                layer metadata (all KW_* keyword values)
      flux        Dataset   float32, shape (H, W), chunked, gzip-4
      alpha       Dataset   uint16,  shape (H, W), chunked, gzip-4
      uncert      Dataset   float32, shape (H, W)  [optional]
      mask        Dataset   uint8,   shape (H, W)  [optional]
      wcs_header  Dataset   scalar string (JSON-serialised FITS WCS header)
  /registry       Dataset   structured array mirroring FITA_LAYERS BINTABLE
  /meta           Group     IVOA provenance (key=value string attrs)  [optional]

Chunking strategy
-----------------
Default chunk shape is min(256, H) x min(256, W).  This is tunable via
the ``chunk_shape`` argument.  For whole-sky mosaics consider (512, 512).

Compression
-----------
Default: gzip level 4 with shuffle filter.  Pass ``compress=None`` to
disable or ``compress='lzf'`` for faster LZF (h5py built-in, no external
library required).

WCS serialisation
-----------------
astropy.wcs.WCS cannot be stored natively in HDF5.  We serialise the WCS
by converting it to a FITS Header, then to a JSON dict of
{keyword: value} pairs.  On read we reconstruct the Header and re-parse.

Round-trip fidelity
-------------------
All FITA keywords, WCS, flux/alpha/uncert/mask arrays, and extra_header
items survive a write/read round-trip.  BSCALE/BZERO scaling is applied
in-memory so the stored float32 always holds physical flux values.

Usage
-----
    from fita.backends.hdf5 import write, read
    from fita.layer import FITALayer
    import numpy as np

    # write
    layer = FITALayer.from_array(np.random.rand(512, 512).astype('float32'),
                                  layer_id=1, name='Test')
    write('test.h5', [layer])

    # read
    layers = read('test.h5')
    print(layers[0].shape)       # (512, 512)
    print(layers[0].flux_data.dtype)  # float32
"""

from __future__ import annotations
import json
import warnings
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple

import numpy as np

try:
    import h5py
    _H5PY = True
except ImportError:
    _H5PY = False

try:
    from astropy.wcs import WCS
    from astropy.io.fits import Header as FITSHeader
    _ASTROPY = True
except ImportError:
    _ASTROPY = False

from ..spec import (
    FITA_VERSION, PACK_FLOAT32, PACK_SPLIT16,
    KW_VERSION, KW_PACK, KW_NLAYERS, KW_CANVAS_W, KW_CANVAS_H,
    KW_LAYER_ID, KW_LAYER_NAME, KW_BLEND_MODE, KW_OPACITY,
    KW_FLUX_MIN, KW_FLUX_MAX, KW_WAVE_CVAL, KW_WAVE_BWID,
    KW_XOFFSET, KW_YOFFSET, KW_ALPHA_SRC, KW_DEPTH,
    KW_UNCERT_EXT, KW_MASK_EXT,
    LAYER_TABLE_COLS,
)
from ..layer import FITALayer

# ── Internal helpers ──────────────────────────────────────────────────────────

def _require_h5py():
    if not _H5PY:
        raise ImportError(
            "h5py is required for HDF5 backend: pip install h5py"
        )

def _require_astropy():
    if not _ASTROPY:
        raise ImportError(
            "astropy is required for WCS serialisation: pip install astropy"
        )


def _chunk_shape(h: int, w: int, target: int = 256) -> Tuple[int, int]:
    """Return a sensible chunk shape for a (H, W) array."""
    return (min(target, h), min(target, w))


def _wcs_to_json(wcs) -> str:
    """Serialise a WCS object to a JSON string via its FITS header."""
    if wcs is None or not _ASTROPY:
        return ""
    try:
        hdr = wcs.to_header()
        d = {k: v for k, v in hdr.items() if k}
        return json.dumps(d)
    except Exception:
        return ""


def _wcs_from_json(s: str):
    """Reconstruct a WCS from a JSON string.  Returns None on failure."""
    if not s or not _ASTROPY:
        return None
    try:
        d = json.loads(s)
        hdr = FITSHeader()
        for k, v in d.items():
            try:
                hdr[k] = v
            except Exception:
                pass
        return WCS(hdr, naxis=2)
    except Exception:
        return None


def _write_dataset(
    group: "h5py.Group",
    name: str,
    data: np.ndarray,
    compress: Optional[str] = "gzip",
    compress_opts: int = 4,
    chunk_shape: Optional[Tuple[int, int]] = None,
) -> None:
    """Create or replace a chunked, compressed dataset in *group*."""
    if data is None:
        return
    if name in group:
        del group[name]

    cs = chunk_shape or _chunk_shape(*data.shape[-2:])
    # For non-2D arrays (unlikely but defensive) fall back to no chunking
    if data.ndim != 2:
        cs = None

    kwargs: Dict[str, Any] = {}
    if compress and cs is not None:
        kwargs["compression"] = compress
        if compress == "gzip":
            kwargs["compression_opts"] = compress_opts
        kwargs["shuffle"] = True
        kwargs["chunks"] = cs

    group.create_dataset(name, data=data, **kwargs)


# ── Write ─────────────────────────────────────────────────────────────────────

def write(
    path: str | Path,
    layers: List[FITALayer],
    pack: str = PACK_FLOAT32,
    canvas_w: Optional[int] = None,
    canvas_h: Optional[int] = None,
    global_attrs: Optional[Dict[str, Any]] = None,
    bunit: str = "ct/s",
    compress: Optional[str] = "gzip",
    compress_opts: int = 4,
    chunk_shape: Optional[Tuple[int, int]] = None,
    overwrite: bool = True,
) -> None:
    """
    Write a list of FITALayer objects to a FITA/HDF5 file.

    Parameters
    ----------
    path          : output file path (.h5 or .fita.h5)
    layers        : list of FITALayer
    pack          : 'FLOAT32' (default) or 'SPLIT16'
                    With SPLIT16 the flux is re-encoded as uint16 on disk then
                    decoded back to float32 on read — useful only for
                    backward-compat testing; for new files use FLOAT32 (HDF5
                    compression is more space-efficient than SPLIT16).
    canvas_w/h    : optional logical canvas dimensions
    global_attrs  : extra key/value pairs to store in root .attrs
    bunit         : FITS BUNIT string for the flux unit
    compress      : 'gzip' (default), 'lzf', 'szip', or None
    compress_opts : gzip level 1-9 (default 4)
    chunk_shape   : (rows, cols) tile size; None = auto (min(256, H), min(256, W))
    overwrite     : replace existing file (default True)
    """
    _require_h5py()

    fpath = Path(path)
    if fpath.exists() and overwrite:
        fpath.unlink()
    elif fpath.exists() and not overwrite:
        raise FileExistsError(f"{fpath} already exists (overwrite=False)")

    with h5py.File(str(fpath), "w") as f:

        # ── Root attributes (global header) ──────────────────────────────────
        f.attrs[KW_VERSION]  = FITA_VERSION
        f.attrs[KW_PACK]     = pack
        f.attrs[KW_NLAYERS]  = len(layers)
        f.attrs["BUNIT"]     = bunit
        if canvas_w:
            f.attrs[KW_CANVAS_W] = canvas_w
        if canvas_h:
            f.attrs[KW_CANVAS_H] = canvas_h
        f.attrs["FITA_BACKEND"] = "HDF5"
        f.attrs["FITA_H5VER"]   = h5py.version.hdf5_version
        if global_attrs:
            for k, v in global_attrs.items():
                try:
                    f.attrs[k] = v
                except Exception:
                    pass

        # ── /layers group ─────────────────────────────────────────────────────
        layers_grp = f.require_group("layers")

        for layer in layers:
            i = layer.layer_id
            gname = f"{i:04d}"
            if gname in layers_grp:
                del layers_grp[gname]
            lg = layers_grp.create_group(gname)

            # -- layer metadata as HDF5 attributes ----------------------------
            lg.attrs[KW_LAYER_ID]   = i
            lg.attrs[KW_LAYER_NAME] = layer.name[:68]
            lg.attrs[KW_BLEND_MODE] = layer.blend_mode
            lg.attrs[KW_OPACITY]    = layer.opacity
            lg.attrs[KW_XOFFSET]    = layer.xoffset
            lg.attrs[KW_YOFFSET]    = layer.yoffset
            lg.attrs[KW_ALPHA_SRC]  = layer.alpha_src
            lg.attrs["VISIBLE"]     = layer.visible
            if layer.flux_min is not None:
                lg.attrs[KW_FLUX_MIN] = layer.flux_min
            if layer.flux_max is not None:
                lg.attrs[KW_FLUX_MAX] = layer.flux_max
            if layer.wave_cval is not None:
                lg.attrs[KW_WAVE_CVAL] = layer.wave_cval
            if layer.wave_bwid is not None:
                lg.attrs[KW_WAVE_BWID] = layer.wave_bwid
            if layer.zdepth is not None:
                lg.attrs[KW_DEPTH] = float(layer.zdepth)
            # extra_header items
            for k, v in layer.extra_header.items():
                try:
                    lg.attrs[f"X_{k}"] = v   # prefix to avoid collisions
                except Exception:
                    pass

            # -- WCS (JSON-serialised) ----------------------------------------
            wcs_json = _wcs_to_json(layer.wcs)
            lg.create_dataset("wcs_header", data=wcs_json)

            # -- flux array ---------------------------------------------------
            cs = chunk_shape or _chunk_shape(*layer.shape)

            if pack == PACK_SPLIT16:
                fmin = layer.flux_min or 0.0
                fmax = layer.flux_max or 1.0
                from ..flux import encode_split16
                flux16, _, bscale, bzero = encode_split16(layer.flux_data, fmin, fmax)
                lg.attrs["BSCALE"] = bscale
                lg.attrs["BZERO"]  = bzero
                _write_dataset(lg, "flux", flux16.astype(np.int16),
                               compress=compress, compress_opts=compress_opts,
                               chunk_shape=cs)
            else:
                _write_dataset(lg, "flux", layer.flux_data,
                               compress=compress, compress_opts=compress_opts,
                               chunk_shape=cs)

            # -- alpha array --------------------------------------------------
            alpha = layer.alpha_data if layer.alpha_data is not None else \
                    np.full(layer.shape, 65535, dtype=np.uint16)
            _write_dataset(lg, "alpha", alpha,
                           compress=compress, compress_opts=compress_opts,
                           chunk_shape=cs)

            # -- uncertainty (optional) ----------------------------------------
            if layer.uncert_data is not None:
                _write_dataset(lg, "uncert", layer.uncert_data.astype(np.float32),
                               compress=compress, compress_opts=compress_opts,
                               chunk_shape=cs)
                lg.attrs[KW_UNCERT_EXT] = "uncert"

            # -- quality mask (optional) ---------------------------------------
            if layer.mask_data is not None:
                _write_dataset(lg, "mask", layer.mask_data.astype(np.uint8),
                               compress=compress, compress_opts=compress_opts,
                               chunk_shape=cs)
                lg.attrs[KW_MASK_EXT] = "mask"

        # ── /registry dataset (structured array) ─────────────────────────────
        # Mirror of the FITS FITA_LAYERS BINTABLE for tools that inspect
        # the file without loading every layer group.
        dt = np.dtype([
            ("layer_id",  np.int32),
            ("name",      "S32"),
            ("blend_mode","S8"),
            ("opacity",   np.float32),
            ("xoffset",   np.float64),
            ("yoffset",   np.float64),
            ("wave_cval", np.float64),
            ("wave_bwid", np.float64),
            ("flux_min",  np.float64),
            ("flux_max",  np.float64),
            ("zdepth",    np.float32),
            ("visible",   np.bool_),
            ("alpha_src", "S8"),
        ])
        reg = np.zeros(len(layers), dtype=dt)
        for j, layer in enumerate(layers):
            reg[j]["layer_id"]  = layer.layer_id
            reg[j]["name"]      = layer.name[:32].encode("utf-8", errors="replace")
            reg[j]["blend_mode"]= layer.blend_mode[:8].encode("utf-8", errors="replace")
            reg[j]["opacity"]   = layer.opacity
            reg[j]["xoffset"]   = layer.xoffset
            reg[j]["yoffset"]   = layer.yoffset
            reg[j]["wave_cval"] = layer.wave_cval if layer.wave_cval is not None else 0.0
            reg[j]["wave_bwid"] = layer.wave_bwid if layer.wave_bwid is not None else 0.0
            reg[j]["flux_min"]  = layer.flux_min  if layer.flux_min  is not None else 0.0
            reg[j]["flux_max"]  = layer.flux_max  if layer.flux_max  is not None else 1.0
            reg[j]["zdepth"]    = layer.zdepth    if layer.zdepth    is not None else -1.0
            reg[j]["visible"]   = layer.visible
            reg[j]["alpha_src"] = layer.alpha_src[:8].encode("utf-8", errors="replace")

        f.create_dataset("registry", data=reg, compression="gzip")


# ── Read ──────────────────────────────────────────────────────────────────────

def read(path: str | Path) -> List[FITALayer]:
    """
    Read a FITA/HDF5 file and return a list of FITALayer objects.

    The returned list is sorted by layer_id ascending.
    """
    _require_h5py()

    layers = []
    fpath = Path(path)

    if not fpath.exists():
        raise FileNotFoundError(f"FITA/HDF5 file not found: {fpath}")

    with h5py.File(str(fpath), "r") as f:
        pack = f.attrs.get(KW_PACK, PACK_FLOAT32)
        if isinstance(pack, bytes):
            pack = pack.decode()

        if "layers" not in f:
            warnings.warn(f"{fpath}: no /layers group found — returning empty list")
            return []

        layers_grp = f["layers"]

        for gname in sorted(layers_grp.keys()):
            lg = layers_grp[gname]

            # -- layer id -----------------------------------------------------
            try:
                idx = int(lg.attrs.get(KW_LAYER_ID, gname))
            except (ValueError, TypeError):
                idx = int(gname)

            # -- metadata attrs -----------------------------------------------
            def _ga(key, default=None):
                v = lg.attrs.get(key, default)
                if isinstance(v, bytes):
                    v = v.decode()
                return v

            name       = _ga(KW_LAYER_NAME, f"Layer {idx}")
            blend_mode = _ga(KW_BLEND_MODE, "NORMAL")
            opacity    = float(_ga(KW_OPACITY, 1.0))
            xoffset    = float(_ga(KW_XOFFSET, 0.0))
            yoffset    = float(_ga(KW_YOFFSET, 0.0))
            alpha_src  = _ga(KW_ALPHA_SRC, "LUM")
            visible    = bool(_ga("VISIBLE", True))
            flux_min   = _ga(KW_FLUX_MIN, None)
            flux_max   = _ga(KW_FLUX_MAX, None)
            wave_cval  = _ga(KW_WAVE_CVAL, None)
            wave_bwid  = _ga(KW_WAVE_BWID, None)
            zdp_raw    = _ga(KW_DEPTH, None)
            zdepth     = float(zdp_raw) if (zdp_raw is not None and float(zdp_raw) >= 0.0) else None

            if flux_min is not None: flux_min = float(flux_min)
            if flux_max is not None: flux_max = float(flux_max)
            if wave_cval is not None: wave_cval = float(wave_cval)
            if wave_bwid is not None: wave_bwid = float(wave_bwid)

            # -- flux array ---------------------------------------------------
            if "flux" not in lg:
                warnings.warn(f"Layer {idx}: no 'flux' dataset — skipping")
                continue

            flux_raw = lg["flux"][()]
            if pack == PACK_SPLIT16:
                bscale = float(lg.attrs.get("BSCALE", 1.0))
                bzero  = float(lg.attrs.get("BZERO",  0.0))
                flux = flux_raw.astype(np.float32) * bscale + bzero
            else:
                flux = flux_raw.astype(np.float32)

            # -- alpha array --------------------------------------------------
            if "alpha" in lg:
                alpha = lg["alpha"][()].astype(np.uint16)
            else:
                alpha = None

            # -- uncertainty --------------------------------------------------
            if "uncert" in lg:
                uncert = lg["uncert"][()].astype(np.float32)
            else:
                uncert = None

            # -- quality mask -------------------------------------------------
            if "mask" in lg:
                mask = lg["mask"][()].astype(np.uint8)
            else:
                mask = None

            # -- WCS ----------------------------------------------------------
            wcs = None
            if "wcs_header" in lg:
                wcs_json = lg["wcs_header"][()]
                if isinstance(wcs_json, bytes):
                    wcs_json = wcs_json.decode()
                wcs = _wcs_from_json(wcs_json)

            # -- extra_header items (prefixed with X_) -----------------------
            extra = {}
            for k, v in lg.attrs.items():
                if k.startswith("X_"):
                    real_key = k[2:]
                    if isinstance(v, bytes):
                        v = v.decode()
                    extra[real_key] = v

            layer = FITALayer(
                flux_data   = flux,
                alpha_data  = alpha,
                layer_id    = idx,
                name        = name,
                blend_mode  = blend_mode,
                opacity     = opacity,
                xoffset     = xoffset,
                yoffset     = yoffset,
                flux_min    = flux_min,
                flux_max    = flux_max,
                wave_cval   = wave_cval,
                wave_bwid   = wave_bwid,
                alpha_src   = alpha_src,
                visible     = visible,
                zdepth      = zdepth,
                wcs         = wcs,
                extra_header= extra,
                uncert_data = uncert,
                mask_data   = mask,
            )
            layers.append(layer)

    layers.sort(key=lambda l: l.layer_id)
    return layers


# ── Utilities ─────────────────────────────────────────────────────────────────

def info(path: str | Path) -> Dict[str, Any]:
    """
    Return a summary dict describing the contents of a FITA/HDF5 file.

    Useful for quick inspection without fully loading all arrays.

    Returns
    -------
    dict with keys:
        version, pack, nlayers, canvas_w, canvas_h, bunit,
        layers: list of {layer_id, name, shape, wave_cval, zdepth,
                         has_uncert, has_mask, has_wcs}
    """
    _require_h5py()

    fpath = Path(path)
    result: Dict[str, Any] = {}

    with h5py.File(str(fpath), "r") as f:
        def _decode(v):
            return v.decode() if isinstance(v, bytes) else v

        result["version"]  = _decode(f.attrs.get(KW_VERSION, "?"))
        result["pack"]     = _decode(f.attrs.get(KW_PACK, PACK_FLOAT32))
        result["nlayers"]  = int(f.attrs.get(KW_NLAYERS, 0))
        result["canvas_w"] = f.attrs.get(KW_CANVAS_W, None)
        result["canvas_h"] = f.attrs.get(KW_CANVAS_H, None)
        result["bunit"]    = _decode(f.attrs.get("BUNIT", ""))
        result["backend"]  = _decode(f.attrs.get("FITA_BACKEND", "HDF5"))
        result["hdf5_ver"] = _decode(f.attrs.get("FITA_H5VER", "?"))

        layer_summaries = []
        if "layers" in f:
            for gname in sorted(f["layers"].keys()):
                lg = f["layers"][gname]
                idx = int(lg.attrs.get(KW_LAYER_ID, gname))
                nm  = _decode(lg.attrs.get(KW_LAYER_NAME, f"Layer {idx}"))
                shape = None
                if "flux" in lg:
                    shape = tuple(lg["flux"].shape)
                wc = lg.attrs.get(KW_WAVE_CVAL, None)
                if wc is not None:
                    wc = float(wc)
                zdp = lg.attrs.get(KW_DEPTH, None)
                if zdp is not None:
                    zdp = float(zdp) if float(zdp) >= 0 else None
                layer_summaries.append({
                    "layer_id":  idx,
                    "name":      nm,
                    "shape":     shape,
                    "wave_cval": wc,
                    "zdepth":    zdp,
                    "has_uncert": "uncert" in lg,
                    "has_mask":   "mask"   in lg,
                    "has_wcs":   ("wcs_header" in lg
                                  and bool(lg["wcs_header"][()])),
                })

        result["layers"] = layer_summaries

    return result


def convert_fits_to_hdf5(
    fits_path: str | Path,
    hdf5_path: Optional[str | Path] = None,
    **kwargs,
) -> Path:
    """
    Convert an existing .fita (FITS) file to FITA/HDF5 format.

    Parameters
    ----------
    fits_path  : input .fita file
    hdf5_path  : output .h5 file; if None, replaces the .fita suffix with .h5
    **kwargs   : forwarded to write() (compress, chunk_shape, etc.)

    Returns
    -------
    Path to the written HDF5 file.
    """
    from ..io import read as fits_read

    fits_path = Path(fits_path)
    if hdf5_path is None:
        hdf5_path = fits_path.with_suffix(".h5")
    else:
        hdf5_path = Path(hdf5_path)

    layers = fits_read(str(fits_path))
    write(hdf5_path, layers, **kwargs)
    return hdf5_path
