> **RATIFIED CANONICAL — v1.2.** Produced on BTOP 2026-08-02 by applying the validating author's
> ratification rulings (§12) to the byte-exact 2026-07-29 v1.1 DRAFT. The normative body (§§1–11)
> is unchanged from that DRAFT except where v1.2 amends it. `FITA_AMENDMENT__2026-08-02.md`
> §3.1–§3.8 has been **APPLIED**: §2.1 (checker), §4.2 (stereo + FITS provenance keywords),
> §8.2 (stereo convention), §8.3 (FITA_ADJ schema, new), §9 (ObsCore v1.2), §13. v1.2 adds only
> OPTIONAL structure, so files conformant at v1.1 remain conformant.
> **This file supersedes the DRAFT and is destined to replace `FITA_FORMAT_STANDARD.md` on ATOP**
> (deliver over the Tailscale bridge; do not maintain two canonicals). Ruling record of provenance:
> `FITA_v1.1_RATIFICATION__2026-08-02.md`.

# FITA — Flexible Image Transfer Alpha
## Format Standard Document — v1.2 (RATIFIED)

| Field | Value |
|---|---|
| **Document status** | **RATIFIED 2026-08-02** — normative; the §12 decisions are ruled (see §12.0). Ruled by I. A. Cisneros. |
| **Format version described** | `FITAVER = 1.1` (supersedes the as-built `1.0`) |
| **Date** | 2026-07-29 |
| **Authored on** | ATOP (`astro-workstation`) during the MWVO concordance sequence |
| **Supersedes** | `FITA_Format_Guide.ipynb` (tutorial), `fita/spec.py` docstring, and the digest in `MWVO_Rehydration_Capsule.md` §4.1, **as normative sources** |
| **Siblings** | `FITR_SPEC.md` (radio, v0.1 DRAFT) · `FITO_IDENTITY.md` / `FITO_SCHEMA.md` (ISM calculation object, DESIGN-ONLY) |

---

## 0. How to read this document

Key words **MUST**, **MUST NOT**, **REQUIRED**, **SHALL**, **SHOULD**, **SHOULD NOT**, **MAY**, and
**OPTIONAL** are to be interpreted as in RFC 2119.

Every normative clause carries a provenance tag:

| Tag | Meaning |
|---|---|
| `[AS-BUILT]` | The v1.0 implementation already does this; the clause records existing behaviour. |
| `[MEASURED]` | Established empirically on ATOP 2026-07-29 against real `.fita` files. Evidence in §11. |
| `[CORRECTION]` | The v1.0 implementation **violates** this clause. Normative here; code change required. |
| `[NEW]` | Not present in any prior source. Requires Ignacio's ruling — see §12. |

A clause with no tag is a restatement of the FITS Standard (v4.0) and is not FITA's to decide.

---

## 1. Scope and purpose

### 1.1 What FITA is

FITA is a **multi-layer astrophysical image format** that carries several co-registered science
images, each with its own calibration, bandpass, uncertainty, quality mask, compositing metadata
and stereo-depth assignment, inside a single file that remains a legal FITS multi-extension file
(MEF).

FITA's reason to exist is one invariant, stated normatively in §5: **the flux is the physics and
nothing in the display path may touch it.** Every other feature is subordinate to that.

### 1.2 Relationship to FITS

A conformant `.fita` file **MUST** be a valid FITS file per the FITS Standard v4.0. FITA adds no new
data structures — it is a *convention over* FITS: reserved `EXTNAME` values, a registry BINTABLE,
and a set of `FITA_*` keywords in the reserved-for-user keyword space.

`[MEASURED]` All 18 `.fita` files on ATOP pass `astropy.io.fits` `verify('exception')` with zero
warnings. The claim "a `.fita` file is a valid FITS MEF" is **TRUE and empirically confirmed**, and
the claim "opens natively in DS9 / QFitsView / FITS Liberator / Aladin without a plugin" is
structurally supported.

**However** — and this is the distinction the concordance audit was called to make — *structural*
legality is not *semantic* correctness. A file can be legal FITS and still mean something different
to a third-party reader than it means to its writer. FITA v1.0 has exactly this problem in two
places (§6.3 alpha encoding, §7 BUNIT). Those are `[CORRECTION]` clauses below.

### 1.3 What FITA is NOT

This section exists to stop concept-merging. It is normative in the sense that a document or
implementation that blurs these boundaries is non-conformant with the format family.

| Not this | Because |
|---|---|
| **FITSA** (`ISM_Motion_new/src/compositing/fitsa.py`) | An older, simpler *annotated event-cutout* format. Different data model, different purpose. FITA supersedes it for multi-band science; FITSA remains in use for event-annotation packaging. **The one-letter name difference is a standing hazard — never abbreviate either as "the FITS-A format".** |
| **FITR** (`.fitr`) | The radio/interferometry sibling. HDF5-native, uv-space first, complex64 visibilities. FITA does not store visibilities, antenna tables, or calibration solutions. See §10.1. |
| **FITO** (`.fito`) | The ISM energy-budget **calculation object**. FITO *consumes* FITA and FITR as inputs and reasons over them; it is not a container for images. FITA has no opinion about paradigms, epistemic half-life, or `(input, core, paradigm)` stamps. See §10.2. |
| A rendering engine | FITA stores compositing *metadata* (blend mode, opacity, alpha). Producing pixels on a screen is the renderer's job. |
| A calibration pipeline | FITA stores calibrated flux and its provenance. It does not define how the calibration was obtained. |

---

## 2. Conformance

### 2.1 Conformance levels

`[NEW]` Two levels are defined. A file's level is not recorded in the file; it is a property a
validator reports.

**FITA-CORE** — a file is FITA-CORE conformant iff it satisfies every **MUST** in §§3–7. This is the
minimum for a file to be called `.fita` and is what any FITA reader may assume.

**FITA-FULL** — FITA-CORE, plus every **SHOULD** in §§3–9 is satisfied, plus a conformant
`FITA_META` provenance HDU (§9) is present. This is the bar for a file that is to be published,
archived, delivered to a collaborator, or registered in a VO service.

`[NEW]` A conformance checker **SHOULD** be provided as `fita.validate(path) -> ConformanceReport`.
`[AS-BUILT v1.2]` It is provided, and exposed on the command line as `fita conform`
(`--quiet`, `--strict`; exit 0 = FITA-FULL, 1 = FITA-CORE, 2 = non-conformant). The absence of
such a checker in v1.0 is why the defects in §11 went undetected through 110 passing tests.

`[NEW v1.2]` The §5.4 flux comparison **MUST** be NaN-aware. `numpy.array_equal` is False
whenever a NaN is present, and blanked pixels are ubiquitous in real data; compare the NaN
masks and the finite pixels separately. A test that is not NaN-aware fails on every real image
and will be disabled rather than fixed.

### 2.2 Conformance of readers

A conformant reader **MUST** treat the `FLUX_*` extension headers as authoritative for all layer
metadata, and **MUST** treat the `FITA_LAYERS` BINTABLE as an index only (§4.3).

A conformant reader **MUST NOT** apply `BSCALE`/`BZERO` a second time to data returned by a FITS
library that has already applied them. `[CORRECTION]` — v1.0 `fita.io.read()` does exactly this in
the `SPLIT16` branch.

---

## 3. File identification

| Property | Value | Tag |
|---|---|---|
| File suffix | `.fita` | `[AS-BUILT]` |
| FITS magic | `SIMPLE = T` | `[AS-BUILT]` |
| Version keyword | `FITAVER` in PRIMARY | `[AS-BUILT]` |
| MIME type | `application/fits` | `[CORRECTION]` |

`[CORRECTION]` v1.0 asserts the MIME type `application/fits+alpha` in `spec.py` and writes it into
the `access_format` column of `FITA_META`. **That type is not registered with IANA and MUST NOT be
emitted into provenance metadata as though it were.** Until registration is actually pursued and
granted, conformant files **MUST** declare `access_format = "application/fits"`. A FITA-specific
type **MAY** be recorded in a separate non-normative keyword. Emitting an unregistered MIME type
into a VO-searchable provenance table is the kind of unearned authority claim the MWVO fences exist
to prevent.

---

## 4. HDU layout (normative)

### 4.1 Canonical layout

```
HDU 0    PRIMARY        No data. Global keywords (§4.2).
HDU 1    FITA_LAYERS    BINTABLE. Layer index, one row per layer (§4.3).
         --- then, for each layer i = 1..FITANL, in ascending i: ---
         FLUX_nnnn      IMAGE. Calibrated physical flux.        REQUIRED
         ALPHA_nnnn     IMAGE. Display transparency.            REQUIRED
         UNCERT_nnnn    IMAGE. 1-sigma per-pixel uncertainty.   OPTIONAL
         MASK_nnnn      IMAGE. Quality bitmask.                 OPTIONAL
         --- end per-layer block ---
HDU N-1  FITA_ADJ       BINTABLE. Adjustment-layer stack.       OPTIONAL  (see §8)
HDU N    FITA_META      BINTABLE. Provenance.                   OPTIONAL at CORE, REQUIRED at FULL
```

`nnnn` is the 1-based layer index, zero-padded to exactly 4 digits (`FLUX_0001`). `[AS-BUILT]`

A conformant writer **MUST** emit the per-layer block contiguously and in ascending layer index.
`[MEASURED]` v1.0 already does this.

`[CORRECTION]` Three layouts are in circulation and they disagree. `spec.py`'s docstring shows
`FITA_ADJ` and omits `UNCERT_*`/`MASK_*`; `io.py` writes `UNCERT_*`/`MASK_*` and never writes
`FITA_ADJ`; the capsule digest matches `io.py`. **The layout above is canonical.** `FITA_ADJ` is
retained as OPTIONAL and currently unimplemented — see §8 and open decision D-3.

### 4.2 PRIMARY keywords

| Keyword | Type | Req. | Meaning | Tag |
|---|---|---|---|---|
| `FITAVER` | str | **MUST** | Format version, e.g. `'1.1'` | `[AS-BUILT]` |
| `FITAPACK` | str | **MUST** | `'FLOAT32'` or `'SPLIT16'` (§6.4) | `[AS-BUILT]` |
| `FITANL` | int | **MUST** | Number of layers | `[AS-BUILT]` |
| `FITACW` | int | **SHOULD** | Canvas width (px) | `[CORRECTION]` |
| `FITACH` | int | **SHOULD** | Canvas height (px) | `[CORRECTION]` |
| `BUNIT` | str | **SHOULD** | Default flux unit if layers do not override | `[AS-BUILT]` |
| `INSTRUME` | str | **MAY** | Originating instrument | `[AS-BUILT]` |
| `FITA_ZSC` | float | **MAY** | Stereo parallax: total horizontal separation in px across the full `FITA_ZDP` range (§8.2) | `[NEW v1.2]` |
| `FITA_ZRF` | float | **MAY** | Reference plane: the `FITA_ZDP` value placed at zero parallax; default `0.0` (§8.2) | `[NEW v1.2]` |
| `FITA_ZAN` | float | **MAY** | Angular measure of the full-range parallax, arcsec on sky (§8.2) | `[NEW v1.2]` |
| `DATE` | str | **SHOULD** | UTC date the file was written, ISO-8601 | `[NEW v1.2]` |
| `CREATOR` | str | **SHOULD** | Software that wrote the file | `[NEW v1.2]` |
| `ORIGIN` | str | **MAY** | Organisation responsible for the file | `[NEW v1.2]` |

`[CORRECTION]` `spec.py` declares `FITACW`/`FITACH` under the heading "Primary HDU **mandatory**
keywords", but `io.py` writes them only when truthy, and `[MEASURED]` **all 18 files on ATOP omit
them entirely**. The conflict is resolved downward to **SHOULD**: layers carry their own WCS and
offsets, so the canvas box is derivable and cannot be made mandatory retroactively without
invalidating every existing file. The "mandatory" heading in `spec.py` is wrong and must be edited.

### 4.3 The `FITA_LAYERS` registry — authority

`[CORRECTION]` **The `FLUX_*` extension header is normative. The `FITA_LAYERS` BINTABLE is a
non-authoritative index.**

This resolves a genuine ambiguity: v1.0 *writes* a full 15-column registry but `fita.io.read()`
builds the registry dict, defines a `_g` accessor — and then never uses either, reading every field
from the `FLUX_*` header instead. The registry is decorative in practice.

Making the header normative is the resolution that matches both the implementation and the FITS
philosophy (a header travels with its data; a table can desynchronise). Consequences:

- A writer **MUST** write every layer property to the `FLUX_*` header (§6.2).
- A writer **MUST** keep `FITA_LAYERS` consistent with the headers.
- A reader **MUST NOT** depend on `FITA_LAYERS` for correctness; it **MAY** use it to enumerate
  layers without touching image data.
- Where the two disagree, the header wins, and a validator **SHOULD** report the discrepancy.

`FITA_LAYERS` columns are as in `spec.py` `LAYER_TABLE_COLS` `[AS-BUILT]`, with one correction:
the `ZDEPTH` column uses `-1.0` as an "absent" sentinel, which is outside the documented `[0,1]`
domain and is not documented anywhere. A writer **MUST** document the sentinel or use a null-valued
column (`TNULL`). See open decision D-5.

---

## 5. The flux/alpha invariant (the core clause)

**5.1** `FLUX_*` **MUST** contain calibrated physical flux in the units declared by `BUNIT`. This
array **IS** the science.

**5.2** `ALPHA_*` is **display-only**. Deriving, recomputing, or overriding alpha **MUST NOT**
modify `FLUX_*` by any amount, including round-off.

**5.3** A reader that writes a file back after any display-side operation **MUST** reproduce
`FLUX_*` bit-for-bit.

`[MEASURED]` Under `FITAPACK = 'FLOAT32'` this invariant **holds exactly**: a write/read round trip
of a 64×64 layer with a 5-decade dynamic range returned `numpy.array_equal(...) == True`, max
absolute error 0, 0 of 4096 pixels altered. Changing the display range alters only `alpha_data`.
**The format's central promise is kept in its default mode.**

`[MEASURED]` Under `FITAPACK = 'SPLIT16'` this invariant **is violated catastrophically** — see
§6.4 and §11.2. That is why §6.4 deprecates it.

**5.4** `[NEW]` The invariant **MUST** be enforced by an automated test that compares flux
bit-for-bit across a write/read cycle, for every packing mode the implementation offers. v1.0's
`test_io_roundtrip_split16` asserts only `alpha_data is not None` and therefore cannot fail on flux
corruption. An untested invariant is a claim, not a guarantee.

---

## 6. Layer data extensions

### 6.1 `FLUX_nnnn`

`BITPIX` **MUST** be `-32` (float32) when `FITAPACK = 'FLOAT32'`. `[AS-BUILT]`
`BUNIT` **SHOULD** be present and **MUST** be a valid FITS unit string (§7).
A 2-D celestial WCS **SHOULD** be present. `[AS-BUILT]`

### 6.2 Layer keywords (in each `FLUX_nnnn` header)

| Keyword | Type | Req. | Meaning | Tag |
|---|---|---|---|---|
| `FITA_LID` | int | **MUST** | Layer index, 1-based, equal to `nnnn` | `[AS-BUILT]` |
| `FITA_LNM` | str | **MUST** | Human label, ≤68 chars | `[AS-BUILT]` |
| `FITA_BLD` | str | **MUST** | Blend-mode code from §8.1 | `[AS-BUILT]` |
| `FITA_OPC` | float | **MUST** | Layer opacity, `[0,1]` | `[AS-BUILT]` |
| `FITA_ALS` | str | **MUST** | Alpha source: `LUM` \| `USER` \| `NONE` | `[AS-BUILT]` |
| `FITA_VIS` | bool | **MUST** | Layer visibility | `[CORRECTION]` |
| `FITA_XOF` | float | **SHOULD** | Canvas x-offset (px) | `[AS-BUILT]` |
| `FITA_YOF` | float | **SHOULD** | Canvas y-offset (px) | `[AS-BUILT]` |
| `FITA_FMN` | float | **SHOULD** | Flux range floor used for alpha derivation | `[AS-BUILT]` |
| `FITA_FMX` | float | **SHOULD** | Flux range ceiling | `[AS-BUILT]` |
| `FITA_WCV` | float | **SHOULD** | Central wavelength, **metres** | `[AS-BUILT]` |
| `FITA_WBW` | float | **MAY** | Bandpass FWHM, metres | `[AS-BUILT]` |
| `FITA_ZDP` | float | **MAY** | Stereo depth, `[0,1]` (§8.2) | `[AS-BUILT]` |
| `FITA_UNC` | str | **MAY** | `EXTNAME` of the companion uncertainty plane | `[AS-BUILT]` |
| `FITA_MSK` | str | **MAY** | `EXTNAME` of the companion mask plane | `[AS-BUILT]` |

`[CORRECTION]` **`FITA_VIS` is new and required.** `[MEASURED]` Layer visibility is currently stored
**only** in the `FITA_LAYERS` table, and since readers take everything from the header (§4.3), it is
silently lost: a layer written with `visible = False` reads back as `visible = True` through the
FITS backend **and** through the Zarr backend. This is real metadata loss on every round trip in
every backend, and it is invisible because nothing tests it.

### 6.3 `ALPHA_nnnn` — encoding

Alpha is an unsigned 16-bit quantity, `0` = fully transparent, `65535` = fully opaque. `[AS-BUILT]`

`[CORRECTION]` A conformant writer **MUST** store alpha using the FITS unsigned-16 convention:
`BITPIX = 16` **with `BZERO = 32768` and `BSCALE = 1`**. Writing the array as plain signed `int16`
without `BZERO` is **non-conformant**.

`[MEASURED]` v1.0 casts alpha to `int16` with no `BZERO`. Consequence: every alpha value above
32767 — i.e. everything more than half-opaque — is stored as a **negative** number. **All 18 `.fita`
files on ATOP exhibit this**, including the six `stereo_atlas` region files and the 437 MB all-sky
dust file written on 2026-07-27. In `rhooph_extinction.fita` every alpha plane is uniformly `-1`,
which is `65535` (fully opaque) wrapped.

The round trip happens to survive *inside this library* because `read()` casts straight back to
`uint16`, so the wrap is undone by a matching bug. **A third-party viewer has no such compensating
bug**: DS9, QFitsView and Aladin will read the alpha plane exactly as written, i.e. as signed values
running from −32768 to +32767. This is the precise sense in which FITA v1.0 is *structurally* legal
FITS but *semantically* wrong — and it is the answer to the capsule's first fault line.

No science flux is affected: alpha is display-only by §5.2, and `[MEASURED]` **0 of 18 files use
`SPLIT16`** (all are `FLOAT32`), so no archived FITA product on ATOP has corrupted flux.

`[CORRECTION]` The `ALPHA_*` header **MUST NOT** declare `BUNIT = 'alpha16'` (§7).

### 6.4 `FITAPACK` — packing modes

**`FLOAT32`** — flux stored as `BITPIX = -32`. Lossless. **This is the default and the only mode a
conformant writer may use for science-grade output at FITA-FULL.** `[MEASURED]` verified
bit-exact.

**`SPLIT16`** — `[CORRECTION]` **DEPRECATED in v1.1. A conformant writer MUST NOT emit
`FITAPACK = 'SPLIT16'`.** A reader encountering it **MUST** raise rather than return flux values.

`[MEASURED]` The mode is not lossy — it is destructive, and the file does not contain the
information needed to recover the flux at all. Three independent faults compound (§11.2):

1. `encode_split16()` returns correct `uint16` in `0..65535`, but `io.write()` casts to `int16`
   without `BZERO = 32768`, wrapping the upper half of the range negative.
2. `io.write()` sets `BSCALE`/`BZERO` on the header, but hands astropy data that is already
   integer-typed, so **astropy discards both keywords**. The written file contains
   `BSCALE = None, BZERO = None` — the encoding parameters that define the flux scale are simply
   **absent from the file**.
3. `io.read()` therefore falls back to `BSCALE = 1.0, BZERO = 0.0` and returns the raw wrapped
   integers as if they were physical flux.

Measured on a 10→1000 Jy ramp: readback range `−32760 .. 32759` against a truth range of
`10 .. 1000`; max relative error `3.5 × 10⁶`; **4096 of 4096 pixels altered**; the brightest pixel
read back as `−1`.

The documented figure of "~1.5 × 10⁻⁵ relative error", repeated in `spec.py`, the guide notebook,
the memory file and the capsule digest, describes only the *encoder function in isolation*, which
`[MEASURED]` is indeed sound (max error 0.0075 on a 985-unit span). It has never described the file
format.

`[CORRECTION]` Even if the three faults are fixed, the "~1.5 × 10⁻⁵ **relative** error" claim is
misleading and **MUST NOT** be restated. The quantisation step is `(FMAX − FMIN)/65535`, which is a
constant **absolute** quantum: it is 1.5 × 10⁻⁵ *of the dynamic range*, not of the pixel value. For
a faint pixel near `FMIN` the relative error approaches 100%. Additionally `normalise()` **clips**
to `[FMIN, FMAX]`, and the default `auto_range()` uses the 0.5/99.5 percentiles, so a default
`SPLIT16` write **discards the brightest 0.5% and faintest 0.5% of pixels outright** — measured at
272× compression of the true peak on a realistic source-plus-sky field. For emission-line and
point-source astronomy those are exactly the pixels that carry the science.

Whether `SPLIT16` is repaired or deleted is a science-budget judgement, not mine — open decision D-2.

### 6.5 `UNCERT_nnnn` and `MASK_nnnn`

`UNCERT_*`: `BITPIX = -32`, 1-sigma per-pixel error, **MUST** be in the same units as its
`FLUX_*`. `[AS-BUILT]`
`MASK_*`: `BITPIX = 8`, bit 0 = bad, bit 1 = saturated, bit 2 = cosmic ray, bit 3 = gap; bits 4–7
reserved. `[AS-BUILT]`
Both **MUST** be cross-referenced from the `FLUX_*` header via `FITA_UNC` / `FITA_MSK`. `[AS-BUILT]`

---

## 7. Units

`BUNIT`, wherever it appears, **MUST** be a string parseable as a unit by the FITS units convention
(FITS Standard §4.3).

`[CORRECTION]` `[MEASURED]` v1.0 emits two invalid `BUNIT` values, both confirmed to fail
`astropy.units.Unit(..., parse_strict='raise')`:

| Written | Where | Verdict | Required |
|---|---|---|---|
| `'alpha16'` | every `ALPHA_*` header, all 18 files | INVALID | Omit `BUNIT`, or `''` (dimensionless) |
| `'same as FLUX'` | every `UNCERT_*` header | INVALID | The **actual** unit string of the parent `FLUX_*` |

`'same as FLUX'` is the worse of the two: it is a note to a human placed in a field a machine reads,
in the one extension whose entire purpose is to be numerically comparable to the flux. A pipeline
that trusts `BUNIT` on an uncertainty plane gets a parse error instead of an error bar.

---

## 8. Compositing and depth semantics

### 8.1 Blend-mode registry

Fourteen modes. `[AS-BUILT]` — all fourteen are implemented in `blend.py` and dispatch correctly.

| Class | Codes |
|---|---|
| Arithmetic | `NORMAL`, `ADD`, `SCREEN`, `MULTIPLY`, `DIFF` |
| Contrast | `OVERLAY`, `SOFTLGT`, `HARDLGT` |
| Exposure | `CDODGE`, `CBURN` |
| HSL | `LUM`, `COLOR`, `HUE`, `SAT` |

All blend functions operate on float32 arrays normalised to `[0,1]`; they are **display**
operations and by §5.2 **MUST NOT** be applied to `FLUX_*`. `FITA_BLD` **MUST** be one of the
fourteen codes; a reader encountering an unknown code **MUST** raise rather than silently fall back
to `NORMAL`.

`[NEW]` The four HSL modes require 3-channel input. For single-channel data the implementation
promotes to greyscale, which makes `LUM` mathematically identical to `NORMAL`. This **SHOULD** be
documented in the guide, as `LUM` is advertised as the canonical multi-band mode and is a no-op on
a single layer.

Astrophysical practice (non-normative): `ADD`/`SCREEN` for emission-line compositing; `LUM` for
false-colour where brightness comes from the science layer and hue from a reference layer.

### 8.2 `FITA_ZDP` — phased stereography

`FITA_ZDP` assigns each layer a depth in `[0,1]`, where `0.0` is the deepest/background plane and
`1.0` the foreground. It encodes **physical ISM penetration depth**, not an arbitrary stacking
order: 21 cm H I → 0.0; Hα → 0.5; X-ray hot plasma → 1.0. `[AS-BUILT]`

A renderer **SHOULD** apply a differential x-offset proportional to `FITA_ZDP` to produce binocular
parallax. `[MEASURED]` `FITA_ZDP` survives round-trip through both the FITS and Zarr backends.

`[CORRECTION]` Absence of depth **MUST** be encoded by omitting the keyword, **not** by writing a
negative sentinel. v1.0 writes `-1.0` into the `ZDEPTH` *table column* while omitting the header
keyword — two different absence conventions in one file. See D-5.

`[NEW v1.2]` This standard does not fix a single parallax scaling — the mapping belongs to a
rendering job, not to a file. It does require that a rendering which *has* fixed one **records
it**, so the depth stimulus remains measurable after the fact. Three OPTIONAL keywords carry that
record, written by a **renderer**, never by the compositor.

**Convention (normative whenever `FITA_ZSC` is present):**

```
FITA_ZSC  total horizontal parallax, in pixels, across the full FITA_ZDP range
FITA_ZRF  the FITA_ZDP value placed at ZERO parallax (the screen plane); default 0.0

per-eye offset:   dx = +/-(FITA_ZSC / 2) * (FITA_ZDP - FITA_ZRF)
                  left eye = -, right eye = +
```

A negative `FITA_ZSC` inverts the depth sense. A layer with no `FITA_ZDP` (absence by omission,
D-5) sits at zero parallax and **MUST NOT** be assigned a default depth.

`FITA_ZRF` exists so the depth budget can be spent in both directions. With `FITA_ZRF = 0.0` the
background sits at the screen and every layer is pushed forward; with `FITA_ZRF = 0.5` a mid-depth
layer sits at the screen, layers below it recede and layers above advance. `FITA_ZRF` **SHOULD**
lie within `[0,1]`.

**The angular measure.** `[NEW v1.2]` A parallax recorded only in pixels is a complete record
**only where no complete model is available**. Otherwise an angular measure is REQUIRED, **unless
it can be deduced from context** — a celestial WCS on any layer is such a context, since pixel
scale x `FITA_ZSC` yields the angle. Therefore `FITA_ZAN` **MAY** be omitted when a usable WCS is
present, and **SHOULD** be written when it is not. An implementation **MUST NOT** fabricate a pixel
scale in order to produce an angle: where the scale is unknown the angle is unknown, and reporting
it as such is the conformant behaviour.

`FITA_ZSC`, `FITA_ZRF` and `FITA_ZAN` **MUST** be finite when present. A `FITA_ZSC` on a cube where
no layer carries `FITA_ZDP` records a stimulus that was never applied, and is reported at SHOULD
severity.

> **Open.** Whether `FITA_ZAN` should measure a *sky* angle or a *viewing* disparity — screen pixel
> pitch and viewing distance, which is never deducible from the file — is not settled. This clause
> specifies the sky angle and is provisional in that respect.

---

### 8.3 `FITA_ADJ` — the adjustment stack

`[NEW v1.2]` `FITA_ADJ` is an OPTIONAL BINTABLE carrying the non-destructive display stack: an
ordered list of adjustments applied at composite time. It is display state and by §5.2 **MUST NOT**
modify `FLUX_*`. When present it **MUST** be written at HDU N-1, immediately before `FITA_META`.

**Schema — one row per adjustment, in application order:**

| Column | Format | Unit | Meaning |
|---|---|---|---|
| `ORDER` | `J` | | Application order, 0-based |
| `ADJ_TYPE` | `16A` | | Adjustment code (§8.3.1) |
| `ENABLED` | `L` | | Whether the adjustment is applied |
| `NAME` | `64A` | | Human label |
| `LAYER_ID` | `J` | | `0` = whole composite, `>0` = that layer only |
| `IN_BLACK` | `D` | | LEVELS input black point |
| `IN_WHITE` | `D` | | LEVELS input white point |
| `GAMMA` | `D` | | LEVELS gamma |
| `OUT_BLACK` | `D` | | LEVELS output black point |
| `OUT_WHITE` | `D` | | LEVELS output white point |
| `BRIGHT` | `D` | | BRIGHTNESS brightness, -1..+1 |
| `CONTRAST` | `D` | | BRIGHTNESS contrast, -1..+1 |
| `STRETCH` | `16A` | | FXSTRETCH mode: linear / log / sqrt / asinh / power |
| `ASINH_A` | `D` | | FXSTRETCH asinh softening parameter |
| `POWER_EXP` | `D` | | FXSTRETCH power-law exponent |
| `CHANNEL` | `2A` | | BANDMAP display channel: R / G / B |
| `WAVE_CVAL` | `D` | m | FXNORM wavelength at which response is sampled |
| `PARAMS` | `nA` | | JSON — variable-length parameters only |

**§8.3.1 Adjustment codes.** `LEVELS`, `CURVES`, `BRIGHTNESS`, `FXSTRETCH`, `BANDMAP`, `FXNORM`.
A reader encountering an unknown `ADJ_TYPE` **MUST** raise rather than silently drop the
adjustment — the same rule §8.1 sets for unknown blend codes. A display stack that quietly loses a
step is worse than one that refuses to load.

**§8.3.2 Typed columns are normative.** The common parameters **MUST** be written as the typed
columns above, not folded into `PARAMS`. FITA's premise is that any FITS reader can open the file;
a reader that opens the file but cannot see that `GAMMA = 2.2` has not been given the data.
`PARAMS` is reserved for parameters with no fixed width — currently `control_points` (CURVES) and
`response_curve` / `wavelengths` (FXNORM).

**§8.3.3 Absence.** A column that does not apply to a row carries the D-5 absence convention: NaN
for floating columns, empty string for character columns.

**§8.3.4 No silent truncation.** The `PARAMS` column width **MUST** be sized to the longest row
actually present. A fixed cap would silently discard long response curves, and undetectable data
loss is the failure mode this format has suffered most.

**§8.3.5 Validation.** When `FITA_ADJ` is present, a validator **MUST** check that the required
columns are present, that every `ADJ_TYPE` is known, and that every non-empty `PARAMS` cell is
parseable JSON — each at MUST severity. An adjustment that cannot be reconstructed is
indistinguishable from one that was never applied.

---

## 9. Provenance — `FITA_META`

At FITA-FULL a `FITA_META` BINTABLE **MUST** be present, carrying one row describing the file.

`[CORRECTION]` `[MEASURED]` **`FITA_META` is absent from all 18 `.fita` files on ATOP, and cannot
be produced by the standard writer at all**: `fita.ivoa.make_meta_hdu()` exists and works, but
`fita.io.write()` has no parameter through which to pass it and never appends it. The documented
provenance model is unreachable through the documented API. A conformant writer **MUST** accept
provenance and emit it.

`[CORRECTION]` The claim "ObsCore DM v1.1 compliant", as it appears in `spec.py`, `ivoa.py`, the
memory file and the capsule, is **an overclaim and MUST be withdrawn**. The 22-column table omits
ObsCore mandatory fields including `obs_publisher_did`, `s_region`, `access_estsize`, `o_ucd`,
`s_xel1`, `s_xel2`, `t_xel` and `em_xel`. Furthermore the per-column UCDs listed in `_OBSCORE_COLS`
are **never written to the file** — no `TUCDn` keywords are emitted — so the semantic annotation
that would make the table VO-interpretable is discarded at write time.

`[AS-BUILT v1.2]` **D-4 is implemented.** `FITA_META` carries a full IVOA **ObsCore DM v1.2**
mandatory column set; every column's UCD is written as `TUCDn`; and `access_format` is
`application/fits`. Provenance is reachable through the documented API via
`io.write(path, layers, provenance=...)`, closing the v1.0 condition in which the provenance
model was documented but unreachable. The wording *"ObsCore DM v1.2"* is now accurate and may
be used without qualification. (Superseded interim wording, retained for the record: *"an
ObsCore-derived provenance subset"*.) Whether to
close it fully is D-4.

`[CORRECTION]` `spec.py` documents UCDs as carried in `UCDXXXXX` keywords; `ivoa.py` writes `UCD1`.
Neither is the FITS convention for table-column UCDs, which is `TUCDn`. Column UCDs **MUST** be
written as `TUCDn`.

---

## 10. Backend equivalence and the format family

### 10.1 The three backends

The FITA **data model** — flux, alpha, uncertainty, mask, WCS, and the layer keywords of §6.2 — is
container-independent and **MUST** be preserved identically across all three backends.

| Backend | Module | Status on ATOP |
|---|---|---|
| FITS-MEF | `fita.io` | Default; verified |
| HDF5 | `fita.backends.hdf5` | `[MEASURED]` **untestable — `h5py` is not installed on ATOP** |
| Zarr | `fita.backends.zarr` | `[MEASURED]` verified (zarr 3.2.1, numcodecs 0.16.5) |

`[MEASURED]` Cross-backend equivalence, FITS ⇄ Zarr, on a layer carrying flux + alpha + uncertainty
+ mask + WCS + all metadata: **flux bit-identical; uncertainty, mask, WCS, `zdepth`, `opacity`,
`blend_mode`, `name` all preserved.** The capsule's fault line 4 is answered: the equivalence claim
is substantially TRUE.

Two qualifications:
- `visible` is lost by **both** backends (§6.2) — a data-model-level defect, not a container one.
- The Zarr backend stores alpha correctly as `uint16 0..65535`. **The FITS backend is the outlier**
  (§6.3). This is independent evidence that `uint16` is the intended model and the FITS writer is
  the thing that is wrong.

The HDF5 backend could not be exercised. Its correctness on ATOP is **unverified**, and the
changelog claim "survives round-trip through all three backends" is therefore confirmed for two of
three. `pip install h5py` is required before that claim may be restated.

### 10.2 FITR — and a broken dependency

FITR is the radio sibling (HDF5-native, complex64 visibilities, `.fitr`). Its `/image/` planes are
claimed by `FITR_SPEC.md` §7 to carry "the **exact same** metadata attributes" as FITA `FLUX_*`
headers.

`[MEASURED]` **The identity is aspirational, not real.** FITR is a v0.1 DRAFT with no reference
implementation; `FITALayer.from_fitr_image()` is marked "planned v1.1" and does not exist. The
identity already breaks at the type level: `FITR_SPEC.md` specifies `alpha` as `uint16`, which is
correct and is what FITA *means*, but not what FITA v1.0 *writes* (§6.3). Any FITR→FITA bridge
built today against real FITA files would ingest signed, wrapped alpha.

`[CORRECTION]` **`FITR_SPEC.md` §8 declares that display mathematics "live in the FITA `FITA_ADJ`
adjustment-layer stack" — and `FITA_ADJ` is never written by `fita.io`.** FITR's specification
therefore delegates a responsibility to a FITA feature that does not exist in any file. This is the
sharpest single instance of the drift the concordance sequence was called to find: two sibling specs
that are individually coherent and jointly broken.

`[CORRECTION]` FITR declares ObsCore DM **v1.2**; FITA declares **v1.1**. Two members of one family
targeting two versions of the same data model, with FITR claiming its provenance is readable by any
FITA reader "with zero modification". One version **MUST** be chosen for the family — D-4.

`adjustment.py` implements the adjustment classes (`LevelsAdjustment`, `CurvesAdjustment`,
`FluxStretchAdjustment`, `AdjustmentStack`) and they are tested, but nothing serialises them. The
capability exists in memory and vanishes on save.

### 10.3 FITO — the sibling boundary

`[NEW]` Per Ignacio's ruling of 2026-07-29, FITO is in scope for this standard **as a sibling with a
stated boundary**, not as a part of FITA.

**FITO** (`.fito`, Flexible Image Transfer *Object*) is the ISM energy-budget **calculation
object** — HDF5, tiered by epistemic half-life (`/input` · `/inference` · `/core`), carrying the
bimodal Physics ∥ Unphysics plasma core, with every derived quantity stamped
`(input_ver, core_ver, paradigm)` and mandatory dust-posterior error bars. It is DESIGN-ONLY: no
code exists.

The boundary, normatively:

| | FITA | FITO |
|---|---|---|
| Holds | calibrated images + display metadata | derived physical quantities + their epistemic status |
| Answers | "what did the instrument record?" | "what does that imply, under which paradigm?" |
| Uncertainty | OPTIONAL (`UNCERT_*`) | **MANDATORY** — no error bars, no valid file |
| Paradigm | none — FITA is paradigm-free | first-class and **bimodal** |
| Direction | FITA is an **input** to FITO | FITO **consumes** FITA and FITR |

**FITA MUST NOT acquire paradigm tags, `[ESTABLISHED]`/`[PROPOSED — MWVO]` fences, or
`(input, core, paradigm)` stamps.** A physics claim has no business in an image container, and the
moment FITA starts carrying one, the fence that keeps established physics separate from proposed
MWVO physics has a hole in it. Conversely FITO **MUST NOT** redefine flux storage; it references
FITA layers.

`[NEW]` The family's shared contract is **interconversion** — "the F is Flexible":
`FITS folder ⇄ FITS-MEF (FITA) ⇄ HDF5 (FITO/FITR)`, round-trip, with any lossy step **logged**.
A conversion that silently loses a property (as `visible` does today) is non-conformant.

---

## 11. Evidence register

All measurements: ATOP, 2026-07-29, Python 3.14.5, astropy 7.2.0, numpy 2.4.6. Scripts in the
session scratchpad (`conformance_audit.py`, `split16_forensics.py`, `backend_equiv.py`, `sweep.py`).

### 11.1 Corpus
18 distinct `.fita` files, 0.9 MB – 437 MB, written 2026-05-18 → 2026-07-28. **All** pass FITS
`verify('exception')` with 0 warnings. **All 18** are `FITAPACK = FLOAT32`. **All 18** have
`FITA_META` absent, `FITA_ADJ` absent, `FITACW`/`FITACH` absent, and **negative alpha**.

### 11.2 `SPLIT16` forensics
Encoder in isolation: `uint16 0..65535`, max error 0.0075 on a 985-unit span — **sound**.
Written file: `BITPIX 16`, `BSCALE None`, `BZERO None`, raw ints `−32760 .. 32759`.
Truth `10 .. 1000` → readback `−32760 .. 32759`. All 4096 pixels altered. Peak read back as `−1`.

### 11.3 Round trip, `FLOAT32`
Flux bitwise identical (`array_equal == True`), 0 pixels altered. `zdepth` 0.5 → 0.5 ✓.
`visible` False → **True ✗**.

### 11.4 Cross-backend
FITS ⇄ Zarr: flux bit-identical; uncert, mask, WCS, zdepth, opacity, blend, name preserved;
Zarr alpha `uint16 0..65535` (correct); `visible` lost in both. HDF5 not testable — `h5py` absent.

### 11.5 Why 110 passing tests missed all of it
`test_io_roundtrip_split16` asserts only `layers_out[0].alpha_data is not None`. No test compares
flux across a `SPLIT16` file cycle; no test inspects written `BITPIX`/`BZERO`; no test checks
`visible`; no test parses `BUNIT`; no test asserts `FITA_META` presence. The suite tests the
*library's functions* and never the *file's conformance*. Hence §2.1's requirement for
`fita.validate()`.

---

## 12. Decisions — RESOLVED (ratified 2026-08-02)

### 12.0 Resolution

**The seven decisions below are RULED by the validating author (I. A. Cisneros), 2026-08-02, on the
FULL STANDARD SLATE.** The per-decision analysis that follows §12.0 is retained as the *rationale of
record*; the binding outcomes are:

| # | RULING |
|---|---|
| **D-1** | **v1.1, grandfather the 18 existing files** (documented reader rule for `1.0` wrapped alpha / invalid `BUNIT`; alpha regenerable from flux). |
| **D-2** | **DELETE `SPLIT16`.** A conformant writer MUST NOT emit `FITAPACK='SPLIT16'`; a reader encountering it MUST raise. |
| **D-3** | **IMPLEMENT `FITA_ADJ`** — serialise the adjustment-layer stack (unblocks `FITR_SPEC.md` §8). |
| **D-4** | **ObsCore v1.2, FULL conformance** — add the missing mandatory columns and write per-column UCDs as `TUCDn`; wire `FITA_META` reachable from `io.write()`. |
| **D-5** | **Omission is absence everywhere; table columns use `TNULL`.** Retire the `ZDEPTH = -1.0` sentinel. |
| **D-6** | **Add `FITA_ZSC`, OPTIONAL**, written by the renderer (not the compositor). |
| **D-7** | **Demote `FITA_Format_Guide.ipynb` to "tutorial"** and correct its two false claims in place. |

The four `[CORRECTION]` clauses (§6.3 alpha `BZERO=32768`; §7 `BUNIT`; §6.2 `FITA_VIS`; §4.3
header-normative / `FITAVER`-increment) were already normative in the DRAFT and are confirmed. MIME
type is `application/fits` until IANA registration is granted (§3).

*The following retains the DRAFT's decision analysis unaltered, as the rationale behind each ruling.*

**D-1 · Version number for the corrected format.**
The corrections in §6.3 (alpha `BZERO`) and §7 (`BUNIT`) change how existing files must be
interpreted. Options: (a) `FITAVER 1.1` with a documented reader rule that `1.0` files carry wrapped
alpha and invalid `BUNIT` — preserves the 18 existing files as readable; (b) rewrite all 18 to
conform and keep one version. **Recommend (a)** — the files are large (437 MB, two × 415 MB) and
alpha is regenerable from flux anyway.

**D-2 · `SPLIT16`: repair or delete?**
Repairing it is straightforward (write `uint16` and let astropy manage `BZERO`, stop double-scaling
on read). But the deeper problem is scientific, not technical: default percentile clipping destroys
the brightest and faintest 1% of pixels, and the error is a constant absolute quantum, so faint
pixels are hit hardest. **Recommend deletion.** FLOAT32 is bit-exact, disk is cheap, and a
half-precision path that silently eats point sources is a liability in a format whose selling point
is that flux is sacred. If you want it for a specific bandwidth-limited use case, say which, and it
can be repaired with mandatory explicit `FMIN`/`FMAX` and no percentile default.

**D-3 · `FITA_ADJ`: implement or remove?**
Adjustment layers are implemented and tested in memory but never serialised, and `FITR_SPEC.md` §8
already depends on them. Options: (a) implement the BINTABLE, (b) remove the concept from both specs
and let renderers own display state. **Recommend (a)** — non-destructive adjustment state is a real
part of "Photoshop for Astronomy", and its absence is what makes display state ephemeral. Related:
your standing position that hand-set display state *is* a work product argues for storing it.

**D-4 · ObsCore version and completeness.**
FITA says v1.1, FITR says v1.2, and neither writes `TUCDn`. Decide (i) one version for the family —
**recommend v1.2**, since FITR is the newer draft and ObsCore 1.2 is current; and (ii) whether to
add the missing mandatory columns to reach real conformance, or to publish honestly as an
"ObsCore-derived subset". **Recommend full conformance** if `.fita` files are ever to be registered
in a VO service or shown to Alfredo Mejía-Narvaez as an LVM differentiator — the provenance claim is
one of the five things on that list.

**D-5 · Absence convention.**
`ZDEPTH = -1.0` in the table vs an omitted `FITA_ZDP` keyword. **Recommend**: omission is absence
everywhere; the table column uses `TNULL`. Purely editorial, but it must be one thing.

**D-6 · `FITA_ZSC` parallax-scale keyword.**
Should a rendered stereo pair record the `ZDP`→pixel-offset mapping it used? Your depth-stimulus
discipline says separation must be measured and traceable to a metric chain. **Recommend yes**, as
an OPTIONAL keyword written by the renderer, not the compositor.

**D-7 · Guide notebook status.**
`FITA_Format_Guide.ipynb` is a 45-cell tutorial that also functions as a de-facto spec, and it
repeats the "~1.5 × 10⁻⁵" claim and the ObsCore claim. **Recommend** demoting it explicitly to
"tutorial — see `FITA_FORMAT_STANDARD.md` for normative text" and correcting the two claims in place.

---

## 13. Versioning

`FITAVER` is a string `'major.minor'`. Minor increments add optional structure or correct encoding
defects. Major increments change the meaning of existing required structure. A reader **MUST**
refuse a major version it does not know and **SHOULD** read unknown minor versions on a
best-effort basis.

| Version | Date | Status | Change |
|---|---|---|---|
| 1.0 | 2026-05-18 | as-built | Initial: layers, alpha, blend modes, FITS/HDF5/Zarr |
| 1.0 | 2026-05-25 | as-built | Added `FITA_ZDP`, `UNCERT_*`, `MASK_*`, HDF5 + Zarr backends, `FITR_SPEC` — **no version bump was made for a format change** |
| 1.1 | 2026-07-29 | drafted | Alpha `BZERO` correction; `BUNIT` correction; `FITA_VIS`; `SPLIT16` deprecated; registry authority fixed; ObsCore overclaim withdrawn; conformance levels; FITO boundary |
| 1.1 | 2026-08-02 | **RATIFIED** | §12 decisions ruled (full slate): D-2 delete SPLIT16 · D-3 implement `FITA_ADJ` · D-4 full ObsCore v1.2 · D-1/5/6/7 per §12.0. Body unchanged. |

| 1.2 | 2026-08-02 | **RATIFIED** | `FITA_ADJ` schema normative (§8.3); stereo geometry `FITA_ZSC`/`FITA_ZRF`/`FITA_ZAN` (§8.2); ObsCore v1.2 achieved and reachable (§9); conformance checker shipped (§2.1); `CHECKSUM`/`DATASUM` and FITS provenance keywords (§4.2). Adds only OPTIONAL structure. |

`[CORRECTION v1.2]` The same omission recurred on 2026-08-02: optional structure (`FITA_ZRF`,
`FITA_ZAN`, the `FITA_ADJ` columns) was added after v1.1 was ratified while the writer still
emitted `FITAVER = '1.1'`. Corrected at v1.2. The rule is restated because this project has now
broken it twice: **any change to required or optional structure requires a version increment,
in the same change as the structure itself.**

`[CORRECTION]` The 2026-05-25 delivery added three keywords and two backends without incrementing
`FITAVER`. Files written before and after that date both claim `1.0` while having different
structure. A conformant writer **MUST** increment `FITAVER` on any change to required or optional
structure.

---

*FITA is developed in the UranoDyne / MWVO project at `C:\Users\astro\fita`.*
*Contact: Ignacio A. Cisneros. This document is the normative reference; where it and any other*
*FITA document disagree, this one governs.*
