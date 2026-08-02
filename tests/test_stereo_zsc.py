"""FITA_ZSC and phased stereography -- decision D-6.

S8.2 leaves the ZDP -> pixel mapping unspecified on purpose: it belongs to a
rendering job, not to a file.  The cost was that a rendered stereo pair carried
no record of the separation it was built with, so the depth stimulus could not
be measured afterwards.  D-6 records the scale actually used.

These tests pin the convention, because a convention stated only in prose
drifts from the code that implements it.
"""

import numpy as np
import pytest

pytest.importorskip("astropy")

from fita import stereo
from fita.io import write, read, read_zdp_scale
from fita.layer import FITALayer
from fita.spec import KW_ZSCALE
from fita.validate import validate


def _ism_layers():
    """The canonical S8.2 depth assignment: HI at the back, X-ray in front."""
    spec = [("HI-21cm", 0.0), ("H-alpha", 0.5), ("X-ray", 1.0), ("undepthed", None)]
    out = []
    for i, (name, z) in enumerate(spec):
        layer = FITALayer.from_array(np.zeros((16, 16), dtype=np.float32),
                                     layer_id=i + 1, name=name)
        layer.zdepth = z
        out.append(layer)
    return out


def test_zdp_zero_is_zero_parallax():
    """Background layers sit in the screen plane."""
    assert stereo.eye_offset(0.0, 24.0, stereo.LEFT) == 0.0
    assert stereo.eye_offset(0.0, 24.0, stereo.RIGHT) == 0.0


def test_full_range_separation_equals_zsc():
    """FITA_ZSC is defined as the parallax across the whole ZDP range."""
    left = stereo.eye_offset(1.0, 24.0, stereo.LEFT)
    right = stereo.eye_offset(1.0, 24.0, stereo.RIGHT)
    assert right - left == pytest.approx(24.0)


def test_eyes_are_symmetric_and_opposite():
    left = stereo.eye_offset(0.5, 24.0, stereo.LEFT)
    right = stereo.eye_offset(0.5, 24.0, stereo.RIGHT)
    assert left == pytest.approx(-6.0)
    assert right == pytest.approx(+6.0)


def test_absent_depth_gets_zero_parallax_not_a_guess():
    """Absence is encoded by omission (D-5); it must not become ZDP=0 by luck
    of a default, nor an error."""
    assert stereo.eye_offset(None, 24.0, stereo.RIGHT) == 0.0


def test_negative_scale_inverts_depth_sense():
    assert stereo.eye_offset(1.0, -24.0, stereo.RIGHT) == pytest.approx(-12.0)


def test_max_parallax_reports_the_fusable_separation():
    layers = _ism_layers()
    assert stereo.max_parallax(layers, 24.0) == pytest.approx(24.0)
    # Half-depth cube: the widest separation is genuinely smaller than |ZSC|.
    for l in layers:
        if l.zdepth is not None:
            l.zdepth = min(l.zdepth, 0.5)
    assert stereo.max_parallax(layers, 24.0) == pytest.approx(12.0)


def test_offsets_cover_every_layer():
    rows = stereo.stereo_offsets(_ism_layers(), 24.0)
    assert len(rows) == 4
    assert rows[0]["zdepth"] == 0.0
    assert rows[3]["zdepth"] is None


def test_zsc_round_trips_through_a_file(tmp_path):
    path = tmp_path / "zsc.fita"
    write(str(path), _ism_layers(), overwrite=True, zdp_scale=24.0)
    assert read_zdp_scale(str(path)) == pytest.approx(24.0)


def test_absent_zsc_reads_as_none_not_zero(tmp_path):
    """None means no renderer recorded a geometry; 0.0 means one did and it
    was flat.  Collapsing them would erase that distinction."""
    path = tmp_path / "nozsc.fita"
    write(str(path), _ism_layers(), overwrite=True)
    assert read_zdp_scale(str(path)) is None


def test_explicit_zero_is_preserved(tmp_path):
    path = tmp_path / "flat.fita"
    write(str(path), _ism_layers(), overwrite=True, zdp_scale=0.0)
    assert read_zdp_scale(str(path)) == 0.0


def test_zsc_does_not_break_conformance(tmp_path):
    path = tmp_path / "ok.fita"
    write(str(path), _ism_layers(), overwrite=True, zdp_scale=24.0)
    assert validate(str(path)).is_core


def test_validator_flags_a_parallax_that_applies_to_nothing(tmp_path):
    """A recorded separation on a cube with no depth is a stimulus that was
    never applied."""
    from astropy.io import fits
    layers = _ism_layers()
    for l in layers:
        l.zdepth = None
    path = tmp_path / "orphan.fita"
    write(str(path), layers, overwrite=True, zdp_scale=24.0)
    report = validate(str(path))
    assert report.is_core                       # SHOULD, not MUST
    assert any("applies to nothing" in str(f) for f in report.findings if not f.ok)


def test_validator_rejects_a_non_numeric_zsc(tmp_path):
    """astropy refuses to write NaN/inf into a header, so the reachable
    corruption is a non-numeric card -- from a hand edit or a foreign writer."""
    from astropy.io import fits
    path = tmp_path / "bad.fita"
    write(str(path), _ism_layers(), overwrite=True, zdp_scale=24.0)
    with fits.open(str(path), mode="update") as hdul:
        hdul[0].header[KW_ZSCALE] = "not-a-number"
    report = validate(str(path))
    assert not report.is_core
    assert any("finite number" in str(f) for f in report.findings if not f.ok)


def test_describe_reports_the_geometry(tmp_path):
    text = stereo.describe(_ism_layers(), 24.0)
    assert "FITA_ZSC" in text
    assert "max separation" in text
    assert "ZDP absent" in text


# ── reference plane (author ruling Q2) ───────────────────────────────────────

def test_reference_plane_defaults_to_background_at_screen():
    """Omitted FITA_ZRF means 0.0 -- the convention's stated default."""
    assert stereo.eye_offset(0.0, 24.0, stereo.RIGHT) == 0.0
    assert stereo.eye_offset(1.0, 24.0, stereo.RIGHT) == pytest.approx(12.0)


def test_reference_plane_puts_layers_behind_the_screen():
    """The point of an explicit reference plane: depth can be spent in BOTH
    directions instead of always pushing everything forward."""
    # H-alpha at the screen: HI (ZDP=0) must recede, X-ray (ZDP=1) advance.
    behind = stereo.eye_offset(0.0, 24.0, stereo.RIGHT, zdp_ref=0.5)
    at = stereo.eye_offset(0.5, 24.0, stereo.RIGHT, zdp_ref=0.5)
    front = stereo.eye_offset(1.0, 24.0, stereo.RIGHT, zdp_ref=0.5)
    assert behind == pytest.approx(-6.0)
    assert at == 0.0
    assert front == pytest.approx(+6.0)
    assert behind < at < front


def test_reference_plane_halves_the_budget_when_centred():
    layers = _ism_layers()
    assert stereo.max_parallax(layers, 24.0, zdp_ref=0.0) == pytest.approx(24.0)
    assert stereo.max_parallax(layers, 24.0, zdp_ref=0.5) == pytest.approx(12.0)


def test_reference_plane_round_trips(tmp_path):
    from fita.io import read_stereo_geometry
    path = tmp_path / "ref.fita"
    write(str(path), _ism_layers(), overwrite=True, zdp_scale=24.0, zdp_ref=0.5)
    geom = read_stereo_geometry(str(path))
    assert geom["zdp_ref"] == pytest.approx(0.5)
    assert geom["zdp_ref_explicit"] is True


def test_absent_reference_plane_reports_the_default_but_flags_it(tmp_path):
    """0.0-by-default and 0.0-because-someone-said-so are different facts."""
    from fita.io import read_stereo_geometry
    path = tmp_path / "noref.fita"
    write(str(path), _ism_layers(), overwrite=True, zdp_scale=24.0)
    geom = read_stereo_geometry(str(path))
    assert geom["zdp_ref"] == 0.0
    assert geom["zdp_ref_explicit"] is False


def test_validator_flags_a_reference_plane_outside_the_zdp_domain(tmp_path):
    from astropy.io import fits
    from fita.spec import KW_ZREF
    path = tmp_path / "badref.fita"
    write(str(path), _ism_layers(), overwrite=True, zdp_scale=24.0, zdp_ref=0.5)
    with fits.open(str(path), mode="update") as hdul:
        hdul[0].header[KW_ZREF] = 3.0
    report = validate(str(path))
    assert any("ZDP domain" in str(f) for f in report.findings if not f.ok)


# ── angular measure (author ruling Q2) ───────────────────────────────────────

def _wcs_layer():
    from astropy.wcs import WCS
    w = WCS(naxis=2)
    w.wcs.crpix = [8, 8]
    w.wcs.cdelt = [-0.001, 0.001]          # 3.6 arcsec/px
    w.wcs.crval = [299.9, 22.7]
    w.wcs.ctype = ["RA---TAN", "DEC--TAN"]
    layer = FITALayer.from_array(np.zeros((16, 16), dtype=np.float32),
                                 layer_id=1, name="wcs", wcs=w)
    layer.zdepth = 1.0
    return layer


def test_angular_measure_is_deduced_from_wcs():
    layer = _wcs_layer()
    assert stereo.pixel_scale_arcsec(layer) == pytest.approx(3.6)
    assert stereo.angular_parallax([layer], 24.0) == pytest.approx(86.4)


def test_angular_measure_is_none_without_wcs():
    """None, not a fabricated number: an invented pixel scale would turn an
    honest absence into a false angular measurement."""
    assert stereo.angular_parallax(_ism_layers(), 24.0) is None


def test_angular_measure_round_trips(tmp_path):
    from fita.io import read_stereo_geometry
    path = tmp_path / "ang.fita"
    write(str(path), _ism_layers(), overwrite=True,
          zdp_scale=24.0, zdp_angular=86.4)
    assert read_stereo_geometry(str(path))["zdp_angular"] == pytest.approx(86.4)


def test_pixel_only_record_is_flagged_when_no_angle_is_deducible(tmp_path):
    """Q2: a bare pixel count is complete only where no model can be had."""
    path = tmp_path / "pixonly.fita"
    write(str(path), _ism_layers(), overwrite=True, zdp_scale=24.0)
    report = validate(str(path))
    assert report.is_core                                  # SHOULD, not MUST
    assert any("pixel-only" in str(f) for f in report.findings if not f.ok)


def test_no_warning_when_the_angle_is_deducible_from_context(tmp_path):
    """A WCS *is* the context the ruling means, so FITA_ZAN may be omitted."""
    path = tmp_path / "wcs.fita"
    write(str(path), [_wcs_layer()], overwrite=True, zdp_scale=24.0)
    report = validate(str(path))
    assert not any("pixel-only" in str(f) for f in report.findings if not f.ok)


def test_no_warning_when_the_angle_is_recorded_outright(tmp_path):
    path = tmp_path / "recorded.fita"
    write(str(path), _ism_layers(), overwrite=True,
          zdp_scale=24.0, zdp_angular=86.4)
    report = validate(str(path))
    assert not any("pixel-only" in str(f) for f in report.findings if not f.ok)


def test_describe_names_the_provenance_of_the_angle():
    recorded = stereo.describe(_ism_layers(), 24.0, 0.0, zdp_angular=86.4)
    assert "recorded" in recorded
    deduced = stereo.describe([_wcs_layer()], 24.0)
    assert "deduced from WCS" in deduced
    neither = stereo.describe(_ism_layers(), 24.0)
    assert "pixel-only" in neither
