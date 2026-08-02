# FITA — Flexible Image Transfer Alpha

**File extension:** `.fita`  
**Based on:** FITS (Flexible Image Transport System, NASA/NOST 100-2.0)  
**IVOA awareness:** ObsCore DM v1.1, FITS WCS Papers I–IV  

---

## What is FITA?

FITA extends the standard FITS data cube with:

| Feature | Description |
|---|---|
| **Per-slice alpha channel** | Each wavelength/frequency/time slice carries its own uint16 transparency mask |
| **Luminance-derived alpha** | Alpha is computed from a user-selected flux range, preserving raw astrophysical flux |
| **32-bit → 16+16 split** | Optional `SPLIT16` packing: 16-bit scaled flux + 16-bit alpha in paired extensions |
| **Variable (x,y) per layer** | Each layer has `FITA_XOF`/`FITA_YOF` canvas position (pixels or WCS) |
| **Photoshop blend modes** | 14 blend modes: NORMAL, SCREEN, MULTIPLY, ADD, OVERLAY, SOFTLGT, HARDLGT, CDODGE, CBURN, DIFF, LUM, COLOR, HUE, SAT |
| **Adjustment layers** | Non-destructive LEVELS, CURVES, BRIGHTNESS, HUESAT, FXSTRETCH, BANDMAP, FXNORM |
| **PSD import** | Import Adobe Photoshop `.psd` files, preserving layer names, blend modes, and masks |
| **IVOA / ObsCore provenance** | `FITA_META` BINTABLE HDU with ObsCore-compatible columns |
| **FITS-native** | Any standard FITS reader can open a `.fita` file |

---

## HDU Layout

```
HDU 0  PRIMARY       Empty data + global FITA keywords
HDU 1  FITA_LAYERS   BINTABLE — layer registry (one row per layer)
HDU 2  FLUX_0001     IMAGE — calibrated flux (float32 or split uint16)
HDU 3  ALPHA_0001    IMAGE — transparency mask (uint16, 0=transparent, 65535=opaque)
HDU 4  FLUX_0002     IMAGE
HDU 5  ALPHA_0002    IMAGE
  ...
HDU N  FITA_ADJ      BINTABLE — adjustment layer stack (optional)
HDU N+1 FITA_META   BINTABLE — IVOA ObsCore provenance (optional)
```

---

## Quick Start

```python
from fita import FITACube, FITALayer

# Import a standard FITS data cube (e.g. IFU cube, HST drizzle cube)
cube = FITACube.from_fits_cube("ngc1068_cube.fits", stretch_mode="asinh")
cube.save("ngc1068.fita")

# Re-select the display flux range — alpha recomputed, raw flux UNTOUCHED
cube.reselect_flux_range(flux_min=10, flux_max=5000, stretch_mode="log")

# Composite all visible layers into a display image
display_img = cube.composite()  # float32 (H, W), range [0, 1]

# Spectral energy distribution at a pixel
waves, fluxes = cube.sed(px=512, py=512)

# Import Photoshop layers
cube_from_psd = FITACube.from_psd("composite.psd")
cube_from_psd.save("composite.fita")
```

---

## 32-bit → 16+16 Split Encoding (`FITA_PACK = SPLIT16`)

```
physical_flux  (float32)
       │
       ▼  normalise to [flux_min, flux_max]
  normed_flux  (float32, 0-1)
       │                          │
       ▼ × 65535                  ▼ asinh / sqrt / log stretch
  FLUX_* uint16              lum (float32, 0-1)
  BSCALE/BZERO recoverable        │
                                  ▼ × 65535
                             ALPHA_* uint16
```

Recovery: `physical_flux ≈ flux16 × BSCALE + BZERO`  
Precision loss: ~0.2% of the selected flux range (16-bit quantisation).

---

## Flux-Range Reselection

The alpha channel is the *only* thing that changes when you move the display
range sliders.  The `FLUX_*` extension always holds calibrated detector counts
or physical flux density.  This separates:

- **Display luminosity** — what your eye sees (alpha-modulated)
- **Astrophysical energy flux** — what the instrument measured (flux data)

This is the invariant that makes FITA suitable for bolometric SED work.

---

## IVOA Compliance Notes

- All WCS keywords follow FITS WCS Papers I–IV conventions
- Spectral axis: `CTYPE3` ∈ `{WAVE, FREQ, VRAD, ENER, …}`
- UCDs added to layer headers: `phot.flux.density`, `em.wl`, `pos.eq.ra/dec`
- `FITA_META` HDU mirrors the 19 mandatory ObsCore columns
- `em.wl;stat.min/max` coverage derived from layer `wave_cval ± wave_bwid/2`
- Access format registered as `application/fits+alpha` (pending IANA)

For formal IVOA DataCube DM compatibility, FITA intends to submit a note to
the IVOA Data Access Layer WG.

---

## SAO DS9 Integration

```python
from fita.plugins.ds9 import send_to_ds9, write_analysis_file
from fita import FITACube

cube = FITACube.load("ngc1068.fita")
send_to_ds9(cube)                           # requires: pip install pyds9
write_analysis_file("fita.ds9.ana")         # analysis menu plugin
```

Or via CLI:
```bash
fita ds9-plugin fita.ds9.ana
# then in DS9: File > Analysis > Load... > fita.ds9.ana
```

---

## qFITSView / ESA FITS Liberator

```python
from fita.plugins.qfitsview import export_rgb_fits, write_liberator_sidecar, tile_compress_fita
from fita import FITACube

cube = FITACube.load("ngc1068.fita")

# RGB false-colour cube for qFITSView
export_rgb_fits(cube, "ngc1068_rgb.fits", r_layer_id=3, g_layer_id=2, b_layer_id=1)

# Sidecar JSON for FITS Liberator Photoshop plugin
write_liberator_sidecar("ngc1068.fita", cube.layers)

# Tile-compressed version (smaller, still valid FITS)
tile_compress_fita("ngc1068.fita", "ngc1068_compressed.fita", algorithm="RICE_1")
```

---

## CLI

```bash
pip install -e ".[all]"

fita from-fits ngc1068_cube.fits ngc1068.fita --stretch asinh
fita info ngc1068.fita
fita reselect ngc1068.fita --fmin 10 --fmax 5000 --stretch log
fita rgb ngc1068.fita rgb.fits --r 3 --g 2 --b 1
fita from-psd composite.psd composite.fita
fita liberator ngc1068.fita
fita ds9-plugin fita.ds9.ana
```

---

## Blend Modes for Astrophysical Compositing

| Mode | FITA Code | Astrophysical Use |
|---|---|---|
| Normal | `NORMAL` | Default overlay |
| Screen | `SCREEN` | Additive glow / emission nebulae |
| Multiply | `MULTIPLY` | Dust absorption masks |
| Add (Linear Dodge) | `ADD` | Emission line sum |
| Luminosity | `LUM` | **Apply flux luminosity to colour layer** — key SED mode |
| Color | `COLOR` | Apply false-colour over calibrated flux luminosity |
| Overlay | `OVERLAY` | Contrast enhancement |

The `LUM` + `COLOR` pair is the canonical approach for multi-wavelength
bolometric SED visualisation: one layer carries the calibrated flux
(luminosity), a second carries hue/chroma from a false-colour mapping or
optical image, and the composite shows physically meaningful brightness
with informative colour.

---

## Towards Bolometric SED Cubes

A multi-wavelength FITA cube where each layer covers one photometric band
constitutes a bolometric spectral energy distribution cube.  The planned
`FITA_SED` extension (v1.1) will:

- Store the SED fitting parameters per pixel (blackbody T, power law α, etc.)
- Link to the IVOA Spectrum DM and SSA protocol
- Support multi-resolution layers (e.g. radio at 1″ + X-ray at 5″ + optical at 0.1″)
  via per-layer WCS without resampling to a common grid

---

## Installation

```bash
git clone https://github.com/fits-alpha/fita
cd fita
pip install -e ".[all]"    # full install including PSD, DS9, matplotlib
pip install -e "."          # core only (astropy + numpy)
```

---

## License

MIT.  Format specification is dedicated to the public domain (CC0).
