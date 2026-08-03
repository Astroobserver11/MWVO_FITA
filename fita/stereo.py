"""
fita.stereo -- phased stereography: turning FITA_ZDP into measured parallax.

FITA_ZDP (S8.2) assigns each layer a depth that encodes *physical ISM
penetration depth* rather than an arbitrary stacking order: 21 cm H I at the
back, H-alpha in the middle, X-ray hot plasma in front.  A stereo renderer
turns that into a differential horizontal offset between two eye views.

v1.4 -- the principal's ruling of 2026-08-02:

    "The scale of the Stereogram is a percentage of the diameter of the field
    under study, made explicit as a measure in units practical to the subject."

Two requirements in one sentence, and both must hold.  The scale is RELATIVE --
a percentage of the field diameter, dimensionless.  The field is ABSOLUTE --
its diameter stated in a unit practical to the subject: pc for a dust cube, km
for a cometary surface, arcsec or deg for a sky field, AU for a disc.

    FITA_FDI = diameter of the field under study
    FITA_FDU = its unit
    FITA_ZSC = total parallax across the full ZDP range, as a % of FITA_FDI
    FITA_ZRF = the ZDP value placed at zero parallax (the screen plane)
    FITA_ZDU = unit of FITA_ZDP; absent means dimensionless [0,1]

    dx(layer) = +/- (FITA_ZSC / 100) * FITA_FDI * (zdp_n - FITA_ZRF) / 2
                left eye = -,  right eye = +

`dx` comes out in units of FITA_FDU.  Converting it to display pixels needs a
WCS or a stated plate scale and is the RENDERER's job -- see
`to_display_pixels()`, which is deliberately a helper here and not a keyword in
the file.  The file records the measured stimulus; the renderer records the
rendering.

**This supersedes the v1.2 pixel convention.**  A pixel count is a property of
a rendering target, not of a field, and is meaningless without a display size
the file does not know.  A percentage alone is unanchored; a physical length
alone is not a stimulus.  Together they are a metric chain, which is what the
MWVO depth-stimulus discipline has required from the start.

FITA_ZAN is retired.  Its question -- sky angle or viewing disparity? -- was
malformed: once the field diameter carries a subject-practical unit, the
separation is expressible in whatever unit the subject wants by arithmetic.
`angular_parallax()` is gone with it; `pixel_scale_arcsec()` survives because a
renderer still needs it.

Nothing here touches FLUX_*: stereo separation is display geometry (S5.2).
"""

from __future__ import annotations

import math
from typing import Dict, Iterable, List, Optional, Tuple

LEFT = "L"
RIGHT = "R"


# ── depth normalisation (S8.2, FITA_ZDU) ─────────────────────────────────────

def normalise_depths(layers: Iterable,
                     zdp_unit: Optional[str] = None) -> List[Optional[float]]:
    """Per-layer FITA_ZDP mapped onto [0,1], in layer order.

    When ``zdp_unit`` is None the depths are already dimensionless and are
    passed through unchanged -- the v1.2 rule, and the strict case.

    When ``zdp_unit`` is given the depths carry a physical quantity (the eight
    archived Edenhofer files hold 624.05 / 1248.10 / 2496.20 pc) and the
    standard requires normalisation *over the range actually present* before
    parallax is applied.  Layers without a depth stay None: absence is encoded
    by omission (D-5) and must not become 0.0.

    A single distinct depth normalises to 0.0 -- the screen plane -- rather
    than dividing by zero.  One shell is not a depth range, and putting it at
    zero parallax says so honestly.
    """
    depths = [getattr(l, "zdepth", None) for l in layers]
    vals = [float(d) for d in depths if d is not None]

    if zdp_unit is None or not vals:
        return [None if d is None else float(d) for d in depths]

    lo, hi = min(vals), max(vals)
    span = hi - lo
    if span <= 0:
        return [None if d is None else 0.0 for d in depths]
    return [None if d is None else (float(d) - lo) / span for d in depths]


# ── parallax (S8.2, normative) ───────────────────────────────────────────────

def eye_offset(zdepth_n: Optional[float], zdp_scale: float, field_dia: float,
               eye: str = LEFT, zdp_ref: float = 0.0) -> float:
    """Horizontal offset for one layer in one eye view, in units of FITA_FDU.

    ``zdepth_n`` is a NORMALISED depth -- run physical depths through
    `normalise_depths()` first.  ``zdp_scale`` is FITA_ZSC as a percentage,
    ``field_dia`` is FITA_FDI.

    A layer with no depth assignment (zdepth is None -- absence is encoded by
    omission, per D-5) sits at zero parallax rather than being guessed at.
    """
    if zdepth_n is None:
        return 0.0
    sign = -1.0 if str(eye).upper().startswith("L") else +1.0
    total = (float(zdp_scale) / 100.0) * float(field_dia)
    return sign * total * (float(zdepth_n) - float(zdp_ref)) / 2.0


def stereo_offsets(layers: Iterable, zdp_scale: float, field_dia: float,
                   zdp_ref: float = 0.0,
                   zdp_unit: Optional[str] = None) -> List[Dict[str, float]]:
    """Per-layer (left, right) offsets for a stereo pair, in FITA_FDU units.

    Returns one record per layer so a renderer can composite each eye view by
    shifting layers horizontally, and so a reviewer can read back exactly what
    separation was applied.  Both the raw and the normalised depth are
    reported: the raw value is what the file says, the normalised one is what
    the parallax was actually computed from, and conflating them is how a
    physical-units cube would silently render as if it were dimensionless.
    """
    layers = list(layers)
    norm = normalise_depths(layers, zdp_unit)
    out: List[Dict[str, float]] = []
    for layer, zn in zip(layers, norm):
        raw = getattr(layer, "zdepth", None)
        out.append({
            "layer_id": int(getattr(layer, "layer_id", 0) or 0),
            "name": str(getattr(layer, "name", "") or ""),
            "zdepth": None if raw is None else float(raw),
            "zdepth_n": zn,
            "dx_left": eye_offset(zn, zdp_scale, field_dia, LEFT, zdp_ref),
            "dx_right": eye_offset(zn, zdp_scale, field_dia, RIGHT, zdp_ref),
        })
    return out


def max_parallax(layers: Iterable, zdp_scale: float, field_dia: float,
                 zdp_ref: float = 0.0,
                 zdp_unit: Optional[str] = None) -> float:
    """Largest left-right separation across the layer set, in FITA_FDU units.

    This is the number a depth-stimulus measurement is actually about: the
    separation a viewer's eyes are asked to fuse.  It equals the full-range
    parallax only when the layers span the whole ZDP range on one side of the
    reference plane.
    """
    widest = 0.0
    for row in stereo_offsets(layers, zdp_scale, field_dia, zdp_ref, zdp_unit):
        if row["zdepth_n"] is None:
            continue
        widest = max(widest, abs(row["dx_right"] - row["dx_left"]))
    return widest


# ── renderer-side conversion (NOT recorded in the file) ──────────────────────

def pixel_scale_arcsec(layer) -> Optional[float]:
    """Sky pixel scale of a layer in arcsec/px, or None if not deducible.

    Returns None rather than a guess when the layer carries no usable WCS -- a
    fabricated pixel scale would turn an honest absence into a false
    measurement.
    """
    wcs = getattr(layer, "wcs", None)
    if wcs is None:
        return None
    try:
        from astropy.wcs.utils import proj_plane_pixel_scales
        scales = proj_plane_pixel_scales(wcs.celestial)
        deg = float(sum(scales) / len(scales))
        if not math.isfinite(deg) or deg <= 0:
            return None
        return deg * 3600.0
    except Exception:
        return None


def to_display_pixels(dx: float, field_dia: float,
                      canvas_width_px: float) -> float:
    """Convert an offset in FITA_FDU units to display pixels.

    The ruling puts this conversion outside the file on purpose: it depends on
    how the field is being shown, which the file cannot know.  The mapping here
    is the simple one -- the field diameter spans ``canvas_width_px`` -- stated
    explicitly so a renderer that wants a different one can see what it is
    replacing.
    """
    if field_dia == 0:
        return 0.0
    return float(dx) / float(field_dia) * float(canvas_width_px)


# ── human-readable summary ───────────────────────────────────────────────────

def describe(layers: Iterable, zdp_scale: float, field_dia: float,
             field_unit: str = "", zdp_ref: float = 0.0,
             zdp_unit: Optional[str] = None) -> str:
    """Human-readable summary of the stereo geometry a file encodes.

    Reports the separation in FITA_FDU, never in pixels -- ruling S4.5.
    """
    layers = list(layers)
    rows = stereo_offsets(layers, zdp_scale, field_dia, zdp_ref, zdp_unit)
    depthed = [r for r in rows if r["zdepth_n"] is not None]
    u = str(field_unit or "").strip() or "?"

    full = (float(zdp_scale) / 100.0) * float(field_dia)
    lines = [
        "FITA_FDI = %.6g %s (field under study)" % (float(field_dia), u),
        "FITA_ZSC = %.3f %% of the field  ->  %.6g %s full-range parallax"
        % (float(zdp_scale), full, u),
        "FITA_ZRF = %.3f (ZDP at the screen plane)" % float(zdp_ref),
        "FITA_ZDU = %s" % (zdp_unit if zdp_unit else
                           "absent -- FITA_ZDP is dimensionless [0,1]"),
        "max separation = %.6g %s across %d layer(s) carrying depth"
        % (max_parallax(layers, zdp_scale, field_dia, zdp_ref, zdp_unit),
           u, len(depthed)),
    ]
    for r in rows:
        if r["zdepth_n"] is None:
            lines.append("  [%d] %-20s ZDP absent -> zero parallax"
                         % (r["layer_id"], r["name"][:20]))
            continue
        rel = r["zdepth_n"] - float(zdp_ref)
        where = "screen" if abs(rel) < 1e-9 else ("front" if rel > 0 else "behind")
        shown = ("ZDP=%.3f" % r["zdepth"] if zdp_unit is None
                 else "ZDP=%.6g %s (n=%.3f)" % (r["zdepth"], zdp_unit, r["zdepth_n"]))
        lines.append("  [%d] %-20s %s  dx = %+.4g / %+.4g %s (L/R)  %s"
                     % (r["layer_id"], r["name"][:20], shown,
                        r["dx_left"], r["dx_right"], u, where))
    return "\n".join(lines)
