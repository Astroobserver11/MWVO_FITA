> # ⚠️ MOVED — this is a pointer, not the standard
>
> **The normative FITA Format Standard is now [`FITA_FORMAT_STANDARD.md`](FITA_FORMAT_STANDARD.md).**
>
> This path is retained only so that existing citations keep resolving. It contains no normative
> text. Do not edit it, do not read requirements from it, and do not cite it in new work.

## Why this file exists

This path was the canonical standard from 2026-08-02. Its name was knowingly frozen at `v1.2`
because published records already cited it — the Zenodo deposit, `CITATION.cff`, the package
metadata and the README all pointed here. The content, meanwhile, advanced to v1.3, then v1.4, and
the implementation went on to v1.5.

The result was a file whose **name contradicted its own contents for three successive versions**.
Anyone reading the directory listing saw `v1.2`; anyone opening the file read `v1.4`; anyone
running the code got `FITAVER = 1.5`. That is the documentation half of the de-facto-spec failure
recorded in §13 — and it was *measured*, on 2026-10-28, as one of six live and mutually
inconsistent version identities for a single format.

## The rule that replaces it

**A version belongs inside a document, never in its name.** A name cannot be corrected without
breaking every citation that points at it, so a name carrying a version number is guaranteed to go
stale. The standard now has the version-neutral name `FITA_FORMAT_STANDARD.md`, which is what its
own 2026-08-02 header had already said it was "destined to" be. `§13`'s table inside that document
is the authority on which version it describes.

## Where the versions are now

| Number | Source of truth |
|---|---|
| `FITAVER` (the **format**) | `FITA_FORMAT_STANDARD.md` §13, and `fita.spec.FITA_VERSION` |
| package version (the **software**) | `pyproject.toml`, and `pip show mwvo-fita` |

These are different numbers and are allowed to differ; see `FITA_FORMAT_STANDARD.md` §13.1.
