# DECISION SLATE — stereo metrology: the three concerns, the fourth datum

**Prepared by:** BTOP, 2026-08-02, from the principal's framework of the same date
**For ruling by:** I. A. Cisneros
**Status:** NOT IMPLEMENTED. Nothing below is in code. Five decisions are open and one
(**D-9**) cannot be guessed — it collides with the already-open D-8.
**Would be:** `FITAVER = 1.5` — genuinely new optional structure, unlike the v1.4 escalation items.

> *A note on terminology:* this document uses **interpupillary** (IPD), the standard optical term,
> for what the framework calls interpapillary. If the other spelling is intended as MWVO usage,
> say so and it will be used throughout instead — the standard should not carry two spellings.

---

## 1. The observation that starts this

Edenhofer produces a synthetic cross-stereo of galactic-plane dust. **The subject is in honest
units — parsecs. What is unnaturally scaled is the viewing geometry**, and nothing in the file says
so.

▣ Verified: the stated factor of **2.3 × 10¹⁸** against a natural IPD of 63 mm implies a stereo
baseline of

```
2.3e18 x 0.063 m  =  1.449e17 m  =  4.70 pc  =  15.3 light-years
```

The arithmetic is self-consistent. A viewer fusing that pair is being asked to occupy a head 4.7 pc
wide.

**This is not an error — it is the only way to render the subject at all.** The defect is that it
is undeclared. v1.4 fixed the same *class* of defect one level down: the eight archived files
carried parsecs in `FITA_ZDP` and nothing said "these are parsecs." Here the file states the
subject's scale correctly and says nothing about the observer's. **The metric chain is complete on
the subject side and missing on the viewer side.**

The expansion factor is not a nuisance to be hidden. It is **the** figure of merit for a synthetic
stereogram — it says exactly how far from a physical observation the representation stands.

---

## 2. The framework, restated as a specification skeleton

Three **concerns**, each independently carrying an epistemic status ∈ {**Established**,
**Proposed**, **Inferred**}:

| # | Concern | v1.4 status |
|---|---|---|
| 1 | **Distance to the subject imaged** | not recorded |
| 2 | **Scale of the subject at that distance** | **`FITA_FDI` / `FITA_FDU`** — already exists |
| 3 | **Returned (derived) scale of the subject imaged** | not recorded |

Plus a fourth **datum**, not a concern — it is a property of the representation, not of the subject:

| 4 | **Implied interpupillary distance** effective for the depth stimulus | not recorded |

**Concern 2 is already v1.4.** The ruling of earlier today supplied it, which is why this slate is
an extension and not a revision.

**Concern 3 is the check, and that is its whole value.** Concern 2 is the scale asserted; concern 3
is the scale recovered from the image. Where they disagree, the disagreement is the measurement.
Recording only one of them discards the diagnostic.

### Two derived quantities the legend must report — and must NOT store

```
apparent angular diameter of the stereo frame  =  FITA_FDI / (distance to subject)
interpupillary expansion factor                =  (implied IPD) / 63 mm
```

Both follow by arithmetic from stored values. **Storing them would record the same fact twice** —
which is precisely the `DISTANPC` defect found this morning, where distance lives in both a
normalised `zdepth` and a private parsec keyword with nothing keeping them consistent. Derive,
never store. See §5, D-12.

### Acquisition data — real platforms

For a moving platform, the baseline is *made* by motion, so the acquisition record is not optional
context, it is how the baseline came to exist:

- **time elapsed between the binocular exposures** — for LBAS this is the origin of the baseline
- focal length · aperture · image scale at the photographic plate
- mission elapsed time
- angle of the imaged subject's surface normal (PDS: *emission angle*)
- phase angle of illumination

**LBAS already accounts for these.** It is *Large Baseline Anamorphic Stereography*: it builds
stereo pairs from sequential exposures of a moving platform, so Δt × platform velocity **is** the
baseline. Edenhofer and LBAS are therefore the two acquisition modes of one metrology:

| | baseline arises from | Δt | expansion factor |
|---|---|---|---|
| **LBAS** (Rosetta/OSIRIS) | platform motion between exposures | **measured, essential** | modest — km-scale |
| **Edenhofer** (synthetic) | chosen viewpoint separation in a volume | undefined — no exposures | **10¹⁸** |

One clause serves both if the baseline is recorded as a *length in the subject's units*, with Δt
recorded when exposures exist and absent when they do not. Absence by omission — D-5.

### The legend requirement

> Report the nature of the subject in units practical for the **physical diameter of the stereo
> frame**: pc or ly for ISM; AU for mm astronomy; km or m for solar-system probe imaging.

This is the v1.4 ruling's *"units practical to the subject"* applied to presentation rather than to
storage. It is the same principle, one layer out.

---

## 3. Draft keyword table

All PRIMARY, all OPTIONAL, all ≤ 8 characters — deliberately **not** the PDS/SPICE long names
(`PHASE_ANGLE`, `EMISSION_ANGLE`, `SPACECRAFT_CLOCK_START_COUNT`), which exceed the FITS limit and
would be written as HIERARCH cards. This morning's measurement showed astropy reads HIERARCH back
perfectly while a foreign reader may not see it at all — the mechanism by which defect #2 hid. The
PDS names belong in the clause text as the mapping, not in the header.

### Metrology — the three concerns and the fourth datum

| Keyword | Type | Meaning |
|---|---|---|
| `FITA_SDI` | float | Concern 1 — distance to the subject imaged |
| `FITA_SDU` | str | Unit of `FITA_SDI` (separate from `FITA_FDU`: mm-astronomy may state distance in pc and field in AU) |
| `FITA_FDI` | float | Concern 2 — field diameter **(v1.4, exists)** |
| `FITA_FDU` | str | Unit of `FITA_FDI` **(v1.4, exists)** |
| `FITA_RSD` | float | Concern 3 — returned/derived scale, in `FITA_FDU` |
| `FITA_IPD` | float | Datum 4 — implied stereo baseline, in `FITA_FDU` |
| `FITA_SDE` | str | Epistemic status of concern 1 |
| `FITA_FDE` | str | Epistemic status of concern 2 |
| `FITA_RSE` | str | Epistemic status of concern 3 |

### Acquisition — present only for real platforms

| Keyword | Type | Meaning | Maps to |
|---|---|---|---|
| `FITA_DTE` | float | Elapsed time between the binocular exposures, seconds | — |
| `FITA_MET` | float | Mission elapsed time at first exposure | PDS `SPACECRAFT_CLOCK_START_COUNT` |
| `FITA_FCL` | float | Focal length, mm | `FOCALLEN` |
| `FITA_APR` | float | Aperture diameter, mm | `APERTURE` |
| `FITA_IMS` | float | Image scale at the plate | — |
| `FITA_EMA` | float | Emission angle — subject surface normal, deg | PDS `EMISSION_ANGLE` |
| `FITA_PHA` | float | Phase angle of illumination, deg | PDS `PHASE_ANGLE` |

### Proposed validator rules

- `FITA_IPD` present without `FITA_FDU` → **MUST** fail. A baseline with no unit is not a length.
  (Exactly parallel to v1.4's `FITA_ZSC`-without-`FITA_FDI`.)
- `FITA_SDI` present without `FITA_SDU` → **MUST** fail.
- Any epistemic keyword present whose concern is absent → **MUST** fail. A status attached to
  nothing is not a claim.
- `FITA_RSD` present with neither `FITA_FDI` nor `FITA_SDI` → **SHOULD** warn: a returned scale with
  nothing to compare against discards its own diagnostic value.
- Epistemic value outside the ruled vocabulary → **MUST** fail.

---

## 4. `fita stereo legend` — derive, never store

A new subcommand emitting the legend from the file, so the legend cannot drift from the data:

```
$ fita stereo legend edenhofer_plane.fita

  Subject      Galactic plane dust, 3D differential extinction
  Frame        2500 pc across at 1250 pc      [scale: ESTABLISHED, distance: INFERRED]
  Angular      ~ 2.0 rad as seen from the stated distance
  Depth        624.05 - 2496.20 pc  (FITA_ZDU = pc)
  Parallax     4.0 % of frame  =  100 pc across the full depth range
  Baseline     4.70 pc implied  =  2.3e18 x natural interpupillary (63 mm)
               ^ SYNTHETIC VIEWPOINT: this is not a physical observation
```

The last line is the point of the whole exercise. A representation whose implied observer is 4.7 pc
wide should say so **in the legend**, not only in the metadata.

---

## 5. Open decisions

### D-9 · The epistemic vocabulary collides with PACI — **cannot be guessed**

{**Established, Proposed, Inferred**} is a three-valued epistemic axis. PACI already has one:
{`MEASURED`, `SCOUTED`, `ANCHORED`} in `ANCHORCL`. **D-8 already asks this question** — "anchor
class is epistemic status, which §10.3 assigns to FITO. Rule once for both." This slate forces it.

They do not map cleanly. PACI's axis answers *where did this number come from*; the new axis
answers *how firmly is this scale claimed*. `ANCHORED` has no counterpart in E/P/I, and `PROPOSED`
none in PACI.

| Option | Consequence |
|---|---|
| **(a) Two independent axes, both recorded** ⟵ *recommended* | Honest — they are different questions. Costs one more keyword per concern. A value may be `MEASURED` yet `PROPOSED` as a scale claim, and that combination is meaningful. |
| (b) Unify onto one vocabulary | Cheapest, but forces a false equivalence and loses `ANCHORED`. |
| (c) E/P/I general; PACI a refinement of `ESTABLISHED` | Elegant, but re-scopes PACI, which §10.3 assigns to FITO — a boundary change, not a naming change. |

**This is a science-representation decision. Not guessing it.**

### D-10 · Natural IPD — fixed constant or recorded?

The expansion factor needs a denominator. Human IPD spans ~55–75 mm.

**Recommend: fix normatively at 63 mm**, stated in the clause, with an optional `FITA_IPN` override.
At a factor of 10¹⁸ a ±20 % spread is noise, and a fixed denominator makes expansion factors
comparable between files — which is the entire reason to report one.

### D-11 · Scope — does the acquisition block belong in FITA at all?

Focal length, aperture, phase angle and MET are *instrument and observation* metadata. FITA is a
display-layer convention over FITS.

| Option | Consequence |
|---|---|
| **(a) Stereo-relevant subset only** (`FITA_DTE`, `FITA_IMS`) ⟵ *recommended* | Keeps FITA about representation. The rest already have FITS/PDS homes; FITA points at them. |
| (b) Full block in FITA | One place to look, at the cost of FITA restating instrument metadata it does not own — the ObsCore lesson, inverted. |
| (c) A separate **platform profile** document | Cleanest conceptually, most work, and it is a third document to keep in sync. |

### D-12 · Derived quantities — confirm they are never stored

Angular diameter and expansion factor both follow by arithmetic. **Recommend: never stored,
always derived**, per the `DISTANPC` finding. Requires confirmation because it means a reader must
compute to display — a real cost, deliberately accepted.

### D-13 · Is the legend normative?

**Recommend: `SHOULD` for renderers, with `fita stereo legend` as the reference implementation.**
Making it `MUST` would bind FITA to presentation behaviour it cannot verify in a file.

---

## 6. Why this is 1.5 and the escalation was not

Asked earlier today whether the folded change should become 1.5, the answer was no: documentation,
CI and packaging change no structure, and stamping a new `FITAVER` onto structurally identical
files is a version claim without a difference.

**This is the opposite case.** Up to sixteen new keywords, new validator rules, a new subcommand —
optional structure, which §13 requires an increment for. If ruled, it is **1.5**.

---

## 7. What is asked

Rule **D-9** (blocking — it also closes D-8), then D-10 through D-13. With those five settled the
clause can be drafted, implemented, corpus-fixtured and validated in one pass, the same shape as
v1.4.

Nothing is implemented until then. Structure that appears in code before it appears in the standard
is a de-facto specification — this project has done that twice and corrected it twice, and found a
third instance in `DISTANPC` this morning.
