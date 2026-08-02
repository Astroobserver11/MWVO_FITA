# WORK ORDER — ATOP: due diligence on FITA v1.1

**From:** BTOP (`desktop-9mn6gd5`) · **To:** ATOP (`astro-workstation`, 100.67.25.66)
**Date:** 2026-08-02 · **Principal:** Ignacio A. Cisneros
**Posture:** adversarial audit. **Do not take this document's claims on trust — that is the point.**

---

## 0. How to read this

You are being asked to **try to break** work BTOP did on 2026-08-02, not to confirm it. The
MWVO pattern is mutual audit and it has already paid twice: ATOP's own conformance audit found
six defects that 110 green tests had missed, and BTOP's referee pass on ATOP's HE source audit
found a real defect in the limb-fraction scaling. Neither machine's output has been correct on
its own.

A finding of "BTOP overstated this" is a **success** of this exercise, not a failure of it.
§5 lists where BTOP believes it is weakest — start there.

Report in the structure of §7. Where you cannot verify a claim, say *unverified*; do not
promote it to *confirmed* because it looks reasonable.

---

## 1. Context — what FITA is, in four lines

FITA (`.fita`) is a multi-layer astrophysical image format: a legal FITS MEF carrying several
co-registered science images, each with calibration, bandpass, uncertainty, quality mask,
compositing metadata and a stereo-depth assignment. Its founding invariant is that **the flux
is the physics and nothing in the display path may touch it**. Repo: `C:\Users\astro\fita\`
(package `fita` = format kernel, `uranodyne` = science stack).

---

## 2. The sync obligation — do this first

The v1.1 standard was **RATIFIED 2026-08-02** on BTOP. ATOP's canonical
`FITA_FORMAT_STANDARD.md` has **not** been updated; the ratified text was Taildropped but not
installed.

1. Run `mwvo_bridge_recv.ps1`, verify the SHA256 manifest, and **replace ATOP's canonical
   `FITA_FORMAT_STANDARD.md`** with the ratified text. Set its status line to RATIFIED.
   **Do not retype or fork it** — sync the bytes over the Tailscale bridge.
1b. **Then apply `FITA_AMENDMENT__2026-08-02.md` §3.1–§3.8** and set the status line to
   **v1.2 (RATIFIED)**. That amendment carries the clause text for everything built after
   ratification — the `FITA_ADJ` schema (§8.3, new), the stereo geometry (§8.2), ObsCore v1.2
   (§9), and the conformance checker (§2.1). Until it is applied, those structures exist only
   in `spec.py`, which is the de-facto-spec condition D-7 just corrected elsewhere.
2. Confirm the ratification record `FITA_v1.1_RATIFICATION__2026-08-02.md` is present and that
   its D-1…D-7 rulings match what the standard's §12 now says.
3. If ATOP's canonical file has diverged since 2026-07-29 (i.e. someone edited it there), **stop
   and report the divergence before overwriting anything.** BTOP's copy is a transport copy;
   the ATOP original governs, and a silent overwrite would destroy the authority relationship.

---

## 3. What BTOP claims to have done

All on 2026-08-02, all under the ratified slate. Each line is a claim to be tested, not a fact
to be accepted.

| # | Claim |
|---|---|
| C1 | **D-2 SPLIT16 deleted** — writer refuses, reader raises. |
| C2 | **Alpha `BZERO=32768`** — new writes use the unsigned-16 convention; the wrapped-negative alpha is gone for new files. |
| C3 | **`BUNIT` valid** — `'alpha16'` omitted; `UNCERT_*` carries the parent flux unit. |
| C4 | **`FITA_VIS` required and emitted** — `visible` survives a round trip. |
| C5 | **`fita.validate()` / `fita conform`** — CORE/FULL levels, §5.4 bit-exact flux test, exit 0/1/2. |
| C6 | **D-4 ObsCore v1.2** — all mandatory columns, `TUCDn` on every column, `access_format='application/fits'`. |
| C7 | **R2 closed** — `io.write(provenance=...)` appends `FITA_META`; a written file validates **FITA-FULL**. |
| C8 | **D-3 `FITA_ADJ`** — adjustment stack serialised with **typed columns** (ruling Q1) and read back with parameters intact. |
| C9 | **D-6 stereo geometry** — `FITA_ZSC` + `FITA_ZRF` reference plane + `FITA_ZAN` angular measure (author rulings Q1/Q2, 2026-08-02) + `fita.stereo`. |
| C10 | **D-7** — guide notebook demoted to tutorial; its two false claims corrected in place. |
| C11 | **Install robustness** — wheels build clean, `fita` on PATH, `fita doctor` added. |
| C12 | **Suite 197 passed / 0 failed.** |
| C13 | **`FITAVER` bumped to 1.2** — Q1/Q2 added OPTIONAL structure after ratification; `FITA_AMENDMENT__2026-08-02.md` carries the clause text to fold into the canonical standard. |

---

## 4. Verification protocol

Work from a **clean checkout or the shipped wheels**, not from BTOP's editable install.

### 4.1 Reproduce the build
```bash
python -m pytest tests/ -q
python -m fita doctor --strict
```
Record the actual counts and exit codes. `doctor` exits 0/1/2 (ok/warnings/failure).

### 4.2 Independent conformance sweep over the 18 archived files
**ATOP holds the corpus; BTOP does not.** This is the part only you can do.
```bash
fita conform <each archived .fita> --quiet
```
Expected, per D-1 grandfathering: every pre-2026-08-02 file reports **NON-CONFORMANT** with
`FITA_VIS` missing, alpha `BZERO` absent, and `BUNIT='alpha16'` — and **no file crashes the
validator**. Report any file that behaves differently, and any that the validator *passes*
(a legacy file that passes means the validator is too lax).

### 4.3 Verify the invariant survives, on real data
For a representative archived file, confirm `FLUX_*` is **bit-identical** before and after a
read/write cycle through the new writer. Be NaN-aware: `np.array_equal` is False whenever a
blanked pixel is present, and real images are full of them — compare NaN masks and finite
pixels separately.

### 4.4 The HDF5 backend — still unverified anywhere
Standard §10.1 records `h5py` **missing on ATOP**, so the "round-trips through all three
backends" claim is confirmed for two of three. `h5py` **is** present on BTOP, and BTOP did
**not** close this gap. Install `h5py` and run a FITS ⇄ HDF5 equivalence check (flux
bit-identical; uncert, mask, WCS, `zdepth`, `opacity`, `blend_mode`, `name`, `visible`
preserved). Until someone does this, the three-backend claim must not be restated.

### 4.5 Attack the new HDUs
- Corrupt `FITA_ADJ`: unknown `ADJ_TYPE`, malformed JSON in `PARAMS`, missing column, empty
  table. The validator should reject; the reader should **raise, not silently drop** an
  adjustment.
- Very long `PARAMS` (e.g. a 10⁴-point response curve). BTOP auto-sizes the column; confirm
  nothing is truncated, and check the file stays readable by a third-party FITS reader.
- `FITA_META` with a missing mandatory column, and with `access_format='application/fits+alpha'`
  (must fail §3).
- `FITA_ZSC` present with no layer carrying `FITA_ZDP`; non-numeric `FITA_ZSC`.

### 4.6 Third-party reader check — the one BTOP cannot do
BTOP verified alpha encoding **only through astropy**. The original defect was invisible from
inside FITA precisely because the library's read path undid the wrap with a matching bug. So:
**open a newly written `.fita` in DS9, QFitsView and Aladin** and confirm the alpha plane reads
as `0..65535`, not `−32768..32767`. Also open a *legacy* file and confirm it looks wrong in the
way the standard predicts. This is the empirical test of the whole "opens natively in the
community's tools" premise, and no test suite can substitute for it.

---

## 5. Where BTOP believes it is weakest — audit these hardest

> Items 1 and 2 were **ruled by the author on 2026-08-02** after this order was first drafted.
> They are no longer open questions, but the *implementations* of those rulings are new and
> unaudited, and neither has yet been folded into the canonical standard text.

Stated plainly so the audit is aimed where it will pay.

1. **The `FITA_ADJ` column schema — RULED 2026-08-02, now needs folding into the standard.**
   D-3 ruled "implement the BINTABLE" but never specified columns; BTOP's first cut put every
   parameter in a JSON blob. The author ruled (**Q1**) that **the common parameters get real
   typed columns**, on the grounds that a reader which can open the file but cannot see
   `GAMMA = 2.2` has not really been given the data. Implemented: 18 columns
   (`ORDER, ADJ_TYPE, ENABLED, NAME, LAYER_ID` + typed `IN_BLACK…WAVE_CVAL`), with JSON
   `PARAMS` reserved for the genuinely variable-length fields (`control_points`,
   `response_curve`, `wavelengths`), and D-5 absence (NaN / empty) for inapplicable columns.
   **Audit task:** confirm the column set actually covers the six adjustment types without
   forcing anything back into JSON; check that a new adjustment type would not require a
   schema break; and confirm `spec.ADJ_TABLE_COLS` reaches the canonical standard's §4.1/§8
   rather than living only in code.

2. **The `FITA_ZSC` convention — RULED 2026-08-02, now needs folding into the standard.**
   The author ruled (**Q2**) that the geometry **carries an explicit reference plane**, and
   that a bare pixel count satisfies the real→model metric chain **only when a complete model
   is missing** — otherwise **an angular measure is required unless it can be deduced from
   context**. Implemented as three OPTIONAL PRIMARY keywords:
   `FITA_ZSC` (px, full ZDP range), `FITA_ZRF` (ZDP at zero parallax, default 0.0),
   `FITA_ZAN` (arcsec). `dx = ±(ZSC/2)·(ZDP − ZRF)`. `fita.stereo.angular_parallax()` performs
   the deduction from a layer WCS, and the validator raises a SHOULD when the angle is neither
   recorded nor deducible.
   **Audit task — this is the one BTOP is least able to check itself:** is "deducible from
   context" correctly scoped? BTOP treats a **celestial WCS** as the context, which yields a
   *sky* angle. A depth stimulus is arguably about the *viewing* geometry — screen pixel pitch
   and viewing distance, i.e. binocular disparity at the eye — which is **never** deducible
   from the file. If the discipline means visual disparity rather than sky angle, `FITA_ZAN`
   is measuring the wrong quantity and a second keyword is needed. **Please rule on this
   explicitly.**

3. **The ObsCore v1.2 mandatory column list was taken from the validator, not from the IVOA
   document.** BTOP did not consult the primary source in this session. **Check the 26 columns
   against the actual IVOA ObsCore DM v1.2 REC** and report any that are wrong, missing, or
   not in fact mandatory. The whole VO-registerability claim rests on this list being right.

4. **No `.fita` has actually been submitted to a VO service.** "VO-registerable" is inferred
   from column presence, not demonstrated. Treat the claim as untested.

5. **The dev (editable) install leaks generic top-level names** — `import pipeline`,
   `import plugins`, `import instrument_db` resolve into the project. The built **wheel is
   clean** (verified), so this is a dev-environment wart, but confirm it is not also true of
   ATOP's install, and check nothing on ATOP has come to depend on those leaked names.

6. **`AdjustmentStack.to_records()` was silently broken before today** — it emitted `a.params`,
   a dict no subclass ever writes to, so any round trip restored **default** adjustments.
   **Search ATOP for code that called `to_records()` or otherwise persisted adjustments**, and
   determine whether any stored display state was lost. BTOP could not check this.

7. **Package version is still `1.0.0` while `FITAVER` is `1.1`.** Deliberate (package ≠ format),
   but it will confuse a Zenodo DOI for the paper. Recommend a ruling.

8. **`fita doctor` and the validator were written by the same agent in the same session.** They
   share assumptions and may share blind spots. An independently written check of even one
   clause (say alpha `BZERO`) is worth more than either.

---

## 6. Out of scope

Do **not** implement the Foundry / `.exe` domain (`FITA_FOUNDRY_DESIGN.md`) — it is PARKed under
the closure ruling until the FITA paper ships. Do not open `FITA_OPLOG`; it is an unratified
proposal. Do not add paradigm or epistemic stamps to FITA (§10.3) — that is FITO's side of the
boundary, and the fence between established and proposed MWVO physics depends on it.

---

## 7. Return format

Write `ATOP_FITA_AUDIT_RETURN__2026-08-XX.md` and Taildrop it back with a SHA256 manifest.

```
## Verdict
  One line: PASSES / PASSES WITH DEFECTS / FAILS, and the single most important reason.

## Claim table
  C1..C12 -> CONFIRMED | REFUTED | UNVERIFIED, each with the evidence (command + actual output).
  "Looks right" is not evidence.

## Corpus sweep
  18 files x conformance level, plus anything anomalous.

## Defects found
  For each: what breaks, the minimal reproduction, severity (MUST/SHOULD),
  and whether it affects FLUX (science) or only display.

## Rulings needed from Ignacio
  Especially the FITA_ADJ schema and the FITA_ZSC convention (§5.1, §5.2) — these are
  unratified inventions currently living in shipped code.

## What you could not verify, and why
```

---

## 8. One standing rule

If any check shows **flux is not bit-exact** across a write/read cycle, stop everything and
report immediately. That is the format's central promise; every other finding in this document
is subordinate to it.

---

*Normative reference: `FITA_FORMAT_STANDARD.md` v1.1 RATIFIED. Where this work order and the
standard disagree, the standard governs.*
