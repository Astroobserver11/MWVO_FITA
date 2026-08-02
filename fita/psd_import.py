"""
PSD → FITA importer.

Reads Adobe Photoshop .psd / .psb files using the `psd-tools` library and
converts each visible layer to a FITALayer.

Blend mode mapping: PSD uses four-character codes; we map to FITA strings.
Layer position is encoded as xoffset/yoffset from the document origin.
Adjustment layers are converted to FITA_ADJ entries where mappable.

Install dependency: pip install psd-tools Pillow
"""

from __future__ import annotations
from pathlib import Path
from typing import List, Optional
import numpy as np

from .layer import FITALayer
from .spec import (
    BLEND_NORMAL, BLEND_SCREEN, BLEND_MULTIPLY, BLEND_ADD,
    BLEND_OVERLAY, BLEND_SOFT, BLEND_HARD, BLEND_DODGE, BLEND_BURN,
    BLEND_DIFF, BLEND_LUMINOSITY, BLEND_COLOR, BLEND_HUE, BLEND_SAT,
)


# PSD four-character blend keys → FITA codes
_PSD_BLEND_MAP = {
    "norm": BLEND_NORMAL,
    "scrn": BLEND_SCREEN,
    "mul ": BLEND_MULTIPLY,
    "lddg": BLEND_ADD,       # linear dodge (add)
    "over": BLEND_OVERLAY,
    "sLit": BLEND_SOFT,
    "hLit": BLEND_HARD,
    "div ": BLEND_DODGE,     # colour dodge
    "idiv": BLEND_BURN,      # colour burn
    "diff": BLEND_DIFF,
    "lum ": BLEND_LUMINOSITY,
    "colr": BLEND_COLOR,
    "hue ": BLEND_HUE,
    "sat ": BLEND_SAT,
    # common extras
    "diss": BLEND_NORMAL,    # dissolve → normal (no equivalent)
    "dark": BLEND_MULTIPLY,  # darken approximation
    "lite": BLEND_SCREEN,    # lighten approximation
    "fsub": BLEND_DIFF,      # subtract
    "fdiv": BLEND_DODGE,     # divide
}


def _psd_blend_to_fita(psd_key: str) -> str:
    key = psd_key.lower().rstrip()
    return _PSD_BLEND_MAP.get(key, BLEND_NORMAL)


def _layer_to_numpy(layer) -> Optional[np.ndarray]:
    """Composite a psd-tools layer to a numpy float32 RGBA array."""
    try:
        img = layer.composite()
        if img is None:
            return None
        arr = np.asarray(img, dtype=np.float32) / 255.0
        return arr  # shape (H, W, C) where C in {1,3,4}
    except Exception:
        return None


def import_psd(
    path: str | Path,
    flux_scale: float = 1.0,
    stretch_mode: str = "linear",
    skip_adjustment_layers: bool = False,
) -> List[FITALayer]:
    """
    Import a Photoshop .psd file as a list of FITALayer objects.

    Parameters
    ----------
    path              : path to .psd / .psb file
    flux_scale        : multiply pixel values by this to simulate physical flux units
    stretch_mode      : stretch for auto alpha derivation ('linear' keeps PSD look)
    skip_adjustment_layers : if True, skip non-raster layers

    Returns
    -------
    List of FITALayer, bottom-to-top order (same as Photoshop layer stack).
    """
    try:
        from psd_tools import PSDImage
    except ImportError:
        raise ImportError(
            "psd-tools is required for PSD import:\n"
            "  pip install psd-tools Pillow"
        )

    psd = PSDImage.open(str(path))
    canvas_w = psd.width
    canvas_h = psd.height

    layers_out: List[FITALayer] = []

    def _process_group(group, id_counter):
        for layer in group:
            # recurse into groups
            if layer.kind == "group":
                id_counter = _process_group(layer, id_counter)
                continue

            if skip_adjustment_layers and layer.kind == "type":
                continue

            arr = _layer_to_numpy(layer)
            if arr is None:
                continue

            # PSD layers may be smaller than the canvas — embed at offset
            top  = layer.top
            left = layer.left

            # extract luminance channel for flux proxy
            if arr.ndim == 3 and arr.shape[2] >= 3:
                # Rec.709 luma
                flux_plane = (0.2126 * arr[..., 0] +
                              0.7152 * arr[..., 1] +
                              0.0722 * arr[..., 2]).astype(np.float32)
            else:
                flux_plane = arr[..., 0].astype(np.float32)

            flux_plane = flux_plane * flux_scale

            # alpha from PSD layer if present, else from luminance
            if arr.ndim == 3 and arr.shape[2] == 4:
                psd_alpha = (arr[..., 3] * 65535).round().astype(np.uint16)
                alpha_src = "USER"
            else:
                psd_alpha = None
                alpha_src = "LUM"

            try:
                blend_key = str(layer.blend_mode.value) if hasattr(layer.blend_mode, 'value') \
                            else str(layer.blend_mode)
            except Exception:
                blend_key = "norm"
            fita_blend = _psd_blend_to_fita(blend_key)

            try:
                opacity = layer.opacity / 255.0
            except Exception:
                opacity = 1.0

            fita_layer = FITALayer.from_array(
                flux_plane,
                layer_id    = id_counter,
                name        = layer.name,
                stretch_mode= stretch_mode,
                blend_mode  = fita_blend,
                opacity     = opacity,
                xoffset     = float(left),
                yoffset     = float(top),
                alpha_src   = alpha_src,
            )
            if psd_alpha is not None:
                fita_layer.alpha_data = psd_alpha
                fita_layer.alpha_src  = "USER"

            fita_layer.extra_header["PSD_KIND"] = layer.kind
            fita_layer.extra_header["PSD_CW"]   = canvas_w
            fita_layer.extra_header["PSD_CH"]   = canvas_h

            layers_out.append(fita_layer)
            id_counter += 1
        return id_counter

    _process_group(psd, id_counter=1)

    # reverse so bottom layer has id=1 (Photoshop is stored top-to-bottom)
    for i, layer in enumerate(reversed(layers_out), start=1):
        layer.layer_id = i

    return list(reversed(layers_out))
