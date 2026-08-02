"""
FITA demo -- runs with no external data files.
Generates synthetic multi-wavelength data, builds a cube, does SED analysis,
exports Excel, and saves plots.

Run from the fita/ directory:
    python demo.py
"""

import numpy as np
from pathlib import Path

# ── 1. Synthetic multi-wavelength scene ──────────────────────────────────────
# Imagine a star-forming region:
#   - A point source YSO at (32, 32) bright in IR, faint in UV
#   - Diffuse HII emission filling the field, bright in Hα
#   - Dust cloud in the upper-left, absorbs UV, glows in mid-IR

rng  = np.random.default_rng(42)
SIZE = 128

def make_scene(wave_m):
    """Create a fake astrophysical image at a given wavelength."""
    data = rng.normal(50.0, 8.0, (SIZE, SIZE)).astype(np.float32)

    # diffuse HII — peaks near Hα (656 nm), fades in IR
    y, x = np.ogrid[:SIZE, :SIZE]
    hii = 200.0 * np.exp(-((x-64)**2 + (y-64)**2) / (2*30**2))
    hii_scale = np.exp(-((wave_m - 656e-9) / 400e-9)**2)
    data += hii * hii_scale

    # YSO point source at (32,32) — peaks in mid-IR
    r_yso = np.sqrt((x-32)**2 + (y-32)**2)
    yso_peak = 2000.0 * np.exp(-((np.log10(max(wave_m,1e-9)) - np.log10(4e-6))**2) / 0.5)
    data += yso_peak * np.exp(-r_yso**2 / (2*2.5**2))

    # second source at (90, 80)
    r2 = np.sqrt((x-90)**2 + (y-80)**2)
    data += 800.0 * np.exp(-r2**2 / (2*1.8**2)) * (wave_m / 1e-6)

    # dust cloud upper-left — absorbs UV, emits in far-IR
    dust = np.exp(-((x-20)**2 + (y-100)**2) / (2*18**2))
    if wave_m < 500e-9:
        data -= 40.0 * dust          # UV absorption
    if wave_m > 10e-6:
        data += 500.0 * dust          # far-IR emission

    return np.clip(data, 0.1, None)


# Wavelengths: UV → Hα → NIR → MIR → far-IR
BANDS = [
    (350e-9,  60e-9,  "UV350",   "HST/ACS/F814W"),
    (500e-9,  90e-9,  "V500",    "HST/WFC3/F606W"),
    (656e-9,  10e-9,  "Ha656",   "HST/ACS/F814W"),
    (2.2e-6,  0.3e-6, "K-band",  "VLT/HAWKI/Ks"),
    (3.6e-6,  0.7e-6, "IRAC36",  "Spitzer/IRAC/3.6um"),
    (4.5e-6,  1.0e-6, "IRAC45",  "Spitzer/IRAC/4.5um"),
    (24e-6,   5e-6,   "MIPS24",  "Spitzer/MIPS/24um"),
    (70e-6,   20e-6,  "PACS70",  "Herschel/PACS/70um"),
]

print("Building synthetic FITA cube...")

from fita import FITACube, FITALayer
from fita.spec import BLEND_ADD, BLEND_SCREEN, BLEND_NORMAL, BLEND_MULTIPLY

layers = []
blend_sequence = [BLEND_NORMAL, BLEND_SCREEN, BLEND_ADD, BLEND_SCREEN,
                  BLEND_ADD, BLEND_ADD, BLEND_SCREEN, BLEND_NORMAL]

for i, (wave, bwid, name, inst_key) in enumerate(BANDS):
    flux = make_scene(wave)

    # calibrate to Jy using the instrument DB
    from fita.calibration import FluxCalibrator
    cal = FluxCalibrator()
    flux_jy, note, meta = cal.calibrate(flux, instrument_key=inst_key,
                                         wave_m=wave, verbose=False)

    layer = FITALayer.from_array(
        flux_jy,
        layer_id    = i + 1,
        name        = name,
        wave_cval   = wave,
        wave_bwid   = bwid,
        blend_mode  = blend_sequence[i],
        stretch_mode= "asinh",
    )
    layer.extra_header["INSTRUME"] = inst_key
    layer.extra_header["CALTYPE"]  = meta.get("CALTYPE", "NONE")
    layer.extra_header["BUNIT"]    = "Jy"
    layers.append(layer)
    print(f"  Layer {i+1}: {name:8s}  wave={wave*1e6:6.2f} um  "
          f"flux range [{layer.flux_min:.3g}, {layer.flux_max:.3g}] Jy  "
          f"cal={meta.get('CALTYPE','?')}")

cube = FITACube(layers=layers)
print(f"\nCube: {cube}")

# ── 2. Save and reload ───────────────────────────────────────────────────────
out_dir = Path(__file__).parent / "demo_output"
out_dir.mkdir(exist_ok=True)

fita_path = out_dir / "starforming_region.fita"
cube.save(fita_path)
print(f"\nSaved: {fita_path}")

cube2 = FITACube.load(fita_path)
print(f"Reloaded: {cube2}")

# ── 3. Re-select flux range (alpha recomputed; flux untouched) ────────────────
print("\nRe-selecting flux range on UV layer...")
cube.reselect_flux_range(flux_min=0, flux_max=50, stretch_mode="log",
                          layer_ids=[1])

# ── 4. Point-source SED at the YSO position ──────────────────────────────────
print("\nExtracting dual SED at YSO position (32, 32)...")
from fita.sed_analysis import DualSED, export_sed_xlsx

sed_yso = DualSED.from_layers(layers, px=32, py=32, aperture_r=5.0)
print(f"  Source type: {sed_yso.source_type}")
print(f"  Wavelengths (μm): {[f'{w*1e6:.2f}' for w in sed_yso.wave_m]}")
print(f"  Flux (Jy):        {[f'{f:.3g}' for f in sed_yso.flux_phys_jy]}")
print(f"  Display lum:      {[f'{l:.2f}' for l in sed_yso.lum_disp]}")

# ── 5. Bolometric luminosity (assume d=500 pc from GAIA-like constraint) ──────
from fita.photometry import SEDPoint, yso_bolometric_luminosity, constrain_distance

# Simulated GAIA stars in the field
mock_gaia = [
    {"parallax_mas": 2.01, "parallax_err_mas": 0.08},
    {"parallax_mas": 1.98, "parallax_err_mas": 0.12},
    {"parallax_mas": 2.05, "parallax_err_mas": 0.09},
]
d_pc, d_err = constrain_distance(mock_gaia, min_snr=5.0)
print(f"\nGAIA distance constraint: {d_pc:.0f} +/- {d_err:.0f} pc")

# Build SED points — use 10% fractional error for demo (Poisson SNR model
# is not meaningful on already-calibrated Jy data; real noise comes from
# per-instrument calibration uncertainty and background RMS, not photon counting)
sed_pts = [
    SEDPoint(wave_m=sed_yso.wave_m[i],
             flux_jy=sed_yso.flux_phys_jy[i],
             err_jy=abs(sed_yso.flux_phys_jy[i]) * 0.10,
             upper_limit=False)
    for i in range(len(sed_yso.wave_m))
    if np.isfinite(sed_yso.flux_phys_jy[i]) and sed_yso.flux_phys_jy[i] > 0
]
lbol, lbol_err = yso_bolometric_luminosity(sed_pts, distance_pc=d_pc)
print(f"YSO bolometric luminosity: {lbol:.1f} +/- {lbol_err:.1f} L_sun")

# ── 6. Calibration report ─────────────────────────────────────────────────────
print()
from fita.calibration import calibration_report
calibration_report(layers)

# ── 7. Excel SED export ───────────────────────────────────────────────────────
xlsx_path = out_dir / "yso_sed.xlsx"
try:
    export_sed_xlsx(sed_yso, str(xlsx_path), include_histogram=True, layers=layers)
except ImportError:
    print("(openpyxl not installed — skip Excel export)")

# ── 8. Plots ──────────────────────────────────────────────────────────────────
try:
    import matplotlib
    matplotlib.use("Agg")

    from fita.export import plot_dual_sed, plot_layer, animate_stack

    # dual SED plot
    fig = plot_dual_sed(
        sed_yso,
        title="YSO at (32,32) — synthetic star-forming region",
        show_histogram=True,
        layers=layers,
        save_path=str(out_dir / "yso_sed.png"),
    )
    print(f"SED plot saved: {out_dir / 'yso_sed.png'}")

    # single-layer plot (Hα)
    fig2 = plot_layer(
        layers[2],  # Hα
        stretch_mode="sqrt",
        save_path=str(out_dir / "ha_layer.png"),
    )
    print(f"Hα layer plot saved: {out_dir / 'ha_layer.png'}")

    # composite display image
    import matplotlib.pyplot as plt
    display = cube.composite()
    fig3, ax = plt.subplots(figsize=(6, 6), dpi=150)
    ax.imshow(display, cmap="inferno", origin="lower", vmin=0, vmax=1)
    ax.set_title("FITA composite (all layers, blend modes applied)", fontsize=10)
    ax.plot(32, 32, "w+", markersize=14, markeredgewidth=2, label="YSO")
    ax.plot(90, 80, "cx", markersize=10, markeredgewidth=2, label="Source 2")
    ax.legend(fontsize=8)
    fig3.savefig(out_dir / "composite.png", bbox_inches="tight", dpi=150)
    plt.close("all")
    print(f"Composite saved: {out_dir / 'composite.png'}")

    # MPEG-4 animation (wavelength mode — GIF if no ffmpeg)
    print("\nGenerating animation (wavelength walk-through)...")
    animate_stack(
        cube,
        out_path=str(out_dir / "wavelength_tour.mp4"),
        mode="wavelength",
        fps=3,
        dpi=100,
        cmap="inferno",
    )

except ImportError:
    print("(matplotlib not installed — skip plots/animation)")

# ── 9. DS9 analysis menu file ─────────────────────────────────────────────────
from fita.plugins.ds9 import write_analysis_file
write_analysis_file(out_dir / "fita.ds9.ana")

# ── 10. FITS Liberator sidecar ────────────────────────────────────────────────
from fita.plugins.qfitsview import write_liberator_sidecar
write_liberator_sidecar(fita_path, layers, out_dir / "fita_liberator.json")

print(f"\nAll demo outputs in: {out_dir.resolve()}")
print("\nFiles produced:")
for f in sorted(out_dir.iterdir()):
    print(f"  {f.name:40s}  {f.stat().st_size:>8,} bytes")
