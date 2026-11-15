"""
Version concordance — one format version, one package version, stated identically
everywhere they are stated.

Why this file exists. On 2026-10-28 this project was measured to be carrying **six
live and mutually inconsistent version identities** for a single format: a Zenodo
DOI at 1.2.0, a standard whose *filename* said v1.2 while its *contents* said v1.4,
a newest tag of v1.3.0, code and CHANGELOG at 1.5, and a couriered archive labelled
1.5.0 that was actually a pre-rename tree. Nobody had lied; every number had been
correct when written, and nothing checked that they still agreed with each other.

Two numbers exist and they are different things (standard §13.1):

    FITAVER          the FORMAT     major.minor        fita.spec.FITA_VERSION
    package version  the SOFTWARE   major.minor.patch  pyproject.toml

They are allowed to differ — a bug fix advances the package alone, which is exactly
what 1.5.1 and 1.5.2 did. What they are not allowed to do is disagree with
themselves across files.
"""
import json
import re
from pathlib import Path

import pytest

# NOT tomllib: it is Python 3.11+, and this project's matrix tests 3.9 (see
# requires-python). On 3.9 the import raised at module scope, so all of this
# file's tests silently FAILED TO COLLECT -- the suite still reported green and
# only CI's collected-count floor caught it. That floor exists for exactly this,
# and it earned its keep here. A regex keeps the file importable everywhere, and
# the one line it reads is asserted to be unique so it cannot match the wrong
# `version =` if the file grows another.
_VERSION_RE = re.compile(r'^version\s*=\s*"([^"]+)"', re.M)

ROOT = Path(__file__).resolve().parent.parent
STANDARD = ROOT / "FITA_FORMAT_STANDARD.md"


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def fmt_version() -> str:
    """FITAVER, from the implementation — the reference every document is held to."""
    from fita.spec import FITA_VERSION
    return FITA_VERSION


@pytest.fixture(scope="module")
def pkg_version() -> str:
    hits = _VERSION_RE.findall(_read(ROOT / "pyproject.toml"))
    assert len(hits) == 1, (
        f"expected exactly one top-level `version = \"...\"` in pyproject.toml, "
        f"found {len(hits)}: {hits}"
    )
    return hits[0]


# ── the two numbers are well formed, and related ─────────────────────────────

def test_fitaver_is_major_minor_only(fmt_version):
    """§13: FITAVER is 'major.minor'. A patch component is malformed.

    This is not pedantry: the ruling on the ObsCore label fix was initially
    `FITAVER = '1.2.1'`, which a conformant reader is entitled to reject.
    """
    assert re.fullmatch(r"\d+\.\d+", fmt_version), (
        f"FITA_VERSION={fmt_version!r} must be major.minor with no patch part"
    )


def test_package_version_is_pep440_triple(pkg_version):
    assert re.fullmatch(r"\d+\.\d+\.\d+", pkg_version), pkg_version


def test_package_version_implements_the_stated_format(fmt_version, pkg_version):
    """The package must declare which format it implements, by construction.

    Allowed: package 1.5.2 implementing format 1.5. Not allowed: package 1.4.x
    while the code's FITA_VERSION says 1.5 — which is precisely the .zenodo.json
    state found on 2026-11-14.
    """
    assert pkg_version.startswith(fmt_version + "."), (
        f"package {pkg_version} does not implement format {fmt_version}; "
        f"either the package version or FITA_VERSION is wrong"
    )


# ── the standard document agrees with the implementation ────────────────────

def test_the_canonical_standard_exists_and_is_version_neutral():
    """A version belongs inside a document, never in its name.

    The old name `FITA_FORMAT_STANDARD.RATIFIED-v1.2.md` could not be corrected
    without breaking every citation to it, so it went stale and contradicted its
    own contents for three versions. A version-neutral name cannot.
    """
    assert STANDARD.is_file(), f"{STANDARD.name} is missing"
    assert not re.search(r"v?\d+\.\d+", STANDARD.name), (
        f"{STANDARD.name} carries a version in its filename, which is guaranteed "
        f"to go stale — state the version in §13 instead"
    )


@pytest.mark.parametrize("label,pattern", [
    ("status line",    r"RATIFIED CANONICAL — v(\d+\.\d+)"),
    ("title line",     r"Format Standard Document — v(\d+\.\d+)"),
    ("version field",  r"`FITAVER = (\d+\.\d+)`"),
])
def test_standard_states_the_implemented_format_version(fmt_version, label, pattern):
    hits = re.findall(pattern, _read(STANDARD))
    assert hits, f"could not find the {label} in {STANDARD.name}"
    assert hits[0] == fmt_version, (
        f"{STANDARD.name} {label} says v{hits[0]} but the implementation is "
        f"FITAVER={fmt_version}. The document and the code have diverged — this is "
        f"the de-facto-spec failure, caught before it reached a published record."
    )


def test_standard_version_table_reaches_the_current_version(fmt_version):
    """§13's table is the declared authority, so it must actually cover the version."""
    rows = re.findall(r"^\| (\d+\.\d+) \|", _read(STANDARD), re.M)
    assert rows, "no §13 version table rows found"
    newest = max(rows, key=lambda s: tuple(int(p) for p in s.split(".")))
    assert newest == fmt_version, (
        f"§13's newest row is {newest} but FITAVER={fmt_version}: the code "
        f"implements structure no normative row describes"
    )


def test_every_keyword_the_validator_enforces_is_specified():
    """Guards the specific gap this pass closed.

    FITA_ZEP and the spectral-frame block were enforced by validate.py for three
    months while appearing in NO normative document. A clause tag the checker can
    emit must be findable in the standard, or a failure message cannot be looked up.
    """
    std = _read(STANDARD)
    for kw in ("FITA_ZEP", "SPECSYS", "VELOSYS", "FITA_VSE", "FITA_ZDU", "FITA_FDI"):
        assert kw in std, f"{kw} is enforced in code but absent from {STANDARD.name}"
    for clause in ("S8.5", "8.5"):
        if clause in std:
            break
    else:
        pytest.fail("the checker emits clause tag S8.5 but §8.5 is not in the standard")


# ── the citation metadata agrees with the package ───────────────────────────

def test_zenodo_json_is_valid_and_concordant(pkg_version):
    """A malformed .zenodo.json fails validation SILENTLY while the webhook still
    returns 202 — that is how `license: "MIT"` (wrong case) got deposited once."""
    z = json.loads(_read(ROOT / ".zenodo.json"))
    assert z["version"] == pkg_version, (
        f".zenodo.json says {z['version']} but the package is {pkg_version}"
    )


def test_citation_cff_is_valid_and_concordant(pkg_version):
    yaml = pytest.importorskip("yaml")
    c = yaml.safe_load(_read(ROOT / "CITATION.cff"))
    assert c["version"] == pkg_version, (
        f"CITATION.cff says {c['version']} but the package is {pkg_version}"
    )


def test_zenodo_description_states_the_real_corpus_size():
    """The description claimed 18 corpus files long after there were 24.

    A reviewer can count the directory, so a stale number here is a published
    inaccuracy about verifiable evidence — the worst kind to carry.
    """
    manifest = ROOT / "corpus" / "MANIFEST.json"
    if not manifest.is_file():
        pytest.skip("corpus/MANIFEST.json absent")
    n_actual = len(json.loads(_read(manifest))["files"])
    desc = json.loads(_read(ROOT / ".zenodo.json"))["description"]
    claimed = re.search(r"corpus of (\d+) files", desc)
    assert claimed, "the .zenodo.json description no longer states a corpus size"
    assert int(claimed.group(1)) == n_actual, (
        f".zenodo.json advertises {claimed.group(1)} corpus files; "
        f"MANIFEST.json lists {n_actual}"
    )


# ── the machine-readable card agrees too ────────────────────────────────────

CARD = ROOT / "fita" / "ai" / "FITA_FORMAT_CARD.json"


def test_format_card_is_valid_json_and_names_the_current_standard(fmt_version):
    """The card is what an AI agent reads INSTEAD of asking, so a stale card is
    worse than none.

    Until 2026-11-14 it declared `conformed_to` as "v1.1 RATIFIED + amendment
    (proposed v1.2)" while the code was at 1.5, and pointed `docs.normative` at
    `FITA_FORMAT_STANDARD.RATIFIED-2026-08-02.md` — the SUPERSEDED v1.1 snapshot —
    describing it as "governs everything".
    """
    if not CARD.is_file():
        pytest.skip("format card absent")
    card = json.loads(_read(CARD))

    assert fmt_version in card["conformed_to"], (
        f"card conformed_to={card['conformed_to']!r} does not state "
        f"FITAVER={fmt_version}"
    )
    normative = card["interfaces"]["docs"]["normative"]
    assert "FITA_FORMAT_STANDARD.md" in normative, normative
    for retired in ("RATIFIED-v1.2", "RATIFIED-2026-08-02", "transport-2026-07-29"):
        assert retired not in normative, (
            f"the card names a superseded document as normative: {normative!r}"
        )


# ── nothing points readers at the retired filename as if it were normative ──

@pytest.mark.parametrize("fname", ["README.md", "pyproject.toml"])
def test_live_documents_link_to_the_canonical_standard(fname):
    """Historical records (amendments, handoffs, errata) legitimately cite the old
    path and are deliberately NOT rewritten — the stub keeps those links alive.
    These two files are not history; they are what a new reader is handed."""
    text = _read(ROOT / fname)
    assert "FITA_FORMAT_STANDARD.md" in text, (
        f"{fname} does not point at the canonical standard"
    )
    for line in text.splitlines():
        if "RATIFIED-v1.2" in line and not line.lstrip().startswith("#"):
            pytest.fail(
                f"{fname} still links the retired standard filename outside a "
                f"comment:\n    {line.strip()}"
            )
