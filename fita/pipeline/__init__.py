"""
Backward-compatibility shim.
Pipeline has moved to uranodyne.pipeline.
All public symbols are re-exported from there.
"""
from uranodyne.pipeline import *             # noqa: F401,F403
from uranodyne.pipeline import (
    IrenBLink,
    ALL_SURVEYS, IRENB_PRESETS, Survey,
    difference_image, significance_map,
    detect_proper_motion, candidates_to_table,
    build_blink_cube, sort_by_epoch, epoch_pairs,
    export_hips,
)
