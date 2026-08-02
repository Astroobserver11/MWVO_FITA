# Handoff — Extending the 3D Dust Field from 1.25 kpc to 2.5 kpc

**Project:** MWVO wide-angle multi-phase ISM hub
**Scope:** how to carry Edenhofer's constrained 3D dust volume outward to 2.5 kpc without
lying about what we know, and how that field folds into the X-ray absorption calculation.
**Status:** engine implemented and verified (`uranodyne.pipeline.edenhofer`,
`.local_survey`, `.xray_absorption`); this document is the design record and the plan for
the remaining data-side work.

---

## 1. The core reframe: "extend" means GRAFT, not extrapolate

Edenhofer et al. 2024 (A&A 685, A82; arXiv:2308.01295) reconstruct differential dust
extinction on a heliocentric sphere out to **1.25 kpc** — not 1.5 — from 54 million stars
with Gaia XP spectra (Zhang et al. 2023 catalogue). The map stops at 1.25 kpc because that
is where the constraining stars run out; distance resolution has already coarsened from
0.4 pc near the Sun to ~7 pc at the edge.

Consequently the same MGVI inference **cannot** be pushed to 2.5 kpc — with no stars to
constrain it, the posterior simply relaxes to the prior. "Extend to 2.5 kpc" therefore
means **graft** a coarser deep map onto the Edenhofer high-resolution core beyond 1.25 kpc.
This is exactly the PACI Scout → Anchor pattern applied to the *radial* axis:

- **0 – 1.25 kpc** — Edenhofer core, Anchor Class **MEASURED** (its own per-voxel posterior).
- **1.25 – 2.5 kpc** — grafted shell, Anchor Class **SCOUTED**, uncertainty inflating with
  distance, validated against CO/HI kinematics rather than trusted blindly.

Recommended graft source: **Lallement 2022 / Vergely 2022 (EXPLORE)** — native Galactic,
continuous to ~3 kpc, ~10–25 pc resolution. Green 2019 (Bayestar) is the deeper fallback.
The graft source is **pluggable** (`graft_outer_shell(core, outer_provider=...)`), so the
choice is not baked in.

---

## 2. Representation: distance-shell FITA (FITO deferred)

Per decision, we do **not** define a new FITO format yet. The volume is carried as a
**distance-shell FITA cube** (`to_distance_shells`): one `FITALayer` per distance bin, with
the layer's stereo `zdepth` keyword repurposed as **normalised distance**. This is a natural
fit — the FITA renderer already treats `zdepth` as parallax, so the dust field renders as a
phased 3D structure with the existing tooling, no new format required.

When a true volumetric container is eventually wanted, FITO should be the 3D-truth sibling
(native voxel grid + posterior samples + FITA-superset provenance, with a documented
FITO → FITA projection = "integrate to distance d"). FITR is **not** a candidate — it is the
radio/interferometry format (uv-visibilities); it has nothing to do with a dust volume.

---

## 3. Honest error accounting past 1.25 kpc (the central requirement)

Two questions were posed directly: *how do we keep honest error bars past 1.25 kpc, and do
we tint the visualisation into fog?* Both are answered by the **same mechanism** — confidence
is encoded three ways that always move together:

1. **Anchor Class demotion.** Every shell beyond 1.25 kpc is hard-tagged **SCOUTED** in its
   PACI triple (`graft_outer_shell` sets `anchor_per_shell`). Nothing past the core can ever
   masquerade as MEASURED.

2. **Uncertainty inflation.** `graft_uncertainty` gives each outer shell an absolute σ whose
   *relative* size grows with distance: ~50% at the seam, worse further out
   (`rel = base_frac + per_kpc·(d − d_core)/1000`). This σ rides on the layer's native
   `uncert_data` slot, so it propagates into the absorption error budget automatically.

3. **Fog = alpha = luminosity.** `confidence_fog_alpha` drives each shell's FITA **alpha**
   down past 1.25 kpc (exponential decay, tunable `fog_length_pc`, small non-zero floor so
   far structure stays faintly visible). Because alpha *is* rendered luminance, the picture
   literally fades into fog exactly where our trust fades — the visual and the statistics are
   the *same number*, not two hand-tuned effects. Deep-core shells render at full luminosity;
   grafted shells recede.

The design rule: **there is no way to brighten a far shell without also lowering its
uncertainty**, because both read the same distance-confidence curve. That is what keeps the
visualisation honest.

---

## 4. Seam validation against CO / HI kinematics

The graft must be *checked*, not trusted. `kinematic_distance_flat(l, v_lsr)` converts a
cloud's CO/HI LSR velocity (from the Dame composite and HI4PI now in the census) into a
kinematic distance via a flat rotation curve (R0 = 8.15 kpc, V0 = 236 km/s). Where a molecular
cloud's kinematic distance disagrees with where the grafted dust wall sits, the graft is
wrong and gets down-weighted.

**Important caveat, already enforced in code:** near the anticenter (|l − 180°| ≲ 10°, which
includes **Taurus at l ≈ 170°**) kinematic distances are degenerate — velocities are near
zero and non-monotonic — so the function returns `NaN` there rather than a garbage number.
For the Taurus field the seam must be validated by other means (Edenhofer's own near-face
distance, or stellar-parallax members), not kinematics. Ophiuchus (l ≈ 353°) is better
behaved and can use the kinematic check.

---

## 5. Unit and frame caveats (the silent-bug list)

- **Units.** Edenhofer/Zhang extinction is a *monochromatic extinction at 542 nm*, **not**
  A_V. The code carries `ZHANG_UNIT_TO_AV = 2.8` as an **approximate** conversion — this must
  be pinned from the Zhang et al. 2023 calibration before any science, and it must be the
  same A_V scale used for Dobashi/2MASS, or the multiphase reconciliation compares two
  different scales and the regression slope is meaningless. This is the single most likely
  silent bug.
- **Frame.** Edenhofer and Dobashi are natively Galactic, so **Galactic CAR is the canonical
  stack frame.** The Dame CO composite and Dame Taurus are already Galactic CAR. The Rho Oph
  COMPLETE 12CO/13CO cubes are **equatorial SIN** — `local_survey.co_wco` detects this and
  converts the field centre to RA/Dec so the native WCS resolves, then reprojects the result
  *into* the Galactic grid. Reproject the SIN cubes into CAR; never the reverse.

---

## 6. Folding the dust field into the absorption calculation

This closes the `separate_emission` gap from the previous turn. The X-ray shadow needs the
**foreground** column — only the dust nearer than the emitting source attenuates it — which a
2D column cannot give but the 3D volume can:

`foreground_nh_map(volume, d_pc)` integrates dA/ds to the source distance → A_V(<d) → N_H(<d).

`MultiWavelengthAbsorptionModel.run_multiphase(inputs, d_source_pc=...)` then uses that
foreground N_H as the absorber in the ROSAT shadow, while an **independent** gas total
N_H = N(HI) + 2 N(H₂) from HI4PI + CO (X_CO = 2×10²⁰, Bolatto+2013) serves as a consistency
cross-check (`regression['gas_dust_ratio']`, expected ≈ 1 where the phases agree). Anchor
Class is ANCHORED only when the source sits inside the constrained volume (≤ 1.25 kpc) or a
point measurement confirms it — otherwise SCOUTED, consistent with §3.

---

## 7. The Unphysics consideration

ATOP replicated Edenhofer's visualisations *via Unphysics* — the Ghose stochastic-unification
formulation (arXiv:2508.19280; ψ = √ρ·exp(iS/ℏ_eff), ℏ_eff ~ 10³³ J·s for ISM turbulence),
per `memory/project_unphysics.md`. A recommendation for the extension:

Keep the **data product** (the grafted extinction field, its σ, its Anchor Class) in the
standard, paradigm-neutral representation described above. Edenhofer's reconstruction is a
Gaussian-process posterior over extinction — a *measurement product*, not a dynamical claim —
and grafting a second measurement onto it is a data operation that should not be entangled
with a choice of physical formalism. Let Unphysics live where it earns its keep: in the
*dynamical* interpretation layer (osmotic-velocity / stochastic reading of the dust–gas
structure), scored against this neutral field as one of the two tracks. In short: **graft in
standard representation; interpret in either paradigm.** That keeps the 1.25→2.5 kpc product
reusable regardless of how the Unphysics-vs-standard scoring turns out, and avoids baking a
research hypothesis into a data container.

---

## 8. Open decisions & next steps

1. **Pin `ZHANG_UNIT_TO_AV`** from Zhang et al. 2023 — blocking for science (§5).
2. **Acquire the graft map** (Lallement/Vergely EXPLORE cube) and implement an
   `outer_provider(distances_pc, core)` that samples it onto the core's frame; until then the
   built-in prior-fog fallback runs but is only a placeholder (honestly SCOUTED, inflated σ).
3. **Reproject the Rho Oph SIN cubes** into Galactic CAR and re-census (the reproject/mosaic
   step ATOP flagged).
4. **Wire the real Edenhofer loader** — `EdenhoferCube.open_dir` is a thin stub; adapt it to
   the actual on-disk layout (or add a `dustmaps`-package loader).
5. **Validate seams** cloud-by-cloud: kinematics for Ophiuchus, parallax/near-face for Taurus.

---

## 9. API quickstart

```python
from uranodyne.pipeline import edenhofer as ed
from uranodyne.pipeline import MultiWavelengthAbsorptionModel

vol   = ed.EdenhoferCube.open_dir()              # or .synthetic() for testing
ext   = ed.graft_outer_shell(vol, d_max_pc=2500) # core MEASURED + SCOUTED graft
cube  = ed.to_distance_shells(ext)               # distance-shell FITA, fog alpha baked in

fg    = ed.foreground_nh_map(vol, d_pc=400.0)    # foreground absorber for the shadow
# inputs: co-registered FITALayers {edenhofer_fg, hi_whi, co_wco, rosat_r1}
res   = MultiWavelengthAbsorptionModel(band="R1").run_multiphase(inputs, d_source_pc=400.0)
# res.regression['gas_dust_ratio'] ~ 1 where dust foreground and HI+CO gas agree
```

*Author: MWVO hub (with ATOP on the data side). Format family: FITA (images+alpha) ·*
*FITR (radio uv) · FITO (volumetric, deferred). Contact: Ignacio A. Cisneros.*
