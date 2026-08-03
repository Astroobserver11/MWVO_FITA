# ERRATUM — FITA v1.2.0 claims conformance to an ObsCore version that does not exist

**Raised by:** ATOP (`astro-workstation`), audit return, 2026-08-02
**Confirmed by:** BTOP, independently, against two IVOA sources, 2026-08-02
**Affects:** FITA v1.2.0 — repository, ratified standard, reference implementation, conformance
corpus, and Zenodo record `10.5281/zenodo.21763344`
**Resolved in:** v1.2.1 (version claim) and **v1.3** (the missing `pol_xel` column)

**Version note.** v1.2.1 briefly set `FITAVER = "1.2.1"`, which is malformed: §13 defines
`FITAVER` as `major.minor`. ATOP was right that the label correction alone required no format
increment. But adding `pol_xel` *is* a change to optional structure, which §13 does require an
increment for — so the format is **1.3**, not 1.2 and not 1.2.1. The package is 1.3.0.

---

## 1. The error

FITA v1.2.0 states, in the normative standard (§9), in the amendment (§3.6), in the reference
implementation, in the README, in the citation metadata, and **inside every `FITA_META` HDU of the
published conformance corpus**, that its provenance table conforms to:

> IVOA ObsCore DM **v1.2**

**There is no ObsCore v1.2.** The Observation Data Model Core Components specification has one
Recommendation: **v1.1, dated 2017-05-09**, with three accepted errata (2023-11-10).

Worse than the label: the standard explicitly authorised the claim's unqualified use —

> *"The wording 'ObsCore DM v1.2' is now accurate and may be used without qualification."*

That sentence is withdrawn in full.

## 2. Verification

Confirmed independently, twice, before acting:

Six axes across two machines, deliberately not all the same kind of evidence:

| # | Axis | By | Result |
|---|---|---|---|
| 1 | `ivoa.net/documents/ObsCore/` | BTOP + ATOP | v1.1, "IVOA Recommendation 09 May 2017". No other version. |
| 2 | IVOA full document index, all statuses | BTOP + ATOP | `ObsCore → 1.1 → Recommendation (20170509)`. **No v1.2 as REC, PR or WD.** |
| 3 | **ALMA live TAP capabilities** | ATOP | Declares `ivo://ivoa.net/std/ObsCore#core-1.1`. |
| 4 | **IVOA errata wiki** | ATOP | No 1.2 in preparation; erratum 4 is a citation pin; **none alter the mandatory set**. |

Axis 3 settles it practically: a working archive in 2026 advertises `#core-1.1`, and there is no
`#core-1.2` standardID available to declare. Axis 4 was ATOP checking the risk to *its own* claim —
had an erratum changed the mandatory set, its column list (read from the 2017 PDF) would be stale.

**Residual uncertainty, stated rather than smoothed over:** the errata index does not summarise
errata 1 and 2, so their non-effect on the mandatory columns is established from the change
summaries, not from their full text. That is a caveat on the *column list*, not on the version
finding, which axes 1–3 settle independently.

ATOP asked that the claim be checked a second way before any retraction was issued, on the
grounds that a retraction which is itself wrong is worse than the original error. That was the
right instinct and it was followed.

## 3. How it happened

The claim was **inherited, then amplified, and never checked against the primary source.**

1. It originates in the v1.1 DRAFT standard's own §12, decision **D-4**, which recommended
   ObsCore v1.2 *"since FITR is the newer draft and ObsCore 1.2 is current."* That premise was
   false when written.
2. The ratification adopted D-4's recommendation verbatim.
3. The implementation, the amendment, the v1.2 standard, the README, the release notes, the
   citation record and the corpus all propagated it.
4. It reached a **permanent, citable DOI** the same day.

**The failure was foreseen and not acted on.** `ATOP_FITA_DUE_DILIGENCE.md` §5.3 — written by
BTOP, before publication — says:

> *"The ObsCore v1.2 mandatory column list was taken from the validator, not from the IVOA
> document. BTOP did not consult the primary source in this session. **Check the columns against
> the actual IVOA ObsCore DM REC** and report any that are wrong, missing, or not in fact
> mandatory. The whole VO-registerability claim rests on this list being right."*

That warning was published alongside the artifact it should have blocked. Flagging a risk is not
the same as clearing it, and a self-identified weakness that ships unresolved is worse than one
nobody noticed — the reader is entitled to assume a documented concern was closed.

Contributing cause: the ATOP audit that would have caught this **arrived 14 hours before
publication and never reached BTOP.** The bridge delivered it to `Downloads\` rather than the
bridge inbox, and the failure was silent. See §6.

## 4. What is corrected (v1.2.1, completed in v1.3)

Every live occurrence of "ObsCore DM v1.2" becomes **"ObsCore DM v1.1"**, and the
completeness claim is downgraded to what is actually verified.

**Historical documents are NOT edited.** The v1.1 DRAFT transport copies, the ratification record,
and the superseded v1.1 ratified standard record what was believed at the time. Editing them would
falsify the audit trail. They contain the error as a matter of record, and this erratum is how a
reader learns that.

## 5. Completeness — RESOLVED, and it found a second defect

The first draft of this erratum left completeness open, because BTOP could not extract Table 1
from the REC PDF and refused to assert a count it had not read. **That hedge was load-bearing.**

ATOP read Table 1 and asked BTOP to check three specific columns. The result:

| Column | In the written table | Enforced as mandatory |
|---|---|---|
| `t_resolution` | present | **was NOT enforced** |
| `pol_states` | present | enforced |
| `pol_xel` | **WAS MISSING ENTIRELY** | was not enforced |

So the corrected wording *would itself have been false* had it claimed completeness — exactly as
ATOP warned: *"If they're missing, the wording must not be corrected until they're added, or the
correction is false too."*

**Fixed in v1.3:** `pol_xel` added to `FITA_META`; the validator now enforces the **30** mandatory
columns of ObsCore v1.1 as read from Table 1 by ATOP. A written file now carries 33 columns, all
30 mandatory ones present, each with a `TUCDn`, and validates FITA-FULL.

**Attribution of the remaining trust:** BTOP has still not read Table 1 itself. The 30-column list
is ATOP's reading, corroborated by BTOP only in that the count matches and every name appears in
BTOP's own token extraction from the REC PDF. Stated so no one mistakes corroboration for
independent verification.

## 6. The delivery failure is a finding in its own right

The audit existed, was correct, was timely — and did not arrive. Two defects:

1. **Taildrop lands in `Downloads\`, not the bridge inbox.** `mwvo_bridge_recv.ps1` drains the
   inbox, so a delivered file is invisible to the receiving procedure.
2. **Nothing detects a missing return.** BTOP proceeded to publication with no signal that an
   audit was outstanding.

A courier route that can fail silently is not a courier route. Until fixed, **no publication
should depend on a bridge delivery having arrived** — confirm receipt explicitly, out of band.

## 7. Also outstanding from the ATOP return

Recorded here so they are not lost with the mail:

- **N-1 — `FITA_ZDP` carries parsecs.** Eight archived ATOP stereo files hold values of 624 /
  1248 / 2496 in `FITA_ZDP`, while standard §8.2 defines the domain as `[0,1]` and the new
  parallax formula assumes it. Either those files are non-conformant, or the domain needs a
  documented physical-units variant. **Unresolved; needs a ruling.**
- **ATOP's canonical standard was already updated** at 04:33 on 2026-08-02. Statements in the
  amendment and this repository that it "still reads v1.1 DRAFT" were stale, not false at the
  time of writing.
- **h5py is installed on ATOP and FITS ⇄ HDF5 equivalence was verified there.** The README's
  "HDF5 round-trip untested" is out of date; it awaits the audit return's evidence to restate.
- **No code has ever been sent to ATOP.** Documents only, so C1–C12 remain unverifiable there.
  The wheel and corpus should go in the next dispatch.

## 8. Standing rule this establishes

> **A conformance claim naming an external standard MUST cite the primary document, with its
> version and date, verified at the time of writing.** Inheriting the claim from an internal
> document — including one of ours — does not discharge that obligation.

FITA's own §11.5 already says the equivalent about tests: a suite that tests the library's
functions and never the file's conformance proves nothing about conformance. The same applies to
standards claims. This project has now made that mistake in both directions.

---

*Raised by ATOP; confirmed by BTOP against the primary source. The v1.2.1 release carries the
correction.*
