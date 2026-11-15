# FITA — Flexible Image Transfer Alpha

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.21763301.svg)](https://doi.org/10.5281/zenodo.21763301)
[![tests](https://github.com/Astroobserver11/MWVO_FITA/actions/workflows/ci.yml/badge.svg)](https://github.com/Astroobserver11/MWVO_FITA/actions/workflows/ci.yml)

**A FITS convention for multi-layer astronomical images with a display channel
that cannot touch the science.**

| | |
|---|---|
| **File suffix** | `.fita` |
| **Format version** | `FITAVER = 1.5` — the **format** |
| **Package version** | `mwvo-fita` 1.5.3 — the **software**; it may advance without `FITAVER` moving ([§13.1](https://github.com/Astroobserver11/MWVO_FITA/blob/main/FITA_FORMAT_STANDARD.md)) |
| **MIME type** | `application/fits` |
| **Based on** | FITS Standard v4.0 — every `.fita` file is a valid FITS MEF |
| **Normative spec** | [`FITA_FORMAT_STANDARD.md`](https://github.com/Astroobserver11/MWVO_FITA/blob/main/FITA_FORMAT_STANDARD.md) |
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
  not how the calibration was obtained. That is
  [URANODYNE](https://github.com/Astroobserver11/uranodyne)'s job.

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
HDU N    FITA_META      BINTABLE — IVOA ObsCore v1.1 provenance   OPTIONAL
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
| **FITA-FULL** | FITA-CORE + every SHOULD + a conformant ObsCore v1.1 `FITA_META`. The bar for publication, archiving or VO registration. |

```bash
fita conform yourfile.fita   # exit 2 = non-conformant, ALWAYS
                             # --strict also exits 1 for CORE-but-not-FULL
fita doctor                         # is this INSTALL correct, from here?
```

A [conformance corpus](https://github.com/Astroobserver11/MWVO_FITA/tree/main/corpus) of 24 files with recorded status ships with
this repository, so an independent implementation can be **scored rather than
trusted**.

---

## Quick start

```bash
# Not on PyPI yet -- install from the repository. See Installation below.
pip install "mwvo-fita @ git+https://github.com/Astroobserver11/MWVO_FITA.git"
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
| **Phased stereography** | `FITA_ZDP` encodes physical ISM penetration depth, dimensionless or in `FITA_ZDU`; `FITA_ZSC` records the parallax as a percentage of the field `FITA_FDI`/`FITA_FDU` — a measure in units practical to the subject, never pixels |
| **Per-layer WCS** | multi-resolution layers without resampling to a common grid |
| **Uncertainty & masks** | companion `UNCERT_*` / `MASK_*` planes |
| **Provenance** | IVOA ObsCore DM v1.1, its column set, UCDs as `TUCDn` |
| **Three backends** | FITS-MEF, HDF5, Zarr — one container-independent data model; all three round-trip `FLUX` bit-exact and all three refuse non-float32 through one shared gate |
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
`FLOAT32` mode — measured, zero pixels altered. Since 1.5.2 it is also
**enforced**: all three writers refuse a `FLUX` array that is not float32
through one shared gate, rather than silently downcasting it. Files are valid
FITS with verifying checksums. The FITS ⇄ Zarr data model is verified
equivalent, and **the HDF5 round-trip is now verified too** — a three-layer
stack returns bit-exact float32 with names and types intact. The "three
backends" claim is confirmed for all three.

**Test counts, with their preconditions.** A bare number is not a claim about
coverage, so here is the whole table. All rows measured 2026-11-14 on CTOP,
Python 3.13.15, astropy 8.0.2, package 1.5.2:

| Configuration | passed | skipped |
|---|---|---|
| kernel only — `pip install ".[dev]"` **← what CI runs** | 293 | 3 |
| \+ `mwvo-fita[uranodyne]` and `uranodyne[pipeline]` | **341** | **0** |

The 3 skips in the CI row are the three URANODYNE-gated modules
(`test_calibration`, `test_pipeline`, `test_wideangle`) — by design, so the
kernel's own gate never depends on the science stack. Install everything and
**nothing is skipped**: a configuration that exists and was run, not an
aspiration.

⚠️ **What that first row used to hide.** Until 2026-11-14 `[dev]` did not
include `h5py`, and the same row read **264 passed, 17 skipped** (before the 14
concordance tests below were written) — the extra 14 skips being every test that
exercises the HDF5 backend, *including both `SPLIT16` refusal tests*. So **"CI green" was never evidence about HDF5.** That
is how a destructive packing mode stayed reachable through the HDF5 and Zarr
writers for three months after D-2 deleted it, while the AI format card
asserted that no conformant path could produce it. `h5py` is now in `[dev]`, so
the matrix exercises all three backends and the 14 tests run. §10.1's "cannot be
used **or verified**" was doing real work, and the dev extra was ignoring it.

Earlier editions of this table reported 221 and 269 from BTOP (Python 3.12) and
ATOP (Python 3.14.5, v1.3.0 source). Three environments produced three different
numbers and all three reported success — which is why counts are published with
their preconditions and why CI asserts a collected floor.

**Not established.** No `.fita` file has been registered with a VO service —
ObsCore completeness is verified by column inspection, not by registration.
Alpha encoding has been verified through astropy but **not yet in DS9,
QFitsView or Aladin**. The format is **not on PyPI**, so every install is from
git; publication is gated on the `[uranodyne]` extra's direct URL, which PyPI
refuses.

**Corrections that shipped.** Earlier versions of this document advertised a
`SPLIT16` packing mode and an ObsCore v1.1 compliance claim. `SPLIT16` was
measured to be *destructive* rather than lossy — the written file did not
retain the information needed to recover the flux at all — and was **deleted**
in v1.1: the writer refuses it and the reader raises. The ObsCore claim was an
overclaim (nine mandatory columns missing, per-column UCDs never written to the
file); it was withdrawn, then earned properly at v1.2. The unregistered MIME
type `application/fits+alpha` is no longer emitted. See
[`FITA_AMENDMENT__2026-08-02.md`](https://github.com/Astroobserver11/MWVO_FITA/blob/main/FITA_AMENDMENT__2026-08-02.md).

---

## Documents

| File | Standing |
|---|---|
| [`FITA_FORMAT_STANDARD.md`](https://github.com/Astroobserver11/MWVO_FITA/blob/main/FITA_FORMAT_STANDARD.md) | **Normative.** Governs everything. Version-neutral filename: the version is stated in §13, never in the name. |
| [`FITA_AMENDMENT__2026-08-02.md`](https://github.com/Astroobserver11/MWVO_FITA/blob/main/FITA_AMENDMENT__2026-08-02.md) | v1.1 → v1.2 clause text — **APPLIED** to the standard above; retained as the record of what changed and why |
| [`FITA_v1.1_RATIFICATION__2026-08-02.md`](https://github.com/Astroobserver11/MWVO_FITA/blob/main/FITA_v1.1_RATIFICATION__2026-08-02.md) | decision log |
| [`corpus/README.md`](https://github.com/Astroobserver11/MWVO_FITA/blob/main/corpus/README.md) | the conformance corpus |
| [`FITA_Format_Guide.ipynb`](https://github.com/Astroobserver11/MWVO_FITA/blob/main/FITA_Format_Guide.ipynb) | tutorial — **non-normative** |

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

The **distribution** is `mwvo-fita`; the **import name** is `fita`.

> ⚠️ **Not published yet.** `mwvo-fita` is not on PyPI at the time of writing, so
> use the git commands below. Do **not** run `pip install fita` — that name on
> PyPI belongs to an unrelated project and will install the wrong software.

**Git must be installed**, because pip shells out to it to clone these URLs. If
`git --version` fails in your shell, no command below will work.

```bash
# Core (numpy + astropy)
pip install "mwvo-fita @ git+https://github.com/Astroobserver11/MWVO_FITA.git"

# With Photoshop PSD import
pip install "mwvo-fita[psd] @ git+https://github.com/Astroobserver11/MWVO_FITA.git"

# With the URANODYNE science stack (see the note below -- install it this way)
pip install "mwvo-fita[uranodyne] @ git+https://github.com/Astroobserver11/MWVO_FITA.git"

# A specific, citable version. v1.3.0 is the newest TAG; the 1.5.x line is not
# tagged, so `@main` is the only way to get it.
pip install "mwvo-fita @ git+https://github.com/Astroobserver11/MWVO_FITA.git@v1.3.0"
```

Once published, the same installs become `pip install mwvo-fita` and
`pip install "mwvo-fita[psd]"`. The `[uranodyne]` extra cannot go to PyPI as
written, because PyPI rejects metadata carrying a direct URL — it will be
switched to a plain `uranodyne>=1.0.0` once URANODYNE is itself published.

### Installing URANODYNE

[URANODYNE](https://github.com/Astroobserver11/uranodyne) is a separate
distribution and is **not** required by the format kernel — `fita` never imports
it; the arrow only points the other way.

> ⚠️ **Do not install it on its own.** `pip install git+…/uranodyne.git` **fails
> resolution**, because URANODYNE requires `mwvo-fita>=1.5.0` and that is not on
> PyPI. Earlier editions of this README advertised exactly that command; it
> could not have worked.

Install it as the extra above, or name both explicitly:

```bash
pip install "mwvo-fita @ git+https://github.com/Astroobserver11/MWVO_FITA.git" \
            "uranodyne @ git+https://github.com/Astroobserver11/uranodyne.git"
```

Either way the dependency cycle resolves, because installing from a direct URL
pins the name `mwvo-fita` to that tree and satisfies URANODYNE's requirement
without a PyPI lookup.

Its own science dependencies are extras of URANODYNE. **Install `pipeline` if
you use IrenBLink:** without SciPy, `blink.significance_map()` warns and returns
a degraded result rather than refusing.

```bash
pip install "uranodyne[pipeline] @ git+https://github.com/Astroobserver11/uranodyne.git"
```

## Citing

    Cisneros, I. A. (2026). FITA — Flexible Image Transfer Alpha: a FITS
    convention for multi-layer astronomical images (v1.5.3).
    Zenodo. https://doi.org/10.5281/zenodo.24239352

Cite the **concept DOI** `10.5281/zenodo.21763301` for the software in general — it always
resolves to the newest deposit. Cite a **version DOI** when reproducibility matters and you
mean one release exactly. Enumerated from the Zenodo API, newest first:

| Release | Version DOI | Note |
|---|---|---|
| **v1.5.3** | `10.5281/zenodo.24239352` | the newest deposit; what the concept DOI resolves to |
| v1.3.0 | `10.5281/zenodo.21765462` | |
| v1.2.1 | `10.5281/zenodo.21765372` | the ObsCore label erratum |
| v1.2.0 | `10.5281/zenodo.21763344` | permanently carries the withdrawn *ObsCore v1.2* claim — see the [erratum](https://github.com/Astroobserver11/MWVO_FITA/blob/main/ERRATUM__ObsCore_version__2026-08-02.md) |
| v1.2.0 | `10.5281/zenodo.21763302` | **superseded duplicate**, 5 minutes older — do not cite |

Two records exist for v1.2.0 because Zenodo archives Releases and does not backfill, so that
release was deleted and recreated to get it deposited. v1.3.0 carries no tagged successor
until v1.5.3: the format reached 1.5 on 2026-08-07 and went untagged for three months.

Machine-readable metadata is in [`CITATION.cff`](https://github.com/Astroobserver11/MWVO_FITA/blob/main/CITATION.cff).

## Licence

MIT for the software ([`LICENSE`](https://github.com/Astroobserver11/MWVO_FITA/blob/main/LICENSE)). The format specification is
dedicated to the public domain under CC0 ([`LICENSE-SPEC`](https://github.com/Astroobserver11/MWVO_FITA/blob/main/LICENSE-SPEC)) —
a specification that cannot be freely re-implemented is not a standard.
