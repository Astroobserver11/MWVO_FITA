# SLATE ADDENDUM 2 — D-14 ruled; the three labels of a velocity slice

**Prepared by:** BTOP, 2026-08-03
**Extends:** Addendum 1 (`__phased_stereo__`) and the stereo-metrology slate
**Contains:** D-14 **RULED** (and sharpened past the proposal), a normative legend clause, one
finding, one item parked.

---

## 1. D-14 — RULED, and the ruling is sharper than the proposal

**Ruled 2026-08-03:**

> The x and y displacements in the phased stereograph have one logical physical interpretation:
> the representation of actual space corresponding to the angular distance for each pixel at the
> accepted distance. **There is no correspondence to the spectral shift or its conversion into
> recession velocity.**

Addendum 1 proposed typing the **cube** — a z axis that is length, angle, or neither. **The ruling
types the axes separately, and that is the better instrument:**

| Axis | Interpretation | Recoverable as a length? |
|---|---|---|
| **x, y** | Actual space = per-pixel angular scale × accepted distance | **Yes** — this is the only metric interpretation the file carries |
| **z (velocity)** | Spectral displacement, and its inferred conversion | **No.** No correspondence to distance whatsoever |

The D-14 proposal is superseded on this point. `FITA_ZDU` still marks *what the depth axis is in*,
but the ruling forbids any legend or renderer from converting a non-length depth axis into a
separation in `FITA_FDU`. The transverse plane and the depth axis are no longer symmetric, and the
implementation must stop treating them as though they were.

### Forced consequences, not proposals

1. **A per-pixel physical scale is required for x and y.** "Angular resolution corresponding to an
   accepted physical distance" is a computation the file must support: pixel angular scale (WCS) ×
   accepted distance (`FITA_SDI`). No new storage — but the legend **MUST** report the transverse
   scale as a real length and **MUST NOT** report the depth axis that way.
2. **Time extrapolation is prohibited for velocity cubes.** A velocity cube constrains only the
   radial component. Extrapolating motion forward smears the field along the virtual z axis and
   yields nothing about tangential velocity — so animating one forward in time **fabricates motion
   the data cannot constrain.** `MUST NOT` for renderers.

---

## 2. A velocity slice carries three labels, not one

**Ruled:** every slice of a velocity cube presented as a phased stereogram carries two labels
explicitly and a third by implication, and **all three belong in the legend.**

| # | Label | Epistemic status | What it is |
|---|---|---|---|
| 1 | **Spectral displacement** | **MEASURED** | The observable. A shift in frequency or wavelength at the detector |
| 2 | **Radial velocity** | **INFERRED** | The Doppler conversion of (1). An interpretation, not an observation |
| 3 | **Local standard of rest** | **DETERMINED** | The frame, and with it the detector's own absolute velocity — the ground truth (2) is computed against |

This is the epistemic axis of **D-9** appearing *within a single slice label*. It is therefore
strong evidence for D-9 option (a) — status attaches to each quantity, not to the file — because
here one quantity is measured, one inferred and one determined, simultaneously, in one number's
provenance. A single per-file status could not express it.

**It also matters for the science claim.** Labelling (2) as inferred is what keeps the figure
honest about the question Addendum 1 §1 quoted: whether the perceived depth presents data flux or
captures the form of nature. A legend that prints only "km/s" has silently promoted an inference
to an observation.

### The keywords already exist — in FITS WCS Paper III

No invention is needed. The primary standard carries all three:

| Label | Keyword | Notes |
|---|---|---|
| Spectral displacement | `CTYPE3` = `'FREQ'` / `'WAVE'`, with `CRVAL3` / `CDELT3` | the measured axis |
| | `RESTFRQ` / `RESTWAV` | the rest reference the shift is measured *from* |
| Radial velocity | `CTYPE3` = `'VRAD'` / `'VOPT'` | the converted axis; the convention used is part of the claim |
| Local standard of rest | **`SPECSYS`** | the frame — `'LSRK'`, `'BARYCENT'`, `'TOPOCENT'` |
| | **`VELOSYS`** | **velocity of that frame with respect to the observer, m/s** — this is precisely "the detector's real absolute velocity" |
| | `SSYSOBS` | the frame the observation was actually taken in, normally `'TOPOCENT'` |

`SPECSYS` + `VELOSYS` *is* the third datum, already standardised. Citing them rather than minting
`FITA_*` equivalents follows the standing rule from the ObsCore erratum §8, and avoids a second
convention for a fact the FITS standard already expresses.

### Proposed legend, for a velocity-cube phased stereogram

```
  Frame        1200 pc across at 1250 pc      [distance: INFERRED -- astronomical estimate]
  Transverse   0.42 pc / pixel  (0.070 arcsec at the accepted distance)
  Slice axis   SPECTRAL DISPLACEMENT  -40 .. +40 km/s      [MEASURED]
               radial velocity, Doppler conversion          [INFERRED]
               frame LSRK, VELOSYS = -14.2 km/s             [DETERMINED]
  Depth        apparent z only -- NO distance claim
               separation is a presentation device, not a measured depth
  Baseline     4.70 pc implied = 2.3e18 x natural interpupillary (63 mm)
               ^ SYNTHETIC VIEWPOINT: not a physical observation
```

Every line that could be mistaken for a measurement now carries what it actually is.

---

## 3. Finding — FITA claims Paper III conformance it does not implement

`fita/spec.py:40` states:

> *"Spectral axis follows FITS WCS Paper III conventions (CTYPE3 = WAVE/FREQ/VRAD)"*

▣ Measured: FITA implements **none** of `SPECSYS`, `VELOSYS`, `RESTFRQ`, `RESTWAV`, `SSYSOBS`, or
`CTYPE3`. It carries only `FITA_WCV` / `FITA_WBW` — central wavelength and bandpass, which are
**photometric band descriptors, not spectral-cube axis descriptors.** They cannot express a
velocity axis at all.

This is the ObsCore failure's shape: a conformance claim to an external standard, inherited into a
comment, never checked against the primary document. It is materially milder — the claim sits in a
docstring, not in the normative standard, and no file header asserts it — but the erratum's
standing rule applies:

> *A conformance claim naming an external standard MUST cite the primary document, with its
> version and date, verified at the time of writing.*

**Recommend:** either implement the Paper III spectral keywords (which §2 now requires anyway, so
this is the same work) or withdraw the claim from the docstring. Implementing is the better
outcome, because a velocity cube cannot carry its three labels without them.

---

## 4. Parked

**The ALMA/ATOMIUM geometry question** — why circular emission patterns rather than a cone —
postponed by the principal, 2026-08-03. Not dropped. The state reached, so it need not be
re-derived:

- The cone is real: `v_los = v_exp·cos θ`, `r_proj = R·sin θ`, so a channel map at fixed `v_los`
  selects one θ and renders one ring. Ring radius `r/R = sqrt(1 - (v_los/v_exp)^2)`: a point at the
  extreme channels, largest and limb-brightened at systemic. **Circles are slices through the
  cone**, and the cone appears only when the whole cube is viewed at once — which is the geometric
  argument for the phased stereogram over a grid of slices.
- No cone appears *on the sky* because radial emission summed over a sphere is isotropic; a cone
  requires an axis, and an axis means collimated outflow.
- Intensity falloff is real but arises from the density profile and tangential path length, not
  from velocity projection.
- **Open thread:** Decin et al. 2022 (A&A 660, A94) report *no ATOMIUM source displays a smooth
  spherical wind* — bipolar waists, equatorial density enhancements, spirals, arcs, "eye" shapes,
  attributed to binarity. So observed circularity may be the beam: ATOMIUM ran at ~0.025", ~0.13–
  0.24" and ~1". **Which resolution tier the displayed cubes came from is a checkable question
  about the figures, and should be settled before publication.**

---

## 5. Standing decisions

| | Status |
|---|---|
| **D-9** epistemic axis vs PACI | open — §2 is new evidence for option (a) |
| D-10 natural IPD constant | open |
| D-11 acquisition-block scope | open |
| D-12 derive, never store | open |
| D-13 legend normative? | **partly answered** — §2 makes the legend's *content* normative |
| **D-14** z-axis kind | **RULED** — axis-split; supersedes the proposal |
| **D-15** phased depth: amplitude or phase | **open, still blocking** |
| D-16 isometric y excursion | open |

Nothing implemented. The `-1.0` sentinel defect from Addendum 1 §1 remains the only item that is
correctness rather than decision, and is still awaiting the go-ahead.
