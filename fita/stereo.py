"""
fita.stereo -- phased stereography: turning FITA_ZDP into measured parallax.

FITA_ZDP (S8.2) assigns each layer a depth in [0,1] that encodes *physical ISM
penetration depth* rather than an arbitrary stacking order: 21 cm H I at 0.0,
H-alpha at 0.5, X-ray hot plasma at 1.0.  A stereo renderer turns that into a
differential horizontal offset between two eye views.

The standard deliberately declines to fix the ZDP -> pixel mapping, because it
belongs to a rendering job and not to a file.  That left a gap: a rendered pair
carried no record of the separation it was built with, so the stimulus could
not be measured after the fact.  Decision D-6 closes it with an OPTIONAL
FITA_ZSC keyword, and this module is the executable statement of what that
keyword means -- a convention documented only in prose drifts from the code
that implements it.

    FITA_ZSC = total horizontal parallax in pixels across the full ZDP range
    FITA_ZRF = the ZDP value placed at zero parallax (the screen plane)
    dx(layer) = +/- (FITA_ZSC / 2) * (ZDP - FITA_ZRF)   (left -, right +)

The reference plane matters because without it the depth budget is always
spent in one direction: everything sits at or in front of the screen.  With
FITA_ZRF = 0.5 the H-alpha layer sits at the screen, HI recedes behind it and
X-ray plasma comes forward.

FITA_ZAN carries the angular measure.  Author ruling Q2: a bare pixel count
satisfies the real->model metric chain ONLY when a complete model is missing;
otherwise an angular measure is required, UNLESS it can be deduced from
context.  A layer WCS is that context, and `angular_parallax()` performs the
deduction -- which is the point of putting it in code rather than prose.

Nothing here touches FLUX_*: stereo separation is display geometry (S5.2).
"""

from __future__ import annotations

import math
from typing import Dict, Iterable, List, Optional, Tuple

LEFT = "L"
RIGHT = "R"


def eye_offset(zdepth: Optional[float], zdp_scale: float, eye: str = LEFT,
               zdp_ref: float = 0.0) -> float:
    """Horizontal offset in pixels for one layer in one eye view.

    A layer with no depth assignment (zdepth is None -- absence is encoded by
    omission, per D-5) sits at zero parallax rather than being guessed at.
    """
    if zdepth is None:
        return 0.0
    sign = -1.0 if str(eye).upper().startswith("L") else +1.0
    return sign * (float(zdp_scale) / 2.0) * (float(zdepth) - float(zdp_ref))


def stereo_offsets(layers: Iterable, zdp_scale: float,
                   zdp_ref: float = 0.0) -> List[Dict[str, float]]:
    """Per-layer (left, right) pixel offsets for a stereo pair.

    Returns one record per layer so a renderer can composite each eye view by
    shifting layers horizontally, and so a reviewer can read back exactly what
    separation was applied.
    """
    out: List[Dict[str, float]] = []
    for layer in layers:
        z = getattr(layer, "zdepth", None)
        out.append({
            "layer_id": int(getattr(layer, "layer_id", 0) or 0),
            "name": str(getattr(layer, "name", "") or ""),
            "zdepth": None if z is None else float(z),
            "dx_left": eye_offset(z, zdp_scale, LEFT, zdp_ref),
            "dx_right": eye_offset(z, zdp_scale, RIGHT, zdp_ref),
        })
    return out


def max_parallax(layers: Iterable, zdp_scale: float,
                 zdp_ref: float = 0.0) -> float:
    """Largest left-right separation, in pixels, across the layer set.

    This is the number a depth-stimulus measurement is actually about: the
    separation a viewer's eyes are asked to fuse.  It equals |FITA_ZSC| only
    when the layers span the full ZDP range on one side of the reference
    plane.
    """
    widest = 0.0
    for layer in layers:
        z = getattr(layer, "zdepth", None)
        if z is None:
            continue
        sep = abs(eye_offset(z, zdp_scale, RIGHT, zdp_ref)
                  - eye_offset(z, zdp_scale, LEFT, zdp_ref))
        widest = max(widest, sep)
    return widest


# ── angular measure (author ruling Q2) ───────────────────────────────────────

def pixel_scale_arcsec(layer) -> Optional[float]:
    """Sky pixel scale of a layer in arcsec/px, or None if not deducible.

    This is the "context" the ruling refers to.  Returns None rather than a
    guess when the layer carries no usable WCS -- a fabricated pixel scale
    would turn an honest absence into a false angular measurement.
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


def angular_parallax(layers: Iterable, zdp_scale: float) -> Optional[float]:
    """Full-range parallax as a sky angle in arcsec, deduced from a WCS.

    Returns None when no layer supplies a usable pixel scale, which is exactly
    the case in which FITA_ZAN must be written explicitly: the angle cannot be
    deduced from context, so a pixel count alone would be an incomplete model.
    """
    for layer in layers:
        scale = pixel_scale_arcsec(layer)
        if scale is not None:
            return abs(float(zdp_scale)) * scale
    return None


def describe(layers: Iterable, zdp_scale: float, zdp_ref: float = 0.0,
             zdp_angular: Optional[float] = None) -> str:
    """Human-readable summary of the stereo geometry a file encodes."""
    layers = list(layers)
    rows = stereo_offsets(layers, zdp_scale, zdp_ref)
    depthed = [r for r in rows if r["zdepth"] is not None]

    if zdp_angular is None:
        deduced = angular_parallax(layers, zdp_scale)
        angle = ("%.3f arcsec (deduced from WCS)" % deduced
                 if deduced is not None
                 else "NOT RECORDED and not deducible -- pixel-only model")
    else:
        angle = "%.3f arcsec (recorded)" % float(zdp_angular)

    lines = [
        "FITA_ZSC = %.3f px (full-range parallax)" % float(zdp_scale),
        "FITA_ZRF = %.3f (ZDP at the screen plane)" % float(zdp_ref),
        "angular  = %s" % angle,
        "max separation = %.3f px across %d layer(s) carrying depth"
        % (max_parallax(layers, zdp_scale, zdp_ref), len(depthed)),
    ]
    for r in rows:
        if r["zdepth"] is None:
            lines.append("  [%d] %-20s ZDP absent -> zero parallax"
                         % (r["layer_id"], r["name"][:20]))
        else:
            rel = r["zdepth"] - float(zdp_ref)
            where = "screen" if abs(rel) < 1e-9 else ("front" if rel > 0 else "behind")
            lines.append("  [%d] %-20s ZDP=%.3f  dx = %+.2f / %+.2f px (L/R)  %s"
                         % (r["layer_id"], r["name"][:20], r["zdepth"],
                            r["dx_left"], r["dx_right"], where))
    return "\n".join(lines)
