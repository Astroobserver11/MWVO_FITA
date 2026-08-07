"""
FITA file I/O — read and write .fita files using astropy.io.fits.

Write layout
------------
HDU 0  PRIMARY      empty + global keywords
HDU 1  FITA_LAYERS  BINTABLE layer registry
HDU 2  FLUX_0001    IMAGE (BITPIX=-32 float or 16 int)
HDU 3  ALPHA_0001   IMAGE (BITPIX=16 uint)
HDU 4  FLUX_0002    ...
...
HDU N  FITA_META    BINTABLE provenance (if metadata supplied)
"""

from __future__ import annotations
import numpy as np
from pathlib import Path
from typing import List, Optional, Dict, Any

try:
    from astropy.io import fits
    from astropy.wcs import WCS
    _ASTROPY = True
except ImportError:
    _ASTROPY = False

from .spec import (
    FITA_VERSION, PACK_FLOAT32, PACK_SPLIT16,
    KW_VERSION, KW_PACK, KW_NLAYERS, KW_CANVAS_W, KW_CANVAS_H,
    KW_ZSCALE, KW_ZREF, KW_ZANG, KW_FIELD_DIA, KW_FIELD_UNI, KW_ZDEPTH_U,
    KW_SPECSYS, KW_VELOSYS, KW_VELOSYS_E, KW_SSYSOBS, KW_RESTFRQ, KW_RESTWAV,
    KW_CTYPE3, KW_CDELT3, KW_CUNIT3, KW_ZDEPTH_EP,
    KW_DEPTH, KW_VISIBLE, KW_UNCERT_EXT, KW_MASK_EXT,
    EXTNAME_LAYERS, EXTNAME_ADJ, EXTNAME_META,
    LAYER_TABLE_COLS, flux_extname, alpha_extname,
)
from .layer import FITALayer
from .flux import encode_split16


def _require_astropy():
    if not _ASTROPY:
        raise ImportError("astropy is required for FITA I/O: pip install astropy")


# ── Write ─────────────────────────────────────────────────────────────────────

def _build_adj_hdu(adjustments: Any):
    """Serialise an AdjustmentStack into the FITA_ADJ BINTABLE (S8, D-3).

    The common parameters are REAL TYPED COLUMNS (author ruling Q1,
    2026-08-02) -- see spec.ADJ_TABLE_COLS.  An earlier draft put every
    type-specific parameter into a single JSON blob; that was compact but
    opaque, and the whole premise of FITA is that any FITS reader can open the
    file.  A reader that opens the file but cannot see that GAMMA = 2.2 has
    not really been given the data.

    JSON is therefore reserved for the parameters that genuinely have no fixed
    width -- curve control points and instrument response arrays.  The PARAMS
    column is sized to the longest row actually present, so nothing is
    silently truncated; the recurring failure in this project has been data
    loss that does not announce itself, and a fixed cap would reintroduce it.

    Columns that do not apply to a row carry the D-5 absence convention: NaN
    for floats, empty string for text.
    """
    import json as _json
    from .adjustment import AdjustmentStack
    from .spec import ADJ_TABLE_COLS, ADJ_SCALAR_COLS, ADJ_VARLEN_FIELDS

    if isinstance(adjustments, AdjustmentStack):
        records = adjustments.to_records()
    elif isinstance(adjustments, (list, tuple)):
        # a bare list of AdjustmentLayer objects is accepted too
        if adjustments and hasattr(adjustments[0], "to_params"):
            records = AdjustmentStack(list(adjustments)).to_records()
        else:
            records = list(adjustments)
    else:
        raise TypeError(
            "adjustments must be an AdjustmentStack or a list of "
            "AdjustmentLayer objects; got %r" % type(adjustments).__name__)

    if not records:
        return None

    # Only the variable-length fields go to JSON.
    payloads = []
    for r in records:
        params = r.get("params") or {}
        varlen = {k: v for k, v in params.items() if k in ADJ_VARLEN_FIELDS}
        payloads.append(_json.dumps(varlen, separators=(",", ":"))
                        if varlen else "")
    width = max(max((len(p) for p in payloads), default=1), 1)

    def _scalar(rec, field, is_text):
        params = rec.get("params") or {}
        if field == "layer_id":
            val = params.get("layer_id", rec.get("layer_id", 0))
            return int(val or 0)
        val = params.get(field, None)
        if val is None:
            return "" if is_text else np.nan
        return str(val) if is_text else float(val)

    cols = []
    for name, fmt, unit, desc in ADJ_TABLE_COLS:
        is_text = fmt.endswith("A")
        if name == "ORDER":
            arr = np.array([int(r.get("order", i)) for i, r in enumerate(records)])
        elif name == "ADJ_TYPE":
            arr = np.array([str(r.get("type", "")) for r in records])
        elif name == "ENABLED":
            arr = np.array([bool(r.get("enabled", True)) for r in records])
        elif name == "NAME":
            arr = np.array([str(r.get("name", "")) for r in records])
        elif name == "PARAMS":
            fmt = "%dA" % width
            arr = np.array(payloads)
        elif name in ADJ_SCALAR_COLS:
            field = ADJ_SCALAR_COLS[name]
            if field == "layer_id":
                arr = np.array([_scalar(r, field, False) for r in records])
            else:
                arr = np.array([_scalar(r, field, is_text) for r in records])
        else:                                   # pragma: no cover - schema drift
            continue
        cols.append(fits.Column(name=name, format=fmt, unit=unit or "",
                                array=arr))

    hdu = fits.BinTableHDU.from_columns(cols)
    hdu.name = EXTNAME_ADJ
    hdu.header.add_comment("FITA adjustment stack (S8, decision D-3)")
    hdu.header.add_comment("Non-destructive display state; FLUX_* is never modified")
    return hdu


def read_zdp_scale(path: str | Path) -> Optional[float]:
    """Read the FITA_ZSC stereo parallax scale, or None if not recorded.

    None and 0.0 are different answers: None means no renderer recorded a
    stereo geometry, 0.0 means one did and it was flat.
    """
    _require_astropy()
    with fits.open(str(path)) as hdul:
        val = hdul[0].header.get(KW_ZSCALE, None)
    return None if val is None else float(val)


def read_stereo_geometry(path: str | Path) -> Dict[str, Optional[float]]:
    """Read the full stereo geometry (S8.2, v1.4).

    `zdp_ref` defaults to 0.0 when the keyword is absent, because that is the
    convention's stated default (background at the screen plane).  Everything
    else returns None when absent, because for those an absence is a real
    statement -- no geometry recorded, no field declared, no unit declared --
    not a default value.

    `zdp_unit` is the one to read carefully: None means FITA_ZDP is
    dimensionless and constrained to [0,1], a string means it carries a
    physical depth in that unit and the [0,1] rule does not apply (N-1).

    `zdp_angular` reads the RETIRED FITA_ZAN.  It is still reported because
    files written before v1.4 carry it and D-1 grandfathering means a reader
    must not choke on them; writers should no longer emit it.
    """
    _require_astropy()
    with fits.open(str(path)) as hdul:
        h = hdul[0].header
        scale = h.get(KW_ZSCALE, None)
        ref = h.get(KW_ZREF, None)
        ang = h.get(KW_ZANG, None)
        fdi = h.get(KW_FIELD_DIA, None)
        fdu = h.get(KW_FIELD_UNI, None)
        zdu = h.get(KW_ZDEPTH_U, None)
        # v1.5 spectral / LSR block
        specsys = h.get(KW_SPECSYS, None)
        velosys = h.get(KW_VELOSYS, None)
        vse = h.get(KW_VELOSYS_E, None)
        ssysobs = h.get(KW_SSYSOBS, None)
        restfrq = h.get(KW_RESTFRQ, None)
        restwav = h.get(KW_RESTWAV, None)
        zep = h.get(KW_ZDEPTH_EP, None)
        cdelt3 = h.get(KW_CDELT3, None)
        cunit3 = h.get(KW_CUNIT3, None)
        ctype3 = h.get(KW_CTYPE3, None)
    return {
        "zdp_scale": None if scale is None else float(scale),
        "zdp_ref": 0.0 if ref is None else float(ref),
        "zdp_ref_explicit": ref is not None,
        "field_dia": None if fdi is None else float(fdi),
        "field_unit": None if fdu is None else str(fdu).strip(),
        "zdp_unit": None if zdu is None else str(zdu).strip(),
        "zdp_angular": None if ang is None else float(ang),
        "specsys": None if specsys is None else str(specsys).strip(),
        "velosys": None if velosys is None else float(velosys),
        "velosys_err": None if vse is None else float(vse),
        "ssysobs": None if ssysobs is None else str(ssysobs).strip(),
        "restfrq": None if restfrq is None else float(restfrq),
        "restwav": None if restwav is None else float(restwav),
        "zdp_epistemic": None if zep is None else str(zep).strip().upper(),
        "ctype3": None if ctype3 is None else str(ctype3).strip(),
        "cdelt3": None if cdelt3 is None else float(cdelt3),
        "cunit3": None if cunit3 is None else str(cunit3).strip(),
    }


def read_adjustments(path: str | Path):
    """Read the FITA_ADJ stack from a .fita file.

    Returns an empty AdjustmentStack when the file carries no FITA_ADJ HDU,
    which is the case for every file written before v1.1.
    """
    import json as _json
    _require_astropy()
    from .adjustment import AdjustmentStack
    from .spec import ADJ_SCALAR_COLS

    with fits.open(str(path)) as hdul:
        if EXTNAME_ADJ not in [str(h.name) for h in hdul]:
            return AdjustmentStack()
        table = hdul[EXTNAME_ADJ]
        present = set(getattr(table.columns, "names", []) or [])
        records = []
        for row in table.data:
            # Variable-length remainder first, then overlay the typed columns.
            raw = str(row["PARAMS"]).strip() if "PARAMS" in present else ""
            params = _json.loads(raw) if raw else {}

            for col, field in ADJ_SCALAR_COLS.items():
                if col not in present:
                    continue
                val = row[col]
                if isinstance(val, (str, np.str_)):
                    val = str(val).strip()
                    if val:
                        params[field] = val
                else:
                    fval = float(val)
                    # NaN is the D-5 absence marker: the column does not apply
                    # to this adjustment type.
                    if not np.isnan(fval):
                        params[field] = int(fval) if field == "layer_id" else fval

            records.append({
                "order":    int(row["ORDER"]),
                "type":     str(row["ADJ_TYPE"]).strip(),
                "enabled":  bool(row["ENABLED"]),
                "name":     str(row["NAME"]).strip(),
                "layer_id": int(row["LAYER_ID"]) if "LAYER_ID" in present else 0,
                "params":   params,
            })
    return AdjustmentStack.from_records(records)


def _build_meta_hdu(provenance: Any, layers: List[FITALayer]):
    """Coerce the `provenance` argument of write() into a FITA_META HDU.

    A caller who has already built an HDU keeps full control; a caller who
    passes a dict gets the layer-derived fields (spatial/spectral extent, axis
    counts) filled in for them, because those are properties of the data and
    are easy to state wrongly by hand.
    """
    if isinstance(provenance, fits.BinTableHDU):
        hdu = provenance
        hdu.name = EXTNAME_META
        return hdu

    if isinstance(provenance, dict):
        from .ivoa import meta_from_layers
        return meta_from_layers(layers, **provenance)

    raise TypeError(
        "provenance must be a dict of ObsCore fields or a BinTableHDU from "
        "fita.ivoa.make_meta_hdu()/meta_from_layers(); got %r"
        % type(provenance).__name__
    )


def write(
    path: str | Path,
    layers: List[FITALayer],
    pack: str = PACK_FLOAT32,
    canvas_w: Optional[int] = None,
    canvas_h: Optional[int] = None,
    global_header: Optional[Dict[str, Any]] = None,
    bunit: str = "ct/s",
    overwrite: bool = True,
    provenance: Optional[Any] = None,
    adjustments: Optional[Any] = None,
    zdp_scale: Optional[float] = None,
    zdp_ref: Optional[float] = None,
    zdp_angular: Optional[float] = None,
    field_dia: Optional[float] = None,
    field_unit: Optional[str] = None,
    zdp_unit: Optional[str] = None,
    specsys: Optional[str] = None,
    velosys: Optional[float] = None,
    velosys_err: Optional[float] = None,
    ssysobs: Optional[str] = None,
    restfrq: Optional[float] = None,
    restwav: Optional[float] = None,
    zdp_epistemic: Optional[str] = None,
    checksum: bool = True,
    date: Optional[str] = None,
    origin: Optional[str] = None,
    creator: Optional[str] = None,
) -> None:
    """Write a list of FITALayer objects to a .fita file.

    provenance:
        Optional ObsCore provenance to emit as the ``FITA_META`` HDU, which
        FITA-FULL requires (standard S9).  Accepts either a ready-made
        BinTableHDU (from ``fita.ivoa.make_meta_hdu`` /
        ``fita.ivoa.meta_from_layers``) or a plain dict of ObsCore column
        values, in which case the HDU is built here and the fields derivable
        from the layers are filled in automatically.

        Until v1.1 this parameter did not exist: ``make_meta_hdu()`` worked but
        nothing could pass its result to the writer, so the documented
        provenance model was unreachable through the documented API and
        FITA_META was absent from every archived file.  That was defect R2 /
        decision D-4.

    adjustments:
        Optional non-destructive display stack (an ``AdjustmentStack`` or a
        list of ``AdjustmentLayer``) emitted as the ``FITA_ADJ`` HDU.

        Also new in v1.1 (decision D-3).  The adjustment classes were
        implemented and tested but nothing serialised them, so display state
        existed in memory and vanished on save -- and ``FITR_SPEC.md`` S8
        already delegated its display mathematics to this HDU, which no file
        had ever contained.

    zdp_scale:
        Optional stereo parallax scale written to PRIMARY as ``FITA_ZSC``:
        the total horizontal separation across the full FITA_ZDP range, as a
        **percentage of** ``field_dia`` (decision D-6; redefined from pixels
        by the principal's ruling of 2026-08-02).

        This is a RENDERER's statement, not a compositor's -- pass it only
        when writing a file whose stereo geometry has actually been fixed.
        Leaving it unset records "no stereo geometry", which is honest;
        writing 0.0 would claim a measured separation of zero.  See
        ``fita.stereo``.

    field_dia, field_unit:
        ``FITA_FDI`` / ``FITA_FDU`` -- the diameter of the field under study
        and its unit, chosen to be practical to the subject (``pc`` for a dust
        cube, ``km`` for a cometary surface, ``arcsec`` or ``deg`` for a sky
        field, ``AU`` for a disc).

        ``zdp_scale`` without these is a MUST failure at validation: a
        percentage of nothing is not a measurement.  A ValueError is raised
        here rather than writing a file the validator will reject.

    zdp_unit:
        ``FITA_ZDU`` -- the unit of FITA_ZDP for this file.  Leave it None and
        FITA_ZDP is dimensionless and must lie in [0,1] (the strict, default
        case).  Set it and FITA_ZDP carries a physical depth in that unit,
        which is how the archived Edenhofer cubes declare their parsecs
        without rewriting 48 layers of science data (N-1).
    """
    _require_astropy()

    # S6.4 / D-2 (ratified 2026-08-02): SPLIT16 is deleted. It was not lossy but
    # destructive (int16 wrap + astropy dropping BSCALE/BZERO on integer data), so a
    # conformant writer MUST NOT emit it.
    if pack == PACK_SPLIT16:
        raise ValueError(
            "FITAPACK='SPLIT16' is deprecated and removed in FITA v1.1 (standard S6.4, "
            "decision D-2): it destroyed flux irrecoverably. Use pack='FLOAT32' (bit-exact)."
        )

    hdul = fits.HDUList()

    # ── PRIMARY ──────────────────────────────────────────────────────────────
    phdr = fits.Header()
    phdr["SIMPLE"]    = True
    phdr[KW_VERSION]  = FITA_VERSION
    phdr[KW_PACK]     = pack
    phdr[KW_NLAYERS]  = len(layers)
    phdr["BUNIT"]     = bunit
    if canvas_w:
        phdr[KW_CANVAS_W] = canvas_w
    if canvas_h:
        phdr[KW_CANVAS_H] = canvas_h
    # S8.2 / D-6: OPTIONAL, renderer-written.  Absence means "no stereo
    # geometry recorded", which is why 0.0 is written only if asked for
    # explicitly rather than as a default.
    #
    # v1.4: FITA_ZSC is a percentage of FITA_FDI, so writing it without the
    # field it is a percentage OF produces a file this library's own validator
    # rejects.  Refuse at the writer rather than emit it -- the project's
    # characteristic defect is silent loss that looks like success, and a
    # writer that happily emits a MUST-failing file is that defect.
    if zdp_scale is not None and (field_dia is None or field_unit is None):
        raise ValueError(
            "zdp_scale (FITA_ZSC) is a percentage of the field diameter and "
            "requires field_dia (FITA_FDI) and field_unit (FITA_FDU). "
            "A percentage of nothing is not a measurement -- standard S8.2, "
            "principal's ruling 2026-08-02."
        )
    if field_dia is not None:
        phdr[KW_FIELD_DIA] = (float(field_dia), "diameter of the field under study")
    if field_unit is not None:
        phdr[KW_FIELD_UNI] = (str(field_unit), "FITS unit of FITA_FDI")
    if zdp_scale is not None:
        phdr[KW_ZSCALE] = (float(zdp_scale),
                           "pct of FITA_FDI, full ZDP range (D-6)")
    if zdp_ref is not None:
        phdr[KW_ZREF] = (float(zdp_ref), "ZDP placed at zero parallax")
    if zdp_unit is not None:
        phdr[KW_ZDEPTH_U] = (str(zdp_unit), "FITS unit of FITA_ZDP")
    # v1.5 -- spectral axis / velocity cubes. Author ruling B, 2026-08-03:
    # adopt the FITS WCS Paper III names rather than minting FITA_ twins.
    if specsys is not None:
        phdr[KW_SPECSYS] = (str(specsys), "spectral reference frame (ADOPTED)")
    if velosys is not None:
        phdr[KW_VELOSYS] = (float(velosys), "frame velocity wrt observer, m/s")
    if ssysobs is not None:
        phdr[KW_SSYSOBS] = (str(ssysobs), "frame the observation was taken in")
    if restfrq is not None:
        phdr[KW_RESTFRQ] = (float(restfrq), "rest frequency, Hz")
    if restwav is not None:
        phdr[KW_RESTWAV] = (float(restwav), "rest wavelength, m")
    # D-17: FITS has no uncertainty companion to VELOSYS, and the LSR's
    # uncertainty is the point (fita.lsr). Refuse an error without its value --
    # an uncertainty on nothing is not a measurement, the same reasoning that
    # makes FITA_ZSC require FITA_FDI.
    if velosys_err is not None and velosys is None:
        raise ValueError(
            "velosys_err (FITA_VSE) is the uncertainty on VELOSYS and requires "
            "velosys. An uncertainty on nothing is not a measurement."
        )
    if velosys_err is not None:
        phdr[KW_VELOSYS_E] = (float(velosys_err), "uncertainty on VELOSYS, m/s")
    # Ruling A: the epistemic label belongs to the AXIS, written once.
    if zdp_epistemic is not None:
        from .lsr import VOCABULARY
        if str(zdp_epistemic).upper() not in VOCABULARY:
            raise ValueError(
                "zdp_epistemic must be one of %s (got %r)"
                % (", ".join(VOCABULARY), zdp_epistemic))
        phdr[KW_ZDEPTH_EP] = (str(zdp_epistemic).upper(),
                              "epistemic status of the FITA_ZDP axis")
    # FITA_ZAN is RETIRED in v1.4 (dissolved, not replaced).  Still writable so
    # a caller reproducing a pre-v1.4 file can, but no longer emitted by
    # anything in this library.
    if zdp_angular is not None:
        phdr[KW_ZANG] = (float(zdp_angular),
                         "RETIRED v1.4: arcsec parallax, full ZDP range")
    # FITS-standard provenance. DATE is deliberately overridable: it is the
    # only non-deterministic value the writer would otherwise introduce.
    if date is None:
        from datetime import datetime, timezone
        date = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    phdr["DATE"] = (date, "UTC date this file was written")
    phdr["CREATOR"] = (creator or ("fita %s" % FITA_VERSION),
                       "software that created this file")
    if origin:
        phdr["ORIGIN"] = (origin, "organisation responsible for this file")

    if global_header:
        for k, v in global_header.items():
            phdr[k] = v
    phdr.add_comment("FITA - Flexible Image Transfer Alpha v" + FITA_VERSION)
    phdr.add_comment("See https://github.com/fits-alpha/fita for specification")
    hdul.append(fits.PrimaryHDU(header=phdr))

    # ── FITA_LAYERS BINTABLE ──────────────────────────────────────────────────
    col_defs = []
    tdata = {c[0]: [] for c in LAYER_TABLE_COLS}

    for layer in layers:
        i = layer.layer_id
        tdata["LAYER_ID"].append(i)
        tdata["NAME"].append(layer.name)
        tdata["EXTNAME_FL"].append(flux_extname(i))
        tdata["EXTNAME_AL"].append(alpha_extname(i))
        tdata["BLEND_MODE"].append(layer.blend_mode)
        tdata["OPACITY"].append(layer.opacity)
        tdata["XOFFSET"].append(layer.xoffset)
        tdata["YOFFSET"].append(layer.yoffset)
        tdata["WAVE_CVAL"].append(layer.wave_cval if layer.wave_cval else 0.0)
        tdata["WAVE_BWID"].append(layer.wave_bwid if layer.wave_bwid else 0.0)
        tdata["FLUX_MIN"].append(layer.flux_min if layer.flux_min is not None else 0.0)
        tdata["FLUX_MAX"].append(layer.flux_max if layer.flux_max is not None else 1.0)
        tdata["ALPHA_SRC"].append(layer.alpha_src)
        tdata["VISIBLE"].append(layer.visible)
        # D-5 (ratified): omission is absence everywhere. The old -1.0 sentinel sat
        # outside the documented [0,1] domain; NaN is the float-column null and the
        # FLUX_* header (normative, S4.3) simply omits FITA_ZDP when depth is unset.
        tdata["ZDEPTH"].append(layer.zdepth if layer.zdepth is not None else np.nan)

    fits_cols = []
    for name, fmt, unit, comment in LAYER_TABLE_COLS:
        arr = np.array(tdata[name])
        c = fits.Column(name=name, format=fmt, unit=unit, array=arr)
        fits_cols.append(c)

    layers_hdu = fits.BinTableHDU.from_columns(fits_cols)
    layers_hdu.name = EXTNAME_LAYERS
    hdul.append(layers_hdu)

    # ── Per-layer FLUX + ALPHA HDUs ───────────────────────────────────────────
    for layer in layers:
        i = layer.layer_id
        lhdr = fits.Header()
        for k, v in layer.to_header_dict().items():
            try:
                lhdr[k] = v
            except Exception:
                pass  # skip keys that don't fit FITS constraints

        if layer.wcs is not None:
            try:
                wcs_header = layer.wcs.to_header()
                lhdr.update(wcs_header)
            except Exception:
                pass

        # D-2 (ratified 2026-08-02): SPLIT16 is deleted. Rejected in write() above;
        # FLOAT32 is the only packing a conformant writer may emit (standard S6.4).
        flux_hdu = fits.ImageHDU(data=layer.flux_data, header=lhdr)

        flux_hdu.name = flux_extname(i)
        hdul.append(flux_hdu)

        ahdr = fits.Header()
        ahdr["FITA_LID"] = i
        # S6.3 [CORRECTION]: alpha is UNSIGNED 16-bit. Handing astropy a uint16 array
        # makes it emit BITPIX=16 with BZERO=32768/BSCALE=1 (the FITS unsigned
        # convention). The old int16 cast wrote every value >32767 as negative, which
        # third-party viewers (DS9/QFitsView/Aladin) read literally.
        # S7 [CORRECTION]: 'alpha16' is not a parseable FITS unit -> omit BUNIT.
        ahdr.add_comment("FITA alpha channel: 0=transparent, 65535=opaque")
        alpha = layer.alpha_data if layer.alpha_data is not None else \
                np.full(layer.shape, 65535, dtype=np.uint16)
        alpha_hdu = fits.ImageHDU(data=alpha.astype(np.uint16), header=ahdr)
        alpha_hdu.name = alpha_extname(i)
        hdul.append(alpha_hdu)

        # ── UNCERT extension (optional) ───────────────────────────────────────
        if layer.uncert_data is not None:
            uhdr = fits.Header()
            uhdr["FITA_LID"] = i
            # S7 [CORRECTION]: the uncertainty plane MUST carry the parent FLUX unit
            # string, not the human note 'same as FLUX' (which fails unit parsing in
            # the one extension whose purpose is numeric comparability with the flux).
            uhdr["BUNIT"]    = lhdr.get("BUNIT", bunit)
            uhdr.add_comment("FITA uncertainty: 1-sigma per-pixel error in flux units")
            unc_name = f"UNCERT_{i:04d}"
            uhdr[KW_UNCERT_EXT] = unc_name
            flux_hdu.header[KW_UNCERT_EXT] = unc_name   # cross-reference from flux HDU
            unc_hdu = fits.ImageHDU(data=layer.uncert_data.astype(np.float32), header=uhdr)
            unc_hdu.name = unc_name
            hdul.append(unc_hdu)

        # ── MASK extension (optional) ─────────────────────────────────────────
        if layer.mask_data is not None:
            mhdr = fits.Header()
            mhdr["FITA_LID"] = i
            mhdr["BUNIT"]    = "bitmask"
            mhdr.add_comment("FITA quality mask: bit0=bad, bit1=saturated, bit2=CR, bit3=gap")
            msk_name = f"MASK_{i:04d}"
            mhdr[KW_MASK_EXT] = msk_name
            flux_hdu.header[KW_MASK_EXT] = msk_name     # cross-reference from flux HDU
            msk_hdu = fits.ImageHDU(data=layer.mask_data.astype(np.uint8), header=mhdr)
            msk_hdu.name = msk_name
            hdul.append(msk_hdu)

    # ── FITA_ADJ (S8) then FITA_META (S9) ────────────────────────────────────
    # S4.1 canonical layout puts FITA_ADJ at HDU N-1 and FITA_META at HDU N.
    if adjustments is not None:
        adj_hdu = _build_adj_hdu(adjustments)
        if adj_hdu is not None:
            hdul.append(adj_hdu)

    if provenance is not None:
        hdul.append(_build_meta_hdu(provenance, layers))

    if checksum:
        # NOT writeto(checksum=True): astropy stamps a wall-clock time into the
        # CHECKSUM/DATASUM card comments, which makes an otherwise
        # deterministic file irreproducible byte-for-byte. add_checksum(when=)
        # lets the comment be pinned, so a generated artifact -- the
        # conformance corpus above all -- can carry real integrity keywords
        # AND regenerate identically. The checksum VALUE still covers the
        # whole HDU including its own card, so this weakens nothing.
        for _hdu in hdul:
            _hdu.add_checksum(when="updated %s" % date)

    hdul.writeto(str(path), overwrite=overwrite)
    hdul.close()


# ── Read ──────────────────────────────────────────────────────────────────────

def read(path: str | Path) -> List[FITALayer]:
    """Read a .fita file and return a list of FITALayer objects."""
    _require_astropy()
    layers = []

    with fits.open(str(path)) as hdul:
        primary = hdul[0].header
        pack = primary.get(KW_PACK, PACK_FLOAT32)

        try:
            ltable = hdul[EXTNAME_LAYERS].data
            registry = {int(row["LAYER_ID"]): row for row in ltable}
        except KeyError:
            registry = {}

        # collect FLUX extensions
        for hdu in hdul:
            name = hdu.name
            if not name.startswith("FLUX_"):
                continue
            try:
                idx = int(name.split("_")[1])
            except (IndexError, ValueError):
                continue

            flux_raw = hdu.data
            if flux_raw is None:
                continue

            # S6.4 / D-2: a reader encountering SPLIT16 MUST raise rather than return
            # flux values — the file does not contain what is needed to recover them.
            if pack == PACK_SPLIT16:
                raise ValueError(
                    f"{path}: FITAPACK='SPLIT16' is deprecated and unreadable in FITA v1.1 "
                    "(standard S6.4, decision D-2). The encoding parameters are absent from "
                    "such files, so the flux cannot be recovered; the data must be re-derived "
                    "from the original source."
                )
            flux = flux_raw.astype(np.float32)

            # corresponding alpha
            aname = alpha_extname(idx)
            try:
                alpha_raw = hdul[aname].data
                alpha = alpha_raw.astype(np.uint16) if alpha_raw is not None else None
            except KeyError:
                alpha = None

            # read WCS if present
            try:
                wcs = WCS(hdu.header, naxis=2)
            except Exception:
                wcs = None

            h = hdu.header
            row = registry.get(idx, {})
            _g = lambda key, default=None: row[key] if isinstance(row, dict) else \
                 (row[key] if key in row.dtype.names else default) if hasattr(row, "dtype") else default

            # optional uncertainty and mask extensions
            unc_name = h.get(KW_UNCERT_EXT, f"UNCERT_{idx:04d}")
            try:
                unc_raw = hdul[unc_name].data
                uncert = unc_raw.astype(np.float32) if unc_raw is not None else None
            except KeyError:
                uncert = None

            msk_name = h.get(KW_MASK_EXT, f"MASK_{idx:04d}")
            try:
                msk_raw = hdul[msk_name].data
                mask = msk_raw.astype(np.uint8) if msk_raw is not None else None
            except KeyError:
                mask = None

            # zdepth: absence is encoded by OMISSION (D-5).  The v1.0 `-1.0`
            # sentinel was retired there and MUST NOT be reinstated by the
            # reader.  This line used to discard every NEGATIVE value as
            # "absent", which was harmless only while S8.2 confined FITA_ZDP to
            # [0,1].  v1.4 made physical depths legal via FITA_ZDU, and the
            # first data class to exercise that is the velocity cube -- whose
            # channels are signed by nature.  The reader silently dropped every
            # approaching channel and renormalised over what survived, so a
            # round trip returned a DIFFERENT stereogram while the summary line
            # was unchanged.  Failure instance #10.
            _zdp_raw = h.get("FITA_ZDP", None)
            zdepth = None if _zdp_raw is None else float(_zdp_raw)

            visible = bool(h.get("FITA_VIS", True))

            layer = FITALayer(
                flux_data   = flux,
                alpha_data  = alpha,
                layer_id    = idx,
                name        = h.get("FITA_LNM", f"Layer {idx}"),
                blend_mode  = h.get("FITA_BLD", "NORMAL"),
                opacity     = float(h.get("FITA_OPC", 1.0)),
                xoffset     = float(h.get("FITA_XOF", 0.0)),
                yoffset     = float(h.get("FITA_YOF", 0.0)),
                flux_min    = h.get("FITA_FMN"),
                flux_max    = h.get("FITA_FMX"),
                wave_cval   = h.get("FITA_WCV"),
                wave_bwid   = h.get("FITA_WBW"),
                alpha_src   = h.get("FITA_ALS", "LUM"),
                zdepth      = zdepth,
                visible     = visible,
                wcs         = wcs,
                uncert_data = uncert,
                mask_data   = mask,
            )

            # Restore extra_header: recover all non-WCS, non-standard keys
            # that were written by to_header_dict() or skyview.py metadata tagging.
            _skip_prefixes = ("SIMPLE", "BITPIX", "NAXIS", "EXTEND",
                              "CD1_", "CD2_", "PC1_", "PC2_",
                              "CTYPE", "CRPIX", "CRVAL", "CDELT",
                              "CUNIT", "LONPOLE", "LATPOLE", "EQUINOX",
                              "RADESYS", "WCSAXES", "WCSNAME",
                              "FITA_LID", "FITA_LNM", "FITA_BLD", "FITA_OPC",
                              "FITA_XOF", "FITA_YOF", "FITA_FMN", "FITA_FMX",
                              "FITA_WCV", "FITA_WBW", "FITA_ALS", "FITA_ZDP",
                              "FITA_UNC", "FITA_MSK",
                              "XTENSION", "PCOUNT", "GCOUNT", "END")
            for card in h.cards:
                k = card.keyword
                if not k or k.startswith("COMMENT") or k.startswith("HISTORY"):
                    continue
                if any(k == s or k.startswith(s) for s in _skip_prefixes):
                    continue
                try:
                    layer.extra_header[k] = card.value
                except Exception:
                    pass

            layers.append(layer)

    layers.sort(key=lambda l: l.layer_id)
    return layers


# ── FITS cube import ──────────────────────────────────────────────────────────

def from_fits_cube(
    path: str | Path,
    flux_min: Optional[float] = None,
    flux_max: Optional[float] = None,
    stretch_mode: str = "asinh",
    wave_axis_unit: str = "m",
) -> List[FITALayer]:
    """
    Import a standard 3-D FITS data cube (x, y, lambda) as FITA layers.

    Each slice along axis 0 becomes one FITALayer, with wavelength/frequency
    read from the WCS.
    """
    _require_astropy()
    layers = []

    with fits.open(str(path)) as hdul:
        primary_hdu = hdul[0]
        data = primary_hdu.data  # shape (nslices, H, W)
        hdr  = primary_hdu.header

        if data is None or data.ndim < 2:
            raise ValueError("No image data in primary HDU")

        if data.ndim == 2:
            data = data[np.newaxis, ...]

        try:
            cube_wcs = WCS(hdr)
        except Exception:
            cube_wcs = None

        nslices = data.shape[0]
        for i in range(nslices):
            plane = data[i].astype(np.float32)
            wave = None
            if cube_wcs is not None:
                try:
                    # get wavelength at slice centre pixel
                    cx = plane.shape[1] // 2
                    cy = plane.shape[0] // 2
                    world = cube_wcs.pixel_to_world(cx, cy, i)
                    # world[2] is the spectral coordinate
                    if hasattr(world, '__len__') and len(world) >= 3:
                        wave = float(world[2].to("m").value) if hasattr(world[2], 'to') else None
                except Exception:
                    wave = None

            layer = FITALayer.from_array(
                plane, layer_id=i + 1,
                name=f"Slice {i + 1}",
                flux_min=flux_min, flux_max=flux_max,
                stretch_mode=stretch_mode,
                wave_cval=wave,
            )
            layers.append(layer)

    return layers
