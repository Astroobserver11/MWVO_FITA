"""
Photoshop / GIMP compatible blend-mode compositing for FITA layers.

All operations work on float32 arrays normalised to [0, 1].
Each function takes (base, blend) and returns the composited result.
Alpha premultiplication is handled externally by FITACube.composite().

Astrophysical note
------------------
The 'LUM' (Luminosity) blend mode is the canonical choice for multi-band
compositing because it lets you map flux → displayed brightness while a
separate colour layer (e.g. an RGB false-colour or optical image) provides
hue/chroma without corrupting the energy-density calibration.
"""

import numpy as np
from typing import Callable, Dict
from .spec import (
    BLEND_NORMAL, BLEND_SCREEN, BLEND_MULTIPLY, BLEND_ADD,
    BLEND_OVERLAY, BLEND_SOFT, BLEND_HARD, BLEND_DODGE, BLEND_BURN,
    BLEND_DIFF, BLEND_LUMINOSITY, BLEND_COLOR, BLEND_HUE, BLEND_SAT,
)


def _rgb_to_hsl(r, g, b):
    maxc = np.maximum(np.maximum(r, g), b)
    minc = np.minimum(np.minimum(r, g), b)
    l = (maxc + minc) / 2.0
    span = maxc - minc
    eps = 1e-9

    s = np.where(
        span < eps, 0.0,
        np.where(l < 0.5, span / (maxc + minc + eps), span / (2.0 - maxc - minc + eps))
    )

    h = np.zeros_like(r)
    h = np.where((maxc == r) & (span > eps), (g - b) / (span + eps) % 6, h)
    h = np.where((maxc == g) & (span > eps), (b - r) / (span + eps) + 2, h)
    h = np.where((maxc == b) & (span > eps), (r - g) / (span + eps) + 4, h)
    h = h / 6.0
    return h, s, l


def _hsl_to_rgb(h, s, l):
    def f(n, h, s, l):
        k = (n + h * 12) % 12
        a = s * np.minimum(l, 1.0 - l)
        return l - a * np.clip(np.minimum(k - 3, 9 - k), -1, 1)
    r = f(0, h, s, l)
    g = f(8, h, s, l)
    b = f(4, h, s, l)
    return r, g, b


def _luminance(r, g, b):
    # ITU-R BT.709 coefficients
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


# ── Primitive blend functions ─────────────────────────────────────────────────

def blend_normal(base, blend):
    return blend

def blend_screen(base, blend):
    return 1.0 - (1.0 - base) * (1.0 - blend)

def blend_multiply(base, blend):
    return base * blend

def blend_add(base, blend):
    return np.clip(base + blend, 0.0, 1.0)

def blend_overlay(base, blend):
    return np.where(
        base < 0.5,
        2.0 * base * blend,
        1.0 - 2.0 * (1.0 - base) * (1.0 - blend),
    )

def blend_soft_light(base, blend):
    return np.where(
        blend <= 0.5,
        base - (1.0 - 2.0 * blend) * base * (1.0 - base),
        base + (2.0 * blend - 1.0) * (
            np.where(base <= 0.25,
                     ((16.0 * base - 12.0) * base + 4.0) * base,
                     np.sqrt(np.clip(base, 0, None))) - base
        ),
    )

def blend_hard_light(base, blend):
    return blend_overlay(blend, base)

def blend_color_dodge(base, blend):
    denom = np.clip(1.0 - blend, 1e-9, None)
    return np.clip(base / denom, 0.0, 1.0)

def blend_color_burn(base, blend):
    denom = np.clip(blend, 1e-9, None)
    return np.clip(1.0 - (1.0 - base) / denom, 0.0, 1.0)

def blend_difference(base, blend):
    return np.abs(base - blend)


# ── HSL component blend modes ────────────────────────────────────────────────
# These require 3-channel (RGB) arrays.  For single-channel data,
# they are applied as luminosity-only.

def blend_luminosity(base_rgb, blend_rgb):
    """Keep base hue+saturation, take blend luminosity — key astro mode."""
    bh, bs, _ = _rgb_to_hsl(*[base_rgb[..., i] for i in range(3)])
    _, _, bl   = _rgb_to_hsl(*[blend_rgb[..., i] for i in range(3)])
    r, g, b = _hsl_to_rgb(bh, bs, bl)
    return np.stack([r, g, b], axis=-1)

def blend_color(base_rgb, blend_rgb):
    """Apply blend hue+saturation to base luminosity — false-colour over flux."""
    _, _, bl   = _rgb_to_hsl(*[base_rgb[..., i] for i in range(3)])
    bh, bs, _ = _rgb_to_hsl(*[blend_rgb[..., i] for i in range(3)])
    r, g, b = _hsl_to_rgb(bh, bs, bl)
    return np.stack([r, g, b], axis=-1)

def blend_hue(base_rgb, blend_rgb):
    bh, bs, bl = _rgb_to_hsl(*[base_rgb[..., i] for i in range(3)])
    nh, _, _   = _rgb_to_hsl(*[blend_rgb[..., i] for i in range(3)])
    r, g, b = _hsl_to_rgb(nh, bs, bl)
    return np.stack([r, g, b], axis=-1)

def blend_saturation(base_rgb, blend_rgb):
    bh, bs, bl = _rgb_to_hsl(*[base_rgb[..., i] for i in range(3)])
    _, ns, _   = _rgb_to_hsl(*[blend_rgb[..., i] for i in range(3)])
    r, g, b = _hsl_to_rgb(bh, ns, bl)
    return np.stack([r, g, b], axis=-1)


# ── Dispatch table ────────────────────────────────────────────────────────────

SCALAR_BLENDS: Dict[str, Callable] = {
    BLEND_NORMAL:   blend_normal,
    BLEND_SCREEN:   blend_screen,
    BLEND_MULTIPLY: blend_multiply,
    BLEND_ADD:      blend_add,
    BLEND_OVERLAY:  blend_overlay,
    BLEND_SOFT:     blend_soft_light,
    BLEND_HARD:     blend_hard_light,
    BLEND_DODGE:    blend_color_dodge,
    BLEND_BURN:     blend_color_burn,
    BLEND_DIFF:     blend_difference,
}

HSL_BLENDS: Dict[str, Callable] = {
    BLEND_LUMINOSITY: blend_luminosity,
    BLEND_COLOR:      blend_color,
    BLEND_HUE:        blend_hue,
    BLEND_SAT:        blend_saturation,
}


def composite(
    base: np.ndarray,
    blend_layer: np.ndarray,
    alpha: np.ndarray,
    opacity: float,
    mode: str,
) -> np.ndarray:
    """
    Alpha-composite blend_layer over base.

    base, blend_layer : float32, shape (H,W) or (H,W,C)
    alpha             : float32, shape (H,W), range [0,1]
    opacity           : scalar float [0,1]
    mode              : blend mode code string
    """
    eff_alpha = np.clip(alpha * opacity, 0.0, 1.0)

    if mode in SCALAR_BLENDS:
        fn = SCALAR_BLENDS[mode]
        blended = fn(base, blend_layer)
    elif mode in HSL_BLENDS:
        fn = HSL_BLENDS[mode]
        if base.ndim == 2:
            # promote single-channel to 3-channel grey for HSL ops
            b3 = np.stack([base, base, base], axis=-1)
            bl3 = np.stack([blend_layer, blend_layer, blend_layer], axis=-1)
            blended = fn(b3, bl3)[..., 0]
        else:
            blended = fn(base, blend_layer)
    else:
        raise ValueError(f"Unknown blend mode: {mode!r}")

    if base.ndim == 3:
        eff_alpha = eff_alpha[..., np.newaxis]

    return base * (1.0 - eff_alpha) + blended * eff_alpha
