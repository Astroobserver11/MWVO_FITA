"""
Flux encoding, range selection, and 32-bit → 16+16 split operations.

The key astrophysical constraint:
  The raw 32-bit float pixel value IS the calibrated energy flux in BUNIT.
  Display manipulations must never destroy that value; they only produce a
  derived alpha/transparency channel for compositing.
"""

import numpy as np
from typing import Literal, Tuple

StretchType = Literal["linear", "log", "sqrt", "asinh", "power"]


# ── The FLOAT32 ruling (P.I., 2026-11-14) ────────────────────────────────────

def require_float32_flux(flux, where: str = "") -> np.ndarray:
    """
    Enforce S6.1 -- FLUX is float32 under FLOAT32 packing -- by raising, not casting.

    ONE source of truth for all three writers. The first pass at this ruling put the
    check inline in `io.py` only, and the HDF5 and Zarr backends went on accepting
    float64: measured, both wrote it and both truncated it back to float32 on read,
    at a relative error of 3.3e-08, with two pixels held distinct on disk collapsing
    into one. Exactly the defect the ruling exists to close, surviving on the paths
    the fix had not reached. Hence a single shared gate rather than three copies.

    Raise rather than cast: losing calibrated precision must always be the caller's
    explicit decision, never a side effect of saving. Flag, don't mask.

    Byte order is not precision -- a big-endian '>f4' straight off a FITS read is
    float32 and passes, which is why this tests kind and itemsize rather than
    comparing against np.float32 directly.
    """
    arr = np.asarray(flux)
    if arr.dtype.kind != "f" or arr.dtype.itemsize != 4:
        raise ValueError(
            f"{where}FLUX must be float32 -- standard S6.1 requires BITPIX=-32 under "
            f"FITAPACK='FLOAT32' -- but got dtype {arr.dtype}. FITA will not downcast "
            f"the calibrated science datum silently. If the precision is expendable, "
            f"say so explicitly:\n"
            f"    layer.flux_data = layer.flux_data.astype('float32')\n"
            f"(FITALayer.from_array() does this for you, with a FITAPrecisionWarning.)"
        )
    return arr


# ── Flux-range extraction ────────────────────────────────────────────────────

def clip_flux(
    data: np.ndarray,
    flux_min: float,
    flux_max: float,
) -> np.ndarray:
    """Return data clipped to [flux_min, flux_max], NaN preserved."""
    out = np.where(np.isfinite(data), np.clip(data, flux_min, flux_max), np.nan)
    return out.astype(np.float32)


def normalise(
    data: np.ndarray,
    flux_min: float,
    flux_max: float,
) -> np.ndarray:
    """Map flux range linearly to [0, 1].  NaN → 0."""
    span = flux_max - flux_min
    if span == 0:
        return np.zeros_like(data, dtype=np.float32)
    normed = (data - flux_min) / span
    normed = np.nan_to_num(normed, nan=0.0)
    return np.clip(normed, 0.0, 1.0).astype(np.float32)


def stretch(
    normed: np.ndarray,
    mode: StretchType = "linear",
    asinh_a: float = 0.1,
    power_exp: float = 0.5,
) -> np.ndarray:
    """
    Apply a display stretch to a [0,1] normalised array.
    The result is still in [0,1] and is used ONLY for alpha derivation
    or display — the original flux array is never modified.
    """
    eps = 1e-9
    if mode == "linear":
        return normed
    elif mode == "log":
        return np.log10(normed * (10 - 1) + 1) / np.log10(10)
    elif mode == "sqrt":
        return np.sqrt(np.clip(normed, 0, None))
    elif mode == "asinh":
        return np.arcsinh(normed / asinh_a) / np.arcsinh(1.0 / asinh_a)
    elif mode == "power":
        return np.power(np.clip(normed, 0, None), power_exp)
    else:
        raise ValueError(f"Unknown stretch mode: {mode!r}")


# ── Luminance derivation ─────────────────────────────────────────────────────

def luminance_from_flux(
    data: np.ndarray,
    flux_min: float,
    flux_max: float,
    stretch_mode: StretchType = "asinh",
    **stretch_kw,
) -> np.ndarray:
    """
    Derive a [0,1] luminance map from the flux within the selected range.
    This is what gets written to the ALPHA extension.
    """
    normed = normalise(data, flux_min, flux_max)
    return stretch(normed, mode=stretch_mode, **stretch_kw)


def luminance_to_alpha16(lum: np.ndarray) -> np.ndarray:
    """Convert [0,1] luminance to uint16 alpha (0-65535)."""
    return (np.clip(lum, 0.0, 1.0) * 65535).round().astype(np.uint16)


# ── 32-bit → 16+16 split ────────────────────────────────────────────────────

def encode_split16(
    flux32: np.ndarray,
    flux_min: float,
    flux_max: float,
    stretch_mode: StretchType = "asinh",
    **stretch_kw,
) -> Tuple[np.ndarray, np.ndarray, float, float]:
    """
    Encode a 32-bit flux plane into two uint16 planes:
      flux16  — linear-scaled flux (recoverable via BSCALE/BZERO)
      alpha16 — stretched luminance transparency

    Returns (flux16, alpha16, bscale, bzero) where
        physical_flux ≈ flux16 * bscale + bzero
    """
    span = flux_max - flux_min
    if span == 0:
        span = 1.0
    bscale = span / 65535.0
    bzero  = flux_min

    normed = normalise(flux32, flux_min, flux_max)
    flux16 = (normed * 65535).round().astype(np.uint16)

    lum    = stretch(normed, mode=stretch_mode, **stretch_kw)
    alpha16 = luminance_to_alpha16(lum)

    return flux16, alpha16, bscale, bzero


def decode_split16(
    flux16: np.ndarray,
    bscale: float,
    bzero: float,
) -> np.ndarray:
    """Recover approximate physical flux from a split-16 flux plane."""
    return flux16.astype(np.float32) * bscale + bzero


# ── Auto flux-range detection ────────────────────────────────────────────────

def auto_range(
    data: np.ndarray,
    low_percentile: float = 0.5,
    high_percentile: float = 99.5,
) -> Tuple[float, float]:
    """
    Robust flux range ignoring NaN/Inf.
    Returns (flux_min, flux_max) suitable for display and alpha encoding.
    """
    finite = data[np.isfinite(data)]
    if finite.size == 0:
        return 0.0, 1.0
    lo = float(np.percentile(finite, low_percentile))
    hi = float(np.percentile(finite, high_percentile))
    if hi <= lo:
        hi = lo + 1.0
    return lo, hi


# ── Per-slice flux statistics ────────────────────────────────────────────────

def flux_stats(data: np.ndarray) -> dict:
    """Return a dict of basic flux statistics for header keywords."""
    finite = data[np.isfinite(data)]
    if finite.size == 0:
        return {"min": 0, "max": 0, "mean": 0, "median": 0, "std": 0, "npix": 0}
    return {
        "min":    float(finite.min()),
        "max":    float(finite.max()),
        "mean":   float(finite.mean()),
        "median": float(np.median(finite)),
        "std":    float(finite.std()),
        "npix":   int(finite.size),
    }
