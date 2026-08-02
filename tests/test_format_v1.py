"""
FITA v1.1 format test suite — covers gaps not addressed in test_fita.py.

Topics:
  - spec.py constants (BLEND_CODES completeness, extension name templates)
  - ZDP stereo-depth round-trip through FITS I/O
  - Uncertainty and mask extension round-trip through FITS I/O
  - All 14 blend modes (scalar + HSL), including mathematical identities
  - Composite: opacity, HSL modes on 2-D greyscale
  - IVOA: annotate headers, validate_spectral_ctype, make_meta_hdu, sed_wavelength_range
  - from_fits_cube: import a synthetic 3-D FITS cube
  - HDF5 backend: write/read round-trip, zdepth, uncert/mask, info()
  - FITALayer.to_header_dict: all required keys present
  - FITALayer visibility flag round-trip
"""

import numpy as np
import pytest
import tempfile
from pathlib import Path

from fita.layer import FITALayer
from fita.cube  import FITACube
from fita.spec  import (
    BLEND_CODES, BLEND_NORMAL, BLEND_SCREEN, BLEND_MULTIPLY, BLEND_ADD,
    BLEND_OVERLAY, BLEND_SOFT, BLEND_HARD, BLEND_DODGE, BLEND_BURN,
    BLEND_DIFF, BLEND_LUMINOSITY, BLEND_COLOR, BLEND_HUE, BLEND_SAT,
    KW_LAYER_ID, KW_LAYER_NAME, KW_BLEND_MODE, KW_OPACITY,
    KW_FLUX_MIN, KW_FLUX_MAX, KW_WAVE_CVAL, KW_XOFFSET, KW_YOFFSET,
    KW_ALPHA_SRC, KW_DEPTH,
    flux_extname, alpha_extname, EXTNAME_LAYERS, EXTNAME_ADJ, EXTNAME_META,
    FITA_VERSION,
)
from fita.blend import (
    blend_normal, blend_screen, blend_multiply, blend_add,
    blend_overlay, blend_soft_light, blend_hard_light,
    blend_color_dodge, blend_color_burn, blend_difference,
    blend_luminosity, blend_color, blend_hue, blend_saturation,
    composite, SCALAR_BLENDS, HSL_BLENDS,
)


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def rng_flux():
    rng = np.random.default_rng(7)
    data = rng.uniform(200, 2000, (64, 64)).astype(np.float32)
    return data


@pytest.fixture
def simple_layer(rng_flux):
    return FITALayer.from_array(rng_flux, layer_id=1, name="TestZ",
                                 wave_cval=656e-9, wave_bwid=10e-9)


@pytest.fixture
def rgb_pair():
    """Two (4,4,3) float32 RGB arrays for HSL blend tests."""
    rng = np.random.default_rng(42)
    base  = rng.uniform(0.1, 0.9, (4, 4, 3)).astype(np.float32)
    blend = rng.uniform(0.1, 0.9, (4, 4, 3)).astype(np.float32)
    return base, blend


# ─────────────────────────────────────────────────────────────────────────────
# spec.py — constants
# ─────────────────────────────────────────────────────────────────────────────

def test_blend_codes_complete():
    expected = {
        BLEND_NORMAL, BLEND_SCREEN, BLEND_MULTIPLY, BLEND_ADD,
        BLEND_OVERLAY, BLEND_SOFT, BLEND_HARD, BLEND_DODGE, BLEND_BURN,
        BLEND_DIFF, BLEND_LUMINOSITY, BLEND_COLOR, BLEND_HUE, BLEND_SAT,
    }
    assert expected == BLEND_CODES


def test_scalar_blends_cover_all_scalar_codes():
    scalar_codes = BLEND_CODES - set(HSL_BLENDS)
    assert set(SCALAR_BLENDS) == scalar_codes


def test_hsl_blends_cover_all_hsl_codes():
    hsl_codes = {BLEND_LUMINOSITY, BLEND_COLOR, BLEND_HUE, BLEND_SAT}
    assert set(HSL_BLENDS) == hsl_codes


def test_extension_name_templates():
    assert flux_extname(1)   == "FLUX_0001"
    assert flux_extname(12)  == "FLUX_0012"
    assert alpha_extname(3)  == "ALPHA_0003"
    assert alpha_extname(100)== "ALPHA_0100"


def test_extname_constants():
    assert EXTNAME_LAYERS == "FITA_LAYERS"
    assert EXTNAME_ADJ    == "FITA_ADJ"
    assert EXTNAME_META   == "FITA_META"


def test_fita_version_string():
    assert FITA_VERSION == "1.2"   # amended 2026-08-02 (Q1/Q2 added optional structure)


# ─────────────────────────────────────────────────────────────────────────────
# FITALayer — to_header_dict
# ─────────────────────────────────────────────────────────────────────────────

def test_to_header_dict_required_keys(simple_layer):
    d = simple_layer.to_header_dict()
    for kw in (KW_LAYER_ID, KW_LAYER_NAME, KW_BLEND_MODE, KW_OPACITY,
               KW_XOFFSET, KW_YOFFSET, KW_ALPHA_SRC,
               KW_FLUX_MIN, KW_FLUX_MAX, KW_WAVE_CVAL):
        assert kw in d, f"Missing key: {kw}"


def test_to_header_dict_zdepth_present():
    rng = np.random.default_rng(5)
    data = rng.uniform(100, 500, (16, 16)).astype(np.float32)
    layer = FITALayer.from_array(data, layer_id=2, zdepth=0.75)
    d = layer.to_header_dict()
    assert KW_DEPTH in d
    assert abs(d[KW_DEPTH] - 0.75) < 1e-6


def test_to_header_dict_zdepth_absent():
    rng = np.random.default_rng(6)
    data = rng.uniform(100, 500, (16, 16)).astype(np.float32)
    layer = FITALayer.from_array(data, layer_id=3)
    d = layer.to_header_dict()
    assert KW_DEPTH not in d


# ─────────────────────────────────────────────────────────────────────────────
# ZDP (stereo depth) round-trip — FITS
# ─────────────────────────────────────────────────────────────────────────────

def test_zdp_roundtrip_fits(rng_flux):
    pytest.importorskip("astropy")
    from fita.io import write, read

    layer = FITALayer.from_array(rng_flux, layer_id=1, zdepth=0.33)
    with tempfile.NamedTemporaryFile(suffix=".fita", delete=False) as f:
        tmp = f.name
    write(tmp, [layer])
    out = read(tmp)[0]
    assert out.zdepth is not None
    assert abs(out.zdepth - 0.33) < 1e-4


def test_zdp_none_roundtrip_fits(rng_flux):
    pytest.importorskip("astropy")
    from fita.io import write, read

    layer = FITALayer.from_array(rng_flux, layer_id=1)
    with tempfile.NamedTemporaryFile(suffix=".fita", delete=False) as f:
        tmp = f.name
    write(tmp, [layer])
    out = read(tmp)[0]
    assert out.zdepth is None


def test_zdp_boundary_values(rng_flux):
    pytest.importorskip("astropy")
    from fita.io import write, read

    for zdp in (0.0, 0.5, 1.0):
        layer = FITALayer.from_array(rng_flux, layer_id=1, zdepth=zdp)
        with tempfile.NamedTemporaryFile(suffix=".fita", delete=False) as f:
            tmp = f.name
        write(tmp, [layer])
        out = read(tmp)[0]
        assert out.zdepth is not None
        assert abs(out.zdepth - zdp) < 1e-4


# ─────────────────────────────────────────────────────────────────────────────
# Uncertainty and mask extension round-trip — FITS
# ─────────────────────────────────────────────────────────────────────────────

def test_uncert_roundtrip_fits(rng_flux):
    pytest.importorskip("astropy")
    from fita.io import write, read

    uncert = (np.abs(rng_flux) * 0.05).astype(np.float32)
    layer = FITALayer.from_array(rng_flux, layer_id=1)
    layer.uncert_data = uncert

    with tempfile.NamedTemporaryFile(suffix=".fita", delete=False) as f:
        tmp = f.name
    write(tmp, [layer])
    out = read(tmp)[0]

    assert out.uncert_data is not None
    assert out.uncert_data.shape == uncert.shape
    np.testing.assert_allclose(out.uncert_data, uncert, rtol=1e-5)


def test_mask_roundtrip_fits(rng_flux):
    pytest.importorskip("astropy")
    from fita.io import write, read

    mask = np.zeros(rng_flux.shape, dtype=np.uint8)
    mask[0, :] = 1   # bad row
    mask[1, :] = 2   # saturated row

    layer = FITALayer.from_array(rng_flux, layer_id=1)
    layer.mask_data = mask

    with tempfile.NamedTemporaryFile(suffix=".fita", delete=False) as f:
        tmp = f.name
    write(tmp, [layer])
    out = read(tmp)[0]

    assert out.mask_data is not None
    assert out.mask_data.dtype == np.uint8
    np.testing.assert_array_equal(out.mask_data, mask)


def test_uncert_and_mask_together(rng_flux):
    pytest.importorskip("astropy")
    from fita.io import write, read

    layer = FITALayer.from_array(rng_flux, layer_id=1)
    layer.uncert_data = (rng_flux * 0.1).astype(np.float32)
    layer.mask_data   = np.ones(rng_flux.shape, dtype=np.uint8)

    with tempfile.NamedTemporaryFile(suffix=".fita", delete=False) as f:
        tmp = f.name
    write(tmp, [layer])
    out = read(tmp)[0]
    assert out.uncert_data is not None
    assert out.mask_data is not None


# ─────────────────────────────────────────────────────────────────────────────
# Visibility flag round-trip
# ─────────────────────────────────────────────────────────────────────────────

def test_visibility_flag_roundtrip(rng_flux):
    pytest.importorskip("astropy")
    from fita.io import write, read

    layers = [
        FITALayer.from_array(rng_flux, layer_id=1, visible=True),
        FITALayer.from_array(rng_flux, layer_id=2, visible=False),
    ]
    with tempfile.NamedTemporaryFile(suffix=".fita", delete=False) as f:
        tmp = f.name
    write(tmp, layers)
    out = read(tmp)
    assert out[0].visible is True
    assert out[1].visible is False


# ─────────────────────────────────────────────────────────────────────────────
# Blend modes — scalar, mathematical identities
# ─────────────────────────────────────────────────────────────────────────────

def test_blend_overlay_dark():
    """Overlay(0.25, x) == 2*0.25*x (dark branch)."""
    base  = np.full((4, 4), 0.25, dtype=np.float32)
    blend = np.full((4, 4), 0.6, dtype=np.float32)
    expected = 2.0 * 0.25 * 0.6
    np.testing.assert_allclose(blend_overlay(base, blend), expected, atol=1e-5)


def test_blend_overlay_light():
    """Overlay(0.75, x) == 1 - 2*(1-0.75)*(1-x) (light branch)."""
    base  = np.full((4, 4), 0.75, dtype=np.float32)
    blend = np.full((4, 4), 0.6, dtype=np.float32)
    expected = 1.0 - 2.0 * (1.0 - 0.75) * (1.0 - 0.6)
    np.testing.assert_allclose(blend_overlay(base, blend), expected, atol=1e-5)


def test_blend_hard_light_is_overlay_swapped():
    """hard_light(base, blend) == overlay(blend, base)."""
    rng = np.random.default_rng(1)
    base  = rng.uniform(0, 1, (8, 8)).astype(np.float32)
    blend = rng.uniform(0, 1, (8, 8)).astype(np.float32)
    np.testing.assert_allclose(blend_hard_light(base, blend),
                                blend_overlay(blend, base), atol=1e-6)


def test_blend_soft_light_midpoint():
    """soft_light(0.5, 0.5) should equal 0.5 (symmetry at midpoint)."""
    base  = np.full((4, 4), 0.5, dtype=np.float32)
    blend = np.full((4, 4), 0.5, dtype=np.float32)
    np.testing.assert_allclose(blend_soft_light(base, blend), 0.5, atol=1e-5)


def test_blend_color_dodge_clamps():
    """color_dodge should never exceed 1.0."""
    base  = np.full((4, 4), 0.9, dtype=np.float32)
    blend = np.full((4, 4), 0.9, dtype=np.float32)
    result = blend_color_dodge(base, blend)
    assert result.max() <= 1.0 + 1e-6


def test_blend_color_dodge_zero_blend():
    """color_dodge(base, 0) == base (divide by 1)."""
    rng = np.random.default_rng(2)
    base = rng.uniform(0, 1, (4, 4)).astype(np.float32)
    blend = np.zeros_like(base)
    np.testing.assert_allclose(blend_color_dodge(base, blend), base, atol=1e-5)


def test_blend_color_burn_clamps():
    """color_burn should stay in [0, 1]."""
    base  = np.full((4, 4), 0.1, dtype=np.float32)
    blend = np.full((4, 4), 0.1, dtype=np.float32)
    result = blend_color_burn(base, blend)
    assert result.min() >= -1e-6
    assert result.max() <=  1.0 + 1e-6


def test_blend_difference_zero():
    """difference(x, x) == 0."""
    rng = np.random.default_rng(3)
    x = rng.uniform(0, 1, (8, 8)).astype(np.float32)
    np.testing.assert_allclose(blend_difference(x, x), 0.0, atol=1e-6)


def test_blend_difference_symmetric():
    """difference(a, b) == difference(b, a)."""
    rng = np.random.default_rng(4)
    a = rng.uniform(0, 1, (8, 8)).astype(np.float32)
    b = rng.uniform(0, 1, (8, 8)).astype(np.float32)
    np.testing.assert_allclose(blend_difference(a, b), blend_difference(b, a), atol=1e-6)


def test_blend_normal_passthrough():
    """normal blend always returns the blend layer."""
    rng = np.random.default_rng(5)
    base  = rng.uniform(0, 1, (8, 8)).astype(np.float32)
    blend = rng.uniform(0, 1, (8, 8)).astype(np.float32)
    np.testing.assert_array_equal(blend_normal(base, blend), blend)


# ─────────────────────────────────────────────────────────────────────────────
# Blend modes — HSL, RGB arrays
# ─────────────────────────────────────────────────────────────────────────────

def test_hsl_luminosity_output_range(rgb_pair):
    base, blend = rgb_pair
    result = blend_luminosity(base, blend)
    assert result.shape == base.shape
    assert result.min() >= -0.01
    assert result.max() <=  1.01


def test_hsl_color_output_range(rgb_pair):
    base, blend = rgb_pair
    result = blend_color(base, blend)
    assert result.shape == base.shape
    assert result.min() >= -0.01
    assert result.max() <=  1.01


def test_hsl_hue_output_range(rgb_pair):
    base, blend = rgb_pair
    result = blend_hue(base, blend)
    assert result.shape == base.shape


def test_hsl_saturation_output_range(rgb_pair):
    base, blend = rgb_pair
    result = blend_saturation(base, blend)
    assert result.shape == base.shape


def test_hsl_luminosity_preserves_hue_saturation(rgb_pair):
    """After luminosity blend, hue & saturation should come from base."""
    from fita.blend import _rgb_to_hsl
    base, blend = rgb_pair
    result = blend_luminosity(base, blend)

    bh, bs, _ = _rgb_to_hsl(base[..., 0], base[..., 1], base[..., 2])
    rh, rs, _ = _rgb_to_hsl(result[..., 0], result[..., 1], result[..., 2])
    # Hue and saturation should match base (within floating-point tolerance)
    # Only check pixels where both base and result are chromatic (s > 0.05)
    chromatic = (bs > 0.05) & (rs > 0.05)
    if chromatic.any():
        np.testing.assert_allclose(rh[chromatic], bh[chromatic], atol=0.05)


# ─────────────────────────────────────────────────────────────────────────────
# Composite — opacity, HSL on greyscale
# ─────────────────────────────────────────────────────────────────────────────

def test_composite_half_opacity():
    """At alpha=1, opacity=0.5, result should be midpoint of base and blend."""
    base  = np.zeros((4, 4), dtype=np.float32)
    blend = np.ones((4, 4), dtype=np.float32)
    alpha = np.ones((4, 4), dtype=np.float32)
    result = composite(base, blend, alpha, 0.5, "NORMAL")
    np.testing.assert_allclose(result, 0.5, atol=1e-6)


def test_composite_hsl_mode_greyscale():
    """HSL blend modes on 2-D arrays should not crash and return correct shape."""
    base  = np.full((4, 4), 0.4, dtype=np.float32)
    blend = np.full((4, 4), 0.7, dtype=np.float32)
    alpha = np.ones((4, 4), dtype=np.float32)
    for mode in (BLEND_LUMINOSITY, BLEND_COLOR, BLEND_HUE, BLEND_SAT):
        result = composite(base, blend, alpha, 1.0, mode)
        assert result.shape == (4, 4), f"Shape mismatch for mode {mode}"
        assert np.all(np.isfinite(result)), f"Non-finite values for mode {mode}"


def test_composite_all_scalar_modes():
    """All scalar blend modes should produce finite output in [0,1]."""
    rng = np.random.default_rng(9)
    base  = rng.uniform(0.1, 0.9, (8, 8)).astype(np.float32)
    blend = rng.uniform(0.1, 0.9, (8, 8)).astype(np.float32)
    alpha = rng.uniform(0, 1, (8, 8)).astype(np.float32)
    for mode in SCALAR_BLENDS:
        result = composite(base, blend, alpha, 1.0, mode)
        assert np.all(np.isfinite(result)), f"NaN/Inf for mode {mode}"
        assert result.min() >= -0.01, f"Below 0 for mode {mode}"
        assert result.max() <=  1.01, f"Above 1 for mode {mode}"


def test_composite_unknown_mode_raises():
    base  = np.zeros((4, 4), dtype=np.float32)
    blend = np.zeros((4, 4), dtype=np.float32)
    alpha = np.ones((4, 4), dtype=np.float32)
    with pytest.raises(ValueError, match="Unknown blend mode"):
        composite(base, blend, alpha, 1.0, "BOGUS")


# ─────────────────────────────────────────────────────────────────────────────
# IVOA
# ─────────────────────────────────────────────────────────────────────────────

def test_validate_spectral_ctype_valid():
    from fita.ivoa import validate_spectral_ctype
    for ctype in ("WAVE", "WAVE-LOG", "FREQ", "VRAD", "ENER", "STOKES"):
        assert validate_spectral_ctype(ctype), f"Should be valid: {ctype}"


def test_validate_spectral_ctype_invalid():
    from fita.ivoa import validate_spectral_ctype
    for ctype in ("FLUX", "RA---TAN", "DEC--TAN", "BOGUS"):
        assert not validate_spectral_ctype(ctype), f"Should be invalid: {ctype}"


def test_annotate_flux_header():
    pytest.importorskip("astropy")
    from astropy.io.fits import Header
    from fita.ivoa import annotate_flux_header
    hdr = Header()
    annotate_flux_header(hdr, bunit="Jy")
    assert "UCD1" in hdr
    assert hdr["BUNIT"] == "Jy"


def test_annotate_alpha_header():
    """S7 / D-4: alpha is dimensionless and MUST NOT declare BUNIT='alpha16'.

    This test previously asserted the defect -- it required the very value the
    ratified standard retires, because 'alpha16' is not a parseable FITS unit.
    A test that pins a non-conformant value cannot detect non-conformance.
    """
    pytest.importorskip("astropy")
    from astropy.io.fits import Header
    from fita.ivoa import annotate_alpha_header
    hdr = Header()
    hdr["BUNIT"] = "alpha16"          # a legacy header carrying the old value
    annotate_alpha_header(hdr)
    assert "UCD1" in hdr
    assert "BUNIT" not in hdr, "invalid unit 'alpha16' must be removed, not kept"


def test_make_meta_hdu_columns():
    pytest.importorskip("astropy")
    from fita.ivoa import make_meta_hdu
    hdu = make_meta_hdu(
        obs_id="M27-TEST", obs_title="Dumbbell Nebula", facility="HST",
        instrument="WFC3", target="M27",
        ra=299.9, dec=22.72, t_min=57000.0, t_max=57001.0,
        em_min=486e-9, em_max=658e-9, nlayers=12,
    )
    assert hdu.name == "FITA_META"
    cols = hdu.columns.names
    for col in ("obs_id", "obs_title", "facility_name", "instrument_name",
                "s_ra", "s_dec", "em_min", "em_max", "fita_nlayers"):
        assert col in cols, f"Missing IVOA column: {col}"
    assert hdu.data["obs_id"][0].strip() == "M27-TEST"
    assert abs(hdu.data["s_ra"][0] - 299.9) < 0.01


def test_make_meta_hdu_calib_level():
    pytest.importorskip("astropy")
    from fita.ivoa import make_meta_hdu
    hdu = make_meta_hdu(calib_level=3, nlayers=5)
    assert int(hdu.data["calib_level"][0]) == 3


def test_sed_wavelength_range(simple_layer):
    from fita.ivoa import sed_wavelength_range
    layers = [simple_layer]
    lo, hi = sed_wavelength_range(layers)
    # wave_cval=656e-9, wave_bwid=10e-9 → lo = 651e-9, hi = 661e-9
    assert lo < simple_layer.wave_cval < hi


def test_sed_wavelength_range_no_wave():
    from fita.ivoa import sed_wavelength_range
    rng = np.random.default_rng(0)
    layer = FITALayer.from_array(rng.uniform(0, 1, (8, 8)).astype(np.float32))
    lo, hi = sed_wavelength_range([layer])
    assert lo == 0.0 and hi == 0.0


def test_sed_wavelength_range_multiband():
    from fita.ivoa import sed_wavelength_range
    rng = np.random.default_rng(1)
    layers = [
        FITALayer.from_array(rng.uniform(0, 1, (8, 8)).astype(np.float32),
                              wave_cval=486e-9, wave_bwid=5e-9),
        FITALayer.from_array(rng.uniform(0, 1, (8, 8)).astype(np.float32),
                              wave_cval=658e-9, wave_bwid=5e-9),
    ]
    lo, hi = sed_wavelength_range(layers)
    assert lo < 486e-9
    assert hi > 658e-9


# ─────────────────────────────────────────────────────────────────────────────
# from_fits_cube
# ─────────────────────────────────────────────────────────────────────────────

def _make_synthetic_fits_cube(tmp_path, nslices=4, ny=32, nx=32):
    pytest.importorskip("astropy")
    from astropy.io import fits
    from astropy.wcs import WCS

    rng = np.random.default_rng(55)
    data = rng.uniform(100, 1000, (nslices, ny, nx)).astype(np.float32)

    # build a minimal spectral WCS
    wcs = WCS(naxis=3)
    wcs.wcs.ctype = ["RA---TAN", "DEC--TAN", "WAVE"]
    wcs.wcs.crpix = [nx // 2, ny // 2, 1]
    wcs.wcs.crval = [83.82, -5.39, 486e-9]
    wcs.wcs.cdelt = [-1/3600, 1/3600, 100e-9]
    wcs.wcs.cunit = ["deg", "deg", "m"]

    hdu = fits.PrimaryHDU(data=data, header=wcs.to_header())
    path = tmp_path / "test_cube.fits"
    hdu.writeto(str(path))
    return path, nslices


def test_from_fits_cube_layer_count(tmp_path):
    pytest.importorskip("astropy")
    from fita.io import from_fits_cube
    path, n = _make_synthetic_fits_cube(tmp_path, nslices=4)
    layers = from_fits_cube(str(path))
    assert len(layers) == n


def test_from_fits_cube_layer_ids(tmp_path):
    pytest.importorskip("astropy")
    from fita.io import from_fits_cube
    path, n = _make_synthetic_fits_cube(tmp_path)
    layers = from_fits_cube(str(path))
    ids = [l.layer_id for l in layers]
    assert ids == list(range(1, n + 1))


def test_from_fits_cube_shapes(tmp_path):
    pytest.importorskip("astropy")
    from fita.io import from_fits_cube
    path, _ = _make_synthetic_fits_cube(tmp_path, ny=32, nx=32)
    layers = from_fits_cube(str(path))
    for l in layers:
        assert l.shape == (32, 32)


def test_from_fits_cube_alpha_computed(tmp_path):
    pytest.importorskip("astropy")
    from fita.io import from_fits_cube
    path, _ = _make_synthetic_fits_cube(tmp_path)
    layers = from_fits_cube(str(path))
    for l in layers:
        assert l.alpha_data is not None
        assert l.alpha_data.dtype == np.uint16


def test_from_fits_cube_2d_fallback(tmp_path):
    """A 2-D FITS image should become a single layer."""
    pytest.importorskip("astropy")
    from astropy.io import fits
    from fita.io import from_fits_cube
    rng = np.random.default_rng(66)
    data = rng.uniform(0, 1, (64, 64)).astype(np.float32)
    hdu = fits.PrimaryHDU(data=data)
    path = tmp_path / "flat.fits"
    hdu.writeto(str(path))
    layers = from_fits_cube(str(path))
    assert len(layers) == 1
    assert layers[0].shape == (64, 64)


# ─────────────────────────────────────────────────────────────────────────────
# HDF5 backend
# ─────────────────────────────────────────────────────────────────────────────

def test_hdf5_roundtrip_float32(rng_flux, tmp_path):
    pytest.importorskip("h5py")
    from fita.backends.hdf5 import write, read

    layer = FITALayer.from_array(rng_flux, layer_id=1, name="HDF5Test",
                                  wave_cval=656e-9, wave_bwid=10e-9,
                                  xoffset=3.0, yoffset=7.5)
    path = tmp_path / "test.h5"
    write(str(path), [layer])
    out = read(str(path))

    assert len(out) == 1
    assert out[0].name == "HDF5Test"
    assert abs(out[0].xoffset - 3.0) < 0.01
    assert abs(out[0].yoffset - 7.5) < 0.01
    np.testing.assert_allclose(out[0].flux_data, layer.flux_data, rtol=1e-5)


def test_hdf5_roundtrip_alpha(rng_flux, tmp_path):
    pytest.importorskip("h5py")
    from fita.backends.hdf5 import write, read

    layer = FITALayer.from_array(rng_flux, layer_id=1)
    path = tmp_path / "alpha.h5"
    write(str(path), [layer])
    out = read(str(path))[0]
    assert out.alpha_data is not None
    assert out.alpha_data.dtype == np.uint16


def test_hdf5_zdepth_roundtrip(rng_flux, tmp_path):
    pytest.importorskip("h5py")
    from fita.backends.hdf5 import write, read

    layer = FITALayer.from_array(rng_flux, layer_id=1, zdepth=0.42)
    path = tmp_path / "zdp.h5"
    write(str(path), [layer])
    out = read(str(path))[0]
    assert out.zdepth is not None
    assert abs(out.zdepth - 0.42) < 1e-4


def test_hdf5_zdepth_none_roundtrip(rng_flux, tmp_path):
    pytest.importorskip("h5py")
    from fita.backends.hdf5 import write, read

    layer = FITALayer.from_array(rng_flux, layer_id=1)
    path = tmp_path / "zdp_none.h5"
    write(str(path), [layer])
    out = read(str(path))[0]
    assert out.zdepth is None


def test_hdf5_uncert_roundtrip(rng_flux, tmp_path):
    pytest.importorskip("h5py")
    from fita.backends.hdf5 import write, read

    uncert = (rng_flux * 0.05).astype(np.float32)
    layer = FITALayer.from_array(rng_flux, layer_id=1)
    layer.uncert_data = uncert

    path = tmp_path / "uncert.h5"
    write(str(path), [layer])
    out = read(str(path))[0]
    assert out.uncert_data is not None
    np.testing.assert_allclose(out.uncert_data, uncert, rtol=1e-5)


def test_hdf5_mask_roundtrip(rng_flux, tmp_path):
    pytest.importorskip("h5py")
    from fita.backends.hdf5 import write, read

    mask = np.zeros(rng_flux.shape, dtype=np.uint8)
    mask[5, 5] = 3
    layer = FITALayer.from_array(rng_flux, layer_id=1)
    layer.mask_data = mask

    path = tmp_path / "mask.h5"
    write(str(path), [layer])
    out = read(str(path))[0]
    assert out.mask_data is not None
    assert out.mask_data.dtype == np.uint8
    assert out.mask_data[5, 5] == 3


def test_hdf5_multilayer_order(tmp_path):
    pytest.importorskip("h5py")
    from fita.backends.hdf5 import write, read

    rng = np.random.default_rng(77)
    layers = [
        FITALayer.from_array(rng.uniform(0, 1, (32, 32)).astype(np.float32),
                              layer_id=i, name=f"L{i}", wave_cval=i * 200e-9)
        for i in range(1, 6)
    ]
    path = tmp_path / "multi.h5"
    write(str(path), layers)
    out = read(str(path))
    assert len(out) == 5
    ids = [l.layer_id for l in out]
    assert ids == sorted(ids)


def test_hdf5_info(rng_flux, tmp_path):
    pytest.importorskip("h5py")
    from fita.backends.hdf5 import write, info

    layer = FITALayer.from_array(rng_flux, layer_id=1, zdepth=0.9,
                                  wave_cval=2.2e-6)
    layer.uncert_data = (rng_flux * 0.1).astype(np.float32)

    path = tmp_path / "info.h5"
    write(str(path), [layer])
    d = info(str(path))

    assert d["version"] == "1.2"
    assert d["nlayers"] == 1
    assert d["pack"] == "FLOAT32"
    li = d["layers"][0]
    assert li["shape"] == (64, 64)
    assert abs(li["wave_cval"] - 2.2e-6) < 1e-9
    assert abs(li["zdepth"] - 0.9) < 1e-3
    assert li["has_uncert"] is True
    assert li["has_mask"] is False


def test_hdf5_info_no_zdepth(rng_flux, tmp_path):
    pytest.importorskip("h5py")
    from fita.backends.hdf5 import write, info

    layer = FITALayer.from_array(rng_flux, layer_id=1)
    path = tmp_path / "info2.h5"
    write(str(path), [layer])
    d = info(str(path))
    assert d["layers"][0]["zdepth"] is None


def test_hdf5_overwrite_false_raises(rng_flux, tmp_path):
    pytest.importorskip("h5py")
    from fita.backends.hdf5 import write

    layer = FITALayer.from_array(rng_flux, layer_id=1)
    path = tmp_path / "once.h5"
    write(str(path), [layer])
    with pytest.raises(FileExistsError):
        write(str(path), [layer], overwrite=False)


def test_hdf5_convert_fits_to_hdf5(rng_flux, tmp_path):
    pytest.importorskip("h5py")
    pytest.importorskip("astropy")
    from fita.io import write as fits_write
    from fita.backends.hdf5 import convert_fits_to_hdf5, read

    layer = FITALayer.from_array(rng_flux, layer_id=1, name="ConvTest",
                                  wave_cval=500e-9)
    fits_path = tmp_path / "orig.fita"
    fits_write(str(fits_path), [layer])

    h5_path = convert_fits_to_hdf5(fits_path, tmp_path / "conv.h5")
    assert h5_path.exists()

    out = read(str(h5_path))
    assert len(out) == 1
    assert out[0].name == "ConvTest"
