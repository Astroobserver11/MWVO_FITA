"""Unit tests for the FITA library (no external files required)."""

import numpy as np
import pytest
import tempfile
from pathlib import Path

from fita.flux import (
    clip_flux, normalise, stretch, luminance_from_flux,
    luminance_to_alpha16, encode_split16, decode_split16, auto_range,
)
from fita.layer import FITALayer
from fita.cube import FITACube
from fita.blend import composite, blend_screen, blend_multiply, blend_add
from fita.adjustment import (
    LevelsAdjustment, CurvesAdjustment, BrightnessAdjustment,
    FluxStretchAdjustment, AdjustmentStack,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def sample_flux():
    rng = np.random.default_rng(42)
    data = rng.normal(loc=1000.0, scale=200.0, size=(64, 64)).astype(np.float32)
    data[0, 0] = np.nan
    return data


@pytest.fixture
def sample_layer(sample_flux):
    return FITALayer.from_array(sample_flux, layer_id=1, name="TestLayer")


# ── Flux operations ───────────────────────────────────────────────────────────

def test_normalise_range(sample_flux):
    lo, hi = auto_range(sample_flux)
    normed = normalise(sample_flux, lo, hi)
    finite = normed[np.isfinite(normed)]
    assert finite.min() >= 0.0
    assert finite.max() <= 1.0


def test_stretch_modes(sample_flux):
    lo, hi = auto_range(sample_flux)
    normed = normalise(sample_flux, lo, hi)
    for mode in ["linear", "log", "sqrt", "asinh", "power"]:
        out = stretch(normed, mode=mode)
        assert out.shape == normed.shape
        assert np.all(out[np.isfinite(out)] >= 0.0)


def test_encode_decode_split16(sample_flux):
    lo, hi = auto_range(sample_flux)
    f16, a16, bscale, bzero = encode_split16(sample_flux, lo, hi)
    assert f16.dtype == np.uint16
    assert a16.dtype == np.uint16
    recovered = decode_split16(f16, bscale, bzero)
    # Only compare pixels that are finite AND within [lo, hi]; out-of-range are clipped by design
    in_range = np.isfinite(sample_flux) & (sample_flux >= lo) & (sample_flux <= hi)
    max_err = np.abs(sample_flux[in_range] - recovered[in_range]).max()
    # round-trip error should be < 0.01 * range (16-bit quantisation over full span)
    assert max_err < (hi - lo) * 0.01


def test_luminance_to_alpha16(sample_flux):
    lo, hi = auto_range(sample_flux)
    lum = luminance_from_flux(sample_flux, lo, hi)
    alpha = luminance_to_alpha16(lum)
    assert alpha.dtype == np.uint16
    assert alpha.min() >= 0
    assert alpha.max() <= 65535


# ── FITALayer ─────────────────────────────────────────────────────────────────

def test_layer_from_array(sample_flux):
    layer = FITALayer.from_array(sample_flux, layer_id=1, name="NGC1068 Ha")
    assert layer.shape == (64, 64)
    assert layer.alpha_data is not None
    assert layer.alpha_data.dtype == np.uint16
    assert layer.flux_min is not None
    assert layer.flux_max is not None


def test_layer_recompute_alpha(sample_layer):
    old_alpha = sample_layer.alpha_data.copy()
    sample_layer.recompute_alpha(flux_min=900.0, flux_max=1200.0, stretch_mode="log")
    assert not np.array_equal(sample_layer.alpha_data, old_alpha)
    assert sample_layer.flux_data is not None  # flux unchanged


def test_layer_set_user_alpha(sample_layer):
    mask = np.random.rand(64, 64).astype(np.float32)
    sample_layer.set_user_alpha(mask)
    assert sample_layer.alpha_src == "USER"
    assert sample_layer.alpha_data.dtype == np.uint16


def test_layer_alpha_float(sample_layer):
    af = sample_layer.alpha_float
    assert af.shape == (64, 64)
    assert af.min() >= 0.0
    assert af.max() <= 1.0


# ── FITACube ──────────────────────────────────────────────────────────────────

def test_cube_add_layers(sample_flux):
    cube = FITACube()
    for i in range(3):
        l = FITALayer.from_array(sample_flux + i * 100, layer_id=i + 1,
                                  wave_cval=(500 + i * 100) * 1e-9)
        cube.add_layer(l)
    assert len(cube.layers) == 3


def test_cube_composite(sample_flux):
    cube = FITACube()
    for i in range(2):
        cube.add_layer(FITALayer.from_array(sample_flux, layer_id=i + 1))
    result = cube.composite()
    assert result.shape[0] > 0
    assert result.shape[1] > 0
    assert result.min() >= 0.0
    assert result.max() <= 1.0


def test_cube_sed(sample_flux):
    cube = FITACube()
    for i, wave in enumerate([500e-9, 700e-9, 900e-9], start=1):
        l = FITALayer.from_array(sample_flux, layer_id=i, wave_cval=wave)
        cube.add_layer(l)
    waves, fluxes = cube.sed(32, 32)
    assert len(waves) == 3
    assert waves[0] < waves[1] < waves[2]


def test_cube_reselect_flux_range(sample_flux):
    cube = FITACube()
    cube.add_layer(FITALayer.from_array(sample_flux))
    old_alpha = cube.layers[0].alpha_data.copy()
    cube.reselect_flux_range(flux_min=800, flux_max=1100)
    assert not np.array_equal(cube.layers[0].alpha_data, old_alpha)


# ── I/O round-trip ────────────────────────────────────────────────────────────

def test_io_roundtrip_float32(sample_flux):
    pytest.importorskip("astropy")
    from fita.io import write, read

    layers_in = [
        FITALayer.from_array(sample_flux, layer_id=1, name="Ha",
                              wave_cval=656e-9, xoffset=10.0, yoffset=5.0),
        FITALayer.from_array(sample_flux * 0.5, layer_id=2, name="OIII",
                              wave_cval=500e-9),
    ]
    with tempfile.NamedTemporaryFile(suffix=".fita", delete=False) as f:
        tmp = f.name

    write(tmp, layers_in, pack="FLOAT32")
    layers_out = read(tmp)

    assert len(layers_out) == 2
    assert layers_out[0].name == "Ha"
    assert layers_out[1].name == "OIII"
    np.testing.assert_allclose(
        layers_out[0].flux_data[np.isfinite(layers_in[0].flux_data)],
        layers_in[0].flux_data[np.isfinite(layers_in[0].flux_data)],
        rtol=1e-5,
    )
    assert abs(layers_out[0].xoffset - 10.0) < 0.01


def test_split16_is_rejected(sample_flux):
    """D-2 (ratified 2026-08-02): SPLIT16 is deleted; the writer MUST refuse it.

    Replaces the former test_io_roundtrip_split16, which asserted only that alpha was
    not None and so could not fail even when SPLIT16 destroyed every flux pixel.
    """
    pytest.importorskip("astropy")
    from fita.io import write

    layer = FITALayer.from_array(sample_flux, layer_id=1)
    with tempfile.NamedTemporaryFile(suffix=".fita", delete=False) as f:
        tmp = f.name
    with pytest.raises(ValueError, match="SPLIT16"):
        write(tmp, [layer], pack="SPLIT16")


def test_flux_invariant_bit_exact(sample_flux):
    """Standard S5.4: flux MUST be reproduced bit-for-bit across a write/read cycle.

    This is the format's central promise. An untested invariant is a claim, not a
    guarantee — so the standard requires exactly this test, per packing mode offered.
    """
    pytest.importorskip("astropy")
    from fita import flux_roundtrip_ok

    layer = FITALayer.from_array(sample_flux, layer_id=1)
    assert flux_roundtrip_ok([layer], pack="FLOAT32")


def test_written_file_is_core_conformant(sample_flux):
    """The writer MUST produce files that pass the format's own checker (S2.1)."""
    pytest.importorskip("astropy")
    from fita import write, validate

    layer = FITALayer.from_array(sample_flux, layer_id=1)
    layer.visible = False                      # the metadata that used to be lost
    with tempfile.NamedTemporaryFile(suffix=".fita", delete=False) as f:
        tmp = f.name
    write(tmp, [layer], overwrite=True)

    report = validate(tmp)
    assert report.is_core, str(report)

    from fita import read
    assert read(tmp)[0].visible is False       # S6.2 FITA_VIS round-trip


def test_cube_save_load(sample_flux):
    pytest.importorskip("astropy")
    cube = FITACube()
    cube.add_layer(FITALayer.from_array(sample_flux, wave_cval=656e-9))
    with tempfile.NamedTemporaryFile(suffix=".fita", delete=False) as f:
        tmp = f.name
    cube.save(tmp)
    cube2 = FITACube.load(tmp)
    assert len(cube2.layers) == 1


# ── Blend modes ───────────────────────────────────────────────────────────────

def test_blend_screen_identity():
    # screen(0, x) == x
    base  = np.zeros((4, 4), dtype=np.float32)
    blend = np.full((4, 4), 0.5, dtype=np.float32)
    np.testing.assert_allclose(blend_screen(base, blend), blend)


def test_blend_multiply_identity():
    # multiply(1, x) == x
    base  = np.ones((4, 4), dtype=np.float32)
    blend = np.full((4, 4), 0.3, dtype=np.float32)
    np.testing.assert_allclose(blend_multiply(base, blend), blend)


def test_blend_add_clamp():
    base  = np.full((4, 4), 0.8, dtype=np.float32)
    blend = np.full((4, 4), 0.8, dtype=np.float32)
    result = blend_add(base, blend)
    assert result.max() <= 1.0


def test_composite_alpha_zero():
    base  = np.full((4, 4), 0.5, dtype=np.float32)
    blend = np.full((4, 4), 1.0, dtype=np.float32)
    alpha = np.zeros((4, 4), dtype=np.float32)
    result = composite(base, blend, alpha, 1.0, "NORMAL")
    np.testing.assert_allclose(result, base)


def test_composite_alpha_one():
    base  = np.full((4, 4), 0.5, dtype=np.float32)
    blend = np.full((4, 4), 1.0, dtype=np.float32)
    alpha = np.ones((4, 4), dtype=np.float32)
    result = composite(base, blend, alpha, 1.0, "NORMAL")
    np.testing.assert_allclose(result, blend)


# ── Adjustment layers ─────────────────────────────────────────────────────────

def test_levels_passthrough():
    data = np.linspace(0, 1, 100, dtype=np.float32)
    adj  = LevelsAdjustment()
    np.testing.assert_allclose(adj.apply(data), data, atol=1e-6)


def test_levels_invert():
    data = np.array([0.0, 0.5, 1.0], dtype=np.float32)
    adj  = LevelsAdjustment(in_black=1.0, in_white=0.0)
    result = adj.apply(data)
    assert result[0] >= result[1] >= result[2] - 1e-6


def test_curves_identity():
    data = np.linspace(0, 1, 50, dtype=np.float32)
    adj  = CurvesAdjustment(control_points=[(0.0, 0.0), (1.0, 1.0)])
    np.testing.assert_allclose(adj.apply(data), data, atol=1e-5)


def test_flux_stretch_adj():
    data = np.linspace(0, 1, 50, dtype=np.float32)
    adj  = FluxStretchAdjustment(stretch_mode="sqrt")
    result = adj.apply(data)
    assert result.min() >= 0.0
    assert result.max() <= 1.0 + 1e-6


def test_adjustment_stack():
    data  = np.linspace(0, 1, 100, dtype=np.float32)
    stack = AdjustmentStack([
        LevelsAdjustment(in_black=0.1, in_white=0.9),
        BrightnessAdjustment(brightness=0.1),
    ])
    result = stack.apply(data)
    assert result.shape == data.shape
