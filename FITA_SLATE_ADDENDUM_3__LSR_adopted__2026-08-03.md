# SLATE ADDENDUM 3 — the LSR is ADOPTED, not established; with the bibliography

**Prepared by:** BTOP, 2026-08-03
**Extends:** Addendum 2 (`__velocity_legend__`)
**Contains:** rulings A–C recorded, the D-4 bibliographic search executed against ADS, and a
measured error budget for the verification pipeline.

---

## 1. Ruling A — the inferred label is an axis property, inherited by every z value

> *Each slice of an astrophysical velocity cube is at least the presentation of a velocity as an
> inferred rate of change. Each z value thus inherits that label; its x,y displacement has no
> effect on that.*

This settles how the epistemic status attaches. It is **not** per-value and **not** per-file: it is
a property of the **axis**, inherited by every slice on it. A z value cannot escape the label by
being displaced in x or y, because displacement is a rendering operation and inference is a
statement about how the number was obtained.

Consequence for the implementation: one status per axis, applied to all slices, written once. This
also **removes a hazard** — a per-slice status would let a file mark some channels measured and
others inferred within one cube, which for a velocity axis is not a state that can honestly exist.

---

## 2. Ruling B — adopt the FITS standard keywords

Accepted and now **unblocked for implementation**: `CTYPE3` / `CRVAL3` / `CDELT3`, `RESTFRQ` /
`RESTWAV`, `SPECSYS`, `VELOSYS`, `SSYSOBS`. No `FITA_*` equivalents are to be minted where the FITS
standard already expresses the fact.

This also discharges the Addendum 2 §3 finding: the Paper III conformance claim in `spec.py:40`
becomes true by implementation rather than being withdrawn.

**One gap in the primary standard, found while checking:** FITS defines `VELOSYS` — the velocity of
the reference frame with respect to the observer — but defines **no companion uncertainty
keyword**. Since §4 below shows that uncertainty is the whole point, this is the one place a
`FITA_*` keyword is justified: the standard is silent, not contradicted. Proposed `FITA_VSE`
(VELOSYS error, same units). Flagged as a decision, not assumed.

---

## 3. Ruling C — the LSR is ADOPTED

> *"established" is dubious: I would say it is "adopted"*

Accepted, and it is the more precise word. An adopted value is one the community agrees to use so
that results are comparable — which is a different epistemic act from measuring something.

**This adds a fourth term to the D-9 vocabulary:**

| Term | Meaning |
|---|---|
| **Established** | Fixed by measurement or by an external standard; not in dispute |
| **Adopted** | A convention agreed for comparability. May be revised; carries a history and an error bar |
| **Inferred** | Derived from an observable through a model |
| **Proposed** | Asserted by the author, awaiting acceptance |

The distinction is load-bearing for velocity cubes: labelling the LSR *established* would tell a
reader the frame is a fixed fact. §4 shows it is not.

---

## 4. Ruling D — the bibliography, and it supports the concern

▣ Searched against NASA ADS, 2026-08-03. **The claim that there is more than one Local Standard of
Rest is correct, and the disagreement is larger than the channel width of the data it is applied
to.**

### The contested quantity: V☉, the Sun's peculiar velocity in the direction of rotation

| Determination | V☉ (km/s) | Method |
|---|---|---|
| Dehnen & Binney 1998 ([1998MNRAS.298..387D](https://ui.adsabs.harvard.edu/abs/1998MNRAS.298..387D)) | **≈ 5.2** | Hipparcos local stellar kinematics |
| Schonrich, Binney & Dehnen 2010 ([2010MNRAS.403.1829S](https://ui.adsabs.harvard.edu/abs/2010MNRAS.403.1829S)) | **12.24 ± 0.47** | chemodynamical model of local kinematics |
| Coskunoglu et al. 2011, RAVE ([2011MNRAS.412.1237C](https://ui.adsabs.harvard.edu/abs/2011MNRAS.412.1237C)) | **≈ 13** | RAVE survey kinematics |
| Reid et al. 2014, BeSSeL ([2014ApJ...783..130R](https://ui.adsabs.harvard.edu/abs/2014ApJ...783..130R)) | **14.6 ± 5.0** | VLBI parallaxes of high-mass star-forming regions |

*The 5.2 figure is not asserted from memory: Schonrich et al. state in their own abstract that
"V_solar is 7 km/s larger than previously estimated", and 12.24 − 7 = 5.2.*

**The spread in V☉ is a factor of ~2.8, and the single revision from Dehnen & Binney to Schonrich
et al. moved it by 7 km/s.** For context, ALMA and HI velocity cubes are routinely channelised at
0.1–1 km/s. **A 7 km/s systematic shift is 7 to 70 channels.** A cube whose slice labels were
computed under one LSR convention and are read under another is mislabelled by more than its own
resolution.

Reid et al. also record the structural reason this persists: Θ₀ and V☉ are strongly **correlated**,
and it is their *sum* that is well constrained — Θ₀ + V☉ = 255.2 ± 5.1 km/s. The individual split
is model-dependent, which is exactly what makes the value adopted rather than measured.

### The quasar-based state of the art — with one distinction that matters

| Work | Result |
|---|---|
| Gaia EDR3, Klioner et al. 2021 ([2021A&A...649A...9G](https://ui.adsabs.harvard.edu/abs/2021A%26A...649A...9G)) | Solar System acceleration **(2.32 ± 0.16) × 10⁻¹⁰ m s⁻²** = 7.33 ± 0.51 km/s/Myr, toward α = 269.1° ± 5.4°, δ = −31.6° ± 4.1°, from quasar proper motions |
| Titov et al. 2011 ([2011A&A...529A..91T](https://ui.adsabs.harvard.edu/abs/2011A%26A...529A..91T)) | VLBI measurement of the secular aberration drift — the precursor technique |
| Truebenbach & Darling 2017 ([2017ApJS..233....3T](https://ui.adsabs.harvard.edu/abs/2017ApJS..233....3T)) | VLBA extragalactic proper motion catalogue, independent aberration drift |

**The distinction, stated so the pipeline does not overclaim:** quasars establish the *inertial
frame* and measure the barycentre's *acceleration* — they do not measure the Sun's peculiar
velocity with respect to the LSR. That still comes from stellar kinematics, which is where the
disagreement in the table above lives. So the SOTA quasar work makes the **frame** rigorous while
leaving the **LSR offset** adopted. Both facts belong in the legend, and they are not the same
fact.

Supporting: GRAVITY Collaboration 2019 ([2019A&A...625L..10G](https://ui.adsabs.harvard.edu/abs/2019A%26A...625L..10G)) gives R₀ to 0.3%, and McMillan 2010
([2010MNRAS.402..934M](https://ui.adsabs.harvard.edu/abs/2010MNRAS.402..934M)) — *"The uncertainty in Galactic parameters"* — is the dedicated treatment of the
correlated error budget.

---

## 5. What this requires of the verification pipeline

The principal's conclusion — *"at best, there is an error bar to be brought into the verification
pipeline"* — is now quantified. Proposed as forced by §4, not as taste:

1. **A velocity cube MUST declare its frame** (`SPECSYS`) and the frame velocity used (`VELOSYS`).
   A cube that does not is not reproducible: its labels cannot be recomputed under a different
   convention.
2. **The LSR carries an uncertainty and it MUST be expressible** — `FITA_VSE`, since FITS provides
   no companion to `VELOSYS`. Where the adopted convention is cited rather than measured, the
   citation belongs with it.
3. **The legend labels the frame ADOPTED, never established or measured** — per Ruling C.
4. **The validator SHOULD warn when the LSR uncertainty exceeds the channel width**, because that
   is precisely the regime in which the slice labels are less certain than their own spacing. This
   is the concrete form of the error bar entering the pipeline, and §4 shows the regime is not
   hypothetical — it is where the historical revisions have landed.

---

## 6. Standing decisions

| | Status |
|---|---|
| **D-9** epistemic axis vs PACI | open — vocabulary now **four** terms (Ruling C); Addendum 2 §2 and Ruling A both favour option (a) |
| D-10 natural IPD constant | open |
| D-11 acquisition-block scope | open |
| D-12 derive, never store | open |
| D-13 legend normative | partly answered |
| D-14 z-axis kind | **RULED** — axis-split |
| **D-15** phased depth: amplitude or phase | **open, still blocking** |
| D-16 isometric y excursion | open |
| **D-17** `FITA_VSE` for the LSR uncertainty | **new** — §2, recommended |

Queued and not decisions: the `-1.0` sentinel fix (forced by D-5) and the Paper III spectral
keywords (now unblocked by Ruling B).
