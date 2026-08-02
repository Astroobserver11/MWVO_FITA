# Contributing to FITA

## The one rule

**The flux is the physics.** No contribution may cause `FLUX_*` to change as a
side effect of anything in the display path. If a change touches the writer,
it must keep `tests/` green — including the NaN-aware bit-exactness test — or
it is wrong regardless of what else it improves.

## Before opening a pull request

```bash
python -m pytest tests/ -q
python -m fita doctor --strict          # run from OUTSIDE the repo directory
python corpus/build_corpus.py --verify
```

The middle one matters: this project has twice shipped an installation that
worked only when the working directory happened to be the repo root.

## Changing the format

The specification governs the code, not the other way round. If a change adds
or alters **required or optional structure**:

1. Propose the clause text as an amendment to the standard.
2. Increment `FITAVER` **in the same change** (§13). This rule exists because
   it has been broken twice.
3. Add a corpus fixture — positive *and* negative — so the new clause is
   scoreable. `corpus/build_corpus.py` refuses to write a fixture whose
   validator verdict disagrees with its own label.

Structure that lives only in `spec.py` is a de-facto specification, which is
what a standard exists to prevent.

## Tests that are worth writing

A test that pins current behaviour is not automatically useful. This project
once had a test asserting `BUNIT == 'alpha16'` — the exact value the standard
retires — so it actively defended the defect. Prefer tests that could fail for
the right reason:

- compare parameter **values** after a round trip, not merely that an object
  came back;
- be NaN-aware — `np.array_equal` is False whenever a NaN is present, and real
  images are full of blanked pixels;
- for a format change, assert what a *third-party reader* would see.

## Binary files

`.gitattributes` marks `*.fita` / `*.fits` as binary. Do not remove it: FITS
headers are ASCII, so git's heuristic classifies these as text and line-ending
conversion silently shifts every 2880-byte block boundary.

## Reporting a conformance bug

Include the output of `fita conform <file>` and, if you can, a minimal file
that reproduces it. A file that the validator *passes* but a third-party reader
mishandles is the most valuable report you can file — that class of defect has
been the hardest to find here.
