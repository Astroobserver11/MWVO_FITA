# Changelog

Format versions follow `FITAVER`; the package version tracks the format it
implements. Per §13 of the standard, **any change to required or optional
structure requires a version increment** — a rule this project has broken
twice and now enforces in code.

## [1.5] — 2026-08-03

Applies the principal's rulings A, B and C of 2026-08-03, and closes **D-14** and
**D-17**. The subject is the velocity cube, and the governing distinction is:

> *The x and y displacements have one logical physical interpretation: actual space
> corresponding to the angular distance for each pixel at the accepted distance.
> **There is no correspondence to the spectral shift or its conversion into
> recession velocity.***

### Fixed — failure instance #10, and it was activated by v1.4
- **The reader silently discarded every negative `FITA_ZDP`.** `io.py` still
  implemented the `-1.0` absence sentinel that **D-5 retired**, and not only for
  `-1.0` — for *any* negative value. This was harmless while §8.2 confined
  `FITA_ZDP` to `[0,1]`, and **v1.4 made physical depths legal**. The first data
  class to exercise that freedom is the velocity cube, whose channels are signed by
  nature. Writing a five-channel cube and reading it back returned a **different
  stereogram** — two channels gone, the survivors renormalised over the remainder,
  and the `max separation` summary line unchanged throughout. Round-trip regression
  tests now compare the *rendered offsets*, not a flag.

### Added
- **The FITS WCS Paper III spectral block, adopted rather than reinvented** (ruling
  B): `SPECSYS`, `VELOSYS`, `SSYSOBS`, `RESTFRQ`, `RESTWAV`, `CTYPE3`/`CDELT3`/
  `CUNIT3`. No `FITA_*` twins for facts the FITS standard already expresses. This
  also discharges the standing claim in `spec.py` to follow Paper III — previously
  asserted in a docstring and implemented nowhere.
- **`FITA_VSE`** (**D-17**) — the uncertainty on `VELOSYS`. The one new `FITA_*`
  name here, justified because FITS defines `VELOSYS` and provides **no companion
  uncertainty keyword**: the standard is silent, not contradicted.
- **`FITA_ZEP`** — the epistemic status of the depth axis. Per ruling A the label is
  a property of the **axis**, inherited by every z value; not per-value, not
  per-file. A slice cannot escape it by being displaced in x or y.
- **`fita.lsr`** — the bibliography, shipped as data and retrieved from NASA ADS
  rather than recalled. Published `V_sun` spans **5.2 → 14.6 km/s**; the single
  1998→2010 revision moved it by **7 km/s**, which at 0.1–1 km/s channelisation is
  **7 to 70 channels**. Vocabulary is four terms (ruling C): `ESTABLISHED`,
  **`ADOPTED`**, `INFERRED`, `PROPOSED`.

### Changed
- **The LSR is `ADOPTED`, not established** (ruling C). An adopted value is one the
  community agrees to use for comparability — a different epistemic act from
  measuring. Reid et al. (2014) give the structural reason it persists: Θ₀ and
  V_sun are correlated and only their *sum* is well constrained, so the split is
  model-dependent.
- **The legend refuses to convert a non-metric depth axis into a distance**
  (**D-14**). A velocity cube reports *apparent z only*, states that the separation
  is a presentation device, and carries all three slice labels at once — spectral
  displacement `MEASURED`, radial velocity `INFERRED`, frame `ADOPTED`. Reporting a
  distance there would assert in a header the very thing awaiting scientific
  consensus.

### Validator
- `VELOSYS` without `SPECSYS` → **MUST** fail: a frame velocity with no frame named.
- `FITA_VSE` without `VELOSYS` → **MUST** fail, and the writer refuses to emit it.
- `FITA_ZEP` outside the closed vocabulary → **MUST** fail.
- A velocity-valued `FITA_ZDU` with no `SPECSYS` → **SHOULD** warn: the labels
  cannot be recomputed under another convention, so the cube is not reproducible.
- `FITA_VSE` wider than `CDELT3` → **SHOULD** warn. This is the error bar entering
  the pipeline, and the historical revisions land squarely in that regime.

### Corpus
Three fixtures, 20 → 23 files: `full_velocity_frame.fita` (non-metric axis, signed
channels, frame declared) and the negative pair `neg_velosys_without_specsys` /
`neg_vse_without_velosys`.

### Compatibility
Adds only OPTIONAL structure; absence of every new keyword reproduces v1.4 meaning.
**The increment is required even though v1.4 was never tagged** — v1.4 corpus files
exist and are committed, so files written before and after would otherwise claim one
version while differing in structure, which is verbatim the `[CORRECTION]` the
standard levels at the 2026-05-25 delivery.

## [1.4] — 2026-08-02

Applies the principal's ruling of 2026-08-02
(`RULING__stereogram_scale_and_N-1__2026-08-02.md`):

> *"The scale of the Stereogram is a percentage of the diameter of the field under
> study, made explicit as a measure in units practical to the subject."*

### Added
- **`FITA_FDI` / `FITA_FDU`** — the diameter of the field under study and its unit,
  chosen to be practical to the subject (`pc`, `km`, `arcsec`, `deg`, `AU`). These
  supply the absolute half of the metric chain.
- **`FITA_ZDU`** — the unit of `FITA_ZDP`, resolving **N-1**. Absent, `FITA_ZDP` is
  dimensionless and must lie in `[0,1]` (unchanged). Present, it carries a physical
  depth and the `[0,1]` constraint does not apply. The eight archived Edenhofer
  files hold 624.05 / 1248.10 / 2496.20 pc: the values were right and the
  *declaration* was missing, so they become conformant by adding one keyword rather
  than by rewriting 48 layers of science data.
- `fita.stereo.normalise_depths()` and `to_display_pixels()`.
- Two corpus fixtures: `full_with_zdepth_units.fita` (parsec depths, FITA-FULL) and
  `neg_zsc_without_field.fita` (the clause that enforces the ruling).

### Changed
- **`FITA_ZSC` is now a percentage of `FITA_FDI`, not a pixel count.** A pixel is a
  property of a rendering target, not of a field, and is meaningless without a
  display size the file does not know. Parallax is now
  `dx = ±(FITA_ZSC/100) × FITA_FDI × (zdp_n − FITA_ZRF)/2`, in units of `FITA_FDU`.
  Converting to display pixels is the renderer's job and is deliberately not
  recorded in the file.
- `fita.stereo` reports separations in `FITA_FDU`, never in pixels.
- `fita doctor` names the exact directory to add to PATH when the console script is
  installed but not reachable — ATOP lost a session to a diagnostic that stated the
  fault without localising it.
- `fita doctor` now **fails** on format/package version drift. It previously printed
  both numbers and returned OK regardless, so it could never have caught N-3.

### Removed
- **`FITA_ZAN` is retired by dissolution.** The open question — sky angle or viewing
  disparity? — was malformed: once the field diameter carries a subject-practical
  unit, the separation follows by arithmetic in whatever unit the subject wants.
  `FITA_ZAN` hard-coded arcsec, the wrong default for a parsec-scale dust cube.
  Readers must still accept it (D-1); writers no longer emit it.

### Fixed
- **N-7** — `fita info` crashed with `TypeError` on every archived file. `FITA_FMN` /
  `FITA_FMX` are SHOULD, not MUST, so a fully FITA-CORE-conformant file may omit
  them; the CLI assumed a keyword the standard makes optional. Absent bounds now
  print as `-`, matching the convention `wave` already used in the same line.

### Also in this release — the environmental escalation

ATOP escalated (HIGH) that N-5 was closed as *environmental* on arithmetic that fit
the observed number without being its cause: `241 − 48 = 193` matched, but reaching
241 *passing* needs five optional dependencies, not one. ATOP measured **234 passed,
7 skipped, 241 collected** on the v1.3.0 tree. The correction that shipped was
therefore still wrong — the erratum's own failure mode, recurring inside the fix for it.

- **Failure instance #9 recorded**: a module-level `pytest.importorskip` reports ONE
  skip per module however many tests it holds, so 48 missing tests appeared as a
  single skip line. The passed count moves and nothing says the denominator moved
  with it. This is in the **test harness** — the instrument the project uses to
  detect silent loss had the defect it exists to detect.
- **CI asserts a collected-count floor** and reports skips (`-rs`). Until now the
  matrix did not install URANODYNE, so every cell silently ran the kernel-only
  subset and reported green; "CI green" was not evidence about coverage.
- **README publishes the counts with their preconditions** — 221 kernel-only, 269
  with URANODYNE, and what each row requires. Three environments had produced three
  numbers and all three reported success.
- **`corpus/TOOLCHAIN.lock`** — an installable pin of the toolchain that produced the
  corpus bytes, generated *from* `MANIFEST.json` so the two cannot drift. Closes
  **N-6**: ATOP skipped byte-comparison because its toolchain differed and there was
  no declared environment to install in order to match.

**RULE E** (no finding closed as *environmental* until the difference is named,
pinned, re-run, published with preconditions, and shipped in the environment
declaration) is drafted by ATOP and **awaits the principal's ruling** — it is not
adopted here.

### Version note — why this is 1.4 and not 1.5

§13 requires an increment for any change to **required or optional structure**. The
escalation items change documentation, CI and packaging; they add no keyword, alter
no HDU, and change no validator verdict. Incrementing for them would stamp a new
`FITAVER` into files that are structurally identical to v1.4 — a version claim
without a structural difference, which is the same defect as a structural difference
without a version claim, running the other way. The stereo ruling is the only
structural change in this release, so the format is **1.4**.

### Compatibility
Adds only OPTIONAL structure. Absence of every new keyword reproduces v1.3 meaning
exactly, so no existing conformant file changes status.

## [1.3] — 2026-08-02

### Added
- **`pol_xel`** to `FITA_META`. ATOP's audit asked whether three specific ObsCore v1.1
  mandatory columns were present; `pol_xel` was **missing entirely** and `t_resolution`
  was written but not enforced. The v1.2.1 correction would itself have been false had it
  claimed completeness. A written file now carries 33 columns, all 30 ObsCore v1.1
  mandatory ones, each with a `TUCDn`.

### Changed
- Validator enforces the **30** ObsCore v1.1 mandatory columns (was 26).
- `FITAVER` is **1.3**. v1.2.1 briefly set `"1.2.1"`, which is malformed — §13 defines
  `FITAVER` as `major.minor`. The label correction alone needed no format increment, but
  adding `pol_xel` changes optional structure, which §13 does require one for.
- `FITR_SPEC.md` corrected — it is where the phantom "ObsCore v1.2" entered the family.

## [1.2.1] — 2026-08-02

### Fixed
- **A conformance claim to a standard version that does not exist.** v1.2.0
  asserted IVOA **ObsCore DM v1.2** in the normative standard, the reference
  implementation, the README, the citation metadata, and inside every
  `FITA_META` HDU of the published corpus. **There is no ObsCore v1.2** —
  v1.1 (2017-05-09) is the only Recommendation, confirmed against two IVOA
  sources. The standard had also explicitly authorised the claim's
  "unqualified use"; that sentence is withdrawn.

  Raised by ATOP's audit, which was written 14 hours before publication and
  never arrived — the bridge delivered it outside the inbox and failed
  silently.

  **Completeness against Table 1 of the v1.1 REC remains UNVERIFIED** and is
  now labelled as such everywhere. See
  [`ERRATUM__ObsCore_version__2026-08-02.md`](ERRATUM__ObsCore_version__2026-08-02.md).

## [1.2.0] — 2026-08-02

Adds only OPTIONAL structure, so v1.1 files remain readable.

### Added
- `FITA_ADJ` BINTABLE — the non-destructive display stack is now serialised
  (D-3). Common parameters are **typed columns**; JSON is reserved for
  genuinely variable-length ones. Satisfies `FITR_SPEC` §8, which had
  delegated its display mathematics to an HDU no file had ever contained.
- Stereo geometry keywords `FITA_ZSC` (parallax in px), `FITA_ZRF` (the depth
  placed at the screen plane) and `FITA_ZAN` (angular measure), with the
  offset convention `dx = ±(ZSC/2)(ZDP − ZRF)` (D-6).
- `CHECKSUM` / `DATASUM` on every HDU, plus `DATE` / `CREATOR` / `ORIGIN`.
  Written deterministically so generated artifacts stay reproducible.
- A conformance corpus of 18 labelled files -- byte-reproducible within a
  recorded toolchain, semantically stable across astropy versions -- with a
  published `survival_spec` for scoring format bridges.
- `fita doctor` — diagnoses whether an *installation* works from where you
  are standing.

### Changed
- `FITA_META` targets IVOA ObsCore **v1.1** (the current Recommendation): its column set, and
  per-column UCDs written as `TUCDn`. Previously nine columns were missing and
  the UCDs were defined in source but never written to the file.
- `io.write()` accepts `provenance=`, making FITA-FULL reachable through the
  documented API for the first time.

### Fixed
- Git classified `*.fita` as text; with `core.autocrlf` this would have
  inserted CR bytes into FITS data sections and destroyed files on clone.
  `.gitattributes` added.
- `AdjustmentStack.to_records()` emitted a parameter dict no subclass ever
  wrote to, so a round trip silently restored **default** adjustments.

## [1.1] — 2026-08-02

Ratification of the v1.1 standard (decisions D-1…D-7).

### Removed
- **`SPLIT16` packing.** Measured destructive, not lossy: the written file did
  not retain the information needed to recover the flux at all. The writer
  refuses it; the reader raises. No archived file used it.

### Fixed
- `ALPHA_*` now uses the FITS unsigned-16 convention (`BZERO=32768`). Files
  written before this carry values above half-opaque as negative numbers, which
  third-party viewers read literally.
- `BUNIT` values `'alpha16'` and `'same as FLUX'` were not parseable FITS
  units; both retired.
- `FITA_VIS` added — layer visibility was silently lost on every round trip in
  every backend.

### Added
- `fita.validate()` / `fita conform` — the conformance checker the standard
  requires, with FITA-CORE and FITA-FULL levels and a NaN-aware bit-exactness
  test for the flux invariant.

## [1.0] — 2026-05-18

Initial: layers, alpha, blend modes, FITS/HDF5/Zarr backends.

> Files written under 1.0 are **grandfathered** (D-1): they remain readable,
> and the validator reports precisely why they do not certify.
