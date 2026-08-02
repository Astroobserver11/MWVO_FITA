"""
smoke_test_wideangle.py — end-to-end synthetic check of the MWVO wide-angle stack.

Runs with NO real data or optional packages (astropy + reproject only): exercises the
HI4PI moment path, the Edenhofer 3D volume, the 1.25->2.5 kpc graft with fog alpha, the
foreground column, and the multiphase (Edenhofer + HI + CO) X-ray absorption solve.

    python smoke_test_wideangle.py     # exit 0 = all green

ATOP-side: after `pip install dustmaps healpy` and the Edenhofer/Lallement fetch, swap the
synthetic volume for EdenhoferCube.from_dustmaps(...) and the provider for
lallement_provider(<explore_cube.fits>) — the rest is unchanged.
"""
import sys
import numpy as np

from uranodyne.pipeline import setup_data
from uranodyne.pipeline import edenhofer as ed
from uranodyne.pipeline import xray_absorption as xa
from uranodyne.pipeline import MultiWavelengthAbsorptionModel
from fita.layer import FITALayer

RESULTS = []
def check(name, cond, detail=""):
    RESULTS.append((name, bool(cond), detail))
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}  {detail}")


def main():
    print(setup_data.readiness_report(), "\n")
    print("SMOKE TEST")

    # 1. Edenhofer synthetic volume + line-of-sight foreground
    vol = ed.EdenhoferCube.synthetic(nd=24, ny=32, nx=32, glon=353.0, glat=17.0)
    fnh = ed.foreground_nh(vol, 353.0, 17.0, 300.0)
    check("edenhofer foreground_nh finite/positive", np.isfinite(fnh) and fnh > 0,
          f"N_H(<300pc)={fnh:.2e}")

    # 2. Graft to 2.5 kpc with a Cartesian provider + fog alpha
    origin, voxel = [-2600., -2600., -1000.], [50., 50., 50.]
    cube = np.full((40, 104, 104), 1e-3, np.float32)
    prov = ed.make_cartesian_provider(cube, origin, voxel, value_is_av=True)
    graft = ed.graft_outer_shell(vol, outer_provider=prov, d_max_pc=2500., n_outer=16)
    fog = ed.confidence_fog_alpha(graft.distances_pc)
    check("graft reaches 2.5 kpc", graft.distances_pc[-1] >= 2400,
          f"d_max={graft.distances_pc[-1]:.0f}pc")
    check("outer shells SCOUTED", graft.anchor_per_shell[-1] == "SCOUTED")
    check("fog fades past core", fog[0] == 1.0 and fog[-1] < 0.5,
          f"fog[0]={fog[0]:.2f} fog[-1]={fog[-1]:.2f}")
    check("cumulative A_V grows across graft",
          graft.integrated_av(2500.) .mean() > graft.integrated_av(1250.).mean())

    # 3. Distance-shell FITA export (fog baked into alpha)
    shells = ed.to_distance_shells(graft, step=6)
    faded = [l for l in shells.layers if l.extra_header.get("FOGALPHA", 1.0) < 1.0]
    check("distance-shell FITA built", len(shells.layers) > 0,
          f"{len(shells.layers)} shells, {len(faded)} fogged")

    # 4. Multiphase absorption: Edenhofer foreground + HI + CO vs ROSAT
    def L(a): return FITALayer.from_array(a.astype("float32"), name="x")
    inp = {"edenhofer_fg": L(ed.foreground_nh_map(vol, 400.)),
           "hi_whi": L(np.full((32, 32), 300.)),
           "co_wco": L(np.full((32, 32), 8.)),
           "rosat_r1": L(np.random.default_rng(0).uniform(2, 9, (32, 32)))}
    res = MultiWavelengthAbsorptionModel(band="R1").run_multiphase(inp, d_source_pc=400.)
    check("multiphase solve returns anchored result", res.anchor_class == "ANCHORED",
          f"gas/dust={res.regression.get('gas_dust_ratio'):.2f}")
    check("CO->N_H2 physics", abs(xa.co_to_nh2(8.) - 1.6e21) < 1e19)
    check("band cross-section sane (tau=1 near 1e20)",
          8e19 < 1.0 / xa.band_sigma("R1") < 2e20,
          f"N_H(tau=1)={1.0/xa.band_sigma('R1'):.2e}")

    npass = sum(1 for _, ok, _ in RESULTS if ok)
    print(f"\n{npass}/{len(RESULTS)} checks passed")
    return 0 if npass == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
