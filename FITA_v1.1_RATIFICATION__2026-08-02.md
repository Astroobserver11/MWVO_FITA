# RATIFICATION — FITA Format Standard v1.1
## Author's ruling on the §12 open decisions · 2026-08-02

**RUNG: memory (ruling).** Per concordance C-10. This is an author decision log, **not** a
restatement of the standard. It records the rulings that convert `FITA_FORMAT_STANDARD.md`
from **v1.1 DRAFT** to **v1.1 (RATIFIED)**. The rulings are to be *applied to the canonical
original on ATOP* (`C:\Users\astro\fita\FITA_FORMAT_STANDARD.md`) — **not** retyped into a new
copy — over the Tailscale bridge. Where this record and the applied standard ever differ, the
standard governs; this record's job is done once the standard reads "RATIFIED".

**Ruled by:** I. A. Cisneros (validating author), on BTOP, 2026-08-02.
**Against:** the byte-exact 2026-07-29 transport copy of v1.1 DRAFT
(`FITA_FORMAT_STANDARD_v1.1_DRAFT.transport-2026-07-29.md`), confirmed current — no 2026-08-01
ruling touched FITA-spec internals.
**Slate chosen:** FULL STANDARD SLATE (the larger build; the standard's own §12 recommendations
adopted verbatim, including the two implementation-heavy calls).

---

## 1. The rulings (§12 D-1 … D-7)

| # | Decision | **RULING** | Consequence |
|---|---|---|---|
| **D-1** | Version of corrected format | **v1.1, grandfather the 18 existing files.** A reader rule documents that `1.0` files carry wrapped alpha and invalid `BUNIT`; alpha is regenerable from flux. | No rewrite of the large files (437 MB ×1, 415 MB ×2). |
| **D-2** | SPLIT16 repair or delete | **DELETE.** A conformant writer MUST NOT emit `FITAPACK='SPLIT16'`; a reader encountering it MUST raise. | Remove the SPLIT16 write path; flux is FLOAT32-only, bit-exact. |
| **D-3** | `FITA_ADJ` implement or remove | **IMPLEMENT** the `FITA_ADJ` BINTABLE — serialise the adjustment-layer stack. | Non-destructive display state becomes persistent; **unblocks FITR §8**, which depends on it. |
| **D-4** | ObsCore version + completeness | **v1.2, FULL conformance.** Add the missing mandatory columns (`obs_publisher_did`, `s_region`, `access_estsize`, `o_ucd`, `s_xel1`, `s_xel2`, `t_xel`, `em_xel`) and write per-column UCDs as `TUCDn`. | `.fita` becomes VO-registerable; the LVM/Alfredo provenance differentiator is real, not claimed. |
| **D-5** | Absence convention | **Omission everywhere; table columns use `TNULL`.** Retire the `ZDEPTH = -1.0` sentinel. | One absence convention across headers and tables. |
| **D-6** | `FITA_ZSC` parallax-scale keyword | **YES, OPTIONAL**, written by the renderer (not the compositor), recording the ZDP→pixel-offset map actually used. | Stereo separation stays measured and traceable. |
| **D-7** | Guide notebook status | **DEMOTE** `FITA_Format_Guide.ipynb` to "tutorial — see FITA_FORMAT_STANDARD.md for normative text"; correct the two false claims (the "~1.5×10⁻⁵" error figure and the ObsCore-compliance claim) in place. | Removes the de-facto second spec. |

## 2. The four `[CORRECTION]`s — adopted as normative (not votes)

These were already normative in the DRAFT; ratification confirms them and makes them the
validator's mandatory checks:

1. **Alpha encoding** — `ALPHA_*` MUST use `BITPIX=16` with `BZERO=32768`, `BSCALE=1` (unsigned-16
   convention). Fixes the wrapped-negative alpha in all 18 files as read by third-party viewers.
2. **Units** — `BUNIT` MUST be a valid FITS unit string. Retire `'alpha16'` (omit or `''`) and
   `'same as FLUX'` (use the parent `FLUX_*` unit string).
3. **`FITA_VIS`** — layer visibility MUST be written to the `FLUX_*` header (new required keyword).
   Stops the silent loss of `visible` on every round trip in every backend.
4. **Registry authority** — the `FLUX_*` header is normative; `FITA_LAYERS` is a non-authoritative
   index. `FITAVER` MUST increment on any change to required or optional structure.

Also confirmed normative: **MIME type is `application/fits`** (not the unregistered
`application/fits+alpha`) until IANA registration is actually granted.

## 3. Status change

`FITA_FORMAT_STANDARD.md`: **v1.1 DRAFT → v1.1 (RATIFIED 2026-08-02).** The §12 "Open decisions —
for Ignacio only" section is now closed; it becomes a record of *how* each was ruled. §2.1's
`fita.validate()` and §5.4's per-packing-mode bit-exact flux test remain the conformance gate.

**This closes the standing open item** "FITA is in production while unspecified" — the disposition
that the 2026-08-01 D-3 CLOSURE ruling required for every open thread. FITA moves from *unspecified*
to *ratified-and-being-implemented*, on the critical path to the terminal deliverable (the FITA
paper as the next SHIP).

## 4. Implementation backlog created by this ruling

The full slate creates a defined punch-list. This is the input to Step 2 (the validator + tool).
Ordered so the validator can be written against a stable spec:

1. **Writer corrections** (the 4 above): alpha `BZERO`, `BUNIT`, `FITA_VIS`, `FITAVER`-increment
   discipline + header-normative writes.
2. **D-2**: remove the SPLIT16 write path; make `read()` raise on `SPLIT16`.
3. **D-5**: omission + `TNULL` absence convention.
4. **D-3**: implement `FITA_ADJ` BINTABLE serialise/deserialise (round-trips the `AdjustmentStack`).
5. **D-4**: full ObsCore v1.2 `FITA_META` — add mandatory columns, write `TUCDn`, wire it reachable
   from `io.write()`.
6. **D-6**: `FITA_ZSC` OPTIONAL renderer keyword.
7. **`fita.validate(path) -> ConformanceReport`** — the validator: CORE (every MUST §§3–7) and FULL
   (＋SHOULDs ＋conformant `FITA_META`), plus the §5.4 bit-exact flux test. **This is the central
   tool and the paper's released software (satisfies promotion-ladder C-11).**
8. **D-7**: demote the guide notebook, fix its two claims.
9. **Install robustness** (parallel): `fita` as a real console script that runs from any directory
   + `fita doctor`. (The IrenBLink lesson; premise of the ".exe domain".)

## 5. Sync obligation

Apply §1–§2 to the **canonical** `FITA_FORMAT_STANDARD.md` on ATOP and edit its status line to
"v1.1 (RATIFIED 2026-08-02)". Do **not** create a second canonical. Pull/return over the Tailscale
bridge (live, 4.2 MB/s per the 2026-08-01 D-1 directive); `rclone` remains preferred for repeated
folder sync once authed (P-1).

---

*Ratification record authored on BTOP. The standard it ratifies is developed at
`C:\Users\astro\fita`. This record is superseded by the standard the moment the standard reads
"RATIFIED".*
