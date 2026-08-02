# FITA — Flexible Image Transfer Alpha

**A FITS convention for multi-layer astronomical images with a display channel
that cannot touch the science.**

| | |
|---|---|
| **File suffix** | `.fita` |
| **Format version** | 1.2 |
| **MIME type** | `application/fits` |
| **Based on** | FITS Standard v4.0 — every `.fita` file is a valid FITS MEF |
| **Normative spec** | [`FITA_FORMAT_STANDARD`](FITA_FORMAT_STANDARD.RATIFIED-2026-08-02.md) |
| **Licence** | MIT (software) · CC0 (specification) |

---

## Purpose

The human mind and perceptual system are astonishing. Evolved through biology
into consciousness, they are complex, agile, and able to resolve pattern and
create understanding. The advancement of technology, remote sensing, and the
exploitation of the electromagnetic spectrum to discover nature is a fact of
our civilisation. Digital darkroom technology has evolved from desktop
publishing to astronomical use, and perhaps toward the exploitation of human
*and machine* vision throughout the sciences.

FITA is a format that enables its user to balance data in a way that
**re-naturalises sliced and measured phenomena lying beyond the reach of human
senses, while maintaining the scientific integrity of the measurements**. It
was designed to satisfy multi-wavelength astronomy and the integration of
multispectral measurements into physical models and astrophysical inference.
FITA is therefore intended to be **multi-wavelength and multidisciplinary**.

FITA is at the heart of the **MWVO — the Multi-Wave Virtual Observatory** —
which exists to facilitate the astronomer's vision of phenomena beyond natural
sensory capacity. The human mind can inhabit the entire phenomenological
electromagnetic space. FITA serves science by systematically maintaining the
integrity of measurement and flux accumulation, while allowing the flexibility
and agility to manipulate presentation and provide sentient access to visual
representations of data.

---

## What it is

A `.fita` file carries several co-registered science images in one FITS
multi-extension file, each with its own calibration, bandpass, uncertainty,
quality mask, compositing metadata and stereo-depth assignment.

It exists for one invariant:

> **The flux is the physics, and nothing in the display path may touch it.**

`FLUX_*` holds calibrated physical flux. `ALPHA_*` holds display transparency
derived from a selected flux range. Moving the display range changes alpha and
**nothing else** — verified bit-for-bit and NaN-aware on every write/read cycle
in the test suite.

Every other feature is subordinate to that.

## What it is not

- **Not a new file format.** It is a *convention over FITS*: reserved `EXTNAME`
  values, a registry table, and `FITA_*` keywords in the user keyword space.
  Any FITS reader opens a `.fita` file today.
- **Not a rendering engine.** It stores compositing *metadata*; producing
  pixels on a screen is the renderer's job.
- **Not a calibration pipeline.** It stores calibrated flux and its provenance,
  not how the calibration was obtained. That is URANODYNE's job.

---

## HDU layout

```
HDU 0    PRIMARY        Global keywords (FITAVER, FITAPACK, FITANL, DATE, CREATOR)
HDU 1    FITA_LAYERS    BINTABLE — layer index (non-authoritative)
         ── per layer, ascending and contiguous: ──
         FLUX_nnnn      IMAGE  calibrated flux (float32)          REQUIRED
         ALPHA_nnnn     IMAGE  display transparency (uint16)      REQUIRED
         UNCERT_nnnn    IMAGE  1-sigma uncertainty                OPTIONAL
         MASK_nnnn      IMAGE  quality bitmask                    OPTIONAL
HDU N-1  FITA_ADJ       BINTABLE — non-destructive display stack  OPTIONAL
HDU N    FITA_META      BINTABLE — IVOA ObsCore v1.2 provenance   OPTIONAL
```

**The `FLUX_*` header is normative**; `FITA_LAYERS` is an index only. A header
travels with its data; a table can desynchronise.

`CHECKSUM` and `DATASUM` are written on every HDU.

---

## Conformance

Two levels, and a checker that reports them:

| Level | Meaning |
|---|---|
| **FITA-CORE** | every MUST in §§3–7. The minimum for a file to be called `.fita`. |
| **FITA-FULL** | FITA-CORE + every SHOULD + a conformant ObsCore v1.2 `FITA_META`. The bar for publication, archiving or VO registration. |

```bash
fita conform yourfile.fita          # --quiet, --strict; exit 0/1/2
fita doctor                         # is this INSTALL correct, from here?
```

A [conformance corpus](corpus/) of 18 files with recorded status ships with
this repository, so an independent implementation can be **scored rather than
trusted**.

---

## Quick start

```bash
pip install fita
```

```python
from fita import FITACube, FITALayer

layers = [
    FITALayer.from_array(halpha, layer_id=1, name="Halpha", wave_cval=656.3e-9),
    FITALayer.from_array(k_band, layer_id=2, name="K",      wave_cval=2.2e-6),
]

cube = FITACube(layers=layers)
cube.save("field.fita", provenance={
    "obs_id": "MY-001", "facility": "SkyView", "ra": 299.9, "dec": 22.7,
})

# Re-select the display range. FLUX_* is untouched, bit-for-bit.
cube.reselect_flux_range(flux_min=10, flux_max=5000, stretch_mode="log")

display = cube.composite()          # float32 (H, W) in [0, 1]
waves, fluxes = cube.sed(px=512, py=512)
```

---

## Features

| Feature | Detail |
|---|---|
| **Per-layer alpha** | uint16 with `BZERO=32768`, derived from a selected flux range |
| **14 blend modes** | `NORMAL SCREEN MULTIPLY ADD OVERLAY SOFTLGT HARDLGT CDODGE CBURN DIFF LUM COLOR HUE SAT` |
| **Adjustment layers** | `FITA_ADJ` — LEVELS, CURVES, BRIGHTNESS, FXSTRETCH, BANDMAP, FXNORM, in typed columns |
| **Phased stereography** | `FITA_ZDP` encodes physical ISM penetration depth; `FITA_ZSC`/`FITA_ZRF`/`FITA_ZAN` record the rendered parallax |
| **Per-layer WCS** | multi-resolution layers without resampling to a common grid |
| **Uncertainty & masks** | companion `UNCERT_*` / `MASK_*` planes |
| **Provenance** | IVOA ObsCore DM v1.2, all mandatory columns, UCDs as `TUCDn` |
| **Three backends** | FITS-MEF, HDF5, Zarr — one container-independent data model |
| **PSD import** | Adobe Photoshop layers, blend modes and masks |

### Blend modes worth knowing

`ADD` / `SCREEN` accumulate emission-line signal without clipping.
`LUM` + `COLOR` is the canonical multi-wavelength pair: brightness from the
calibrated flux layer, hue from a false-colour or reference layer — so the
composite is *physically meaningful in brightness* and merely informative in
colour.

> On single-channel data the four HSL modes promote to greyscale, which makes
> `LUM` mathematically identical to `NORMAL`. It is a no-op on one layer.

### Phased stereography

`FITA_ZDP` assigns each layer a depth in `[0,1]` encoding **physical ISM
penetration depth**, not an arbitrary stacking order — 21 cm H I at `0.0`,
H-alpha at `0.5`, X-ray plasma at `1.0`. A renderer applies a differential
horizontal offset:

```
dx = ±(FITA_ZSC / 2) × (FITA_ZDP − FITA_ZRF)
```

`FITA_ZRF` is the depth placed at the screen plane, so the depth budget can be
spent in both directions rather than always pushed forward.

---

## Interoperability

| Target | How |
|---|---|
| **Any FITS reader** | directly — `.fita` is a valid FITS MEF |
| **SAO DS9** | `send_to_ds9()`, or a generated analysis-menu file |
| **qFITSView** | RGB false-colour FITS export |
| **FITS Liberator** | sidecar JSON |
| **Aladin** | HiPS tiles + MOC |
| **Photoshop** | PSD import |
| **HDF5 / Zarr** | same data model, different container |

---

## Status, honestly

A young convention with one reference implementation. What is established, and
what is not:

**Established.** The flux/alpha invariant holds bit-for-bit in the default
`FLOAT32` mode — measured, zero pixels altered. Files are valid FITS with
verifying checksums. The FITS ⇄ Zarr data model is verified equivalent.
241 tests pass.

**Not established.** The HDF5 backend round-trip is **untested**, so the
"all three backends" claim is confirmed for two of three. No `.fita` file has
been registered with a VO service — ObsCore completeness is verified by column
inspection, not by registration. Alpha encoding has been verified through
astropy but **not yet in DS9, QFitsView or Aladin**.

**Corrections that shipped.** Earlier versions of this document advertised a
`SPLIT16` packing mode and an ObsCore v1.1 compliance claim. `SPLIT16` was
measured to be *destructive* rather than lossy — the written file did not
retain the information needed to recover the flux at all — and was **deleted**
in v1.1: the writer refuses it and the reader raises. The ObsCore claim was an
overclaim (nine mandatory columns missing, per-column UCDs never written to the
file); it was withdrawn, then earned properly at v1.2. The unregistered MIME
type `application/fits+alpha` is no longer emitted. See
[`FITA_AMENDMENT__2026-08-02.md`](FITA_AMENDMENT__2026-08-02.md).

---

## Documents

| File | Standing |
|---|---|
| [`FITA_FORMAT_STANDARD`](FITA_FORMAT_STANDARD.RATIFIED-2026-08-02.md) | **Normative.** Governs everything. |
| [`FITA_AMENDMENT__2026-08-02.md`](FITA_AMENDMENT__2026-08-02.md) | v1.1 → v1.2 clause text |
| [`FITA_v1.1_RATIFICATION__2026-08-02.md`](FITA_v1.1_RATIFICATION__2026-08-02.md) | decision log |
| [`corpus/README.md`](corpus/README.md) | the conformance corpus |
| [`FITA_Format_Guide.ipynb`](FITA_Format_Guide.ipynb) | tutorial — **non-normative** |

Where any document and the standard disagree, **the standard governs**.

---

## Command line

```bash
fita conform FILE...        # validate against the standard
fita doctor                 # diagnose this installation
fita info FILE              # layer summary
fita from-fits IN OUT       # import a FITS cube
fita from-psd IN OUT        # import Photoshop layers
fita reselect FILE          # re-derive alpha from a new flux range
fita rgb FILE OUT           # RGB composite for qFITSView
fita ds9-plugin [OUT]       # DS9 analysis-menu file
fita liberator FILE         # FITS Liberator sidecar
```

## Installation

```bash
pip install fita                 # core: numpy + astropy
pip install "fita[psd]"          # + Photoshop import
```

## Citing

See [`CITATION.cff`](CITATION.cff).

## Licence

MIT for the software ([`LICENSE`](LICENSE)). The format specification is
dedicated to the public domain under CC0 ([`LICENSE-SPEC`](LICENSE-SPEC)) —
a specification that cannot be freely re-implemented is not a standard.
