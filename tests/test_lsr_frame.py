"""v1.5 -- the spectral frame block, signed depths, and the three slice labels.

Author rulings of 2026-08-03 (A, B, C) plus D-14 and D-17. These tests assert
what a THIRD-PARTY READER would see, not merely that a function ran -- S11.5.
"""

import numpy as np
import pytest
from astropy.io import fits

from fita.io import write, read, read_stereo_geometry
from fita.layer import FITALayer
from fita.validate import validate
from fita import lsr, stereo


def _cube(tmp_path, vals, name="c.fita", **kw):
    layers = []
    for i, v in enumerate(vals):
        l = FITALayer.from_array(np.zeros((8, 8), dtype=np.float32),
                                 layer_id=i + 1, name="ch%d" % i)
        l.zdepth = v
        layers.append(l)
    p = tmp_path / name
    write(str(p), layers, **kw)
    return str(p)


# --- failure instance #10: negative depths were silently discarded ----------

def test_negative_depths_survive_a_round_trip(tmp_path):
    """The -1.0 sentinel was retired by D-5; the reader must not reinstate it.

    It discarded ANY negative value as absent. Harmless while S8.2 confined
    FITA_ZDP to [0,1] -- but v1.4 made physical depths legal, and velocity
    channels are signed by nature. Every approaching channel vanished.
    """
    p = _cube(tmp_path, (-40.0, -20.0, 0.0, 20.0, 40.0), zdp_unit="km/s",
              zdp_scale=4.0, field_dia=1200.0, field_unit="pc", specsys="LSRK")
    assert [l.zdepth for l in read(p)] == [-40.0, -20.0, 0.0, 20.0, 40.0]


def test_absent_depth_stays_absent(tmp_path):
    """D-5: omission is absence. Fixing the sentinel must not resurrect -1.0
    as a value, nor turn a genuinely absent depth into 0.0."""
    layers = [FITALayer.from_array(np.zeros((4, 4), dtype=np.float32),
                                   layer_id=1, name="none")]
    p = tmp_path / "absent.fita"
    write(str(p), layers)
    assert read(str(p))[0].zdepth is None


def test_a_signed_cube_renders_the_same_before_and_after_a_round_trip(tmp_path):
    """The defect's real signature: the summary line was unchanged while the
    geometry underneath was different. Compare the RENDERED result, not a flag."""
    vals = (-40.0, -20.0, 0.0, 20.0, 40.0)
    p = _cube(tmp_path, vals, zdp_unit="km/s", zdp_scale=4.0,
              field_dia=1200.0, field_unit="pc", specsys="LSRK")
    mem = [FITALayer.from_array(np.zeros((8, 8), dtype=np.float32),
                                layer_id=i + 1, name="ch%d" % i)
           for i in range(len(vals))]
    for l, v in zip(mem, vals):
        l.zdepth = v
    kw = dict(zdp_scale=4.0, field_dia=1200.0, zdp_unit="km/s")
    assert (stereo.stereo_offsets(read(p), **kw)
            == stereo.stereo_offsets(mem, **kw))


# --- ruling B: adopt the FITS WCS Paper III names ---------------------------

def test_spectral_frame_round_trips(tmp_path):
    p = _cube(tmp_path, (-40.0, 0.0, 40.0), zdp_unit="km/s", zdp_scale=4.0,
              field_dia=1200.0, field_unit="pc", specsys="LSRK",
              velosys=-14200.0, velosys_err=7000.0, ssysobs="TOPOCENT",
              restfrq=1.42040575e9, zdp_epistemic="INFERRED")
    g = read_stereo_geometry(p)
    assert g["specsys"] == "LSRK"
    assert g["velosys"] == -14200.0
    assert g["velosys_err"] == 7000.0
    assert g["ssysobs"] == "TOPOCENT"
    assert g["zdp_epistemic"] == "INFERRED"


def test_the_keywords_are_the_standard_fits_names_not_fita_twins(tmp_path):
    """Ruling B. A third-party reader looks for SPECSYS, not FITA_SPS."""
    p = _cube(tmp_path, (0.0,), zdp_unit="km/s", specsys="LSRK",
              velosys=-14200.0)
    with fits.open(p) as h:
        hdr = h[0].header
    assert "SPECSYS" in hdr and "VELOSYS" in hdr
    assert not any(k.startswith("FITA_SP") or k.startswith("FITA_VEL")
                   for k in hdr)


# --- D-17 / validator -------------------------------------------------------

def test_velosys_error_without_velosys_is_refused_by_the_writer(tmp_path):
    """An uncertainty on nothing is not a measurement -- the same reasoning
    that makes FITA_ZSC require FITA_FDI."""
    with pytest.raises(ValueError, match="uncertainty on nothing"):
        _cube(tmp_path, (0.0,), velosys_err=7000.0)


def test_velosys_without_specsys_fails_MUST(tmp_path):
    p = _cube(tmp_path, (0.0,))
    q = str(tmp_path / "nf.fita")
    with fits.open(p) as h:
        h[0].header["VELOSYS"] = -14200.0
        h.writeto(q, overwrite=True)
    bad = [f for f in validate(q).findings
           if not f.ok and f.clause == "S8.5" and f.severity == "MUST"]
    assert bad and "requires SPECSYS" in bad[0].message


def test_velocity_axis_without_a_frame_warns(tmp_path):
    """Without SPECSYS the labels cannot be recomputed under another
    convention, so the cube is not reproducible."""
    p = _cube(tmp_path, (-40.0, 0.0, 40.0), zdp_unit="km/s")
    msgs = [f.message for f in validate(p).findings
            if not f.ok and f.clause == "S8.5"]
    assert any("not reproducible" in m for m in msgs)


def test_lsr_uncertainty_wider_than_the_channel_warns(tmp_path):
    """The error bar entering the pipeline. Published V_sun spans 5.2-14.6
    km/s while cubes are channelised at 0.1-1 km/s."""
    p = _cube(tmp_path, (-40.0, 0.0, 40.0), zdp_unit="km/s", specsys="LSRK",
              velosys=-14200.0, velosys_err=7000.0,
              global_header={"CDELT3": 1000.0, "CUNIT3": "m/s"})
    msgs = [f.message for f in validate(p).findings
            if not f.ok and f.clause == "S8.5"]
    assert any("exceeds the channel width" in m for m in msgs)


def test_a_tight_lsr_uncertainty_does_not_warn(tmp_path):
    p = _cube(tmp_path, (-40.0, 0.0, 40.0), zdp_unit="km/s", specsys="LSRK",
              velosys=-14200.0, velosys_err=200.0,
              global_header={"CDELT3": 1000.0, "CUNIT3": "m/s"})
    msgs = [f.message for f in validate(p).findings
            if not f.ok and f.clause == "S8.5"]
    assert not any("exceeds the channel width" in m for m in msgs)


def test_epistemic_vocabulary_is_closed(tmp_path):
    with pytest.raises(ValueError, match="ESTABLISHED"):
        _cube(tmp_path, (0.0,), zdp_epistemic="GUESSED")


# --- D-14: the legend must not convert a non-metric axis into a distance ----

def test_velocity_legend_states_no_distance_claim():
    layers = []
    for i, v in enumerate((-40.0, 0.0, 40.0)):
        l = FITALayer.from_array(np.zeros((8, 8), dtype=np.float32),
                                 layer_id=i + 1, name="ch%d" % i)
        l.zdepth = v
        layers.append(l)
    out = stereo.describe(layers, 4.0, 1200.0, "pc", zdp_unit="km/s",
                          specsys="LSRK", velosys_kms=-14.2)
    assert "NON-METRIC" in out and "NOT a distance claim" in out
    # ruling A: all three labels, every time
    assert "MEASURED" in out and "INFERRED" in out and "ADOPTED" in out


def test_length_axis_still_reports_a_recoverable_distance():
    layers = []
    for i, d in enumerate((624.05, 1248.10, 2496.20)):
        l = FITALayer.from_array(np.zeros((8, 8), dtype=np.float32),
                                 layer_id=i + 1, name="d%d" % i)
        l.zdepth = d
        layers.append(l)
    out = stereo.describe(layers, 4.0, 2500.0, "pc", zdp_unit="pc")
    assert "METRIC" in out and "NON-METRIC" not in out
    assert "NOT a distance claim" not in out


@pytest.mark.parametrize("unit,metric", [
    ("pc", True), ("km", True), ("AU", True), ("m", True),
    ("km/s", False), ("Hz", False), ("MHz", False),
    ("deg", False), ("arcsec", False), (None, False),
])
def test_metric_classification(unit, metric):
    assert stereo._depth_axis_is_metric(unit) is metric


# --- the bibliography ships with the code ----------------------------------

def test_the_published_spread_is_carried_not_assumed():
    lo, hi, ptp = lsr.v_sun_spread()
    assert lo == pytest.approx(5.2) and hi == pytest.approx(14.6)
    assert ptp > 9.0
    assert len(lsr.DETERMINATIONS) >= 4
    for d in lsr.DETERMINATIONS:
        assert d.bibcode and d.ads_url.startswith("https://ui.adsabs.harvard.edu/")


def test_lsr_is_adopted_not_established():
    """Ruling C. Labelling it established would tell a reader the frame is a
    fixed fact; the spread above shows it is not."""
    assert lsr.LSR_STATUS == lsr.ADOPTED
    assert lsr.ADOPTED in lsr.VOCABULARY and len(lsr.VOCABULARY) == 4


def test_channel_width_verdict_boundaries():
    assert lsr.channel_width_verdict(7.0, 1.0)
    assert lsr.channel_width_verdict(0.2, 1.0) is None
    assert lsr.channel_width_verdict(None, 1.0) is None
    assert lsr.channel_width_verdict(7.0, None) is None


# --- failure instance #11: the truncated write that keeps its size ---------

def _truncate_and_pad(tmp_path, n_keep, repair_fitanl):
    """Reproduce the Frame15 shape: drop trailing layers, pad back to size."""
    layers = [FITALayer.from_array(np.zeros((16, 16), dtype=np.float32),
                                   layer_id=i + 1, name="L%d" % (i + 1))
              for i in range(4)]
    good = tmp_path / "good.fita"
    write(str(good), layers)
    full = good.stat().st_size

    p = tmp_path / ("t%d%s.fita" % (n_keep, repair_fitanl))
    with fits.open(str(good), memmap=False) as opened:
        keep = fits.HDUList([h.copy() for h in opened
                             if not (h.name.startswith(("FLUX_", "ALPHA_"))
                                     and int(h.name.split("_")[1]) > n_keep)])
        if repair_fitanl:
            keep[0].header["FITANL"] = n_keep
    keep.writeto(str(p), overwrite=True)
    with open(p, "ab") as f:
        f.write(b"\0" * (full - p.stat().st_size))
    assert p.stat().st_size == full        # the whole point: size is unchanged
    return str(good), str(p)


def test_truncated_write_is_caught_even_when_the_header_agrees(tmp_path):
    """ATOP, 2026-08-03: Frame15 held 19 of 26 FLUX extensions at exactly the
    size of the fourteen good copies, valid FITS, passing verify(). It was
    caught only because the dead writer left FITANL stale.

    Measured: repair FITANL to match the truncation and every other check
    passes. Orphan trailing blocks are the only surviving signal.
    """
    good, bad = _truncate_and_pad(tmp_path, 1, repair_fitanl=True)
    assert validate(good).is_core                       # control
    res = validate(bad)
    must = [f for f in res.findings if not f.ok and f.severity == "MUST"]
    assert not res.is_core
    assert any("orphan bytes" in f.message for f in must)


def test_stale_fitanl_truncation_is_caught_twice(tmp_path):
    """The actual Frame15 case: two independent MUST failures, not one."""
    _, bad = _truncate_and_pad(tmp_path, 1, repair_fitanl=False)
    must = [f for f in validate(bad).findings
            if not f.ok and f.severity == "MUST"]
    assert any("FITANL" in f.message for f in must)
    assert any("orphan bytes" in f.message for f in must)


def test_a_healthy_file_has_no_orphan_bytes(tmp_path):
    p = tmp_path / "clean.fita"
    write(str(p), [FITALayer.from_array(np.zeros((8, 8), dtype=np.float32),
                                        layer_id=1, name="a")])
    assert not [f for f in validate(str(p)).findings
                if not f.ok and "orphan bytes" in f.message]
