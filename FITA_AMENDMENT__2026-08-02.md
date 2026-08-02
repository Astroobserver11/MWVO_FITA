# AMENDMENT — FITA Format Standard, v1.1 → v1.2

**RUNG: memory (amendment).** This is a clause-level amendment package, **not** a restatement
of the standard. Its job is to be **folded into the canonical `FITA_FORMAT_STANDARD.md` on
ATOP**, clause by clause, after which this document is spent. Where this document and the
applied standard ever differ, **the standard governs**.

| Field | Value |
|---|---|
| **Status** | **PROPOSED** — normative text awaiting application to the canonical standard |
| **Amends** | `FITA_FORMAT_STANDARD.md` v1.1 (RATIFIED 2026-08-02) |
| **New format version** | `FITAVER = 1.2` (author ruling, 2026-08-02) |
| **Arising from** | Author rulings **Q1** and **Q2**, 2026-08-02, plus the implementation of the ratified D-1…D-7 slate |
| **Authored on** | BTOP (`desktop-9mn6gd5`) |
| **Applies to** | ATOP canonical original — **sync the bytes, do not retype** |

---

## 0. Why this document exists

The v1.1 DRAFT that seeded this work has been superseded twice and updated zero times.

1. **Ratification (2026-08-02).** D-1…D-7 were ruled. A ratified text exists on BTOP
   (`FITA_FORMAT_STANDARD.RATIFIED-2026-08-02.md`) but **was never installed as ATOP's
   canonical file**, which still reads `v1.1 DRAFT` and still presents seven settled questions
   as open. The ratification record is self-limiting — *"this record's job is done once the
   standard reads RATIFIED"* — and that has not happened.

2. **Implementation (2026-08-02).** Building the ratified slate required decisions the slate did
   not make. D-3 ruled *that* `FITA_ADJ` exists, not what its columns are. D-6 ruled *that*
   `FITA_ZSC` exists, not what it means. Those gaps were filled by author rulings Q1 and Q2, and
   the results currently live **only in `fita/spec.py`**.

The second point is the dangerous one. Code that defines format structure, with no
corresponding clause in the standard, *is* a de-facto specification — which is precisely what
D-7 demoted the guide notebook for. This amendment closes that loop.

---

## 1. Supersession map

| Document | Standing after this amendment |
|---|---|
| ATOP `FITA_FORMAT_STANDARD.md` (v1.1 DRAFT) | **Superseded.** Apply the ratification, then §3 below → becomes v1.2 RATIFIED. **This is the only authority.** |
| `FITA_FORMAT_STANDARD.RATIFIED-2026-08-02.md` (BTOP) | Intermediate. Correct as of ratification; predates §3 below. |
| `FITA_v1.1_RATIFICATION__2026-08-02.md` | Historical decision log. Retain — it records *why*. |
| v1.1 DRAFT transport copies (×2) | Historical. Retain for the audit trail; mark superseded. |
| `FITA_FOUNDRY_DESIGN.md` v0.3 | **Partly executed, partly PARKed.** Its C1/C2/C2b/C7 are done; the Ring-B bus and `.exe` surfaces remain parked pending the FITA paper. Not superseded, but no longer a status source. |
| `FITA_Format_Guide.ipynb` | Non-normative tutorial (D-7). Unchanged by this amendment. |
| `spec.py`, `validate.py` | Implementations. **Must follow the standard, not lead it** — that is what §3 restores. |

---

## 2. The version ruling, and a self-correction

**Ruling: `FITAVER = 1.2`.**

§13 requires: *"A conformant writer **MUST** increment `FITAVER` on any change to required or
optional structure."* The Q1/Q2 rulings added new optional structure **after** v1.1 was
ratified:

- `FITA_ZRF` and `FITA_ZAN` — two new OPTIONAL PRIMARY keywords (§3.4)
- the `FITA_ADJ` column schema — previously undefined (§3.5)

**Self-correction.** Between ratification and this amendment, that structure was added while the
writer still emitted `FITAVER = '1.1'`. That is verbatim the `[CORRECTION]` §13 levels at the
2026-05-25 delivery — *"added three keywords and two backends without incrementing `FITAVER`"* —
committed again, in the same session that ratified the rule. It is corrected here rather than
quietly: `fita/spec.py` now emits `1.2`, and `validate.ENFORCED_VERSION` is `1.2`.

**Why 1.2 and not a re-cut of 1.1.** BTOP wrote real `1.1` files earlier the same day. Re-cutting
1.1 underneath them would produce two structurally different file populations both declaring one
version — the exact ambiguity §13 exists to prevent.

**Reader rule.** A reader **MUST** refuse an unknown *major* version and **SHOULD** read unknown
*minor* versions best-effort. `1.1` files are `1.2`-readable: the added structure is OPTIONAL
throughout, so nothing that validated at 1.1 stops validating at 1.2.

---

## 3. Normative clause text

Apply each block to the canonical standard at the section named. Tags follow the standard's own
taxonomy (§0).

### 3.1 §2.1 — conformance checker `[REVISED]`

> **Replace** the sentence *"No such checker exists in v1.0; the absence of one is why the
> defects in §11 went undetected through 110 passing tests."* with:

`[AS-BUILT]` A conformance checker is provided as `fita.validate(path) -> ConformanceReport`,
exposed on the command line as `fita conform` (`--quiet`, `--strict`; exit 0 = FITA-FULL,
1 = FITA-CORE, 2 = non-conformant). The report exposes `.is_core`, `.is_full`, `.level`, and a
list of `Finding(clause, severity, ok, message, where)`. `flux_roundtrip_ok()` implements the
§5.4 bit-exactness requirement.

`[NEW]` The §5.4 flux comparison **MUST** be NaN-aware. `numpy.array_equal` returns False
whenever a NaN is present, and blanked pixels are ubiquitous in real data; a conformant test
compares the NaN masks and the finite pixels separately. A test that is not NaN-aware fails on
every real image and will be disabled rather than fixed.

### 3.2 §4.1 — canonical HDU layout `[REVISED]`

> **Replace** the note *"`FITA_ADJ` is retained as OPTIONAL and currently unimplemented — see §8
> and open decision D-3."* with:

`[AS-BUILT]` `FITA_ADJ` is OPTIONAL and **implemented** (D-3); its schema is normative in §8.3.
When present it **MUST** be written at HDU N−1, immediately before `FITA_META`. Both remain
OPTIONAL at FITA-CORE; only `FITA_META` is REQUIRED at FITA-FULL.

### 3.3 §4.2 — PRIMARY keywords `[REVISED]`

> **Append** three rows to the PRIMARY keyword table:

| Keyword | Type | Req. | Meaning | Tag |
|---|---|---|---|---|
| `FITA_ZSC` | float | **MAY** | Stereo parallax scale: total horizontal separation in pixels across the full `FITA_ZDP` range | `[NEW]` |
| `FITA_ZRF` | float | **MAY** | Reference plane: the `FITA_ZDP` value placed at zero parallax. Default `0.0` when omitted | `[NEW]` |
| `FITA_ZAN` | float | **MAY** | Angular measure of the full-range parallax, in arcsec on sky | `[NEW]` |

All three are written by a **renderer**, never by the compositor. Semantics in §8.2.

### 3.4 §8.2 — phased stereography `[REPLACES]` the closing paragraphs

> **Replace** the final paragraph (*"This standard deliberately does not specify the parallax
> scaling… A future `FITA_ZSC` keyword could record the scaling actually used — see D-6."*)
> with the following.

`[NEW]` This standard does not fix a single parallax scaling — the mapping belongs to a rendering
job, not to a file. It does require that a rendering which *has* fixed one **records it**, so the
depth stimulus remains measurable after the fact. Three OPTIONAL keywords carry that record.

**Convention (normative whenever `FITA_ZSC` is present):**

```
FITA_ZSC  total horizontal parallax, in pixels, across the full FITA_ZDP range
FITA_ZRF  the FITA_ZDP value placed at ZERO parallax (the screen plane); default 0.0

per-eye offset:   dx = ±(FITA_ZSC / 2) × (FITA_ZDP − FITA_ZRF)
                  left eye = −, right eye = +
```

A negative `FITA_ZSC` inverts the depth sense. A layer with no `FITA_ZDP` (absence by omission,
D-5) sits at zero parallax and **MUST NOT** be assigned a default depth.

`FITA_ZRF` exists so the depth budget can be spent in both directions. With `FITA_ZRF = 0.0` the
background sits at the screen and every layer is pushed forward; with `FITA_ZRF = 0.5` a
mid-depth layer sits at the screen, layers below it recede and layers above advance.
`FITA_ZRF` **SHOULD** lie within `[0,1]`.

**The angular measure.** `[NEW]` A parallax recorded only in pixels is a complete record **only
where no complete model is available**. Otherwise an angular measure is REQUIRED, **unless it can
be deduced from context**. A celestial WCS on any layer is such a context: pixel scale ×
`FITA_ZSC` yields the angle. Therefore:

- `FITA_ZAN` **MAY** be omitted when a usable celestial WCS is present.
- `FITA_ZAN` **SHOULD** be written when no WCS is present, since the record is otherwise
  pixel-only.
- An implementation **MUST NOT** fabricate a pixel scale in order to produce an angle; where the
  scale is unknown the angle is unknown, and reporting it as such is the conformant behaviour.

**Validator behaviour.** `FITA_ZSC`, `FITA_ZRF`, `FITA_ZAN` **MUST** be finite when present.
A `FITA_ZSC` on a cube where no layer carries `FITA_ZDP` records a stimulus that was never
applied and is reported at SHOULD severity.

> **Open — see §5.** Whether `FITA_ZAN` should measure a *sky* angle or a *viewing* disparity is
> not settled; this clause specifies the sky angle and is provisional in that respect.

### 3.5 §8.3 — `FITA_ADJ` adjustment stack `[NEW SECTION]`

`[NEW]` `FITA_ADJ` is an OPTIONAL BINTABLE carrying the non-destructive display stack: an ordered
list of adjustments applied at composite time. It is display state, and by §5.2 **MUST NOT**
modify `FLUX_*`.

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
| `BRIGHT` | `D` | | BRIGHTNESS brightness, −1…+1 |
| `CONTRAST` | `D` | | BRIGHTNESS contrast, −1…+1 |
| `STRETCH` | `16A` | | FXSTRETCH mode: `linear\|log\|sqrt\|asinh\|power` |
| `ASINH_A` | `D` | | FXSTRETCH asinh softening parameter |
| `POWER_EXP` | `D` | | FXSTRETCH power-law exponent |
| `CHANNEL` | `2A` | | BANDMAP display channel: `R\|G\|B` |
| `WAVE_CVAL` | `D` | m | FXNORM wavelength at which response is sampled |
| `PARAMS` | `nA` | | JSON — variable-length parameters only |

**§8.3.1 Adjustment codes.** `LEVELS`, `CURVES`, `BRIGHTNESS`, `FXSTRETCH`, `BANDMAP`, `FXNORM`
(see the `ADJ_*` constants). A reader encountering an unknown `ADJ_TYPE` **MUST** raise rather
than silently drop the adjustment — the same rule §8.1 sets for unknown blend codes. A display
stack that quietly loses a step is worse than one that refuses to load.

**§8.3.2 Typed columns are normative.** `[NEW]` (Author ruling Q1.) The common parameters
**MUST** be written as the typed columns above, not folded into `PARAMS`. FITA's premise is that
any FITS reader can open the file; a reader that opens the file but cannot see that
`GAMMA = 2.2` has not been given the data. `PARAMS` is reserved for parameters with no fixed
width — currently `control_points` (CURVES), and `response_curve` / `wavelengths` (FXNORM).

**§8.3.3 Absence.** A column that does not apply to a row carries the D-5 absence convention:
NaN for floating columns, empty string for character columns. A row whose type uses no
variable-length parameters **SHOULD** write an empty `PARAMS`.

**§8.3.4 No silent truncation.** The `PARAMS` column width **MUST** be sized to the longest row
actually present. A fixed cap would silently discard long response curves, and undetectable data
loss is the failure mode this format has suffered most.

**§8.3.5 Validation.** When `FITA_ADJ` is present, a validator **MUST** check: the required
columns are present; every `ADJ_TYPE` is known; every non-empty `PARAMS` cell is parseable JSON.
Each is MUST severity — an adjustment that cannot be reconstructed is indistinguishable from one
that was never applied.

### 3.6 §9 — provenance `[REVISED]`

> **Replace** *"Conformant wording until the gap is closed: 'an ObsCore-derived provenance
> subset'. Whether to close it fully is D-4."* and the surrounding `[CORRECTION]` with:

`[AS-BUILT]` D-4 is implemented. `FITA_META` carries a **full IVOA ObsCore DM v1.2** mandatory
column set (32 columns total), and every column's UCD is written as `TUCDn` — the FITS convention
for table-column UCDs. The earlier `UCD1` / `UCDXXXXX` forms are withdrawn. The wording *"ObsCore
DM v1.2"* is now accurate and may be used without qualification.

`[AS-BUILT]` `FITA_META` is reachable through the documented API:
`io.write(path, layers, provenance=...)` accepts either a dict of ObsCore fields or a prebuilt
`BinTableHDU`, and `ivoa.meta_from_layers()` derives the fields that are properties of the data
(`s_xel1`, `s_xel2`, `em_min`, `em_max`, `em_xel`) rather than of operator intent. The v1.0
condition — provenance model documented but unreachable, absent from every archived file — is
resolved.

`[AS-BUILT]` `access_format` is `application/fits`. The unregistered `application/fits+alpha`
**MUST NOT** be emitted (§3), and the validator enforces this at MUST severity.

### 3.7 §10.1 — backend equivalence `[REVISED]`

> **Replace** the HDF5 status row and the closing paragraph with:

`[MEASURED]` `h5py` is **present on BTOP** and absent on ATOP as of 2026-07-29. The HDF5 backend
is therefore now *testable*, and remains **untested**: the claim "survives round-trip through all
three backends" is still confirmed for two of three (FITS, Zarr) and **MUST NOT** be restated in
full until a FITS ⇄ HDF5 equivalence run is recorded in §11.

### 3.8 §13 — versioning `[REVISED]`

> **Append** to the version table:

| Version | Date | Status | Change |
|---|---|---|---|
| 1.2 | 2026-08-02 | **this amendment** | `FITA_ADJ` schema normative (§8.3); stereo geometry `FITA_ZSC`/`FITA_ZRF`/`FITA_ZAN` (§8.2); ObsCore v1.2 achieved and reachable (§9); conformance checker shipped (§2.1) |

> **Append** to the `[CORRECTION]` note on version discipline:

`[CORRECTION]` The same omission recurred on 2026-08-02: optional structure (`FITA_ZRF`,
`FITA_ZAN`, the `FITA_ADJ` columns) was added after v1.1 was ratified while the writer still
emitted `FITAVER = '1.1'`. Corrected in this amendment. The rule is restated because it has now
been broken twice by the same project: **any change to required or optional structure requires a
version increment, in the same commit as the change.**

---

## 4. Implementation record

What exists, and how it was checked. Recorded so §11's evidence register can absorb it.

| Clause | Implementation | Verification |
|---|---|---|
| §2.1 checker | `fita/validate.py`, `fita conform` | Reproduces expected failures on legacy files; catches injected corruption |
| §5.4 flux invariant | `flux_roundtrip_ok()` | Bit-exact, NaN-aware; asserted per packing mode |
| §6.3 alpha | `io.py` writes `uint16` → astropy emits `BZERO=32768` | Range verified `0..65535` |
| §6.2 `FITA_VIS` | `to_header_dict()` | `visible` round-trips `[T,F,T]` |
| §6.4 SPLIT16 | raises on **both** write and read | `test_split16_is_rejected` |
| §7 `BUNIT` | `alpha16` omitted; UNCERT carries parent unit | Unit parsing asserted |
| §8.2 stereo | `fita/stereo.py`, 3 keywords | Reference plane, deduction from WCS (3.6″/px × 24 px = 86.4″), pixel-only flagged |
| §8.3 `FITA_ADJ` | `spec.ADJ_TABLE_COLS`, `io._build_adj_hdu`, `io.read_adjustments` | All 6 types round-trip with parameters, order, `enabled`; typed columns legible in a plain table reader |
| §9 ObsCore | `fita/ivoa.py` | 32 columns, 32 `TUCDn`, `access_format='application/fits'`; a written file validates **FITA-FULL** |
| — install | wheels + `fita` on PATH + `fita doctor` | Wheels verified in a clean venv, importable from the shadowing directory |

**Suite: 197 passed, 0 failed.**

**Not verified:** the HDF5 backend (§3.7); third-party rendering of alpha in DS9 / QFitsView /
Aladin; any actual VO registration. See `ATOP_FITA_DUE_DILIGENCE.md`.

---

## 5. Open question — the one thing §3.4 does not settle

**Does `FITA_ZAN` measure a sky angle or a viewing disparity?**

§3.4 above specifies **sky angle** (arcsec), because that is the reading under which "deducible
from context" has a referent — the WCS is in the file. But a depth *stimulus* is arguably about
**viewing geometry**: screen pixel pitch and viewing distance, i.e. binocular disparity at the
eye. That quantity is **never** deducible from the file.

If the discipline means visual disparity, `FITA_ZAN` as specified measures the wrong quantity and
a second keyword is required. The clause is marked provisional in that respect and should not be
folded as final until ruled.

---

## 6. How to apply this

1. Install the ratified text as ATOP's canonical `FITA_FORMAT_STANDARD.md` (see
   `ATOP_FITA_DUE_DILIGENCE.md` §2) — **sync the bytes, do not retype**. If ATOP's copy has
   diverged, stop and report before overwriting.
2. Apply §3.1–§3.8 to that file.
3. Set the status line to **v1.2 (RATIFIED)** and the date.
4. Fold §4 into §11's evidence register.
5. Leave §5 open in §12 until ruled.
6. Then this document is spent — retain it as history, not as authority.

---

## 7. What remains after this

- **§5 above** — the `FITA_ZAN` semantics ruling.
- **HDF5 verification** (§3.7) — now possible; `h5py` is installed on BTOP.
- **Third-party reader check** — the alpha encoding has only ever been verified through astropy,
  which is exactly the path that hid the original defect.
- **The paper track** — ratify ✓ → validator ✓ → **corpus** → **Zenodo DOI** → paper. The corpus
  is the next unstarted item.
- **The Foundry** stays PARKed until the paper ships.

---

*Amends `FITA_FORMAT_STANDARD.md`. Once applied, the standard governs and this document is
history.*
