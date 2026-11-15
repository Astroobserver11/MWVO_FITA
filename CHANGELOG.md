# Changelog

Format versions follow `FITAVER`; the package version tracks the format it
implements. Per §13 of the standard, **any change to required or optional
structure requires a version increment** — a rule this project has broken
twice and now enforces in code.

## [1.5.3] — 2026-11-14

Version concordance. No code behaviour changed; `FITAVER` stays **1.5** throughout.

### Fixed — the documentation half of the de-facto-spec failure
- **The standard now describes the format the code implements.** `FITA_ZEP` and the
  FITS WCS Paper III spectral block had been *enforced by the validator since
  2026-08-07 while appearing in no normative document at all* — the checker emitted
  clause tag `S8.5` against a clause that did not exist. §8.5 now specifies the
  author's rulings A, B and C of 2026-08-07: the adopted FITS keywords (`SPECSYS`,
  `VELOSYS`, `SSYSOBS`, `RESTFRQ`/`RESTWAV`), the closed four-term `FITA_ZEP`
  vocabulary, and `FITA_VSE` with the channel-width test
  $\sigma_{\texttt{VELOSYS}} \le |\texttt{CDELT3}|$. §8.4 is left deliberately
  unassigned so document numbering matches the tag the checker reports.
  §13 gains the 1.5 row; **§13.1 is new** and states that `FITAVER` is not the
  package version.
- **The standard has a version-neutral filename.** It was
  `FITA_FORMAT_STANDARD.RATIFIED-v1.2.md` while its contents said v1.4 — the name
  knowingly frozen because published records cite it, at the cost of a filename that
  contradicted the document for three successive versions. It is now
  **`FITA_FORMAT_STANDARD.md`**, which its own 2026-08-02 header had already said it
  was "destined to" be. The old path is retained as a **pointer stub** so existing
  citations keep resolving. *A version belongs inside a document, never in its name:
  a name cannot be corrected without breaking every citation to it.*
- **Four files in the repository root each looked like "the standard"** by filename
  alone — the direct cause of the question "why are there inconsistencies in the repo
  around the format documentation". The three superseded ones (the v1.1 ratification
  snapshot and two 2026-07-29 transport copies) now carry SUPERSEDED banners pointing
  at the canonical document. They are otherwise **unedited**: their byte-exactness is
  what makes the ratification chain auditable.
- **Citation metadata aligned.** `.zenodo.json` said `1.4.0` while the code said 1.5
  and `CITATION.cff` said 1.5.0; its description advertised a **corpus of 18 files
  when there are 24** — a published inaccuracy about evidence a reviewer can count.
  `CITATION.cff` now records that only v1.2.0 has a version DOI, since Zenodo does
  not backfill. The `Documentation` URL no longer points at a versioned filename.
- **The README advertised a URANODYNE install command that could not work.**
  `pip install git+…/uranodyne.git` fails resolution, because URANODYNE requires
  `mwvo-fita>=1.5.0`, which is not on PyPI. Replaced with the `[uranodyne]` extra and
  the explicit two-URL form, both measured.
- **The README claimed the HDF5 round-trip was untested.** It is tested now, so the
  claim was carried one release too long; the "all three backends" statement is
  confirmed for all three. Test counts replaced with same-day measurements and their
  preconditions.

### Changed
- **`h5py` added to `[dev]`.** CI installs `[dev]`, which did not include it, so the
  14 tests exercising the HDF5 backend — **including both `SPLIT16` refusal tests** —
  silently skipped. "CI green" was therefore never evidence about HDF5, which is how
  a destructive packing mode stayed reachable through the HDF5 and Zarr writers for
  three months after D-2 deleted it. §10.1's "cannot be used **or verified**" was
  doing real work and the dev extra was ignoring it. The CI row moves from
  264 passed / 17 skipped to **293 passed / 3 skipped**, the 3 being the
  URANODYNE-gated modules by design.

### Added
- `tests/test_version_concordance.py` — **15 tests that assert the concordance holds**,
  so it cannot drift again in silence: `FITAVER` is `major.minor` with no patch part,
  the package version implements the stated format, the standard's status line, title,
  version field and §13 table all agree with `fita.spec.FITA_VERSION`, every keyword
  the validator enforces is findable in the standard, `.zenodo.json` and
  `CITATION.cff` agree with `pyproject.toml` and still parse, the advertised corpus
  size matches `MANIFEST.json`, the machine-readable AI format card names the
  current standard rather than a superseded one, and no live document links the
  retired filename. Full suite with everything installed: **341 passed, 0 skipped.**

## [1.5.2] — 2026-11-14

### Fixed — the FLOAT32 ruling only reached one of the three writers
- **1.5.1 gated `io.py` (FITS). The HDF5 and Zarr writers went on accepting
  float64.** Found by actually exercising HDF5 rather than trusting the previous
  fix: both backends wrote a float64 FLUX array without complaint and truncated it
  back to float32 on read — relative error $3.3\times10^{-8}$, two pixels held
  distinct on disk collapsing into one. The identical defect the ruling exists to
  close, surviving untouched on the paths the fix had not reached.
  **The check now lives in one place**, `fita.flux.require_float32_flux()`, called
  by all three writers. A test asserts each `write()` calls it, so a future writer
  cannot quietly skip the gate — the inline-in-one-place mistake is what caused this.
  The legitimate float32 path stays bit-exact on both backends (verified with
  `h5py` 3.16.0 and `zarr` 3.4.2 actually installed, not skipped).

### Verified
- **HDF5 is now exercised, not merely claimed.** §10.1 left the backend
  "unconfirmed" while `h5py` was absent. With it present: a 3-layer stack
  round-trips bit-exact as float32, layer names and object types survive, and the
  SPLIT16 refusals on write *and* read execute for real (those two tests had only
  ever skipped).
- **FITA ↔ uranodyne over HDF5.** uranodyne contains no HDF5 code — `IrenBLink.save()`
  goes through `fita.io.write`, i.e. FITS — but it consumes the `FITALayer` objects
  FITA's HDF5 reader returns: `difference_image()` and `significance_map()` run on
  HDF5-sourced layers and recover an injected source at 7.81σ.
- Gate with every optional component installed (HDF5, Zarr, PSD, and uranodyne's
  pipeline set): **325 passed, 1 skipped, 0 failed**, up from 288/18 at the start of
  the day. SciPy now does the significance-map work; that path previously warned and
  degraded.

## [1.5.1] — 2026-11-14

Applies the principal's ruling of 2026-11-14: **FITA enforces float32 FLUX.**

`FITAVER` stays **1.5**. This release enforces an existing MUST (§6.1) and changes
no structure, so no format increment is due under §13. The package version moves
because behaviour does: calls that used to succeed now raise.

### Fixed — the writer emitted files its own validator rejected
- **`fita.write()` accepted a float64 FLUX array and wrote `BITPIX=-64`.** astropy
  writes whatever dtype it is handed and `io.py` handed it `layer.flux_data`
  unchecked, so the library produced files that `validate()` then called
  **NON-CONFORMANT** (§6.1 MUST). The reader compounded it, force-casting back to
  float32 on the way in: **FITA could write a file it could not read back.**
  Measured round trip — max relative error $3.3\times10^{-8}$, and two pixels held
  distinct on disk collapsed into a single value. A silent breach of the one array
  the standard calls sacred, committed by the implementation itself.
  **Ruled: raise, do not cast.** Losing calibrated precision is now always the
  caller's explicit decision, never a side effect of saving.

- 🔴 **`flux_roundtrip_ok()` was blind to the precision loss it exists to detect.**
  The function whose entire purpose is to prove the flux/alpha invariant by
  "bit-for-bit comparison" cast **both** sides to float32 before comparing, so a
  float64 layer that demonstrably lost precision was compared *after* truncation
  and reported as bit-exact. It returned `True` on a broken round trip.
  Now compares the arrays as they are, tolerating byte order but never width.
  *This is the project's characteristic defect for the third time — after the
  SPLIT16 "lossy" claim and `conform` exiting 0 on non-conformant files: the fault
  reappearing inside the tool built to stop it.* A test now greps the function's own
  source so the cast cannot return unnoticed.

- **`SPLIT16` was still reachable through the Zarr and HDF5 backends.** D-2 deleted
  it in v1.1 as *destructive*, and `fita/ai/FITA_FORMAT_CARD.json` asserted that
  "the writer now raises on both write and read, so no conformant path can produce
  or consume it." **That claim was false.** `io.py` raised, but both alternative
  backends went on calling `encode_split16()` with no guard — measured: the Zarr
  backend accepted `pack='SPLIT16'` and wrote the file. Both now raise on write
  *and* on read; the read path previously rescaled by `BSCALE`/`BZERO` and returned
  numbers that cannot be recovered from a wrapped int16 store — confident nonsense.
  The format card's claim is now true.

### Added
- **`FITAPrecisionWarning`**, exported from `fita`. `FITALayer.from_array()` still
  casts to float32 — correct, since §6.1 mandates it, and it is the right place for
  a float64 science array to land — but it did so in silence. It now warns when the
  cast is lossy, using `np.can_cast` so a big-endian `'>f4'` straight off a FITS
  read never raises a spurious warning. Byte order is not precision.
- `tests/test_float32_enforcement.py` — 15 tests covering the ruling, all three
  defects, and the legitimate paths that must not pay for them.

### Unaffected
The 24-file conformance corpus is **clean and unchanged**: all 35 FLUX HDUs were
already `BITPIX=-32`, and the conform split stays 9 accepted / 15 rejected. The
published artifact and its DOI never carried this defect — it was latent in the
library, not in the data.

## [1.5] — 2026-08-07

Applies the principal's rulings A, B and C of 2026-08-07, and closes **D-14** and
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
