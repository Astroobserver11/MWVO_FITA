# Changelog

Format versions follow `FITAVER`; the package version tracks the format it
implements. Per §13 of the standard, **any change to required or optional
structure requires a version increment** — a rule this project has broken
twice and now enforces in code.

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
