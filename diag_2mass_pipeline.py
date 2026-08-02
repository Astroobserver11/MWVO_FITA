"""
Diagnose 2MASS J calibration and the save/load cycle.
"""
import numpy as np
import warnings
warnings.filterwarnings("ignore")

# ── 1. Check calibrated values in-memory before save ─────────────────────────
from fita.pipeline.skyview import fetch_survey
from fita.pipeline.surveys import TWOMASS_J

print("=== 1. Fetch & calibrate 2MASS J ===")
layer = fetch_survey(299.901, +22.721, 5.0, TWOMASS_J,
                     pixels=64, calibrate=True, verbose=True)

data = layer.flux_data
finite = data[np.isfinite(data)]
print(f"  pixels  : {finite.size}")
print(f"  min     : {finite.min():.4e} Jy")
print(f"  max     : {finite.max():.4e} Jy")
print(f"  median  : {np.median(finite):.4e} Jy")
print(f"  flux_min: {layer.flux_min}")
print(f"  flux_max: {layer.flux_max}")

# ── 2. Raw (uncalibrated) values ──────────────────────────────────────────────
print("\n=== 2. Same fetch, no calibration ===")
layer_raw = fetch_survey(299.901, +22.721, 5.0, TWOMASS_J,
                          pixels=64, calibrate=False, verbose=True)
data_raw = layer_raw.flux_data
finite_raw = data_raw[np.isfinite(data_raw)]
print(f"  min: {finite_raw.min():.1f}  max: {finite_raw.max():.1f}  "
      f"median: {np.median(finite_raw):.1f} (DN)")

# ── 3. Check what calibration formula produces ────────────────────────────────
print("\n=== 3. Calibration formula trace ===")
dn_values = np.array([116.0, 500.0, 9000.0], dtype=np.float32)
abzpt = 23.0
exptime = 1.0
rate = dn_values / exptime
abmag = abzpt - 2.5 * np.log10(rate)
flux_jy = 3631.0 * 10 ** (-0.4 * abmag)
for dn, ab, jy in zip(dn_values, abmag, flux_jy):
    print(f"  DN={dn:7.0f}  abmag={ab:.2f}  flux={jy:.4e} Jy")

print()
print("Conclusion: 2MASS J from SkyView gives sub-mJy calibrated values.")
print("For M27 display composites, raw DN passthrough is more appropriate.")
print("Fix: set jy_per_dn=1.0 (passthrough) OR flag cal_type=NONE for SkyView surveys.")
