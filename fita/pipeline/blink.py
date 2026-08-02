"""Backward-compat shim: moved to uranodyne.pipeline.blink."""
from uranodyne.pipeline.blink import *      # noqa: F401,F403
from uranodyne.pipeline.blink import (
    difference_image, significance_map,
    detect_proper_motion, candidates_to_table,
    build_blink_cube, sort_by_epoch, epoch_pairs,
    mask_extended_emission, gaia_guided_pm_check,
    ProperMotionCandidate,
)
