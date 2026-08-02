"""
FITALayer — a single slice/layer of a FITA data cube.

Each layer holds:
  - flux_data  : 2-D float32 array (the calibrated astrophysical flux)
  - alpha_data : 2-D uint16 array  (transparency mask derived from flux luminance)
  - wcs        : astropy.wcs.WCS   (2-D sky coordinates; may be None)
  - metadata   : dict of header keywords
"""

from __future__ import annotations
import numpy as np
from dataclasses import dataclass, field
from typing import Optional, Tuple

from .spec import (
    BLEND_NORMAL, PACK_FLOAT32,
    KW_LAYER_ID, KW_LAYER_NAME, KW_BLEND_MODE, KW_OPACITY,
    KW_FLUX_MIN, KW_FLUX_MAX, KW_WAVE_CVAL, KW_WAVE_BWID,
    KW_XOFFSET, KW_YOFFSET, KW_ALPHA_SRC, KW_DEPTH, KW_VISIBLE,
)
from .flux import luminance_from_flux, luminance_to_alpha16, auto_range, flux_stats


@dataclass
class FITALayer:
    flux_data:   np.ndarray                    # float32, shape (H, W)
    alpha_data:  Optional[np.ndarray] = None   # uint16,  shape (H, W) or None
    layer_id:    int   = 1
    name:        str   = ""
    blend_mode:  str   = BLEND_NORMAL
    opacity:     float = 1.0
    xoffset:     float = 0.0
    yoffset:     float = 0.0
    flux_min:    Optional[float] = None
    flux_max:    Optional[float] = None
    wave_cval:   Optional[float] = None   # metres
    wave_bwid:   Optional[float] = None   # metres
    alpha_src:   str   = "LUM"            # 'LUM'|'USER'|'NONE'
    visible:     bool  = True
    zdepth:      Optional[float] = None   # 0.0=background, 1.0=foreground; stereo parallax weight
    wcs:         object = field(default=None, repr=False)
    extra_header: dict  = field(default_factory=dict, repr=False)
    uncert_data: Optional[np.ndarray] = field(default=None, repr=False)  # float32 uncertainty map
    mask_data:   Optional[np.ndarray] = field(default=None, repr=False)  # uint8 quality/mask bits

    # ── Construction helpers ──────────────────────────────────────────────────

    @classmethod
    def from_array(
        cls,
        data: np.ndarray,
        layer_id: int = 1,
        name: str = "",
        flux_min: Optional[float] = None,
        flux_max: Optional[float] = None,
        stretch_mode: str = "asinh",
        blend_mode: str = BLEND_NORMAL,
        opacity: float = 1.0,
        xoffset: float = 0.0,
        yoffset: float = 0.0,
        wave_cval: Optional[float] = None,
        wave_bwid: Optional[float] = None,
        wcs=None,
        **kw,
    ) -> "FITALayer":
        """Create a FITALayer from a raw numpy array, computing alpha from flux."""
        flux = np.asarray(data, dtype=np.float32)
        if flux_min is None or flux_max is None:
            lo, hi = auto_range(flux)
            flux_min = flux_min if flux_min is not None else lo
            flux_max = flux_max if flux_max is not None else hi

        lum   = luminance_from_flux(flux, flux_min, flux_max, stretch_mode)
        alpha = luminance_to_alpha16(lum)

        return cls(
            flux_data=flux, alpha_data=alpha,
            layer_id=layer_id, name=name or f"Layer {layer_id}",
            blend_mode=blend_mode, opacity=opacity,
            xoffset=xoffset, yoffset=yoffset,
            flux_min=float(flux_min), flux_max=float(flux_max),
            wave_cval=wave_cval, wave_bwid=wave_bwid,
            alpha_src="LUM", wcs=wcs, **kw,
        )

    # ── Properties ────────────────────────────────────────────────────────────

    @property
    def shape(self) -> Tuple[int, int]:
        return self.flux_data.shape[-2], self.flux_data.shape[-1]

    @property
    def alpha_float(self) -> np.ndarray:
        """Alpha as float32 [0,1] for compositing."""
        if self.alpha_data is None:
            return np.ones(self.shape, dtype=np.float32)
        return self.alpha_data.astype(np.float32) / 65535.0

    @property
    def stats(self) -> dict:
        return flux_stats(self.flux_data)

    # ── Flux range operations ─────────────────────────────────────────────────

    def recompute_alpha(
        self,
        flux_min: Optional[float] = None,
        flux_max: Optional[float] = None,
        stretch_mode: str = "asinh",
        **kw,
    ) -> None:
        """Recompute alpha from a new flux range without touching flux_data."""
        fmin = flux_min if flux_min is not None else self.flux_min
        fmax = flux_max if flux_max is not None else self.flux_max
        if fmin is None or fmax is None:
            fmin, fmax = auto_range(self.flux_data)
        self.flux_min = float(fmin)
        self.flux_max = float(fmax)
        lum = luminance_from_flux(self.flux_data, fmin, fmax, stretch_mode, **kw)
        self.alpha_data = luminance_to_alpha16(lum)
        self.alpha_src = "LUM"

    def set_user_alpha(self, alpha: np.ndarray) -> None:
        """Override alpha with a user-supplied mask (uint16 or float [0,1])."""
        if alpha.dtype in (np.float32, np.float64):
            self.alpha_data = luminance_to_alpha16(np.clip(alpha, 0, 1))
        else:
            self.alpha_data = alpha.astype(np.uint16)
        self.alpha_src = "USER"

    # ── Header serialisation ──────────────────────────────────────────────────

    def to_header_dict(self) -> dict:
        d = {
            KW_LAYER_ID:   self.layer_id,
            KW_LAYER_NAME: self.name[:68],
            KW_BLEND_MODE: self.blend_mode,
            KW_OPACITY:    self.opacity,
            KW_XOFFSET:    self.xoffset,
            KW_YOFFSET:    self.yoffset,
            KW_ALPHA_SRC:  self.alpha_src,
            KW_VISIBLE:    self.visible,
        }
        if self.flux_min is not None:
            d[KW_FLUX_MIN] = self.flux_min
        if self.flux_max is not None:
            d[KW_FLUX_MAX] = self.flux_max
        if self.wave_cval is not None:
            d[KW_WAVE_CVAL] = self.wave_cval
        if self.wave_bwid is not None:
            d[KW_WAVE_BWID] = self.wave_bwid
        if self.zdepth is not None:
            d[KW_DEPTH] = float(self.zdepth)
        d.update(self.extra_header)
        return d
