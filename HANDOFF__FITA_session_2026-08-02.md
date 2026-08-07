# HANDOFF — FITA / MWVO session of 2026-08-02

**Purpose:** let a fresh thread resume without re-deriving anything. Read this, then the
normative standard. Everything below is verified state, not plan.

**Machine:** you are on **BTOP** (`desktop-9mn6gd5`). **ATOP** is `astro-workstation`
(100.67.25.66). Confusing the two has already cost a delivery — check before addressing anything.

---

## 1. Where things actually stand

| | |
|---|---|
| **Repo** | https://github.com/Astroobserver11/MWVO_FITA — public |
| **Sibling** | https://github.com/Astroobserver11/uranodyne — public |
| **Concept DOI** | `10.5281/zenodo.21763301` (always newest) |
| **Format version** | `FITAVER = 1.4` · package `1.4.0` |
| **Tests** | 221 collected kernel-only · 269 with URANODYNE — see README for the full precondition table. CI runs the kernel-only row and now asserts a collected floor |
| **Corpus** | 20 labelled files, byte-reproducible within the toolchain pinned in `corpus/TOOLCHAIN.lock` |
| **Local paths** | `C:\Users\astro\fita` (kernel) · `.../fita/uranodyne` (nested repo) |

**Releases:** v1.2.0 (DOI'd, contains a false claim), v1.2.1 (erratum), v1.3.0 (erratum
completed). v1.2.0's DOI is permanent — the erratum is how a reader learns.

---

## 2. What FITA is, in four lines

A FITS *convention* — not a new container — for multi-layer astronomical images where the
display channel cannot alter the science. `FLUX_*` holds calibrated flux; `ALPHA_*` holds
display transparency derived from a selected range. Re-selecting the display changes alpha and
**nothing else**, verified bit-for-bit and NaN-aware. Every `.fita` is a valid FITS MEF.

**URANODYNE** is the observing engine that produces those files. *FITA is the noun; UranoDyne is
the verb.* It imports `fita`; the dependency never runs the other way.

---

## 3. The one thing to internalise

This project's characteristic failure is **silent loss that looks like success**. It has now
happened nine times, and the last two are inside the instruments built to catch the first seven:

| # | Failure | How it hid |
|---|---|---|
| 1 | `SPLIT16` destroyed flux | encoder was sound in isolation; the *file* was not |
| 2 | Alpha written signed, no `BZERO` | the library's reader undid the wrap with a matching bug |
| 3 | `visible` lost every round trip | nothing tested it |
| 4 | `to_records()` restored *default* adjustments | it returned objects, so it "worked" |
| 5 | Git treated `*.fita` as text | FITS headers are ASCII; CRLF would shift every 2880-byte block |
| 6 | Checksum certified pre-corruption bytes | in-place table edit didn't update the cached datasum |
| 7 | **ObsCore v1.2 does not exist** | inherited from an internal doc, never checked against the source |
| 8 | **`fita conform` exited 0 on a NON-CONFORMANT file** | it printed every defect correctly and returned success; only `--strict` propagated the verdict. *In the validator* |
| 9 | **Module-level `importorskip` hides uncollected tests** | pytest reports ONE skip per module however many tests it holds, so 48 missing tests showed as one skip line. The passed count moves; nothing says the denominator moved with it. *In the test harness* |
| 10 | **The reader discarded every negative `FITA_ZDP`** | it still implemented the `-1.0` sentinel **D-5 retired** — and for *any* negative value. Dormant while §8.2 forced `[0,1]`; **v1.4 made physical depths legal and woke it.** A five-channel velocity cube round-tripped to a *different stereogram* — two channels gone, survivors renormalised — while `max separation` printed the same number throughout |

**#9 is the worst-placed of all.** The test suite is the instrument this project uses to detect
silent loss, and it had the defect it exists to detect. It is also why "CI green on 3 OS × 3
Python" was not evidence about coverage: the matrix does not install URANODYNE, so every cell was
silently running the kernel-only subset. Closed by asserting a **collected-count floor** in CI —
one step that makes the denominator visible.

**Corollary to the corollary.** #7 and #9 share a shape worth naming: *a number that fits is not a
cause*. `241 − 48 = 193` reproduced the observed count exactly and was still the wrong
explanation — the real one needed five optional dependencies, not one. See RULE E, §5.

**Corollary:** a green test proves the function ran, not that the file is right. Prefer tests
that compare *values* after a round trip, are NaN-aware, and assert what a *third-party reader*
would see.

---

## 4. Governance — how decisions get made here

Ratifiable = **not forced**. Forced by measurement, by an external standard, or by the flux/alpha
invariant → it's correctness, not a decision. The standard's tags encode this: `[MEASURED]` and
`[CORRECTION]` are not votes; `[NEW]` requires a ruling.

**Only Ignacio rules.** Agents prepare decisions — question stated so "no" is possible, options
enumerated, recommendation *with reasoning*, consequence. That is what makes a slate rulable in
one sitting.

**Danger:** structure that lives only in code *is* a de-facto specification. This happened twice
(the guide notebook, then `spec.py`) and both were corrected. If you add format structure,
increment `FITAVER` **in the same change** (§13, `major.minor` — no patch level) and write the
clause.

---

## 5. Open items, in priority order

0. **CLOSED — N-1 and `FITA_ZAN`.** Ruled 2026-08-02
   (`RULING__stereogram_scale_and_N-1__2026-08-02.md`): the stereogram scale is a percentage of the
   field diameter, stated in a unit practical to the subject. Implemented as **v1.4** — `FITA_FDI`
   / `FITA_FDU` / `FITA_ZDU` added, `FITA_ZSC` redefined from pixels, `FITA_ZAN` retired by
   dissolution. The eight archived files become conformant by adding **one keyword**; that header
   edit is still owed and is ATOP's to make (they are not on BTOP).
1. **RULE E — needs Ignacio's ruling.** ATOP drafts (escalation §3): a finding **MUST NOT** be
   closed as *environmental* until the difference is named and pinned, re-run under the declared
   environment, both results published with preconditions, and the difference added to the shipped
   environment declaration. Raised because N-5 was closed on arithmetic that fit the number
   without being the cause.
2. **PyPI distribution name.** `fita`, `fitb`, `fitr`, `fito` are all TAKEN by unrelated projects;
   the FIT(a–z) namespace cannot be controlled and bulk-registering would be squatting. Author
   accepted the fix: prefix with **`mwvo-`** (`mwvo`, `mwvo-fita`, `mwvo-fitr`, `mwvo-fito`,
   `uranodyne` all free). Not yet claimed. **There is no working `pip install` until this is done.**
3. **`fitsverify`** — never run. HEASARC's C tool; `fitscheck` is not a substitute. Gate
   *announcing* on it, not publishing.
4. **Third-party readers** — alpha has only ever been verified through astropy, the exact path
   where defect #2 hid. DS9 / QFitsView / Aladin unverified.
5. **ATOP sync** — code dispatch sent 2026-08-02 (`outbox_2026-08-02_ATOP_CODE`). Awaiting the
   audit return on C1–C12.
6. **FITS convention registration** — not started. Still the highest-leverage adoption step.
7. **The paper.** Track: ratify ✓ validator ✓ corpus ✓ DOI ✓ → registration → paper.
8. **`DISTANPC` — undeclared structure in a UranoDyne writer.** `uranodyne/pipeline/edenhofer.py`
   normalises distance into `zdepth` **and** stashes the parsec value in a private 8-char keyword
   `DISTANPC`, which `extra_header` writes straight into every `FLUX_*` header. It is nowhere in
   the standard. v1.4 makes it redundant — `FITA_ZDP` in parsecs plus `FITA_ZDU = 'pc'` says the
   same thing normatively. Third instance of "structure that lives only in code is a de-facto
   specification" (§4). ATOP is looking at this.
9. **PACI / `FITA_ZCAT` boundary (D-8)** — anchor class is epistemic status, which §10.3 assigns
   to FITO. Rule once for both.

---

## 6. Accepted but not built

- **Phased Stereogram Profile** (standard §8.4) — proposed in the ATOP dispatch, author accepted
  it as a **FITA profile, not a new format**. Boxcar traversal keywords, dual z-LUT × XY-LUT
  (which is the existing `LUM`+`COLOR` pair), depth-within-window using the v1.2 stereo formula
  unchanged, and **`FITA_ZCAT`** — catalogued entries with expected z, which turns a fly-through
  into an audit. That last is the piece to build first.
- **Transfusion Theater** — the FITA ↔ **ImageJ2** round-trip apparatus, via a **PyImageJ bridge**
  (not a Java re-implementation, which would fork the spec). PyImageJ shares NumPy arrays with
  `opencv-python`, so no second reader is needed. The corpus `roundtrip/` tier and its
  `survival_spec` exist specifically to score it. **PARKed until the paper ships.**
- **The Foundry `.exe` domain** (`FITA_FOUNDRY_DESIGN.md`) — C1/C2/C2b/C7 done; the Ring-B bus and
  `fitad`/MCP surfaces PARKed.

---

## 7. Traps that will bite you again

- **The bridge fails silently.** Taildrop lands in `Downloads\`, not the bridge inbox, and
  nothing detects a missing return. **Never let a publication depend on a delivery having
  arrived.** Confirm out of band.
- **Zenodo:** does **not** backfill — only archives releases created *after* the webhook exists;
  fix by deleting and recreating the *release* (the tag can stay). `license` is a **controlled
  vocabulary** (`mit`, not `MIT`) and a bad id fails validation *silently* while the webhook still
  returns 202. Its search index lags minutes — absence is not evidence.
- **astropy** stamps a wall-clock time into `CHECKSUM` comments; use
  `add_checksum(when=...)` for reproducible output. It also regenerates `BZERO` from a uint16
  dtype, so header-only fixtures heal themselves.
- **Windows console** is cp1252 — non-ASCII in emitted strings raises `UnicodeEncodeError`. Use
  ASCII in clause labels; `_safe_console()` guards the CLI.
- **Namespace shadowing:** a directory named `fita` in the cwd becomes a namespace package that
  beats an editable install. `fita doctor` detects it. Fixed here with
  `--config-settings editable_mode=compat`.

---

## 8. Read next, in order

1. `FITA_FORMAT_STANDARD.RATIFIED-v1.2.md` — **normative, governs everything**
2. `ERRATUM__ObsCore_version__2026-08-02.md` — the ObsCore failure, in full
3. `corpus/README.md` — how an implementation is scored
4. `ATOP_FITA_DUE_DILIGENCE.md` §5 — where BTOP believes it is weakest
5. `FITA_FOUNDRY_DESIGN.md` — parked, but the architecture

The canonical original lives on **ATOP**. Where any copy and it disagree, **it governs**.
