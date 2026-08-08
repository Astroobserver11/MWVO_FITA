# ERRATUM — twenty-nine dates in this repository were four days early

**Raised by:** ATOP, gate return `ATOP-0001`, 2026-08-08
**Confirmed by:** BTOP against git commit timestamps, same day
**Affects:** 13 files, 29 occurrences, including three ruling records and the v1.5 CHANGELOG entry
**Corrected in:** this commit. Nothing was tagged or released while the wrong dates stood.

---

## 1. The error

Work performed and committed on **2026-08-07** was dated **2026-08-03** throughout — in document
headers, in three addendum *filenames*, in source comments, and in `CHANGELOG.md`.

The most serious instance is a claim about the principal:

> *"Applies the principal's rulings A, B and C of 2026-08-03"*

That is a statement about **when a ruling was made**, wrong by four days, in a project whose entire
discipline is provenance.

## 2. How it was found

Not by BTOP. ATOP noticed that a BTOP dispatch dated `2026-08-03` answered, and quoted verbatim, a
document ATOP had written on **2026-08-07 11:39** — *the minute matched and the date did not*. It
arrived twenty-five minutes after the document it answered.

ATOP proposed `w32tm /resync`. **That diagnosis was wrong and the finding was right**, which is
worth separating: it inferred a machine fault from an artifact fault. The remedy would have changed
nothing.

## 3. Verification

▣ BTOP system clock at the time of correction: `Sat Aug 8 13:43 EDT 2026` — **correct**.

▣ `git log --since=2026-08-03 --until=2026-08-07` returns **no commits** on 08-03, 08-04, 08-05 or
08-06. No work happened on the claimed date at all. Every commit touching the affected files is
timestamped **2026-08-07**.

So the clock was never wrong. **The dates were typed wrong**, by the agent, into artifacts — which
is a harder failure to detect than a skewed clock, because no tool checks it and every file agrees
with every other file.

## 4. What changed

All 29 occurrences `2026-08-03` → `2026-08-07`. The three addenda are renamed to match; no document
cross-referenced the old filenames, so no links broke.

**Historical records were not edited**, per the standing practice: the v1.1 DRAFT transports, the
ratification record and the superseded standards are untouched. The files corrected here are not
records of what was once believed — they are records of *when something happened*, and a wrong one
is not preserved by leaving it.

## 5. Why this is recorded rather than quietly fixed

A silent date correction is indistinguishable from a date being right all along. This project has
an erratum for a version number that did not exist; a misdated ruling is the same class of defect
and gets the same treatment.

## 6. The rule this establishes

> **A date written into an artifact is a claim, and claims are checked against a source.** For
> "when did this happen", the source is the commit timestamp, not the agent's belief about today.

Nothing here was published while the wrong dates stood — no tag, no release, no DOI. The gate held,
which is the only reason this is an erratum about a repository and not about a citable record.

---

*Detected by ATOP through a cross-machine timing inconsistency; confirmed by BTOP against git.*
