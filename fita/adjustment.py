"""
FITA adjustment layers — non-destructive display transforms.

Adjustment layers modify how flux data is *displayed* without altering the
calibrated flux values.  They are stored in the FITA_ADJ BINTABLE and
applied at composite time.

The key astrophysical invariant:
  No adjustment layer ever modifies layer.flux_data.
  Only the derived display normalisation and alpha are affected.

Available adjustments:
  LEVELS      — input black/white/gamma + output remap
  CURVES      — RGB tone curve (piecewise linear)
  BRIGHTNESS  — brightness + contrast
  HUESAT      — hue / saturation / lightness
  FXSTRETCH   — astrophysical stretch (log/sqrt/asinh/linear/power)
  BANDMAP     — assign wavelength bands to RGB display channels
  FXNORM      — normalise by instrument response curve
"""

from __future__ import annotations
import json
import numpy as np
from dataclasses import dataclass, field, fields as dataclass_fields
from typing import Any, Callable, Dict, List, Optional, Tuple

from .spec import (
    ADJ_LEVELS, ADJ_CURVES, ADJ_BRIGHTNESS, ADJ_HUE_SAT,
    ADJ_FLUX_STRETCH, ADJ_BANDMAP, ADJ_FLUX_NORM,
)


# ── Base ──────────────────────────────────────────────────────────────────────

@dataclass
class AdjustmentLayer:
    adj_type:  str  = field(default="")
    enabled:   bool = True
    name:      str  = ""
    params:    dict = field(default_factory=dict)

    def apply(self, data: np.ndarray) -> np.ndarray:
        """Apply this adjustment to a float32 [0,1] display array."""
        raise NotImplementedError

    # ── serialisation (D-3) ──────────────────────────────────────────────
    # The type-specific state of every adjustment lives in typed dataclass
    # fields (in_black, gamma, stretch_mode, ...), NOT in the inherited
    # `params` dict -- no subclass ever writes to `params`.  Deriving the
    # parameters by field introspection therefore captures the real state,
    # and any adjustment class added later serialises without further work.

    def to_params(self) -> Dict[str, Any]:
        """Type-specific parameters of this adjustment, JSON-ready."""
        base = {f.name for f in dataclass_fields(AdjustmentLayer)}
        out: Dict[str, Any] = {}
        for f in dataclass_fields(self):
            if f.name in base:
                continue
            out[f.name] = _encode(getattr(self, f.name))
        if self.params:                      # anything a caller stashed by hand
            out.setdefault("_extra", _encode(self.params))
        return out

    @classmethod
    def from_params(cls, params: Dict[str, Any], *, enabled: bool = True,
                    name: str = "") -> "AdjustmentLayer":
        """Rebuild an adjustment of this class from `to_params()` output."""
        known = {f.name for f in dataclass_fields(cls)}
        extra = params.pop("_extra", None) if isinstance(params, dict) else None
        kwargs = {k: _decode(v) for k, v in (params or {}).items() if k in known}
        obj = cls(**kwargs)
        obj.enabled = bool(enabled)
        obj.name = name
        if extra:
            obj.params = _decode(extra)
        return obj


# ── JSON encoding helpers ────────────────────────────────────────────────────
# numpy arrays (instrument response curves, wavelength grids) have no JSON
# representation, so they are tagged on the way out and restored on the way
# back.  Silently dropping them -- or silently returning a list where an array
# was stored -- is how "it round-trips" claims stop being true.

_NDARRAY_TAG = "__ndarray__"


def _encode(value):
    if isinstance(value, np.ndarray):
        return {_NDARRAY_TAG: value.tolist()}
    if isinstance(value, (np.floating, np.integer)):
        return value.item()
    if isinstance(value, tuple):
        return [_encode(v) for v in value]
    if isinstance(value, list):
        return [_encode(v) for v in value]
    if isinstance(value, dict):
        return {k: _encode(v) for k, v in value.items()}
    return value


def _decode(value):
    if isinstance(value, dict):
        if _NDARRAY_TAG in value:
            return np.asarray(value[_NDARRAY_TAG], dtype=np.float64)
        return {k: _decode(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_decode(v) for v in value]
    return value


# ── Levels ────────────────────────────────────────────────────────────────────

@dataclass
class LevelsAdjustment(AdjustmentLayer):
    """
    Remap input [in_black, in_white] → gamma → output [out_black, out_white].
    Identical to Photoshop Image > Adjustments > Levels.
    """
    in_black:   float = 0.0
    in_white:   float = 1.0
    gamma:      float = 1.0
    out_black:  float = 0.0
    out_white:  float = 1.0

    def __post_init__(self):
        self.adj_type = ADJ_LEVELS

    def apply(self, data: np.ndarray) -> np.ndarray:
        span = max(self.in_white - self.in_black, 1e-9)
        d = np.clip((data - self.in_black) / span, 0.0, 1.0)
        if self.gamma != 1.0:
            d = np.power(d, 1.0 / max(self.gamma, 1e-9))
        out_span = self.out_white - self.out_black
        return np.clip(d * out_span + self.out_black, 0.0, 1.0)


# ── Curves ────────────────────────────────────────────────────────────────────

@dataclass
class CurvesAdjustment(AdjustmentLayer):
    """
    Piecewise-linear tone curve.
    control_points: list of (input, output) pairs in [0,1]×[0,1], sorted by input.
    """
    control_points: List[Tuple[float, float]] = field(
        default_factory=lambda: [(0.0, 0.0), (1.0, 1.0)]
    )

    def __post_init__(self):
        self.adj_type = ADJ_CURVES
        # JSON has no tuple type, so a round-tripped curve comes back as a
        # list of 2-element lists.  Normalise here so the in-memory form is
        # the same whether the curve was authored or loaded.
        self.control_points = [tuple(p) for p in self.control_points]

    def apply(self, data: np.ndarray) -> np.ndarray:
        pts = sorted(self.control_points)
        xs  = np.array([p[0] for p in pts])
        ys  = np.array([p[1] for p in pts])
        return np.clip(np.interp(data, xs, ys), 0.0, 1.0).astype(np.float32)


# ── Brightness / Contrast ─────────────────────────────────────────────────────

@dataclass
class BrightnessAdjustment(AdjustmentLayer):
    """Photoshop-style brightness (-1 to +1) and contrast (-1 to +1)."""
    brightness: float = 0.0
    contrast:   float = 0.0

    def __post_init__(self):
        self.adj_type = ADJ_BRIGHTNESS

    def apply(self, data: np.ndarray) -> np.ndarray:
        b = self.brightness
        c = self.contrast
        # contrast: slope through 0.5
        slope = np.tan((c + 1) * np.pi / 4) if c < 1.0 else 1e6
        d = (data - 0.5) * slope + 0.5
        d = d + b
        return np.clip(d, 0.0, 1.0).astype(np.float32)


# ── Astrophysical stretch ─────────────────────────────────────────────────────

@dataclass
class FluxStretchAdjustment(AdjustmentLayer):
    """
    Re-apply an astrophysical stretch to the display normalisation.
    This does NOT change flux_data — it changes only the display mapping.

    stretch_mode: 'linear' | 'log' | 'sqrt' | 'asinh' | 'power'
    asinh_a:  controls the linear/non-linear transition for asinh stretch
    power_exp: exponent for power-law stretch
    """
    stretch_mode: str   = "asinh"
    asinh_a:      float = 0.1
    power_exp:    float = 0.5

    def __post_init__(self):
        self.adj_type = ADJ_FLUX_STRETCH

    def apply(self, data: np.ndarray) -> np.ndarray:
        from .flux import stretch as _stretch
        return _stretch(
            data,
            mode=self.stretch_mode,
            asinh_a=self.asinh_a,
            power_exp=self.power_exp,
        )


# ── Band mapping ──────────────────────────────────────────────────────────────

@dataclass
class BandMapAdjustment(AdjustmentLayer):
    """
    Assign a wavelength-indexed layer to an RGB display channel.
    Used to build false-colour bolometric SEDs.

    channel: 'R' | 'G' | 'B'
    layer_id: which FITA layer provides the signal for this channel
    """
    channel:  str = "R"
    layer_id: int = 1

    def __post_init__(self):
        self.adj_type = ADJ_BANDMAP

    def apply(self, data: np.ndarray) -> np.ndarray:
        return data  # handled at cube composite level


# ── Flux normalisation ────────────────────────────────────────────────────────

@dataclass
class FluxNormAdjustment(AdjustmentLayer):
    """
    Divide each pixel by an instrument response / effective area curve to
    convert detector counts to physical flux density (Jy or erg/s/cm²/Hz).

    response_curve: 1-D array of relative response values, one per wavelength
    wavelengths:    corresponding wavelength values (metres)
    """
    response_curve: Optional[np.ndarray] = None
    wavelengths:    Optional[np.ndarray] = None
    wave_cval:      float = 0.0

    def __post_init__(self):
        self.adj_type = ADJ_FLUX_NORM

    def apply(self, data: np.ndarray) -> np.ndarray:
        if self.response_curve is None or self.wavelengths is None:
            return data
        resp = float(np.interp(self.wave_cval, self.wavelengths, self.response_curve,
                               left=1.0, right=1.0))
        if resp == 0:
            return data
        return np.clip(data / resp, 0.0, None).astype(np.float32)


# ── Adjustment stack ──────────────────────────────────────────────────────────

class AdjustmentStack:
    """Ordered list of adjustment layers applied in sequence."""

    def __init__(self, adjustments: Optional[List[AdjustmentLayer]] = None):
        self.adjustments: List[AdjustmentLayer] = adjustments or []

    def add(self, adj: AdjustmentLayer) -> None:
        self.adjustments.append(adj)

    def apply(self, data: np.ndarray) -> np.ndarray:
        for adj in self.adjustments:
            if adj.enabled:
                data = adj.apply(data)
        return data

    def to_records(self) -> List[dict]:
        """One serialisable record per adjustment, in application order.

        Until D-3 this emitted ``a.params`` -- a dict no subclass ever writes
        to -- so every record carried an empty parameter set and a round trip
        silently restored default adjustments.  It now emits the real
        type-specific state via ``to_params()``.
        """
        return [
            {"order": i,
             "type": a.adj_type,
             "enabled": bool(a.enabled),
             "name": a.name or "",
             "layer_id": int(getattr(a, "layer_id", 0) or 0),
             "params": a.to_params()}
            for i, a in enumerate(self.adjustments)
        ]

    @classmethod
    def from_records(cls, records: List[dict]) -> "AdjustmentStack":
        """Rebuild a stack from ``to_records()`` output, preserving order."""
        stack = cls()
        for rec in sorted(records, key=lambda r: r.get("order", 0)):
            adj_type = str(rec.get("type", "")).strip()
            klass = ADJ_REGISTRY.get(adj_type)
            if klass is None:
                raise ValueError(
                    "unknown adjustment type %r in FITA_ADJ; known types: %s"
                    % (adj_type, ", ".join(sorted(ADJ_REGISTRY)))
                )
            params = rec.get("params") or {}
            if isinstance(params, str):
                params = json.loads(params) if params.strip() else {}
            stack.add(klass.from_params(dict(params),
                                        enabled=rec.get("enabled", True),
                                        name=rec.get("name", "")))
        return stack


# ── type registry ────────────────────────────────────────────────────────────
# Maps the FITA_ADJ ADJ_TYPE code back to the class that implements it.  A
# reader encountering an unknown code MUST raise rather than silently drop the
# adjustment (the same rule S8.1 sets for unknown blend modes) -- a display
# stack that quietly loses a step is worse than one that refuses to load.

ADJ_REGISTRY: Dict[str, type] = {
    ADJ_LEVELS:       LevelsAdjustment,
    ADJ_CURVES:       CurvesAdjustment,
    ADJ_BRIGHTNESS:   BrightnessAdjustment,
    ADJ_FLUX_STRETCH: FluxStretchAdjustment,
    ADJ_BANDMAP:      BandMapAdjustment,
    ADJ_FLUX_NORM:    FluxNormAdjustment,
}
