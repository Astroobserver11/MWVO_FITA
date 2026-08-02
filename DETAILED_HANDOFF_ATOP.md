# Detailed Handoff — MWVO Wide-Angle ISM Hub (code build) → ATOP Code

**Purpose.** This is a work order + reference for taking the wide-angle multi-phase ISM
code from *verified-on-synthetic* to *running-on-real-data*. Everything below is
implemented and passing (`pytest tests/test_wideangle.py` = 6/6; `python
smoke_test_wideangle.py` = 9/9). What remains is data wiring and a short punch-list, all
enumerated in §6–§7.

**Repo:** `C:\Users\astro\fita\` — the `fita` format kernel (images+alpha) and the
`uranodyne` science package. New wide-angle code lives in `uranodyne/pipeline/`, with thin
`fita/pipeline/` re-export shims (the project's established pattern).

---

## 1. Orientation

The hub co-registers every ISM phase (HI, CO, dust, 3D dust, X-ray, polarization) onto a
common Galactic frame with an explicit provenance ledger, so the multi-phase energy budget
and cross-validations become aligned-pixel arithmetic. Two new capabilities this build:

- **3D dust (Edenhofer 2024) folded into the X-ray absorption** — gives the *foreground*
  column the shadow model actually needs (only dust nearer than the source attenuates it),
  closing the emission-separation gap.
- **1.25 → 2.5 kpc graft** — extends the constrained Edenhofer volume with a coarse deep map
  (Lallement/Vergely), with honest error inflation and a fog-alpha visual encoding.

---

## 2. Package map (new/changed files)

```
uranodyne/pipeline/
  paci.py            PACI provenance triple (Citation·Uncertainty·Anchor Class)
  hi4pi.py           HI4PI cube stitch + cutout (memmap, moment maps, tile mosaic)
  local_survey.py    SkyView-Jar over LOCAL originals (Planck/IRIS/ROSAT/Dobashi/2MASS/CO)
  xray_absorption.py shadow model + multiphase (Edenhofer fg + HI + CO) + kriging (CAP)
  edenhofer.py       3D dust volume: LOS integrate, foreground_nh, fog, graft to 2.5 kpc
  setup_data.py      readiness/env check + Edenhofer fetch helper
fita/pipeline/       shims: hi4pi, local_survey, xray_absorption, paci, edenhofer
tests/test_wideangle.py   durable units (incl. PACI .fita round-trip)
smoke_test_wideangle.py   end-to-end synthetic check (the handoff contract)
HANDOFF_edenhofer_1p25_to_2p5kpc.md   the extension design record
```

---

## 3. Engines — API you'll actually call

**Edenhofer 3D (`edenhofer`)**
- `EdenhoferCube.from_dustmaps(l, b, size_deg, ...)` — official loader (needs `dustmaps`).
- `EdenhoferCube.synthetic(...)` — deterministic test volume, no data needed.
- `foreground_nh_map(vol, d_pc)` — 2-D foreground N_H to a source distance (the absorber).
- `graft_outer_shell(core, outer_provider=lallement_provider(cube), d_max_pc=2500)`.
- `to_distance_shells(vol_or_graft)` — FITA cube, one layer/shell, `zdepth`=distance,
  alpha faded past 1.25 kpc.
- `kinematic_distance_flat(l, v_lsr)` — seam validator (returns NaN near the anticenter).

**Absorption (`xray_absorption`, `MultiWavelengthAbsorptionModel`)**
- `.run_multiphase(inputs, d_source_pc=...)` — Edenhofer foreground as absorber, HI+CO gas
  total as cross-check (`regression['gas_dust_ratio']` ≈ 1 where phases agree).
- `krige_anchors(xy, values, shape)` — ordinary kriging with data-derived correlation
  length = the CAP spatial posterior (mean + honest variance field).
- `co_to_nh2`, `hi_to_nh`, `total_gas_nh`, `band_sigma`, `predict_transmission`.

**HI4PI (`hi4pi`)** — `HI4PICube.open_allsky('CAR').subcube(l,b,size,vmin,vmax)`,
`moment0/1`, `stitch_tiles`, `cutout`.

**Local surveys (`local_survey`)** — `cutout(key, l, b, size, target_wcs=...)`,
`co_wco(key, ...)` (reuses HI4PI engine; Dame & now the galactic-CAR Oph cubes),
`absorption_inputs(l, b, size)`, `polarization_layers(q, u, ...)`.

---

## 4. PACI provenance (verified to round-trip)

Every layer carries the triple in `extra_header`: `CITATION`, `UNCERTVL`, `ANCHORCL`
(`MEASURED`|`SCOUTED`|`ANCHORED`), `UNCKIND`. `paci.tag_layer(layer, Provenance(...))` stamps
it; `paci.promote_to_anchored(...)` performs the Scout→Anchor promotion after point
confirmation. **Confirmed:** the triple and the per-pixel `uncert_data` survive a `.fita`
`write`→`read` round-trip (`tests/test_wideangle.py::test_paci_roundtrip_through_fita`).

Rule enforced in code: nothing beyond the Edenhofer 1.25 kpc boundary can be `MEASURED` —
graft shells are hard-tagged `SCOUTED`, their σ inflates with distance, and their FITA alpha
fades. Brightness and stated uncertainty read the same distance-confidence curve, so a far
shell cannot be made to *look* more certain than it is.

---

## 5. Physics reference (constants + citations)

| Quantity | Value | Source |
|---|---|---|
| N_H / A_V | 2.21e21 cm⁻²/mag | Güver & Özel 2009 |
| Zhang unit → A_V | ×2.8 | Edenhofer 2024 (Zhang 2023 curve, Zenodo 6674521) — **pinned** |
| σ(E) photoelectric | Morrison & McCammon 1983 | band-avg R1=1.18e-20, R2=7.27e-21 cm² |
| X_CO | 2.0e20 cm⁻²/(K km/s) | Bolatto, Wolfire & Leroy 2013 |
| N(HI)/W_HI | 1.823e18 cm⁻²/(K km/s) | optically-thin 21-cm |
| Edenhofer extent | 69 pc – 1.25 kpc | Edenhofer 2024, A&A 685 A82 |

Sanity anchor: band-avg σ(R1) puts τ=1 at N_H≈8.5×10¹⁹ — where the ¼ keV band is known to
go optically thick. Verified in the smoke test.

---

## 6. Verified vs. stubbed — honest status

| Component | Status |
|---|---|
| PACI triple + `.fita` round-trip | **Verified** (unit test) |
| Physics kernels (σ, X_CO, N_H, kriging) | **Verified** (unit + smoke) |
| Edenhofer LOS integrate / foreground / fog / graft | **Verified on synthetic** |
| `run_multiphase` (Edenhofer fg + HI + CO vs ROSAT) | **Verified on synthetic** |
| Cartesian graft provider (trilinear) | **Verified on synthetic cube** |
| `EdenhoferCube.from_dustmaps` | **Written, unrun** — needs `dustmaps` + fetch |
| `lallement_provider` (real EXPLORE cube) | **Written, unrun** — header geometry inferred |
| HEALPix paths (Planck cutout, Zenodo loader) | **Written, unrun** — needs `healpy` |
| Census locator (schema-agnostic) | **Verified** on synthetic `census_files` |
| `separate_emission` (R1/R2 LHB/halo split) | **Not implemented** — routed around by Edenhofer fg |
| HI4PI subcube WCS | Exact for CAR; **approximate** for SFL/AIT |

---

## 7. Punch-list / work order

**Blocking before any science result:**
1. `pip install dustmaps healpy spectral_cube`; then `python -c "import
   uranodyne.pipeline.setup_data as s; print(s.readiness_report())"` — expect all packages ✓.
2. `python -c "from uranodyne.pipeline.setup_data import fetch_edenhofer; fetch_edenhofer()"`.
3. Point config at real data (see §8): set `FITA_CENSUS_DB` to the actual `MWVO_MERGED.db`
   path, `FITA_HI4PI_ALLSKY`, `FITA_EDENHOFER_DIR`. (Readiness currently reports these not
   found from defaults.)
4. Run `EdenhoferCube.from_dustmaps(...)` once on a real field and fix any API mismatch
   (differential vs. integrated extinction; sigma mode).
5. Acquire a Lallement/Vergely EXPLORE cube, run `lallement_provider(path)` once, verify the
   header-derived origin/voxel (or pass them explicitly).

**Non-blocking, soon:**
6. Re-run `smoke_test_wideangle.py` swapping `synthetic()`→`from_dustmaps()` and the
   Cartesian provider→`lallement_provider(<cube>)`. If it stays 9/9, integration held.
7. Decide `separate_emission`: build the R1/R2 hardness-ratio LHB/halo split, or keep relying
   on the Edenhofer foreground (fine when a source distance is known).
8. Point `co_wco` at the finished `OphA_12co_galCAR.fits` / `OphA_13co_galCAR.fits` (registry
   already updated to those tokens — just confirm they're in the census).

---

## 8. Config — environment variables

| Var | Purpose | Example |
|---|---|---|
| `FITA_CENSUS_DB` | catalog for the locator | `H:\MWVO_DATA\MWVO_MERGED.db` |
| `FITA_HI4PI_ALLSKY` | dir with CAR/SFL/AIT.fits | `I:\...\ANIMATION OVERFLOW` |
| `FITA_HI4PI_TILES` | os.pathsep tile roots | `I:\...\HI4Pi Cubes` |
| `FITA_EDENHOFER_DIR` | Edenhofer HEALPix shells | (Zenodo release dir) |
| `FITA_SURVEY_ROOTS` | glob fallback roots | `H:\MWVO_DATA` |
| `FITA_SKYVIEW_CACHE` | SkyView SCOUTED cache | `.\skyview_cache` |

The locator is now schema-agnostic: it discovers a `files` / `census_files` / `all_files`
table automatically, so `MWVO_MERGED.db` works directly.

---

## 9. Known limitations / referee notes

- **Doc-vs-code reconciled:** the "kriging posterior with data-derived correlation length"
  claim is now backed by `krige_anchors` (ordinary kriging, exponential model, empirical
  semivariogram length). `triangulate()` remains the OLS shadow-slope fit; use `krige_anchors`
  for the CAP spatial propagation. Don't conflate the two.
- **Anticenter kinematics:** `kinematic_distance_flat` returns NaN for |l−180°|≲10°, so
  **Taurus (l≈170°) cannot be seam-validated by kinematics** — use Edenhofer near-face
  distance or stellar parallax there. Ophiuchus (l≈353°) is fine.
- **Frame discipline:** Galactic CAR is canonical. The Oph COMPLETE cubes are now
  ATOP-reprojected to galactic CAR — use those, don't re-handle SIN.
- **Unit trap:** Lallement A_V/pc must be divided by 2.8 to sit on the Edenhofer Zhang-unit
  scale before grafting — handled inside `make_cartesian_provider(value_is_av=True)`, but if
  a provider passes already-Zhang-unit density, set `value_is_av=False`.
- **Fat cubes:** the galactic-CAR Oph cubes are ~14% finite (NaN padding). A bbox-crop pass
  reclaims ~7 GB; not blocking.

---

## 10. Suggested next module + evolution

The natural next engine is **`grid`** — reproject *all* tracers (HI4PI, Dame CO, galCAR Oph,
Planck, IRIS, ROSAT, Edenhofer foreground) onto one shared Galactic-CAR grid at a chosen
resolution, producing a single co-registered FITA stack. Every cross-validation
(HI↔CO, ¹²CO↔¹³CO, gas↔dust, dust-shell↔ROSAT, polarization↔column) then becomes a pixel
operation that inherits Anchor Class — a MEASURED↔MEASURED test is strong, anything touching
a SCOUTED layer is flagged weaker, so no comparison silently over-claims. `reproject.py`
already provides the primitives; `grid` is mostly orchestration + a manifest.

---

## 11. Cross-references

- **ATOP data-side outputs:** `H:\MWVO_DATA\CO_COMPLETE_Oph\galactic\OphA_{12,13}co_galCAR.fits`
  (galactic CAR, censused), `MWVO_MERGED.db` (census ∪ archive ∪ canonical), `dedup_report.md`,
  `BIBLIOGRAPHY.md` (PACI Citation leg — recommend a URL hard-verify pass).
- **Memory nodes:** `project_mwvo_hub`, `reference_survey_sourcing`,
  `feedback_paci_cap_methodology`, `project_storage_network`, `project_unphysics`.
- **Design record:** `HANDOFF_edenhofer_1p25_to_2p5kpc.md`.

---

## 12. Contract for a fresh thread

If starting a new ATOP Code thread from this file: the single acceptance test is
`python smoke_test_wideangle.py` staying **9/9** after the real-data swaps in §7. That one
command is the definition of "the integration held." Keep both source catalogs untouched
(ATOP's standing rule); nothing here deletes data.

*MWVO wide-angle hub. Format family: FITA (images+alpha) · FITR (radio uv) · FITO*
*(volumetric, deferred). Contact: Ignacio A. Cisneros.*
