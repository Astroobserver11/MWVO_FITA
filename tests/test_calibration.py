"""Tests for calibration, photometry, SED analysis, and dual representation."""

import numpy as np
import pytest
import tempfile
from pathlib import Path

from fita.layer import FITALayer
from fita.cube  import FITACube
# fita.calibration / .photometry / .sed_analysis are thin re-export shims
# over the URANODYNE science stack, which is a separate distribution. Skip
# rather than fail so the format kernel stays independently testable.
pytest.importorskip("uranodyne")

from fita.calibration import (
    InstrumentDB, FluxCalibrator,
    erg_per_cm2_s_A_to_jy, mjy_sr_to_jy_pixel,
)
from fita.photometry import (
    aperture_photometry, classify_source, stack_photometry,
    yso_bolometric_luminosity, constrain_distance, SEDPoint,
)
from fita.sed_analysis import (
    DualSED, luminosity_histogram, bolometric_surface_histogram,
    build_cumulative_header, export_sed_xlsx,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def flat_flux():
    """A flat 64×64 flux image with a point source at centre."""
    rng = np.random.default_rng(7)
    data = rng.normal(100.0, 5.0, (64, 64)).astype(np.float32)
    # inject a point source at (32, 32)
    for dy in range(-2, 3):
        for dx in range(-2, 3):
            r2 = dx**2 + dy**2
            data[32+dy, 32+dx] += 500.0 * np.exp(-r2 / 2.0)
    return data


@pytest.fixture
def sed_cube():
    """A 4-layer cube spanning UV → MIR."""
    rng = np.random.default_rng(99)
    layers = []
    waves = [350e-9, 700e-9, 2.2e-6, 24e-6]
    for i, w in enumerate(waves):
        data = rng.normal(1000.0 - i*200, 50.0, (64, 64)).astype(np.float32)
        data[30:34, 30:34] += 2000.0
        l = FITALayer.from_array(data, layer_id=i+1,
                                  wave_cval=w, wave_bwid=w*0.1,
                                  xoffset=0.0, yoffset=0.0)
        l.extra_header["BUNIT"] = "Jy"
        layers.append(l)
    return FITACube(layers=layers)


# ── Instrument database ───────────────────────────────────────────────────────

def test_db_loads():
    db = InstrumentDB()
    assert len(db.keys) > 0


def test_db_lookup_exact():
    db = InstrumentDB()
    entry = db.lookup("HST", "WFC3", "F160W")
    assert entry is not None
    assert entry["pivot_wavelength_m"] == pytest.approx(1.5369e-6, rel=1e-3)


def test_db_lookup_partial():
    db = InstrumentDB()
    entry = db.lookup("", "IRAC", "3.6um")
    assert entry is not None or db.lookup("Spitzer", "IRAC", "3.6um") is not None


def test_db_add_custom():
    db = InstrumentDB()
    db.add_entry("MyTel/MyCam/F550W", {
        "pivot_wavelength_m": 550e-9,
        "bunit_raw": "Jy",
    })
    entry = db.lookup("MyTel", "MyCam", "F550W")
    assert entry is not None


def test_db_load_user_config(tmp_path):
    import json
    cfg = {"MYTEL/CAM/FILT": {"pivot_wavelength_m": 600e-9, "bunit_raw": "Jy"}}
    cfg_path = tmp_path / "my_instruments.json"
    cfg_path.write_text(json.dumps(cfg))
    db = InstrumentDB()
    db.load_user_config(cfg_path)
    assert db.lookup(key="MYTEL/CAM/FILT") is not None


# ── Unit conversions ──────────────────────────────────────────────────────────

def test_erg_to_jy_order_of_magnitude():
    # HST F606W: PHOTFLAM ~7.7e-20 erg/s/cm^2/Å, 10 e-/s → f_λ=7.7e-19 → ~8.9e-15 Jy (fJy range)
    # f_ν = f_λ × λ² / c ; λ=589nm=5.89e-5 cm, λ²=3.47e-9 cm², c=3e10 cm/s → ×1e23 → Jy
    flux_erg = np.array([7.7e-19], dtype=np.float32)  # 10 e-/s × PHOTFLAM
    jy = erg_per_cm2_s_A_to_jy(flux_erg, 589e-9)
    assert jy[0] > 1e-16 and jy[0] < 1e-12  # femto-Jy range for faint HST source


def test_mjy_sr_to_jy_pixel():
    flux = np.array([1.0], dtype=np.float32)  # 1 MJy/sr
    pix_arcsec = 1.22
    jy = mjy_sr_to_jy_pixel(flux, pix_arcsec)
    pix_sr = (pix_arcsec / 206265.0) ** 2
    expected = 1e6 * pix_sr
    assert jy[0] == pytest.approx(expected, rel=1e-4)


# ── FluxCalibrator ────────────────────────────────────────────────────────────

def test_calibrator_passthrough():
    cal = FluxCalibrator()
    data = np.ones((10, 10), dtype=np.float32) * 100.0
    jy, note, meta = cal.calibrate(data, verbose=False)
    assert jy.shape == (10, 10)
    assert meta["CALTYPE"] == "NONE"


def test_calibrator_instrument_key():
    cal = FluxCalibrator()
    data = np.ones((10, 10), dtype=np.float32) * 10.0  # 10 MJy/sr
    jy, note, meta = cal.calibrate(
        data, instrument_key="Herschel/PACS/70um",
        wave_m=70e-6, verbose=False,
    )
    # 10 MJy/sr × (3.2 arcsec)^2 should give a small Jy value
    assert jy.mean() > 0
    assert "Jy" in meta.get("CALTYPE", "") or meta["CALTYPE"] in ("MJYSR", "DIRECT_JY")


# ── Aperture photometry ───────────────────────────────────────────────────────

def test_aperture_photometry_point_source(flat_flux):
    flux_net, flux_err, bg = aperture_photometry(
        flat_flux, cx=32, cy=32,
        aperture_r=4.0, bg_inner=7.0, bg_outer=12.0,
    )
    # point source adds ~500 Jy, background ~100 Jy/pix
    assert flux_net > 100.0
    assert flux_err > 0


def test_aperture_photometry_empty_field():
    flat = np.full((64, 64), 1.0, dtype=np.float32)
    flux_net, flux_err, bg = aperture_photometry(
        flat, cx=32, cy=32,
        aperture_r=4.0, bg_inner=7.0, bg_outer=12.0,
    )
    # background == source, net should be ~0
    assert abs(flux_net) < 5.0


def test_classify_point_source(flat_flux):
    stype, morph = classify_source(flat_flux, 32, 32, psf_fwhm_pix=3.0)
    assert stype in ("POINT", "COMPACT_EXT")
    assert "half_light_r_pix" in morph


def test_classify_diffuse_source():
    # create a broad extended blob
    rng = np.random.default_rng(123)
    data = rng.normal(100.0, 5.0, (64, 64)).astype(np.float32)
    y, x = np.ogrid[:64, :64]
    r2 = (x - 32)**2 + (y - 32)**2
    data += 300.0 * np.exp(-r2 / (2 * 15**2))  # sigma=15 pix
    stype, morph = classify_source(data, 32, 32, psf_fwhm_pix=3.0, aperture_r=25.0)
    assert stype in ("DIFFUSE", "COMPACT_EXT")


def test_stack_photometry(sed_cube):
    results = stack_photometry(
        sed_cube.layers, cx=32, cy=32,
        aperture_r=5.0, bg_inner=8.0, bg_outer=14.0,
    )
    assert len(results) == 4
    assert all(r.wave_m is not None for r in results)
    # results should be sorted by wavelength
    waves = [r.wave_m for r in results]
    assert waves == sorted(waves)


# ── YSO bolometric luminosity ─────────────────────────────────────────────────

def test_yso_lbol():
    # simple SED: 4 points across MIR, 500 pc distance
    from fita.photometry import SEDPoint
    pts = [
        SEDPoint(wave_m=3.6e-6, flux_jy=0.1, err_jy=0.01),
        SEDPoint(wave_m=4.5e-6, flux_jy=0.15, err_jy=0.01),
        SEDPoint(wave_m=8.0e-6, flux_jy=0.5, err_jy=0.05),
        SEDPoint(wave_m=24e-6,  flux_jy=2.0, err_jy=0.2),
    ]
    lbol, lbol_err = yso_bolometric_luminosity(pts, distance_pc=500.0)
    assert lbol > 0
    assert lbol < 1000  # sanity: a few L_sun for this SED


def test_constrain_distance():
    stars = [
        {"parallax_mas": 2.0, "parallax_err_mas": 0.1},
        {"parallax_mas": 2.1, "parallax_err_mas": 0.15},
        {"parallax_mas": 0.5, "parallax_err_mas": 0.4},  # low SNR, should be down-weighted
    ]
    d_pc, d_err = constrain_distance(stars, min_snr=5.0)
    assert d_pc is not None
    assert 450 < d_pc < 550  # near 500 pc


# ── DualSED ───────────────────────────────────────────────────────────────────

def test_dual_sed_from_layers(sed_cube):
    sed = DualSED.from_layers(sed_cube.layers, px=32, py=32, aperture_r=4.0)
    assert len(sed.wave_m) == 4
    assert len(sed.flux_phys_jy) == 4
    assert len(sed.lum_disp) == 4
    assert sed.wave_m[0] < sed.wave_m[-1]  # sorted ascending


def test_dual_sed_to_dict(sed_cube):
    sed = DualSED.from_layers(sed_cube.layers, px=32, py=32)
    d = sed.to_dict()
    assert "wave_m" in d
    assert "flux_phys_jy" in d
    assert "lum_disp" in d


# ── Surface histograms ────────────────────────────────────────────────────────

def test_luminosity_histogram(sed_cube):
    layer = sed_cube.layers[0]
    be_d, h_d, be_f, h_f = luminosity_histogram(layer, n_bins=64)
    assert len(be_d) == 65
    assert h_d.sum() > 0
    assert h_f.sum() > 0


def test_bolometric_surface_histogram(sed_cube):
    bc, hist = bolometric_surface_histogram(sed_cube.layers, n_bins=64)
    assert len(bc) == 64
    assert hist.sum() > 0


# ── Cumulative FITS header ────────────────────────────────────────────────────

def test_cumulative_header(sed_cube):
    hdr = build_cumulative_header(sed_cube.layers)
    assert hdr is not None
    # should have wavelength coverage keywords
    assert "EM_MIN" in hdr or "EM_NL" in hdr


# ── Excel SED export ──────────────────────────────────────────────────────────

def test_export_sed_xlsx(sed_cube, tmp_path):
    pytest.importorskip("openpyxl")
    sed = DualSED.from_layers(sed_cube.layers, px=32, py=32)
    out = tmp_path / "test_sed.xlsx"
    export_sed_xlsx(sed, str(out), include_histogram=True, layers=sed_cube.layers)
    assert out.exists()
    assert out.stat().st_size > 1000
