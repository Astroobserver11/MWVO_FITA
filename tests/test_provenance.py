"""Tests for ObsCore v1.1 provenance -- decision D-4, defect R2.

Two things are being guarded here:

  * that FITA_META can be produced *through the documented API* at all.  It
    could not before v1.1: make_meta_hdu() worked, but io.write() had no
    parameter to accept its result, so the provenance model was unreachable
    and FITA_META was absent from every archived file.

  * that the table is ObsCore v1.1 *complete and annotated*, not merely
    present.  The withdrawn "ObsCore compliant" claim was false on both
    counts: nine mandatory columns were missing, and the per-column UCDs were
    defined in the source but never written to the file.
"""

import numpy as np
import pytest

pytest.importorskip("astropy")

from astropy.io import fits

from fita.io import write
from fita.layer import FITALayer
from fita.validate import validate
from fita.ivoa import make_meta_hdu, meta_from_layers, ACCESS_FORMAT


# ObsCore DM v1.1 mandatory columns -- the same set the validator enforces.
OBSCORE_MANDATORY = {
    "obs_publisher_did", "obs_collection", "obs_id",
    "s_ra", "s_dec", "s_region", "s_fov", "s_xel1", "s_xel2",
    "t_min", "t_max", "t_exptime", "t_xel",
    "em_min", "em_max", "em_xel", "em_res_power",
    "o_ucd", "pol_states", "facility_name", "instrument_name",
    "dataproduct_type", "calib_level", "access_url", "access_format",
    "access_estsize",
}


def _layers(n=3):
    waves = [656e-9, 1.25e-6, 2.2e-6][:n]
    return [
        FITALayer.from_array(
            np.linspace(0, 1, 32 * 48, dtype=np.float32).reshape(32, 48),
            layer_id=i + 1, name="band%d" % (i + 1), wave_cval=w)
        for i, w in enumerate(waves)
    ]


def test_all_obscore_v12_mandatory_columns_present():
    hdu = make_meta_hdu(obs_id="X")
    missing = OBSCORE_MANDATORY - set(hdu.columns.names)
    assert not missing, "missing ObsCore v1.1 mandatory columns: %s" % sorted(missing)


def test_every_column_carries_a_tucd():
    """S9: column UCDs MUST be written as TUCDn, not UCD1/UCDXXXXX."""
    hdu = make_meta_hdu(obs_id="X")
    tucds = [k for k in hdu.header if k.startswith("TUCD")]
    assert len(tucds) == len(hdu.columns.names)


def test_access_format_is_not_the_unregistered_type():
    """S3: 'application/fits+alpha' is not registered and must not be emitted."""
    hdu = make_meta_hdu(obs_id="X")
    assert ACCESS_FORMAT == "application/fits"
    assert str(hdu.data["access_format"][0]).strip() != "application/fits+alpha"


def test_meta_from_layers_derives_axis_counts_and_coverage():
    layers = _layers(3)
    hdu = meta_from_layers(layers, obs_id="X")
    d = hdu.data
    assert int(d["s_xel1"][0]) == 48 and int(d["s_xel2"][0]) == 32
    assert int(d["em_xel"][0]) == 3
    assert float(d["em_min"][0]) == pytest.approx(656e-9)
    assert float(d["em_max"][0]) == pytest.approx(2.2e-6)


def test_write_accepts_provenance_dict_and_reaches_full(tmp_path):
    """The headline: a file written through the public API validates FITA-FULL."""
    path = tmp_path / "full.fita"
    write(str(path), _layers(), overwrite=True, provenance=dict(
        obs_id="TEST-001", facility="SkyView", instrument="DSS2",
        target="M27", ra=299.9, dec=22.7, calib_level=2, estsize_kb=64,
        extra={
            "obs_publisher_did": "ivo://mwvo/fita?TEST-001",
            "obs_collection": "MWVO",
            "s_region": "POLYGON ICRS 299.8 22.6 300.0 22.6 300.0 22.8",
        }))
    report = validate(str(path))
    assert report.is_core
    assert report.is_full, "expected FITA-FULL, got %s" % report.level


def test_write_accepts_a_prebuilt_hdu(tmp_path):
    path = tmp_path / "hdu.fita"
    hdu = meta_from_layers(_layers(), obs_id="PREBUILT")
    write(str(path), _layers(), overwrite=True, provenance=hdu)
    with fits.open(str(path)) as hdul:
        assert "FITA_META" in [h.name for h in hdul]
        assert str(hdul["FITA_META"].data["obs_id"][0]).strip() == "PREBUILT"


def test_meta_is_the_last_hdu(tmp_path):
    """S4.1 canonical layout puts FITA_META last."""
    path = tmp_path / "order.fita"
    write(str(path), _layers(), overwrite=True, provenance={"obs_id": "O"})
    with fits.open(str(path)) as hdul:
        assert hdul[-1].name == "FITA_META"


def test_without_provenance_the_file_is_core_but_not_full(tmp_path):
    """Provenance stays opt-in: omitting it must not break a CORE write."""
    path = tmp_path / "core.fita"
    write(str(path), _layers(), overwrite=True)
    report = validate(str(path))
    assert report.is_core
    assert not report.is_full


def test_bad_provenance_type_is_rejected(tmp_path):
    with pytest.raises(TypeError):
        write(str(tmp_path / "bad.fita"), _layers(), overwrite=True,
              provenance="not a dict or an HDU")


def test_cube_save_passes_provenance_through(tmp_path):
    from fita.cube import FITACube
    path = tmp_path / "cube.fita"
    FITACube(layers=_layers()).save(str(path), provenance={"obs_id": "CUBE"})
    assert validate(str(path)).is_full
