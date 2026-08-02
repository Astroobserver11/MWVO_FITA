"""Durable units for the MWVO wide-angle ISM hub (Edenhofer + CO + PACI)."""
import numpy as np
import pytest

from fita.layer import FITALayer
from fita import io as fio
# These exercise the URANODYNE science stack, which is a separate distribution.
# They belong in that repository; until they move, skip rather than fail so the
# format kernel stays independently testable.
pytest.importorskip("uranodyne")

from uranodyne.pipeline import paci, edenhofer as ed
from uranodyne.pipeline import xray_absorption as xa


# ── PACI provenance survives a .fita save/load round-trip ───────────────────
def test_paci_roundtrip_through_fita(tmp_path):
    lyr = FITALayer.from_array(np.ones((8, 8), np.float32), layer_id=1, name="t")
    paci.tag_layer(lyr, paci.Provenance("Edenhofer 2024", 0.13, paci.MEASURED, "ABS"),
                   uncert_map=np.full((8, 8), 0.2, np.float32))
    p = tmp_path / "rt.fita"
    fio.write(str(p), [lyr])
    back = fio.read(str(p))[0]
    assert back.extra_header["ANCHORCL"] == "MEASURED"
    assert "Edenhofer" in back.extra_header["CITATION"]
    assert back.extra_header["UNCKIND"] == "MAP"
    assert back.uncert_data is not None and np.allclose(back.uncert_data, 0.2)


# ── physics constants ───────────────────────────────────────────────────────
def test_band_sigma_optically_thick_scale():
    assert 8e19 < 1.0 / xa.band_sigma("R1") < 2e20      # 1/4 keV thick near 1e20
    assert xa.band_sigma("R2") < xa.band_sigma("R1")     # R2 less low-E weight

def test_gas_columns():
    assert xa.co_to_nh2(8.0) == pytest.approx(1.6e21, rel=1e-6)
    assert xa.hi_to_nh(300.0) == pytest.approx(5.469e20, rel=1e-3)
    assert xa.total_gas_nh(300.0, 8.0) == pytest.approx(5.469e20 + 3.2e21, rel=1e-3)


# ── Edenhofer volume + graft + fog ──────────────────────────────────────────
def test_foreground_and_graft():
    vol = ed.EdenhoferCube.synthetic(nd=20, ny=16, nx=16)
    assert ed.foreground_nh(vol, 170.0, -16.0, 300.0) > 0
    assert vol.integrated_av(1000.0).mean() >= vol.integrated_av(200.0).mean()
    graft = ed.graft_outer_shell(vol, d_max_pc=2500.0, n_outer=10)
    assert graft.distances_pc[-1] >= 2400
    assert graft.anchor_per_shell[-1] == paci.SCOUTED
    fog = ed.confidence_fog_alpha(graft.distances_pc)
    assert fog[0] == 1.0 and fog[-1] < 0.5


# ── kriging (CAP posterior) is exact at anchors, uncertain away ──────────────
def test_krige_exact_at_anchors():
    xy = np.array([[2, 2], [12, 3], [7, 12], [3, 9]], float)
    val = np.array([1.0, 3.0, 2.0, 4.0])
    mean, var = xa.krige_anchors(xy, val, (16, 16), nugget=1e-9)
    for (x, y), v in zip(xy.astype(int), val):
        assert mean[y, x] == pytest.approx(v, abs=1e-3)
        assert var[y, x] == pytest.approx(0.0, abs=1e-3)
    assert var[8, 8] > 0.0                               # uncertain between anchors


# ── census locator is schema-agnostic ───────────────────────────────────────
def test_census_table_discovery():
    import sqlite3
    from uranodyne.pipeline.local_survey import _census_table
    con = sqlite3.connect(":memory:")
    con.execute("CREATE TABLE census_files (full_path TEXT, filename TEXT)")
    con.execute("INSERT INTO census_files VALUES ('H:/x/COGAL_all_mom.fits','COGAL_all_mom.fits')")
    tbl, pathc, namec = _census_table(con)
    assert tbl == "census_files" and pathc == "full_path" and namec == "filename"
