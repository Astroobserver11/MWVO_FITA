"""
FITA — Flexible Image Transfer Alpha
======================================
Format specification constants, keyword registry, and blend-mode codes.

File extension : .fita
MIME type      : application/fits+alpha  (pending IANA registration)
FITS magic     : SIMPLE = T  (fully backward-compatible FITS)

HDU layout
----------
0  PRIMARY        Empty data; carries global FITA keywords + WCS skeleton
1  FITA_LAYERS    BINTABLE — layer/slice registry (one row per layer)
2  FLUX_0001      IMAGE    — flux data for layer 1 (16-bit scaled int or 32-bit float)
3  ALPHA_0001     IMAGE    — alpha mask for layer 1 (BITPIX=16, uint, 0-65535)
4  FLUX_0002      ...
5  ALPHA_0002     ...
N  FITA_ADJ       BINTABLE — adjustment-layer stack (optional)
N+1 FITA_META    BINTABLE — IVOA / VOTable-compatible provenance (optional)

Coordinate convention
---------------------
Each layer carries its own 2-D WCS (CRPIX, CRVAL, CD matrix) so its
(x,y) canvas position is encoded in standard FITS world-coordinates.
A CANVAS_W / CANVAS_H keyword in PRIMARY defines the logical bounding box.

32-bit → 16+16 packing (FITA_PACK = 'SPLIT16')
-----------------------------------------------
When FITA_PACK = 'SPLIT16', each FLUX extension is stored as BITPIX=16
uint with BSCALE/BZERO encoding the physical flux range:
    flux_16  = round( (flux - FMIN) / (FMAX - FMIN) * 65535 )
    alpha_16 = luminance-derived transparency, same 0-65535 range

Alternatively FITA_PACK = 'FLOAT32' stores full 32-bit flux in FLUX_*
and ALPHA_* as uint16.  Default is FLOAT32.

IVOA notes
----------
- Headers use UCDs (Unified Content Descriptors) via UCDXXXXX keywords
- Spectral axis follows FITS WCS Paper III conventions (CTYPE3 = WAVE/FREQ/VRAD)
- FITA_META HDU provides ObsCore-compatible provenance columns
- See https://www.ivoa.net/documents/DataCube/ for IVOA DataCube DM
"""

# v1.2 — author ruling 2026-08-02.  S13 requires an increment on ANY change to
# required or optional structure, and the rulings Q1/Q2 added new optional
# structure AFTER v1.1 was ratified: the FITA_ADJ column schema, and the
# FITA_ZRF / FITA_ZAN stereo keywords.  Leaving this at "1.1" would have
# repeated verbatim the [CORRECTION] the standard levels at the 2026-05-25
# delivery — three keywords added with no version bump, so files written
# before and after claimed one version while differing in structure.
# v1.4 — principal's ruling 2026-08-02 (RULING__stereogram_scale_and_N-1):
# "The scale of the Stereogram is a percentage of the diameter of the field
# under study, made explicit as a measure in units practical to the subject."
# That adds FITA_FDI / FITA_FDU / FITA_ZDU as optional structure, redefines
# FITA_ZSC, and retires FITA_ZAN.  S13 requires the increment in this change.
FITA_VERSION = "1.4"   # S13 is major.minor; stereo scale is now field-relative

# ── Primary HDU mandatory keywords (all ≤8 chars, standard FITS) ────────────
KW_VERSION   = "FITAVER"    # str  format version
KW_PACK      = "FITAPACK"   # str  'FLOAT32' | 'SPLIT16'  (→ HIERARCH if needed)
KW_NLAYERS   = "FITANL"     # int  number of layers
KW_CANVAS_W  = "FITACW"     # int  canvas width  (pixels)
KW_CANVAS_H  = "FITACH"     # int  canvas height (pixels)
KW_BUNIT     = "BUNIT"      # str  physical flux unit (FITS standard)
KW_INSTRUME  = "INSTRUME"   # str  originating instrument
KW_FIELD_DIA = "FITA_FDI"   # float OPTIONAL diameter of the field under study, in FITA_FDU
KW_FIELD_UNI = "FITA_FDU"   # str   OPTIONAL FITS unit of FITA_FDI ('pc'|'km'|'arcsec'|'deg'|'AU')
KW_ZSCALE    = "FITA_ZSC"   # float OPTIONAL stereo parallax, as a PERCENTAGE of FITA_FDI
KW_ZREF      = "FITA_ZRF"   # float OPTIONAL reference plane: ZDP at zero parallax
KW_ZDEPTH_U  = "FITA_ZDU"   # str   OPTIONAL FITS unit of FITA_ZDP; absent => dimensionless [0,1]
KW_ZANG      = "FITA_ZAN"   # float RETIRED v1.4 — see the dissolution note below

# Stereo geometry — decision D-6, ratified 2026-08-02; convention settled by
# author ruling Q2, 2026-08-02.  All three keywords are OPTIONAL and written
# by a RENDERER, never by the compositor.
#
# S8.2 deliberately does not specify how FITA_ZDP maps to a pixel offset: the
# mapping is a property of a rendering job, not of the file.  But the MWVO
# depth-stimulus discipline requires that stereo separation be *measured* and
# traceable, and a rendered pair whose parallax cannot be recovered is not
# traceable.  These keywords record the geometry actually used.
#
# Convention (normative when FITA_ZSC is present) — REDEFINED in v1.4:
#
#     FITA_FDI = diameter of the field under study
#     FITA_FDU = its unit, chosen to be practical to the SUBJECT: pc for a
#                dust cube, km for a cometary surface, arcsec or deg for a sky
#                field, AU for a disc.
#     FITA_ZSC = total horizontal parallax across the full FITA_ZDP range, as
#                a PERCENTAGE of FITA_FDI (dimensionless; 4.0 means 4 %).
#     FITA_ZRF = the ZDP value placed at ZERO parallax (the screen plane).
#                Defaults to 0.0 when omitted, i.e. background at the screen.
#
#     per-eye offset:  dx = ±(FITA_ZSC / 100) * FITA_FDI * (zdp_n − FITA_ZRF) / 2
#                      left eye = −,  right eye = +
#
# dx is in units of FITA_FDU.  Converting it to display pixels needs the WCS or
# a stated plate scale and is the RENDERER's job — that conversion is
# deliberately not recorded in the file.  The file records the *measured*
# stimulus; the renderer records the *rendering*.
#
# Why this replaced a pixel count.  v1.2 defined FITA_ZSC in pixels, but a
# pixel is a property of a rendering target, not of a field, and is meaningless
# without a display size the file does not know.  A percentage alone is
# unanchored; a physical length alone is not a stimulus.  Together they are a
# metric chain, which is what the MWVO depth-stimulus discipline requires.
#
# Validator consequence: FITA_ZSC present without FITA_FDI and FITA_FDU is a
# MUST failure.  A percentage of nothing is not a measurement.
#
# With FITA_ZRF = 0.0 a layer at ZDP=0 (21 cm HI) sits in the screen plane and
# ZDP=1 (X-ray plasma) carries the full separation forward.  With FITA_ZRF =
# 0.5 the H-alpha layer sits at the screen, HI recedes behind it and the X-ray
# plasma comes forward — the depth budget is spent symmetrically about a
# chosen plane rather than always pushed one way.  A negative FITA_ZSC
# inverts the depth sense.
#
# FITA_ZDU — the unit of FITA_ZDP for this file, resolving N-1.
#
# Eight archived stereo files carry Edenhofer distance bins (624.05 / 1248.10 /
# 2496.20 pc) in FITA_ZDP, while S8.2 defines the domain as [0,1].  The
# principal's ruling: those values are in a unit practical to the subject, so
# the writer's instinct was right — the defect is that the parsec-ness is
# nowhere DECLARED.  A reader has no way to know.  It is a missing declaration,
# not a wrong value.
#
#     FITA_ZDU ABSENT   → FITA_ZDP is dimensionless and MUST lie in [0,1]
#                         (the v1.2 rule, unchanged — absence stays the strict
#                         case, so no existing conformant file changes meaning)
#     FITA_ZDU PRESENT  → FITA_ZDP carries a physical depth in that unit and
#                         the [0,1] constraint MUST NOT be applied
#
# A renderer MUST normalise a FITA_ZDU-bearing cube to [0,1] over the range
# actually present before applying parallax.  See fita.stereo.normalise_depths().
# This makes the eight files conformant by adding ONE keyword rather than by
# rewriting 48 layers of real science data — consistent with D-5 (absence by
# omission) and D-1 (grandfathering).
#
# FITA_ZAN — RETIRED in v1.4, by dissolution rather than by replacement.
#
# The open question was "sky angle or viewing disparity?"  The answer is
# neither: the question was malformed.  Once the field diameter is declared in
# a subject-practical unit and the scale is a percentage of it, the separation
# is expressible in whatever unit the subject wants — angle for a sky field,
# length for a cube — by arithmetic, with no new keyword and no ambiguity.
# FITA_ZAN hard-coded arcsec, which privileges the sky-projection case and is
# exactly the wrong default for a 3D dust cube measured in parsecs.
#
# Readers MUST continue to accept FITA_ZAN in files written before v1.4 (D-1);
# writers SHOULD NOT emit it.

# ── Layer-level keywords (carried in each FLUX_* extension) ─────────────────
KW_LAYER_ID   = "FITA_LID"   # int   layer index (1-based)
KW_LAYER_NAME = "FITA_LNM"   # str   human label
KW_BLEND_MODE = "FITA_BLD"   # str   blend mode code
KW_OPACITY    = "FITA_OPC"   # float 0.0-1.0 layer opacity
KW_FLUX_MIN   = "FITA_FMN"   # float physical flux lower bound
KW_FLUX_MAX   = "FITA_FMX"   # float physical flux upper bound
KW_WAVE_CVAL  = "FITA_WCV"   # float central wavelength (metres)
KW_WAVE_BWID  = "FITA_WBW"   # float bandpass width    (metres)
KW_XOFFSET    = "FITA_XOF"   # float canvas x-offset in pixels
KW_YOFFSET    = "FITA_YOF"   # float canvas y-offset in pixels
KW_ALPHA_SRC  = "FITA_ALS"   # str   alpha derivation: 'LUM'|'USER'|'NONE'
KW_DEPTH      = "FITA_ZDP"   # float stereo depth 0.0 (background) to 1.0 (foreground)
KW_VISIBLE    = "FITA_VIS"   # bool  layer visibility flag (T=visible, F=hidden)
KW_UNCERT_EXT = "FITA_UNC"   # str   name of companion UNCERT_* extension (if present)
KW_MASK_EXT   = "FITA_MSK"   # str   name of companion MASK_*   extension (if present)

# ── FITA_LAYERS BINTABLE columns ─────────────────────────────────────────────
LAYER_TABLE_COLS = [
    ("LAYER_ID",   "J",   "",            "Layer index"),
    ("NAME",       "32A", "",            "Layer label"),
    ("EXTNAME_FL", "16A", "",            "FLUX extension name"),
    ("EXTNAME_AL", "16A", "",            "ALPHA extension name"),
    ("BLEND_MODE", "8A",  "",            "Blend mode code"),
    ("OPACITY",    "E",   "",            "0-1 opacity"),
    ("XOFFSET",    "D",   "pixel",       "Canvas x offset"),
    ("YOFFSET",    "D",   "pixel",       "Canvas y offset"),
    ("WAVE_CVAL",  "D",   "m",           "Central wavelength"),
    ("WAVE_BWID",  "D",   "m",           "Bandpass FWHM"),
    ("FLUX_MIN",   "D",   "",            "Scaling floor"),
    ("FLUX_MAX",   "D",   "",            "Scaling ceiling"),
    ("ALPHA_SRC",  "8A",  "",            "Alpha derivation"),
    ("VISIBLE",    "L",   "",            "Visibility flag"),
    ("ZDEPTH",     "E",   "",            "Stereo depth 0=bg 1=fg"),
]

# ── FITA_ADJ BINTABLE columns (S8 / decision D-3) ───────────────────────────
#
# Author ruling 2026-08-02 (Q1): the common adjustment parameters get REAL
# TYPED COLUMNS.  An earlier draft put every type-specific parameter in a
# single JSON blob, which was compact but opaque: the whole premise of FITA is
# that any FITS reader can open the file, and a reader that can open the file
# but cannot see that GAMMA = 2.2 has not really been given the data.  JSON is
# now reserved for the parameters that genuinely have no fixed width.
#
# A column that does not apply to a row carries the D-5 absence convention:
# NaN for floats, empty string for text.  Only CURVES and FXNORM populate
# PARAMS at all.
ADJ_TABLE_COLS = [
    ("ORDER",     "J",   "",      "Application order, 0-based"),
    ("ADJ_TYPE",  "16A", "",      "Adjustment code (see ADJ_* constants)"),
    ("ENABLED",   "L",   "",      "Whether this adjustment is applied"),
    ("NAME",      "64A", "",      "Human label"),
    ("LAYER_ID",  "J",   "",      "0 = whole composite, >0 = that layer"),
    # -- LEVELS ---------------------------------------------------------
    ("IN_BLACK",  "D",   "",      "LEVELS input black point"),
    ("IN_WHITE",  "D",   "",      "LEVELS input white point"),
    ("GAMMA",     "D",   "",      "LEVELS gamma"),
    ("OUT_BLACK", "D",   "",      "LEVELS output black point"),
    ("OUT_WHITE", "D",   "",      "LEVELS output white point"),
    # -- BRIGHTNESS -----------------------------------------------------
    ("BRIGHT",    "D",   "",      "BRIGHTNESS brightness, -1..+1"),
    ("CONTRAST",  "D",   "",      "BRIGHTNESS contrast, -1..+1"),
    # -- FXSTRETCH ------------------------------------------------------
    ("STRETCH",   "16A", "",      "FXSTRETCH mode: linear|log|sqrt|asinh|power"),
    ("ASINH_A",   "D",   "",      "FXSTRETCH asinh softening parameter"),
    ("POWER_EXP", "D",   "",      "FXSTRETCH power-law exponent"),
    # -- BANDMAP --------------------------------------------------------
    ("CHANNEL",   "2A",  "",      "BANDMAP display channel: R|G|B"),
    # -- FXNORM ---------------------------------------------------------
    ("WAVE_CVAL", "D",   "m",     "FXNORM wavelength at which response is sampled"),
    # -- variable-length remainder --------------------------------------
    ("PARAMS",    "A",   "",      "JSON: variable-length parameters only"),
]

# Typed column -> AdjustmentLayer field.  Anything not listed here and not in
# ADJ_VARLEN_FIELDS is a structural column (ORDER, ADJ_TYPE, ...).
ADJ_SCALAR_COLS = {
    "LAYER_ID":  "layer_id",
    "IN_BLACK":  "in_black",
    "IN_WHITE":  "in_white",
    "GAMMA":     "gamma",
    "OUT_BLACK": "out_black",
    "OUT_WHITE": "out_white",
    "BRIGHT":    "brightness",
    "CONTRAST":  "contrast",
    "STRETCH":   "stretch_mode",
    "ASINH_A":   "asinh_a",
    "POWER_EXP": "power_exp",
    "CHANNEL":   "channel",
    "WAVE_CVAL": "wave_cval",
}

# Fields with no fixed width -- these stay in the JSON PARAMS column.
ADJ_VARLEN_FIELDS = {"control_points", "response_curve", "wavelengths"}

# ── Blend mode codes (Photoshop / GIMP compatible subset) ───────────────────
BLEND_NORMAL   = "NORMAL"
BLEND_SCREEN   = "SCREEN"
BLEND_MULTIPLY = "MULTIPLY"
BLEND_ADD      = "ADD"       # linear dodge — common in astro compositing
BLEND_OVERLAY  = "OVERLAY"
BLEND_SOFT     = "SOFTLGT"
BLEND_HARD     = "HARDLGT"
BLEND_DODGE    = "CDODGE"
BLEND_BURN     = "CBURN"
BLEND_DIFF     = "DIFF"
BLEND_LUMINOSITY = "LUM"     # preserves flux luminosity, applies colour
BLEND_COLOR    = "COLOR"     # applies hue/chroma, preserves luminosity
BLEND_HUE      = "HUE"
BLEND_SAT      = "SAT"

BLEND_CODES = {
    BLEND_NORMAL, BLEND_SCREEN, BLEND_MULTIPLY, BLEND_ADD,
    BLEND_OVERLAY, BLEND_SOFT, BLEND_HARD, BLEND_DODGE, BLEND_BURN,
    BLEND_DIFF, BLEND_LUMINOSITY, BLEND_COLOR, BLEND_HUE, BLEND_SAT,
}

# ── Adjustment layer types ───────────────────────────────────────────────────
ADJ_LEVELS       = "LEVELS"       # input/output levels remap
ADJ_CURVES       = "CURVES"       # tone curve (spline)
ADJ_BRIGHTNESS   = "BRIGHTNESS"   # brightness + contrast
ADJ_HUE_SAT     = "HUESAT"       # hue / saturation / lightness
ADJ_COLOR_BALANCE= "COLBAL"       # shadows/mids/highs colour shift
ADJ_FLUX_STRETCH = "FXSTRETCH"    # astrophysical stretch (log/sqrt/asinh/linear)
ADJ_BANDMAP      = "BANDMAP"      # assign wavelength band to RGB channel
ADJ_FLUX_NORM    = "FXNORM"       # normalise to instrument response curve

# ── IVOA UCDs used in provenance ────────────────────────────────────────────
UCD_FLUX      = "phot.flux.density"
UCD_WAVE      = "em.wl"
UCD_FREQ      = "em.freq"
UCD_RA        = "pos.eq.ra"
UCD_DEC       = "pos.eq.dec"
UCD_TIME      = "time.epoch"
UCD_EXPOSURE  = "obs.exposure"

# ── Extension name templates ─────────────────────────────────────────────────
def flux_extname(idx: int) -> str:
    return f"FLUX_{idx:04d}"

def alpha_extname(idx: int) -> str:
    return f"ALPHA_{idx:04d}"

EXTNAME_LAYERS = "FITA_LAYERS"
EXTNAME_ADJ    = "FITA_ADJ"
EXTNAME_META   = "FITA_META"

PACK_FLOAT32 = "FLOAT32"
PACK_SPLIT16 = "SPLIT16"
