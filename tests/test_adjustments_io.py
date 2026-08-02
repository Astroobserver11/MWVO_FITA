"""FITA_ADJ serialisation -- decision D-3.

Adjustment layers were implemented and unit-tested from the beginning, but
nothing ever wrote them to a file: the capability existed in memory and
vanished on save.  `FITR_SPEC.md` S8 meanwhile delegated its display
mathematics to this HDU, which no file had ever contained -- the standard's
sharpest example of two specs individually coherent and jointly broken.

These tests assert the property that was missing: display state that survives
a save/load cycle *with its parameters intact*.  Asserting only that an
adjustment comes back would pass even against the old `to_records()`, which
emitted an empty parameter dict and silently restored defaults.
"""

import numpy as np
import pytest

pytest.importorskip("astropy")

from astropy.io import fits

from fita.adjustment import (
    AdjustmentStack, ADJ_REGISTRY,
    LevelsAdjustment, CurvesAdjustment, BrightnessAdjustment,
    FluxStretchAdjustment, BandMapAdjustment, FluxNormAdjustment,
)
from fita.io import write, read, read_adjustments
from fita.layer import FITALayer
from fita.validate import validate


def _layers(n=1):
    return [
        FITALayer.from_array(
            np.linspace(0, 1, 32 * 32, dtype=np.float32).reshape(32, 32),
            layer_id=i + 1, name="b%d" % (i + 1), wave_cval=656e-9)
        for i in range(n)
    ]


def _full_stack():
    return AdjustmentStack([
        LevelsAdjustment(in_black=0.1, in_white=0.9, gamma=2.2, name="lv"),
        CurvesAdjustment(control_points=[(0.0, 0.0), (0.3, 0.6), (1.0, 1.0)]),
        BrightnessAdjustment(brightness=0.2, contrast=-0.3),
        FluxStretchAdjustment(stretch_mode="log", asinh_a=0.25, power_exp=0.7),
        BandMapAdjustment(channel="G", layer_id=2),
        FluxNormAdjustment(response_curve=np.array([1.0, 0.8, 0.6]),
                           wavelengths=np.array([1e-6, 2e-6, 3e-6]),
                           wave_cval=2e-6),
    ])


def test_every_registered_type_round_trips_in_memory():
    back = AdjustmentStack.from_records(_full_stack().to_records())
    assert len(back.adjustments) == 6
    assert {a.adj_type for a in back.adjustments} <= set(ADJ_REGISTRY)


def test_parameters_survive_a_file_round_trip(tmp_path):
    """The headline: parameters, not just adjustment objects, come back."""
    path = tmp_path / "adj.fita"
    write(str(path), _layers(), overwrite=True, adjustments=_full_stack())
    a = read_adjustments(str(path)).adjustments

    assert a[0].in_black == pytest.approx(0.1)
    assert a[0].gamma == pytest.approx(2.2)
    assert a[0].name == "lv"
    assert a[1].control_points == [(0.0, 0.0), (0.3, 0.6), (1.0, 1.0)]
    assert a[2].brightness == pytest.approx(0.2)
    assert a[2].contrast == pytest.approx(-0.3)
    assert a[3].stretch_mode == "log"
    assert a[3].asinh_a == pytest.approx(0.25)
    assert a[4].channel == "G" and a[4].layer_id == 2


def test_numpy_arrays_return_as_arrays(tmp_path):
    """A response curve that comes back as a list is not a round trip."""
    path = tmp_path / "arr.fita"
    write(str(path), _layers(), overwrite=True, adjustments=_full_stack())
    norm = read_adjustments(str(path)).adjustments[5]
    assert isinstance(norm.response_curve, np.ndarray)
    assert np.allclose(norm.response_curve, [1.0, 0.8, 0.6])
    assert np.allclose(norm.wavelengths, [1e-6, 2e-6, 3e-6])


def test_disabled_flag_survives(tmp_path):
    """`enabled` is the adjustment-stack analogue of the lost `visible` flag."""
    stack = _full_stack()
    stack.adjustments[3].enabled = False
    path = tmp_path / "off.fita"
    write(str(path), _layers(), overwrite=True, adjustments=stack)
    assert read_adjustments(str(path)).adjustments[3].enabled is False


def test_order_is_preserved(tmp_path):
    """Adjustments are applied in sequence, so order is part of the data."""
    path = tmp_path / "order.fita"
    write(str(path), _layers(), overwrite=True, adjustments=_full_stack())
    back = read_adjustments(str(path)).adjustments
    assert [a.adj_type for a in back] == [a.adj_type for a in _full_stack().adjustments]


def test_params_column_is_sized_to_content_not_truncated(tmp_path):
    """A long response curve must not be silently clipped."""
    long_curve = np.linspace(1.0, 0.1, 200)
    stack = AdjustmentStack([
        FluxNormAdjustment(response_curve=long_curve,
                           wavelengths=np.linspace(1e-6, 3e-6, 200),
                           wave_cval=2e-6)])
    path = tmp_path / "long.fita"
    write(str(path), _layers(), overwrite=True, adjustments=stack)
    back = read_adjustments(str(path)).adjustments[0]
    assert len(back.response_curve) == 200
    assert np.allclose(back.response_curve, long_curve)


def test_common_parameters_are_typed_columns_not_json(tmp_path):
    """Author ruling Q1: a third-party FITS reader must be able to SEE the
    parameters, not just the file.  GAMMA=2.2 has to be readable as a number
    in the table, without parsing an opaque blob."""
    path = tmp_path / "typed.fita"
    write(str(path), _layers(), overwrite=True, adjustments=_full_stack())
    with fits.open(str(path)) as hdul:
        t = hdul["FITA_ADJ"]
        names = set(t.columns.names)
        assert {"GAMMA", "IN_BLACK", "BRIGHT", "CONTRAST",
                "STRETCH", "CHANNEL", "WAVE_CVAL"} <= names
        assert float(t.data["GAMMA"][0]) == pytest.approx(2.2)
        assert str(t.data["CHANNEL"][4]).strip() == "G"
        assert str(t.data["STRETCH"][3]).strip() == "log"


def test_inapplicable_columns_use_the_absence_convention(tmp_path):
    """D-5: NaN for floats, empty for text, when a column does not apply."""
    path = tmp_path / "absent.fita"
    write(str(path), _layers(), overwrite=True, adjustments=_full_stack())
    with fits.open(str(path)) as hdul:
        t = hdul["FITA_ADJ"].data
        assert np.isnan(float(t["GAMMA"][2]))          # BRIGHTNESS has no gamma
        assert str(t["CHANNEL"][0]).strip() == ""      # LEVELS has no channel


def test_params_json_carries_only_variable_length_fields(tmp_path):
    """Scalars belong in columns; JSON is for what has no fixed width."""
    import json
    path = tmp_path / "varlen.fita"
    write(str(path), _layers(), overwrite=True, adjustments=_full_stack())
    with fits.open(str(path)) as hdul:
        payloads = [str(v).strip() for v in hdul["FITA_ADJ"].data["PARAMS"]]
    assert payloads[0] == "", "LEVELS is all scalars; PARAMS should be empty"
    assert "control_points" in payloads[1]
    assert "gamma" not in payloads[0]
    keys = set()
    for p in payloads:
        if p:
            keys |= set(json.loads(p))
    assert keys <= {"control_points", "response_curve", "wavelengths"}


def test_adj_precedes_meta_in_hdu_order(tmp_path):
    """S4.1: FITA_ADJ at HDU N-1, FITA_META at HDU N."""
    path = tmp_path / "both.fita"
    write(str(path), _layers(), overwrite=True,
          adjustments=_full_stack(), provenance={"obs_id": "X"})
    with fits.open(str(path)) as hdul:
        names = [h.name for h in hdul]
    assert names[-2:] == ["FITA_ADJ", "FITA_META"]


def test_flux_is_untouched_by_an_adjustment_stack(tmp_path):
    """S5: adjustments are display state and MUST NOT alter FLUX_*."""
    layers = _layers()
    original = layers[0].flux_data.copy()
    path = tmp_path / "flux.fita"
    write(str(path), layers, overwrite=True, adjustments=_full_stack())
    back = read(str(path))[0].flux_data
    assert np.array_equal(back, original)


def test_absent_adj_gives_an_empty_stack(tmp_path):
    """Every file written before v1.1 has no FITA_ADJ; that must not raise."""
    path = tmp_path / "none.fita"
    write(str(path), _layers(), overwrite=True)
    assert read_adjustments(str(path)).adjustments == []


def test_unknown_adjustment_type_raises_rather_than_dropping():
    """S8.1's rule for unknown blend codes applies here too."""
    with pytest.raises(ValueError, match="unknown adjustment type"):
        AdjustmentStack.from_records(
            [{"order": 0, "type": "NOT_A_REAL_TYPE", "params": {}}])


def test_validator_rejects_a_malformed_adj_table(tmp_path):
    path = tmp_path / "bad.fita"
    write(str(path), _layers(), overwrite=True, adjustments=_full_stack())
    with fits.open(str(path), mode="update") as hdul:
        hdul["FITA_ADJ"].data["ADJ_TYPE"][0] = "BOGUS"
    report = validate(str(path))
    assert not report.is_core
    assert any("ADJ_TYPE" in str(f) for f in report.findings if not f.ok)


def test_cube_save_load_preserves_the_stack(tmp_path):
    from fita.cube import FITACube
    path = tmp_path / "cube.fita"
    FITACube(layers=_layers(), adjustments=_full_stack()).save(str(path))
    reloaded = FITACube.load(str(path))
    assert len(reloaded.adjustments.adjustments) == 6
    assert reloaded.adjustments.adjustments[0].gamma == pytest.approx(2.2)


def test_a_file_with_adjustments_still_reaches_full(tmp_path):
    path = tmp_path / "full.fita"
    write(str(path), _layers(), overwrite=True,
          adjustments=_full_stack(), provenance={"obs_id": "ADJ-FULL"})
    assert validate(str(path)).is_full
