"""FITA_ZSC and phased stereography -- decision D-6, as ruled in v1.4.

S8.2 leaves the ZDP -> pixel mapping unspecified on purpose: it belongs to a
rendering job, not to a file.  The cost was that a rendered stereo pair carried
no record of the separation it was built with, so the depth stimulus could not
be measured afterwards.  D-6 records the scale actually used.

**v1.4 supersedes the pixel convention.**  The principal ruled, 2026-08-02:

    "The scale of the Stereogram is a percentage of the diameter of the field
    under study, made explicit as a measure in units practical to the subject."

So the scale is relative (FITA_ZSC, a percentage) and the field is absolute
(FITA_FDI in FITA_FDU) -- together a metric chain.  A pixel count could never
supply one, being a property of a rendering target the file cannot know.

These tests pin the convention, because a convention stated only in prose
drifts from the code that implements it.  Throughout: a 1200 pc field at
FITA_ZSC = 4 %, so the full-range parallax is 48 pc and each eye takes 24.
"""

import numpy as np
import pytest

pytest.importorskip("astropy")

from fita import stereo
from fita.io import write, read, read_zdp_scale
from fita.layer import FITALayer
from fita.spec import KW_ZSCALE
from fita.validate import validate

FDI = 1200.0        # pc -- the field under study
FDU = "pc"
ZSC = 4.0           # per cent of FDI  ->  48 pc of full-range parallax
FULL = 48.0         # (ZSC / 100) * FDI
HALF = 24.0         # per eye at the full range, reference plane at 0


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


def _field(**kw):
    """The keyword set every conformant FITA_ZSC writer must now supply."""
    base = dict(zdp_scale=ZSC, field_dia=FDI, field_unit=FDU)
    base.update(kw)
    return base


# ── the parallax formula ─────────────────────────────────────────────────────

def test_zdp_zero_is_zero_parallax():
    """Background layers sit in the screen plane."""
    assert stereo.eye_offset(0.0, ZSC, FDI, stereo.LEFT) == 0.0
    assert stereo.eye_offset(0.0, ZSC, FDI, stereo.RIGHT) == 0.0


def test_full_range_separation_is_the_declared_percentage_of_the_field():
    """FITA_ZSC is a percentage of FITA_FDI, and the result is in FITA_FDU."""
    left = stereo.eye_offset(1.0, ZSC, FDI, stereo.LEFT)
    right = stereo.eye_offset(1.0, ZSC, FDI, stereo.RIGHT)
    assert right - left == pytest.approx(FULL)


def test_eyes_are_symmetric_and_opposite():
    left = stereo.eye_offset(0.5, ZSC, FDI, stereo.LEFT)
    right = stereo.eye_offset(0.5, ZSC, FDI, stereo.RIGHT)
    assert left == pytest.approx(-right)


def test_the_same_percentage_on_a_different_field_gives_a_different_measure():
    """The point of the ruling: the scale is relative, the stimulus is not.

    4 % of a 1200 pc dust cube and 4 % of a 0.35 deg sky field are the same
    scale and completely different measurements.  A pixel count could not tell
    them apart, which is why it was superseded.
    """
    cube = stereo.eye_offset(1.0, ZSC, 1200.0, stereo.RIGHT)
    sky = stereo.eye_offset(1.0, ZSC, 0.35, stereo.RIGHT)
    assert cube == pytest.approx(24.0)          # pc
    assert sky == pytest.approx(0.007)          # deg
    assert cube != sky


def test_absent_depth_gets_zero_parallax_not_a_guess():
    """Absence is encoded by omission (D-5); it must not become ZDP=0 by luck
    of a default, nor an error."""
    assert stereo.eye_offset(None, ZSC, FDI, stereo.RIGHT) == 0.0


def test_negative_scale_inverts_depth_sense():
    assert stereo.eye_offset(1.0, -ZSC, FDI, stereo.RIGHT) == pytest.approx(-HALF)


def test_max_parallax_reports_the_fusable_separation():
    layers = _ism_layers()
    assert stereo.max_parallax(layers, ZSC, FDI) == pytest.approx(FULL)
    # Half-depth cube: the widest separation is genuinely smaller.
    for l in layers:
        if l.zdepth is not None:
            l.zdepth = min(l.zdepth, 0.5)
    assert stereo.max_parallax(layers, ZSC, FDI) == pytest.approx(FULL / 2)


def test_offsets_cover_every_layer():
    rows = stereo.stereo_offsets(_ism_layers(), ZSC, FDI)
    assert len(rows) == 4
    assert rows[0]["zdepth"] == 0.0
    assert rows[3]["zdepth"] is None


# ── FITA_ZDU: physical depth units (N-1) ─────────────────────────────────────

def _edenhofer_layers():
    """The distance bins the eight archived ATOP stereo files actually carry."""
    out = []
    for i, d in enumerate((624.05, 1248.10, 2496.20)):
        layer = FITALayer.from_array(np.zeros((16, 16), dtype=np.float32),
                                     layer_id=i + 1, name=f"shell_{d:.0f}pc")
        layer.zdepth = d
        out.append(layer)
    return out


def test_dimensionless_depths_pass_through_unchanged():
    """No FITA_ZDU means the depths are already normalised -- the strict case."""
    assert stereo.normalise_depths(_ism_layers()) == [0.0, 0.5, 1.0, None]


def test_physical_depths_normalise_over_the_range_actually_present():
    """624/1248/2496 pc is a real depth range, not a violation of [0,1]."""
    norm = stereo.normalise_depths(_edenhofer_layers(), zdp_unit="pc")
    assert norm[0] == pytest.approx(0.0)
    assert norm[2] == pytest.approx(1.0)
    assert 0.0 < norm[1] < 1.0


def test_normalisation_preserves_absence():
    """A layer with no depth must not acquire one by being normalised."""
    layers = _edenhofer_layers()
    layers[1].zdepth = None
    assert stereo.normalise_depths(layers, zdp_unit="pc")[1] is None


def test_a_single_shell_is_not_a_depth_range():
    """One distinct depth normalises to the screen plane, not to a ZeroDivision
    and not to 1.0 -- one shell is not a range, and saying so is honest."""
    layers = _edenhofer_layers()[:1]
    assert stereo.normalise_depths(layers, zdp_unit="pc") == [0.0]


def test_parsec_depths_produce_the_same_parallax_as_their_normalised_twins():
    """The unit declares meaning; it must not change the stimulus."""
    physical = stereo.max_parallax(_edenhofer_layers(), ZSC, FDI, zdp_unit="pc")
    assert physical == pytest.approx(FULL)


def test_zdu_round_trips_and_stays_conformant(tmp_path):
    """N-1 resolved: parsecs in FITA_ZDP are legal once FITA_ZDU declares them."""
    from fita.io import read_stereo_geometry
    path = tmp_path / "zdu.fita"
    write(str(path), _edenhofer_layers(), overwrite=True,
          **_field(field_dia=2500.0, zdp_unit="pc"))
    assert read_stereo_geometry(str(path))["zdp_unit"] == "pc"
    assert validate(str(path)).is_core


def test_parsec_depths_without_zdu_are_non_conformant(tmp_path):
    """The defect N-1 actually names: not a wrong value, a missing declaration.

    The same file that passes with FITA_ZDU must fail without it, or the
    keyword would be decoration rather than the thing that makes the parsecs
    legible to a reader.
    """
    from astropy.io import fits
    path = tmp_path / "nozdu.fita"
    write(str(path), _edenhofer_layers(), overwrite=True,
          **_field(field_dia=2500.0, zdp_unit="pc"))
    with fits.open(str(path), mode="update") as hdul:
        del hdul[0].header["FITA_ZDU"]
    report = validate(str(path))
    assert not report.is_core
    assert any("FITA_ZDP in [0,1]" in str(f) for f in report.findings if not f.ok)


def test_zdu_must_be_a_real_fits_unit(tmp_path):
    from astropy.io import fits
    path = tmp_path / "badunit.fita"
    write(str(path), _edenhofer_layers(), overwrite=True,
          **_field(field_dia=2500.0, zdp_unit="pc"))
    with fits.open(str(path), mode="update") as hdul:
        hdul[0].header["FITA_ZDU"] = "parsecs-ish"
    assert not validate(str(path)).is_core


# ── round-tripping the geometry ──────────────────────────────────────────────

def test_zsc_round_trips_through_a_file(tmp_path):
    path = tmp_path / "zsc.fita"
    write(str(path), _ism_layers(), overwrite=True, **_field())
    assert read_zdp_scale(str(path)) == pytest.approx(ZSC)


def test_the_field_round_trips_with_the_scale(tmp_path):
    """A scale that survives without its field is a percentage of nothing."""
    from fita.io import read_stereo_geometry
    path = tmp_path / "field.fita"
    write(str(path), _ism_layers(), overwrite=True, **_field())
    geom = read_stereo_geometry(str(path))
    assert geom["field_dia"] == pytest.approx(FDI)
    assert geom["field_unit"] == FDU


def test_absent_zsc_reads_as_none_not_zero(tmp_path):
    """None means no renderer recorded a geometry; 0.0 means one did and it
    was flat.  Collapsing them would erase that distinction."""
    path = tmp_path / "nozsc.fita"
    write(str(path), _ism_layers(), overwrite=True)
    assert read_zdp_scale(str(path)) is None


def test_explicit_zero_is_preserved(tmp_path):
    path = tmp_path / "flat.fita"
    write(str(path), _ism_layers(), overwrite=True, **_field(zdp_scale=0.0))
    assert read_zdp_scale(str(path)) == 0.0


def test_zsc_does_not_break_conformance(tmp_path):
    path = tmp_path / "ok.fita"
    write(str(path), _ism_layers(), overwrite=True, **_field())
    assert validate(str(path)).is_core


# ── the clause that enforces the ruling ──────────────────────────────────────

def test_writer_refuses_a_scale_with_no_field():
    """Refuse at the writer, not only at the validator.

    A writer that happily emits a file its own validator rejects is this
    project's characteristic defect -- silent loss that looks like success.
    """
    with pytest.raises(ValueError, match="percentage of nothing"):
        write("unused.fita", _ism_layers(), overwrite=True, zdp_scale=ZSC)


def test_validator_rejects_a_scale_with_no_field(tmp_path):
    """A third-party writer can still produce one, so the MUST must exist."""
    from astropy.io import fits
    path = tmp_path / "nofield.fita"
    write(str(path), _ism_layers(), overwrite=True, **_field())
    with fits.open(str(path), mode="update") as hdul:
        del hdul[0].header["FITA_FDI"]
    report = validate(str(path))
    assert not report.is_core
    assert any("percentage of nothing" in str(f) for f in report.findings if not f.ok)


def test_validator_rejects_a_scale_with_no_field_unit(tmp_path):
    """A number without a unit is not a measure practical to the subject."""
    from astropy.io import fits
    path = tmp_path / "nounit.fita"
    write(str(path), _ism_layers(), overwrite=True, **_field())
    with fits.open(str(path), mode="update") as hdul:
        del hdul[0].header["FITA_FDU"]
    assert not validate(str(path)).is_core


def test_validator_rejects_a_non_positive_field_diameter(tmp_path):
    from astropy.io import fits
    path = tmp_path / "zerofield.fita"
    write(str(path), _ism_layers(), overwrite=True, **_field())
    with fits.open(str(path), mode="update") as hdul:
        hdul[0].header["FITA_FDI"] = 0.0
    assert not validate(str(path)).is_core


def test_validator_flags_a_parallax_that_applies_to_nothing(tmp_path):
    """A recorded separation on a cube with no depth is a stimulus that was
    never applied."""
    layers = _ism_layers()
    for l in layers:
        l.zdepth = None
    path = tmp_path / "orphan.fita"
    write(str(path), layers, overwrite=True, **_field())
    report = validate(str(path))
    assert report.is_core                       # SHOULD, not MUST
    assert any("applies to nothing" in str(f) for f in report.findings if not f.ok)


def test_validator_rejects_a_non_numeric_zsc(tmp_path):
    """astropy refuses to write NaN/inf into a header, so the reachable
    corruption is a non-numeric card -- from a hand edit or a foreign writer."""
    from astropy.io import fits
    path = tmp_path / "bad.fita"
    write(str(path), _ism_layers(), overwrite=True, **_field())
    with fits.open(str(path), mode="update") as hdul:
        hdul[0].header[KW_ZSCALE] = "not-a-number"
    report = validate(str(path))
    assert not report.is_core
    assert any("finite number" in str(f) for f in report.findings if not f.ok)


def test_describe_reports_the_geometry_in_subject_units_not_pixels():
    text = stereo.describe(_ism_layers(), ZSC, FDI, FDU)
    assert "FITA_ZSC" in text
    assert "FITA_FDI" in text
    assert "max separation" in text
    assert "ZDP absent" in text
    assert "pc" in text
    assert " px" not in text          # ruling S4.5: never report pixels


def test_describe_names_the_depth_unit_when_there_is_one():
    text = stereo.describe(_edenhofer_layers(), ZSC, 2500.0, FDU, zdp_unit="pc")
    assert "FITA_ZDU = pc" in text
    plain = stereo.describe(_ism_layers(), ZSC, FDI, FDU)
    assert "dimensionless" in plain


# ── reference plane (author ruling Q2, unchanged by v1.4) ────────────────────

def test_reference_plane_defaults_to_background_at_screen():
    """Omitted FITA_ZRF means 0.0 -- the convention's stated default."""
    assert stereo.eye_offset(0.0, ZSC, FDI, stereo.RIGHT) == 0.0
    assert stereo.eye_offset(1.0, ZSC, FDI, stereo.RIGHT) == pytest.approx(HALF)


def test_reference_plane_puts_layers_behind_the_screen():
    """The point of an explicit reference plane: depth can be spent in BOTH
    directions instead of always pushing everything forward."""
    # H-alpha at the screen: HI (ZDP=0) must recede, X-ray (ZDP=1) advance.
    behind = stereo.eye_offset(0.0, ZSC, FDI, stereo.RIGHT, zdp_ref=0.5)
    at = stereo.eye_offset(0.5, ZSC, FDI, stereo.RIGHT, zdp_ref=0.5)
    front = stereo.eye_offset(1.0, ZSC, FDI, stereo.RIGHT, zdp_ref=0.5)
    assert behind == pytest.approx(-HALF / 2)
    assert at == 0.0
    assert front == pytest.approx(+HALF / 2)
    assert behind < at < front


def test_reference_plane_halves_the_budget_when_centred():
    layers = _ism_layers()
    assert stereo.max_parallax(layers, ZSC, FDI, zdp_ref=0.0) == pytest.approx(FULL)
    assert stereo.max_parallax(layers, ZSC, FDI, zdp_ref=0.5) == pytest.approx(FULL / 2)


def test_reference_plane_round_trips(tmp_path):
    from fita.io import read_stereo_geometry
    path = tmp_path / "ref.fita"
    write(str(path), _ism_layers(), overwrite=True, **_field(zdp_ref=0.5))
    geom = read_stereo_geometry(str(path))
    assert geom["zdp_ref"] == pytest.approx(0.5)
    assert geom["zdp_ref_explicit"] is True


def test_absent_reference_plane_reports_the_default_but_flags_it(tmp_path):
    """0.0-by-default and 0.0-because-someone-said-so are different facts."""
    from fita.io import read_stereo_geometry
    path = tmp_path / "noref.fita"
    write(str(path), _ism_layers(), overwrite=True, **_field())
    geom = read_stereo_geometry(str(path))
    assert geom["zdp_ref"] == 0.0
    assert geom["zdp_ref_explicit"] is False


def test_validator_flags_a_reference_plane_outside_the_zdp_domain(tmp_path):
    from astropy.io import fits
    from fita.spec import KW_ZREF
    path = tmp_path / "badref.fita"
    write(str(path), _ism_layers(), overwrite=True, **_field(zdp_ref=0.5))
    with fits.open(str(path), mode="update") as hdul:
        hdul[0].header[KW_ZREF] = 3.0
    report = validate(str(path))
    assert any("ZDP domain" in str(f) for f in report.findings if not f.ok)


# ── FITA_ZAN: retired by dissolution (v1.4) ──────────────────────────────────

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


def test_pixel_scale_survives_for_the_renderer():
    """The deduction FITA_ZAN needed is gone; the pixel scale itself is not.
    A renderer still has to get from a subject unit onto a screen."""
    assert stereo.pixel_scale_arcsec(_wcs_layer()) == pytest.approx(3.6)


def test_pixel_scale_is_none_without_wcs():
    """None, not a fabricated number: an invented pixel scale would turn an
    honest absence into a false measurement."""
    assert stereo.pixel_scale_arcsec(_ism_layers()[0]) is None


def test_display_conversion_is_the_renderers_job():
    """dx is in FITA_FDU; pixels come from a canvas the file does not know."""
    dx = stereo.eye_offset(1.0, ZSC, FDI, stereo.RIGHT)
    assert stereo.to_display_pixels(dx, FDI, 1000.0) == pytest.approx(20.0)


def test_a_retired_zan_still_reads(tmp_path):
    """D-1 grandfathering: pre-v1.4 files carry FITA_ZAN and must not choke."""
    from fita.io import read_stereo_geometry
    path = tmp_path / "zan.fita"
    write(str(path), _ism_layers(), overwrite=True, **_field(zdp_angular=86.4))
    assert read_stereo_geometry(str(path))["zdp_angular"] == pytest.approx(86.4)


def test_a_retired_zan_is_flagged_but_not_fatal(tmp_path):
    """SHOULD, not MUST: the file is still readable and still conformant at
    CORE.  Retirement is a message to writers, not a condemnation of files."""
    path = tmp_path / "zan2.fita"
    write(str(path), _ism_layers(), overwrite=True, **_field(zdp_angular=86.4))
    report = validate(str(path))
    assert report.is_core
    assert any("retired in v1.4" in str(f) for f in report.findings if not f.ok)


def test_the_library_no_longer_emits_zan(tmp_path):
    """Writers should not emit it -- so the default path must not."""
    from astropy.io import fits
    path = tmp_path / "clean.fita"
    write(str(path), _ism_layers(), overwrite=True, **_field())
    with fits.open(str(path)) as hdul:
        assert "FITA_ZAN" not in hdul[0].header
