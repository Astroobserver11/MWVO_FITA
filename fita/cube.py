"""
FITACube — the top-level container for a FITA multi-layer dataset.

A FITACube holds an ordered list of FITALayer objects and orchestrates:
  - flat compositing into a display image
  - flux-range re-selection across all layers
  - SED (spectral energy distribution) assembly
  - read/write delegation to fita.io
"""

from __future__ import annotations
from pathlib import Path
from typing import List, Optional, Tuple, Dict, Any
import numpy as np

from .layer import FITALayer
from .blend import composite
from .spec import PACK_FLOAT32
from .flux import auto_range


class FITACube:
    """
    Multi-layer multi-wavelength FITA data cube.

    Layers are ordered bottom-to-top (layer[0] is composited first).
    """

    def __init__(
        self,
        layers: Optional[List[FITALayer]] = None,
        canvas_w: Optional[int] = None,
        canvas_h: Optional[int] = None,
        bunit: str = "ct/s",
        meta: Optional[Dict[str, Any]] = None,
        adjustments=None,
    ):
        from .adjustment import AdjustmentStack
        self.layers: List[FITALayer] = layers or []
        self._canvas_w = canvas_w
        self._canvas_h = canvas_h
        self.bunit = bunit
        self.meta: Dict[str, Any] = meta or {}
        # Non-destructive display stack (S8/D-3).  Persisted as FITA_ADJ, so
        # hand-set display state survives a save/load cycle instead of being
        # rebuilt from memory each session.
        self.adjustments = adjustments if adjustments is not None else AdjustmentStack()

    # ── Canvas geometry ───────────────────────────────────────────────────────

    @property
    def canvas_w(self) -> int:
        if self._canvas_w:
            return self._canvas_w
        if not self.layers:
            return 0
        return max(
            int(l.xoffset + l.shape[1]) for l in self.layers
        )

    @property
    def canvas_h(self) -> int:
        if self._canvas_h:
            return self._canvas_h
        if not self.layers:
            return 0
        return max(
            int(l.yoffset + l.shape[0]) for l in self.layers
        )

    # ── Layer management ──────────────────────────────────────────────────────

    def add_layer(self, layer: FITALayer) -> None:
        layer.layer_id = len(self.layers) + 1
        self.layers.append(layer)

    def remove_layer(self, layer_id: int) -> None:
        self.layers = [l for l in self.layers if l.layer_id != layer_id]
        for i, l in enumerate(self.layers, start=1):
            l.layer_id = i

    def get_layer(self, layer_id: int) -> Optional[FITALayer]:
        for l in self.layers:
            if l.layer_id == layer_id:
                return l
        return None

    def reorder(self, id_order: List[int]) -> None:
        """Reorder layers by a list of layer_ids (bottom-to-top)."""
        lmap = {l.layer_id: l for l in self.layers}
        self.layers = [lmap[i] for i in id_order if i in lmap]
        for i, l in enumerate(self.layers, start=1):
            l.layer_id = i

    # ── Alpha re-selection ────────────────────────────────────────────────────

    def reselect_flux_range(
        self,
        flux_min: Optional[float] = None,
        flux_max: Optional[float] = None,
        stretch_mode: str = "asinh",
        layer_ids: Optional[List[int]] = None,
        **kw,
    ) -> None:
        """
        Re-derive alpha channels from a new flux range selection.
        Astrophysical flux data is untouched.

        layer_ids: if None, applies to all layers.
        """
        targets = self.layers if layer_ids is None else \
                  [l for l in self.layers if l.layer_id in (layer_ids or [])]
        for layer in targets:
            layer.recompute_alpha(flux_min, flux_max, stretch_mode, **kw)

    # ── Flat composite ────────────────────────────────────────────────────────

    def composite(
        self,
        canvas_w: Optional[int] = None,
        canvas_h: Optional[int] = None,
        background: float = 0.0,
    ) -> np.ndarray:
        """
        Composite all visible layers into a single float32 (H, W) image.

        Layers are placed at their (xoffset, yoffset) positions within the
        canvas.  Returns normalised [0,1] display image.
        """
        W = canvas_w or self.canvas_w
        H = canvas_h or self.canvas_h
        if W == 0 or H == 0:
            return np.full((1, 1), background, dtype=np.float32)

        result = np.full((H, W), background, dtype=np.float32)

        for layer in self.layers:
            if not layer.visible:
                continue

            flux   = layer.flux_data
            alpha  = layer.alpha_float

            lh, lw = layer.shape
            x0 = int(layer.xoffset)
            y0 = int(layer.yoffset)
            x1 = min(x0 + lw, W)
            y1 = min(y0 + lh, H)
            fx0 = max(0, -x0); fy0 = max(0, -y0)
            cx0 = max(0, x0);  cy0 = max(0, y0)

            if x1 <= 0 or y1 <= 0 or cx0 >= W or cy0 >= H:
                continue

            fx1 = fx0 + (x1 - cx0)
            fy1 = fy0 + (y1 - cy0)

            base_crop  = result[cy0:y1, cx0:x1]
            blend_crop = flux[fy0:fy1, fx0:fx1]
            alpha_crop = alpha[fy0:fy1, fx0:fx1]

            # normalise flux for display (NaN treated as 0)
            fmin = layer.flux_min if layer.flux_min is not None else float(np.nanmin(flux))
            fmax = layer.flux_max if layer.flux_max is not None else float(np.nanmax(flux))
            span = fmax - fmin or 1.0
            blend_norm = np.clip(
                np.nan_to_num((blend_crop - fmin) / span, nan=0.0), 0.0, 1.0
            )

            result[cy0:y1, cx0:x1] = composite(
                base_crop, blend_norm, alpha_crop,
                layer.opacity, layer.blend_mode
            )

        return result

    # ── SED assembly ──────────────────────────────────────────────────────────

    def sed(self, px: int, py: int) -> Tuple[np.ndarray, np.ndarray]:
        """
        Extract the spectral energy distribution at pixel (px, py).

        Returns (wavelengths, fluxes) arrays, sorted by wavelength.
        Layers without wave_cval are omitted.
        """
        waves, fluxes = [], []
        for layer in self.layers:
            if layer.wave_cval is None:
                continue
            lx = int(px - layer.xoffset)
            ly = int(py - layer.yoffset)
            lh, lw = layer.shape
            if 0 <= lx < lw and 0 <= ly < lh:
                waves.append(layer.wave_cval)
                fluxes.append(float(layer.flux_data[ly, lx]))

        if not waves:
            return np.array([]), np.array([])

        order = np.argsort(waves)
        return np.array(waves)[order], np.array(fluxes)[order]

    # ── I/O delegation ────────────────────────────────────────────────────────

    def save(
        self,
        path: str | Path,
        pack: str = PACK_FLOAT32,
        overwrite: bool = True,
        provenance=None,
    ) -> None:
        """Write this cube to a .fita file.

        provenance: optional ObsCore metadata (dict or BinTableHDU) emitted as
        the FITA_META HDU.  Required to reach FITA-FULL -- see io.write().

        The cube's adjustment stack is written automatically as FITA_ADJ when
        it is non-empty, so display state set by hand is preserved rather than
        discarded on save.
        """
        from .io import write
        adjustments = self.adjustments
        if adjustments is not None and not getattr(adjustments, "adjustments", None):
            adjustments = None          # nothing to write; omit the HDU
        write(
            path, self.layers,
            pack=pack,
            provenance=provenance,
            adjustments=adjustments,
            canvas_w=self._canvas_w,
            canvas_h=self._canvas_h,
            bunit=self.bunit,
            global_header=self.meta,
            overwrite=overwrite,
        )

    @classmethod
    def load(cls, path: str | Path) -> "FITACube":
        """Load a .fita file, including its FITA_ADJ display stack if present."""
        from .io import read, read_adjustments
        layers = read(path)
        return cls(layers=layers, adjustments=read_adjustments(path))

    @classmethod
    def from_fits_cube(
        cls,
        path: str | Path,
        flux_min: Optional[float] = None,
        flux_max: Optional[float] = None,
        stretch_mode: str = "asinh",
    ) -> "FITACube":
        from .io import from_fits_cube
        layers = from_fits_cube(path, flux_min, flux_max, stretch_mode)
        return cls(layers=layers)

    @classmethod
    def from_psd(
        cls,
        path: str | Path,
        flux_scale: float = 1.0,
        stretch_mode: str = "linear",
    ) -> "FITACube":
        from .psd_import import import_psd
        layers = import_psd(path, flux_scale=flux_scale, stretch_mode=stretch_mode)
        return cls(layers=layers)

    # ── Repr ──────────────────────────────────────────────────────────────────

    def __repr__(self) -> str:
        return (
            f"FITACube({len(self.layers)} layers, "
            f"canvas={self.canvas_w}x{self.canvas_h}, "
            f"bunit={self.bunit!r})"
        )
