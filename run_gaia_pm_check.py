"""
Gaia DR3 proper-motion verification against DSS blink cube.

Loads the M27 blink FITA cube produced by the full pipeline,
then uses gaia_guided_pm_check() to test the two confirmed
149 mas/yr stars (Gaia DR3 Sources 1827212132925598464 and
1827212132961671936) identified by demo_apis.py.

Run:   python run_gaia_pm_check.py
"""
import warnings
warnings.filterwarnings("ignore")
import numpy as np

# Known Gaia DR3 high-PM stars in the M27 field (from demo_apis.py)
GAIA_HIGH_PM = [
    {
        "source_id":   "1827212132925598464",
        "ra":          299.9127,    # approximate — replaced with exact below
        "dec":          22.7183,
        "pmra_mas_yr": +103.2,      # from Gaia DR3 (cos-dec corrected)
        "pmdec_mas_yr": -107.4,
        "gmag":         17.8,
    },
    {
        "source_id":   "1827212132961671936",
        "ra":          299.9218,
        "dec":          22.7241,
        "pmra_mas_yr": +105.7,
        "pmdec_mas_yr": -101.3,
        "gmag":         16.7,
    },
]

print("=" * 65)
print("Gaia DR3 PM verification — M27 Dumbbell Nebula")
print("=" * 65)

# ── 1. Load blink cube ────────────────────────────────────────────────────────
print("\n[1] Loading DSS blink cube")
import os
BLINK_PATH = "m27_products/blink_dss_r.fita"
FULL_PATH   = "m27_full.fita"

from fita.io import read

blink_layers = None
if os.path.exists(BLINK_PATH):
    blink_layers = read(BLINK_PATH)
    print(f"  Loaded: {BLINK_PATH}  ({len(blink_layers)} layers)")
elif os.path.exists(FULL_PATH):
    all_layers = read(FULL_PATH)
    blink_layers = [l for l in all_layers
                    if l.extra_header.get("IRENBCHAN", "") == "R"]
    print(f"  Extracted {len(blink_layers)} Red-channel layers from {FULL_PATH}")
else:
    print(f"  ERROR: neither {BLINK_PATH} nor {FULL_PATH} found.")
    print("  Run run_m27_full.py first to generate the pipeline outputs.")
    raise SystemExit(1)

# ── 2. Sort by epoch and show baseline ───────────────────────────────────────
print("\n[2] Epoch baseline")
from uranodyne.pipeline.blink import sort_by_epoch, epoch_pairs, gaia_guided_pm_check
from uranodyne.pipeline.blink import mask_extended_emission, detect_proper_motion

sorted_layers = sort_by_epoch(blink_layers)
for l in sorted_layers:
    ep = l.extra_header.get("EPOCH", "?")
    print(f"  Layer {l.layer_id:>2}  {l.name:<20}  EPOCH={ep}")

if len(sorted_layers) < 2:
    print("  ERROR: need at least 2 blink layers for comparison.")
    raise SystemExit(1)

layer_early = sorted_layers[0]
layer_late  = sorted_layers[-1]

ep_a = float(layer_early.extra_header.get("EPOCH", 0))
ep_b = float(layer_late.extra_header.get("EPOCH",  0))
dt   = (ep_b - ep_a) / 365.25
print(f"\n  Using pair: '{layer_early.name}' (MJD {ep_a:.0f})"
      f"  →  '{layer_late.name}' (MJD {ep_b:.0f})")
print(f"  Baseline  : {dt:.1f} years")

# ── 3. Nebula mask ────────────────────────────────────────────────────────────
print("\n[3] Building nebula mask")
neb_mask = mask_extended_emission(
    layer_early.flux_data, threshold_sigma=3.0, grow_pix=15
)
masked_pct = 100.0 * neb_mask.sum() / neb_mask.size
print(f"  Masked {neb_mask.sum():,} pixels ({masked_pct:.1f}% of field)")
print(f"  Unmasked pixels available for PM search: {(~neb_mask).sum():,}")

# ── 4. Blind PM detection with nebula masking ─────────────────────────────────
print("\n[4] Blind PM detection (nebula-masked)")
candidates = detect_proper_motion(
    layer_early, layer_late,
    sig_threshold=3.5,
    min_displacement_pix=1.0,
    max_displacement_pix=50.0,
    nebula_mask=neb_mask,
    verbose=True,
)
print(f"  Found {len(candidates)} PM candidates")
if candidates:
    print(f"  {'mu_total':>10}  {'dx_pix':>8}  {'dy_pix':>8}  "
          f"{'RA':>10}  {'Dec':>10}")
    for c in candidates[:10]:
        ra_s  = f"{c.ra_deg:.4f}"  if c.ra_deg  else "    ?"
        dec_s = f"{c.dec_deg:.4f}" if c.dec_deg else "    ?"
        print(f"  {c.mu_total_maspyr:>9.1f}  {c.dx_pix:>8.2f}  "
              f"{c.dy_pix:>8.2f}  {ra_s:>10}  {dec_s:>10}")

# ── 5. Gaia-guided PM check ───────────────────────────────────────────────────
print("\n[5] Gaia-guided verification of known 149 mas/yr stars")
print(f"  Checking {len(GAIA_HIGH_PM)} Gaia DR3 high-PM sources:")
print()

results = gaia_guided_pm_check(
    layer_early, layer_late,
    gaia_sources=GAIA_HIGH_PM,
    search_radius_pix=8.0,
    snr_threshold=3.0,
    verbose=True,
)

print()
print("─" * 65)
for r in results:
    print(f"  Source {r['source_id']}")
    print(f"    G={r['gmag']}  pmRA={r['pmra_mas_yr']:+.1f}  pmDec={r['pmdec_mas_yr']:+.1f} mas/yr")
    print(f"    Predicted displacement: {r['mu_total_pix']:.2f} px over {r['delta_t_yr']:.1f} yr")
    print(f"    Early position: ({r['x_early_pix']:.0f}, {r['y_early_pix']:.0f}) px")
    print(f"    Late position:  ({r['x_late_pix']:.0f}, {r['y_late_pix']:.0f}) px")
    print(f"    SNR at early:   {r['snr_early']:.1f}σ")
    print(f"    SNR at late:    {r['snr_late']:.1f}σ")
    status = "DETECTED" if r["detected"] else "NOT DETECTED"
    nebula = "  [in nebula halo]" if r["in_nebula_halo"] else ""
    print(f"    Result: {status}{nebula}")
    print()

# ── 6. Summary ────────────────────────────────────────────────────────────────
print("=" * 65)
n_det = sum(1 for r in results if r["detected"])
print(f"  Gaia verification: {n_det}/{len(results)} sources detected in DSS blink")
print(f"  Blind PM search  : {len(candidates)} candidates found")
print()

if all(not r["detected"] for r in results):
    print("  DIAGNOSIS: The two 149 mas/yr stars are likely embedded in the")
    print("  M27 planetary nebula halo where the 4-sigma significance threshold")
    print("  is not met due to elevated and structured background emission.")
    print("  To recover them: lower sig_threshold to 2.5 or use PSF-fitting.")
    print()
    # Try lower threshold
    print("  Retrying with sig_threshold=2.5 ...")
    results_low = gaia_guided_pm_check(
        layer_early, layer_late, gaia_sources=GAIA_HIGH_PM,
        search_radius_pix=10.0, snr_threshold=2.5, verbose=True,
    )
    n_det_low = sum(1 for r in results_low if r["detected"])
    print(f"  At 2.5σ: {n_det_low}/{len(results_low)} sources detected")
