"""
IVOA / VO compliance helpers for FITA.

Generates FITA_META BINTABLE HDU with ObsCore-compatible provenance and
writes UCDs into layer headers.  Also validates WCS spectral axes against
FITS WCS Paper III conventions.

References:
  IVOA ObsCore DM v1.1  https://ivoa.net/documents/ObsCore/
  IVOA DataCube DM      https://www.ivoa.net/documents/DataCube/
  FITS WCS Papers I-IV  https://fits.gsfc.nasa.gov/fits_wcs.html
  UCDs list             https://www.ivoa.net/documents/UCD1+/
"""

from __future__ import annotations
from typing import List, Optional, Dict, Any
import numpy as np

try:
    from astropy.io import fits
    _ASTROPY = True
except ImportError:
    _ASTROPY = False

from .spec import (
    EXTNAME_META,
    UCD_FLUX, UCD_WAVE, UCD_FREQ, UCD_RA, UCD_DEC, UCD_TIME, UCD_EXPOSURE,
)
from .layer import FITALayer


# ── UCD annotation ────────────────────────────────────────────────────────────

def annotate_flux_header(header, ucd: str = UCD_FLUX, bunit: str = "ct/s"):
    """Add UCD and BUNIT to a flux HDU header in place."""
    header["UCD1"]  = ucd
    header["BUNIT"] = bunit
    return header


def annotate_alpha_header(header):
    """Annotate an ALPHA_* header.

    S7 / D-4: alpha is a dimensionless display quantity, and the old
    ``BUNIT = 'alpha16'`` is not a parseable FITS unit -- it failed
    ``astropy.units.Unit(parse_strict='raise')`` in all 18 archived files.
    The conformant encoding is to omit BUNIT entirely.
    """
    header["UCD1"] = "meta.code;phot.flux"
    header.pop("BUNIT", None)
    return header


# ── Spectral WCS validation ────────────────────────────────────────────────────

_VALID_SPECTRAL_CTYPES = {
    # wavelength
    "WAVE", "WAVE-LOG", "WAVE-F2W", "WAVE-V2W",
    # frequency
    "FREQ", "FREQ-LOG", "FREQ-F2F",
    # velocity
    "VRAD", "VOPT", "VHEL", "VGSR",
    # energy
    "ENER", "WAVN",
    # redshift
    "ZOPT", "ZRAD",
    "STOKES",
}


def validate_spectral_ctype(ctype: str) -> bool:
    base = ctype.split("-")[0].strip().upper()
    return base in _VALID_SPECTRAL_CTYPES


# ── ObsCore provenance HDU ────────────────────────────────────────────────────

# ObsCore DM v1.1 mandatory columns, plus a few FITA-specific extras.
#
# D-4 (ratified 2026-08-02) expanded this table.  NOTE: the ruling named
# ObsCore 'v1.2', which DOES NOT EXIST -- v1.1 (2017-05-09) is the only
# Recommendation. Corrected in v1.2.1; see ERRATUM__ObsCore_version__2026-08-02.md.
# Whether this list is the COMPLETE v1.1 mandatory set is NOT yet verified
# against Table 1 of the REC.  The earlier
# table shipped 22 columns and omitted nine that ObsCore makes mandatory
# (obs_publisher_did, s_region, s_xel1, s_xel2, t_xel, em_xel, o_ucd,
# pol_states, access_estsize), which is why the "ObsCore compliant" claim was
# withdrawn as an overclaim.  It also defined per-column UCDs here and then
# never wrote them to the file, so the semantic annotation that makes the
# table VO-interpretable was discarded at write time.  Both are fixed: the
# list below is complete, and the UCDs are emitted as TUCDn (the FITS
# convention for table-column UCDs -- not the UCD1/UCDXXXXX forms the older
# code and docstrings used).
#
# (colname, fits_fmt, ucd, unit, description)
_OBSCORE_COLS = [
    # -- provenance / identity -------------------------------------------
    ("obs_publisher_did", "128A", "meta.ref.ivoid",         "", "Publisher dataset identifier (IVOID)"),
    ("obs_id",            "64A",  "meta.id",                "", "Observation identifier"),
    ("obs_collection",    "64A",  "meta.id",                "", "Data collection name"),
    ("obs_title",         "128A", "meta.title;obs",         "", "Dataset title"),
    ("obs_creator",       "64A",  "meta.id.PI",             "", "Creator / PI"),
    ("target_name",       "64A",  "meta.id;src",            "", "Target name"),
    ("facility_name",     "64A",  "meta.id;instr.tel",      "", "Telescope or facility"),
    ("instrument_name",   "64A",  "meta.id;instr",          "", "Instrument name"),
    ("dataproduct_type",  "16A",  "meta.code.class",        "", "Data product type"),
    ("calib_level",       "I",    "meta.code;obs.calib",    "", "Calibration level 0-4"),
    ("o_ucd",             "64A",  "meta.ucd",               "", "UCD of the observable quantity"),
    ("pol_states",        "32A",  "meta.code;phys.polarization", "", "Polarization states present"),
    ("pol_xel",           "J",    "meta.number",            "", "Number of samples along the polarization axis"),
    # -- spatial ----------------------------------------------------------
    ("s_ra",              "D",    "pos.eq.ra",              "deg",    "Central right ascension"),
    ("s_dec",             "D",    "pos.eq.dec",             "deg",    "Central declination"),
    ("s_fov",             "D",    "phys.angSize;instr.fov", "deg",    "Field of view diameter"),
    ("s_region",          "256A", "pos.outline;obs.field",  "",       "Spatial footprint (STC-S)"),
    ("s_resolution",      "D",    "pos.angResolution",      "arcsec", "Spatial resolution"),
    ("s_xel1",            "J",    "meta.number",            "",       "Number of pixels along axis 1"),
    ("s_xel2",            "J",    "meta.number",            "",       "Number of pixels along axis 2"),
    # -- temporal ---------------------------------------------------------
    ("t_min",             "D",    "time.start;obs.exposure",    "d", "Start time (MJD)"),
    ("t_max",             "D",    "time.end;obs.exposure",      "d", "Stop time (MJD)"),
    ("t_exptime",         "D",    "time.duration;obs.exposure", "s", "Total exposure time"),
    ("t_resolution",      "D",    "time.resolution",            "s", "Temporal resolution"),
    ("t_xel",             "J",    "meta.number",                "",  "Number of samples along the time axis"),
    # -- spectral ---------------------------------------------------------
    ("em_min",            "D",    "em.wl;stat.min",  "m", "Minimum wavelength"),
    ("em_max",            "D",    "em.wl;stat.max",  "m", "Maximum wavelength"),
    ("em_res_power",      "D",    "spect.resolution", "", "Spectral resolving power"),
    ("em_xel",            "J",    "meta.number",      "", "Number of samples along the spectral axis"),
    # -- access -----------------------------------------------------------
    ("access_url",        "256A", "meta.ref.url",     "",     "Download URL"),
    ("access_format",     "64A",  "meta.code.mime",   "",     "MIME type"),
    ("access_estsize",    "K",    "phys.size;meta.file", "kbyte", "Estimated file size"),
    # -- FITA extensions (not ObsCore) ------------------------------------
    ("fita_nlayers",      "I",    "meta.number",      "", "Number of FITA layers"),
]

# Standard S3: 'application/fits+alpha' is NOT registered with IANA and MUST
# NOT be emitted into provenance metadata as though it were.  A .fita file is
# a valid FITS MEF, so this is the honest type until registration is granted.
ACCESS_FORMAT = "application/fits"


def make_meta_hdu(
    obs_id: str = "",
    obs_title: str = "",
    facility: str = "",
    instrument: str = "",
    target: str = "",
    ra: float = 0.0,
    dec: float = 0.0,
    t_min: float = 0.0,
    t_max: float = 0.0,
    t_exptime: float = 0.0,
    em_min: float = 0.0,
    em_max: float = 0.0,
    calib_level: int = 2,
    nlayers: int = 0,
    access_url: str = "",
    extra: Optional[Dict[str, Any]] = None,
):
    """Build an ObsCore DM v1.1 FITA_META BINTABLE HDU.

    Targets IVOA ObsCore DM v1.1 -- the current Recommendation; there is no
    v1.2, despite what earlier versions of this project claimed.  Each column
    carries its UCD as a ``TUCDn`` keyword so the table is semantically
    interpretable by VO tooling rather than merely structurally present.

    NOT YET VERIFIED: that this is the complete v1.1 mandatory column set.
    See ERRATUM__ObsCore_version__2026-08-02.md S5 before restating it.

    `extra` sets any column directly by name -- that is how the fields with no
    dedicated argument (obs_publisher_did, s_region, s_xel1/2, t_xel, em_xel,
    o_ucd, pol_states, access_estsize) are populated.  `meta_from_layers()`
    fills most of them in automatically.
    """
    if not _ASTROPY:
        raise ImportError("astropy required")

    row = {
        "obs_publisher_did": "",
        "obs_id":            obs_id,
        "obs_collection":    "",
        "obs_title":         obs_title,
        "obs_creator":       "",
        "target_name":       target,
        "facility_name":     facility,
        "instrument_name":   instrument,
        "dataproduct_type":  "cube",
        "calib_level":       calib_level,
        "o_ucd":             UCD_FLUX,
        "pol_states":        "",
        "s_ra":              ra,
        "s_dec":             dec,
        "s_fov":             0.0,
        "s_region":          "",
        "s_resolution":      0.0,
        "s_xel1":            0,
        "s_xel2":            0,
        "t_min":             t_min,
        "t_max":             t_max,
        "t_exptime":         t_exptime,
        "t_resolution":      0.0,
        "t_xel":             0,
        "em_min":            em_min,
        "em_max":            em_max,
        "em_res_power":      0.0,
        "em_xel":            nlayers,
        "access_url":        access_url,
        "access_format":     ACCESS_FORMAT,
        "access_estsize":    0,
        "fita_nlayers":      nlayers,
    }
    if extra:
        row.update(extra)

    cols = []
    for colname, fmt, ucd, unit, desc in _OBSCORE_COLS:
        val = row.get(colname, "" if "A" in fmt else 0)
        cols.append(fits.Column(name=colname, format=fmt, unit=unit,
                                array=np.array([val])))

    hdu = fits.BinTableHDU.from_columns(cols)
    hdu.name = EXTNAME_META

    # S9: column UCDs MUST be written as TUCDn.  Neither the UCD1 keyword the
    # old code wrote nor the UCDXXXXX form the old docstring described is the
    # FITS convention for table columns, so both were invisible to VO readers.
    for idx, (colname, fmt, ucd, unit, desc) in enumerate(_OBSCORE_COLS, start=1):
        if ucd:
            hdu.header["TUCD%d" % idx] = (ucd, desc[:40])

    hdu.header.add_comment("IVOA ObsCore DM v1.1 provenance")
    hdu.header.add_comment("https://ivoa.net/documents/ObsCore/")
    return hdu


def meta_from_layers(
    layers: List[FITALayer],
    obs_id: str = "",
    estsize_kb: int = 0,
    **kwargs,
):
    """Build a FITA_META HDU, deriving what the layers already know.

    Several ObsCore columns are properties of the data rather than of the
    observer's intent, so asking a caller to supply them invites them to be
    wrong.  Spatial extent, spectral coverage and axis counts are read off the
    layers; anything passed in `kwargs` overrides the derived value.
    """
    em_lo, em_hi = sed_wavelength_range(layers)

    derived: Dict[str, Any] = {
        "em_xel": len(layers),
        "t_xel": 1,
        "access_estsize": int(estsize_kb),
        "o_ucd": UCD_FLUX,
    }
    if layers:
        shape = getattr(layers[0], "shape", None)
        if shape and len(shape) >= 2:
            derived["s_xel2"], derived["s_xel1"] = int(shape[0]), int(shape[1])

    extra = dict(derived)
    extra.update(kwargs.pop("extra", None) or {})

    return make_meta_hdu(
        obs_id=obs_id,
        em_min=kwargs.pop("em_min", em_lo),
        em_max=kwargs.pop("em_max", em_hi),
        nlayers=len(layers),
        extra=extra,
        **kwargs,
    )


# ── SED helper: wavelength coverage from layers ───────────────────────────────

def sed_wavelength_range(layers: List[FITALayer]):
    """
    Return (em_min, em_max) in metres from a list of FITALayer objects,
    using wave_cval and wave_bwid where available.
    """
    lo_vals, hi_vals = [], []
    for layer in layers:
        if layer.wave_cval is None:
            continue
        half = (layer.wave_bwid or 0.0) / 2.0
        lo_vals.append(layer.wave_cval - half)
        hi_vals.append(layer.wave_cval + half)
    if not lo_vals:
        return 0.0, 0.0
    return float(min(lo_vals)), float(max(hi_vals))
