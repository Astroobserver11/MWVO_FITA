"""
FITA — Flexible Image Transfer Alpha
=====================================
An extension of the FITS data cube format adding per-slice alpha channels,
variable layer positioning, Photoshop-compatible blend modes, non-destructive
adjustment layers, and IVOA/ObsCore provenance.

Quick start
-----------
    from fita import FITACube, FITALayer

    # From a standard FITS data cube
    cube = FITACube.from_fits_cube("ngc1068_cube.fits", stretch_mode="asinh")
    cube.save("ngc1068.fita")

    # Re-select flux range (alpha recomputed; flux unchanged)
    cube.reselect_flux_range(flux_min=10, flux_max=5000, stretch_mode="log")

    # SED at a pixel
    waves, fluxes = cube.sed(px=512, py=512)

    # Flat composite display image
    display = cube.composite()

    # Import from Photoshop
    cube2 = FITACube.from_psd("composite.psd")
"""

from .cube    import FITACube
from .layer   import FITALayer
from .flux    import (
    clip_flux, normalise, stretch, luminance_from_flux,
    luminance_to_alpha16, encode_split16, decode_split16, auto_range,
)
from .blend   import composite, SCALAR_BLENDS, HSL_BLENDS
from .io      import (read, write, from_fits_cube,
                      read_adjustments, read_zdp_scale)
from .stereo  import stereo_offsets, eye_offset, max_parallax
from .validate import validate, ConformanceReport, flux_roundtrip_ok
from .adjustment import (
    AdjustmentStack, LevelsAdjustment, CurvesAdjustment,
    BrightnessAdjustment, FluxStretchAdjustment, BandMapAdjustment,
    FluxNormAdjustment,
)
# Science / pipeline tools — now in the uranodyne package.
# Re-exported here for backward compatibility so existing code such as
#   from fita import IrenBLink
# or
#   from fita.calibration import InstrumentDB
# continues to work unchanged.
try:
    from uranodyne.calibration  import InstrumentDB, FluxCalibrator, get_db, calibration_report
    from uranodyne.photometry   import (
        aperture_photometry, measure_layer, stack_photometry,
        classify_source, yso_bolometric_luminosity,
        query_gaia_parallaxes, constrain_distance,
    )
    from uranodyne.sed_analysis import DualSED, luminosity_histogram, \
                                       bolometric_surface_histogram, \
                                       build_cumulative_header, export_sed_xlsx
    from uranodyne.export       import plot_dual_sed, plot_layer, animate_stack
except ImportError:
    pass  # uranodyne not installed — format-kernel-only mode

from .spec import FITA_VERSION
__version__ = FITA_VERSION   # N-3: one source of truth (fita.spec)
__all__ = [
    "FITACube", "FITALayer",
    "clip_flux", "normalise", "stretch",
    "luminance_from_flux", "luminance_to_alpha16",
    "encode_split16", "decode_split16", "auto_range",
    "composite", "SCALAR_BLENDS", "HSL_BLENDS",
    "read", "write", "from_fits_cube",
    "AdjustmentStack", "LevelsAdjustment", "CurvesAdjustment",
    "BrightnessAdjustment", "FluxStretchAdjustment",
    "BandMapAdjustment", "FluxNormAdjustment",
    "InstrumentDB", "FluxCalibrator", "get_db", "calibration_report",
    "aperture_photometry", "measure_layer", "stack_photometry",
    "classify_source", "yso_bolometric_luminosity",
    "query_gaia_parallaxes", "constrain_distance",
    "DualSED", "luminosity_histogram", "bolometric_surface_histogram",
    "build_cumulative_header", "export_sed_xlsx",
    "plot_dual_sed", "plot_layer", "animate_stack",
]
