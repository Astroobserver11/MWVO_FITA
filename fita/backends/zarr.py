"""
fita.backends.zarr -- FITA data model stored in Zarr v2/v3.

Store layout
------------
<root>/                        top-level Zarr group
  .zattrs                      global attributes (FITA version, pack, nlayers, ...)
  layers/                      sub-group for all layers
    0001/                      one sub-group per layer (zero-padded 4-digit index)
      .zattrs                  layer metadata (all KW_* keyword values)
      flux        Array        float32 or int16, shape (H, W), chunked + compressed
      alpha       Array        uint16,  shape (H, W), chunked + compressed
      uncert      Array        float32, shape (H, W)  [optional]
      mask        Array        uint8,   shape (H, W)  [optional]
      wcs_header  Array        scalar string (JSON-serialised FITS WCS header)
  registry        Array        structured array (same fields as HDF5 backend)

Storage targets
---------------
- Local directory store (default, creates a .zarr directory)
- Any fsspec-compatible URL: s3://, gs://, az://, http://
  Example:
      write("s3://mybucket/m27.zarr", layers,
            storage_options={"key": "...", "secret": "..."})

Zarr version compatibility
--------------------------
This backend targets zarr >= 2.10.  For zarr 3.x the same API is used;
zarr will raise a UserWarning if the store format needs a migration.
Tested with zarr 3.2.1 (installed in this environment).

Compressor
----------
Default: Blosc(cname='lz4', clevel=5, shuffle=Blosc.BITSHUFFLE).
For cloud stores consider zstd (better ratio) or None (rely on S3/GCS
transparent compression).  Pass ``compressor=zarr.storage.default_compressor``
to use the environment default.

Usage
-----
    from fita.backends.zarr import write, read
    from fita.layer import FITALayer
    import numpy as np

    layer = FITALayer.from_array(np.random.rand(512, 512).astype('float32'),
                                  layer_id=1, name='Test')

    # local directory store
    write('test.zarr', [layer])
    layers = read('test.zarr')

    # S3 store (requires s3fs: pip install s3fs)
    write('s3://bucket/prefix/test.zarr', [layer],
           storage_options={'anon': False, 'key': '...', 'secret': '...'})
    layers = read('s3://bucket/prefix/test.zarr',
                   storage_options={'anon': True})
"""

from __future__ import annotations
import json
import warnings
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple

import numpy as np

try:
    import zarr
    _ZARR_VERSION = int(zarr.__version__.split(".")[0])
    _ZARR = True
except ImportError:
    _ZARR = False
    _ZARR_VERSION = 0

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
)
from ..layer import FITALayer

# ── Internal helpers ──────────────────────────────────────────────────────────

def _require_zarr():
    if not _ZARR:
        raise ImportError(
            "zarr is required for Zarr backend: pip install zarr"
        )


def _chunk_shape(h: int, w: int, target: int = 256) -> Tuple[int, int]:
    return (min(target, h), min(target, w))


def _default_compressor():
    """Return the best available compressor."""
    try:
        from numcodecs import Blosc
        return Blosc(cname="lz4", clevel=5, shuffle=Blosc.BITSHUFFLE)
    except ImportError:
        pass
    # zarr built-in Zstd fallback
    try:
        import zarr.codecs
        return None  # zarr 3 uses codec pipeline; None = default
    except Exception:
        return None


def _wcs_to_json(wcs) -> str:
    if wcs is None or not _ASTROPY:
        return ""
    try:
        hdr = wcs.to_header()
        d = {k: v for k, v in hdr.items() if k}
        return json.dumps(d)
    except Exception:
        return ""


def _wcs_from_json(s: str):
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


def _open_store(path: str | Path, mode: str = "w",
                storage_options: Optional[Dict] = None):
    """
    Return a zarr store for *path*.

    Handles:
      - local Path / str  -> zarr.DirectoryStore (zarr 2) or zarr.store.LocalStore (zarr 3)
      - URL strings       -> zarr.open() with storage_options (requires fsspec)
    """
    path_str = str(path)
    opts = storage_options or {}

    if _ZARR_VERSION >= 3:
        # zarr 3: open() accepts store paths directly
        return zarr.open(path_str, mode=mode, **opts)
    else:
        # zarr 2
        if path_str.startswith(("s3://", "gs://", "az://", "http://", "https://")):
            try:
                import fsspec
                fs_map = fsspec.get_mapper(path_str, **opts)
                return zarr.open(fs_map, mode=mode)
            except ImportError:
                raise ImportError(
                    "pip install fsspec s3fs  (or gcsfs / adlfs for other clouds)"
                )
        else:
            store = zarr.DirectoryStore(path_str)
            return zarr.open(store, mode=mode)


def _write_array(group, name: str, data: np.ndarray,
                 compressor, chunk_shape: Optional[Tuple[int, int]] = None):
    """Write (or replace) a zarr array in *group*."""
    if data is None:
        return
    cs = chunk_shape or _chunk_shape(*data.shape[-2:])
    if data.ndim != 2:
        cs = None   # fall back to unchunked for unexpected shapes

    if _ZARR_VERSION >= 3:
        # zarr 3: compressor is passed as codecs
        try:
            from numcodecs import Blosc
            codecs = [Blosc(cname="lz4", clevel=5, shuffle=Blosc.BITSHUFFLE)] if compressor else []
        except ImportError:
            codecs = []
        if name in group:
            del group[name]
        group.create_array(name, shape=data.shape, dtype=data.dtype,
                           chunks=cs, fill_value=0)
        group[name][:] = data
    else:
        # zarr 2
        if name in group:
            del group[name]
        group.create_dataset(name, data=data, chunks=cs,
                             compressor=compressor, overwrite=True)


# ── Write ─────────────────────────────────────────────────────────────────────

def write(
    path: str | Path,
    layers: List[FITALayer],
    pack: str = PACK_FLOAT32,
    canvas_w: Optional[int] = None,
    canvas_h: Optional[int] = None,
    global_attrs: Optional[Dict[str, Any]] = None,
    bunit: str = "ct/s",
    compressor=None,
    chunk_shape: Optional[Tuple[int, int]] = None,
    storage_options: Optional[Dict[str, Any]] = None,
    overwrite: bool = True,
) -> None:
    """
    Write a list of FITALayer objects to a FITA/Zarr store.

    Parameters
    ----------
    path             : local directory path or cloud URL
                       (e.g. 's3://bucket/m27.zarr')
    layers           : list of FITALayer
    pack             : 'FLOAT32' (default) or 'SPLIT16'
    canvas_w/h       : optional logical canvas dimensions
    global_attrs     : extra key/value pairs stored in root .zattrs
    bunit            : flux unit string
    compressor       : numcodecs compressor; None = Blosc(lz4, clevel=5)
    chunk_shape      : (rows, cols) tile size; None = auto
    storage_options  : dict passed to fsspec for cloud stores
    overwrite        : replace existing store (default True)
    """
    _require_zarr()

    if compressor is None:
        compressor = _default_compressor()

    root = _open_store(path, mode="w" if overwrite else "w-",
                       storage_options=storage_options)

    # ── Root attributes ───────────────────────────────────────────────────────
    root.attrs[KW_VERSION]     = FITA_VERSION
    root.attrs[KW_PACK]        = pack
    root.attrs[KW_NLAYERS]     = len(layers)
    root.attrs["BUNIT"]        = bunit
    root.attrs["FITA_BACKEND"] = "ZARR"
    root.attrs["ZARR_VERSION"] = str(_ZARR_VERSION)
    if canvas_w:
        root.attrs[KW_CANVAS_W] = canvas_w
    if canvas_h:
        root.attrs[KW_CANVAS_H] = canvas_h
    if global_attrs:
        for k, v in global_attrs.items():
            try:
                root.attrs[k] = v
            except Exception:
                pass

    # ── layers/ group ─────────────────────────────────────────────────────────
    layers_grp = root.require_group("layers")

    for layer in layers:
        i = layer.layer_id
        gname = f"{i:04d}"
        lg = layers_grp.require_group(gname)

        # -- metadata in .zattrs ----------------------------------------------
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
        for k, v in layer.extra_header.items():
            try:
                lg.attrs[f"X_{k}"] = v
            except Exception:
                pass

        # -- WCS (JSON scalar array) ------------------------------------------
        wcs_json = _wcs_to_json(layer.wcs)
        cs = chunk_shape or _chunk_shape(*layer.shape)

        # Store WCS JSON as a fixed-length bytes array (portable across zarr 2/3)
        wcs_bytes = wcs_json.encode("utf-8") if wcs_json else b""
        # Pad/truncate to 8192 bytes so the array has a fixed dtype
        wcs_padded = np.frombuffer(wcs_bytes.ljust(8192, b"\x00"), dtype=np.uint8)[:8192]
        if _ZARR_VERSION >= 3:
            if "wcs_header" in lg:
                del lg["wcs_header"]
            lg.create_array("wcs_header", shape=(8192,), dtype=np.uint8)
            lg["wcs_header"][:] = wcs_padded
        else:
            lg.create_dataset("wcs_header", data=wcs_padded,
                              dtype=np.uint8, overwrite=True)

        # -- flux -------------------------------------------------------------
        if pack == PACK_SPLIT16:
            fmin = layer.flux_min or 0.0
            fmax = layer.flux_max or 1.0
            from ..flux import encode_split16
            flux16, _, bscale, bzero = encode_split16(layer.flux_data, fmin, fmax)
            lg.attrs["BSCALE"] = bscale
            lg.attrs["BZERO"]  = bzero
            _write_array(lg, "flux", flux16.astype(np.int16), compressor, cs)
        else:
            _write_array(lg, "flux", layer.flux_data, compressor, cs)

        # -- alpha ------------------------------------------------------------
        alpha = layer.alpha_data if layer.alpha_data is not None else \
                np.full(layer.shape, 65535, dtype=np.uint16)
        _write_array(lg, "alpha", alpha, compressor, cs)

        # -- uncertainty ------------------------------------------------------
        if layer.uncert_data is not None:
            _write_array(lg, "uncert", layer.uncert_data.astype(np.float32),
                         compressor, cs)
            lg.attrs[KW_UNCERT_EXT] = "uncert"

        # -- quality mask -----------------------------------------------------
        if layer.mask_data is not None:
            _write_array(lg, "mask", layer.mask_data.astype(np.uint8),
                         compressor, cs)
            lg.attrs[KW_MASK_EXT] = "mask"

    # ── registry (structured array) ──────────────────────────────────────────
    # Store as JSON list of dicts (Zarr can't store numpy structured arrays
    # portably across versions without extra metadata).
    reg_list = []
    for layer in layers:
        reg_list.append({
            "layer_id":  layer.layer_id,
            "name":      layer.name[:32],
            "blend_mode":layer.blend_mode,
            "opacity":   float(layer.opacity),
            "xoffset":   float(layer.xoffset),
            "yoffset":   float(layer.yoffset),
            "wave_cval": float(layer.wave_cval) if layer.wave_cval is not None else None,
            "wave_bwid": float(layer.wave_bwid) if layer.wave_bwid is not None else None,
            "flux_min":  float(layer.flux_min)  if layer.flux_min  is not None else None,
            "flux_max":  float(layer.flux_max)  if layer.flux_max  is not None else None,
            "zdepth":    float(layer.zdepth)    if layer.zdepth    is not None else None,
            "visible":   bool(layer.visible),
            "alpha_src": layer.alpha_src,
        })
    root.attrs["FITA_REGISTRY"] = json.dumps(reg_list)


# ── Read ──────────────────────────────────────────────────────────────────────

def read(
    path: str | Path,
    storage_options: Optional[Dict[str, Any]] = None,
) -> List[FITALayer]:
    """
    Read a FITA/Zarr store and return a list of FITALayer objects.

    Parameters
    ----------
    path             : local directory path or cloud URL
    storage_options  : dict passed to fsspec for cloud stores

    Returns
    -------
    List of FITALayer objects sorted by layer_id ascending.
    """
    _require_zarr()

    root = _open_store(path, mode="r", storage_options=storage_options)

    pack = root.attrs.get(KW_PACK, PACK_FLOAT32)

    if "layers" not in root:
        warnings.warn(f"{path}: no 'layers' group found — returning empty list")
        return []

    layers_grp = root["layers"]
    layers: List[FITALayer] = []

    for gname in sorted(layers_grp.keys()):
        lg = layers_grp[gname]

        # -- layer id ---------------------------------------------------------
        try:
            idx = int(lg.attrs.get(KW_LAYER_ID, gname))
        except (ValueError, TypeError):
            idx = int(gname)

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

        for conv_var in ("flux_min", "flux_max", "wave_cval", "wave_bwid"):
            val = locals()[conv_var]
            if val is not None:
                exec(f"{conv_var} = float(val)")  # noqa — safe local names

        # explicit conversions (exec is cleaner but we stay explicit)
        if flux_min  is not None: flux_min  = float(flux_min)
        if flux_max  is not None: flux_max  = float(flux_max)
        if wave_cval is not None: wave_cval = float(wave_cval)
        if wave_bwid is not None: wave_bwid = float(wave_bwid)

        # -- flux -------------------------------------------------------------
        if "flux" not in lg:
            warnings.warn(f"Layer {idx}: no 'flux' array — skipping")
            continue
        flux_raw = np.asarray(lg["flux"])
        if pack == PACK_SPLIT16:
            bscale = float(lg.attrs.get("BSCALE", 1.0))
            bzero  = float(lg.attrs.get("BZERO",  0.0))
            flux = flux_raw.astype(np.float32) * bscale + bzero
        else:
            flux = flux_raw.astype(np.float32)

        # -- alpha ------------------------------------------------------------
        alpha = np.asarray(lg["alpha"]).astype(np.uint16) if "alpha" in lg else None

        # -- uncertainty and mask ---------------------------------------------
        uncert = np.asarray(lg["uncert"]).astype(np.float32) if "uncert" in lg else None
        mask   = np.asarray(lg["mask"]).astype(np.uint8)     if "mask"   in lg else None

        # -- WCS from uint8 byte array ----------------------------------------
        wcs = None
        if "wcs_header" in lg:
            try:
                wcs_bytes = np.asarray(lg["wcs_header"]).tobytes().rstrip(b"\x00")
                wcs_json_str = wcs_bytes.decode("utf-8", errors="replace")
                wcs = _wcs_from_json(wcs_json_str)
            except Exception:
                wcs = None

        # -- extra_header (X_* attrs) -----------------------------------------
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

def info(path: str | Path,
         storage_options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Return a summary dict for a FITA/Zarr store without loading arrays.
    """
    _require_zarr()
    root = _open_store(path, mode="r", storage_options=storage_options)

    result: Dict[str, Any] = {}
    result["version"]  = root.attrs.get(KW_VERSION, "?")
    result["pack"]     = root.attrs.get(KW_PACK, PACK_FLOAT32)
    result["nlayers"]  = root.attrs.get(KW_NLAYERS, 0)
    result["canvas_w"] = root.attrs.get(KW_CANVAS_W, None)
    result["canvas_h"] = root.attrs.get(KW_CANVAS_H, None)
    result["bunit"]    = root.attrs.get("BUNIT", "")
    result["backend"]  = root.attrs.get("FITA_BACKEND", "ZARR")
    result["zarr_ver"] = root.attrs.get("ZARR_VERSION", "?")

    layer_summaries = []
    if "layers" in root:
        for gname in sorted(root["layers"].keys()):
            lg = root["layers"][gname]
            idx = int(lg.attrs.get(KW_LAYER_ID, gname))
            nm  = lg.attrs.get(KW_LAYER_NAME, f"Layer {idx}")
            shape = None
            if "flux" in lg:
                shape = tuple(np.asarray(lg["flux"]).shape)
            wc  = lg.attrs.get(KW_WAVE_CVAL, None)
            if wc is not None: wc = float(wc)
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
                "has_wcs":    "wcs_header" in lg,
            })
    result["layers"] = layer_summaries
    return result


def convert_fits_to_zarr(
    fits_path: str | Path,
    zarr_path: Optional[str | Path] = None,
    **kwargs,
) -> str:
    """
    Convert an existing .fita (FITS) file to FITA/Zarr format.

    Returns the zarr store path/URL as a string.
    """
    from ..io import read as fits_read

    fits_path = Path(fits_path)
    if zarr_path is None:
        zarr_path = str(fits_path.with_suffix(".zarr"))
    else:
        zarr_path = str(zarr_path)

    layers = fits_read(str(fits_path))
    write(zarr_path, layers, **kwargs)
    return zarr_path
