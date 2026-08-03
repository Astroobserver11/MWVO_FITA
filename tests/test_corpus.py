"""The conformance corpus must agree with its own manifest.

The corpus is the artifact a third-party implementation is scored against and
part of what the Zenodo record will contain. Two properties have to hold or it
is not usable as evidence:

  * every file still validates to the level recorded for it, and
  * regenerating produces byte-identical output.

Both are checked here, so the corpus cannot drift from its labels the way the
guide notebook drifted from the standard.
"""

import json
from pathlib import Path

import pytest

pytest.importorskip("astropy")

from fita.validate import validate

CORPUS = Path(__file__).resolve().parent.parent / "corpus"
MANIFEST = CORPUS / "MANIFEST.json"

pytestmark = pytest.mark.skipif(
    not MANIFEST.exists(),
    reason="corpus not built; run python corpus/build_corpus.py")


def _manifest():
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def _entries():
    return _manifest()["files"]


def test_manifest_lists_every_tier():
    counts = _manifest()["counts"]
    for tier in ("conformance", "legacy", "science", "roundtrip"):
        assert counts.get(tier, 0) > 0, "tier %r is empty" % tier


@pytest.mark.parametrize("entry", _entries(), ids=lambda e: e["file"])
def test_file_validates_to_its_recorded_level(entry):
    path = CORPUS / entry["file"]
    assert path.exists(), "corpus file missing: %s" % entry["file"]
    report = validate(str(path))
    assert report.level == entry["expected_level"], (
        "%s: manifest says %s, validator says %s"
        % (entry["file"], entry["expected_level"], report.level))


@pytest.mark.parametrize("entry", _entries(), ids=lambda e: e["file"])
def test_failing_clauses_match_the_manifest(entry):
    """A negative fixture must break the clause it claims to break."""
    report = validate(str(CORPUS / entry["file"]))
    actual = sorted({f.clause for f in report.findings if not f.ok})
    assert actual == entry["failing_clauses"], (
        "%s: clause set drifted\n  manifest: %s\n  actual:   %s"
        % (entry["file"], entry["failing_clauses"], actual))


def test_nothing_in_the_corpus_crashes_the_reader():
    """Including the legacy tier -- a v1.0 file must OPEN, just not certify."""
    from astropy.io import fits
    for entry in _entries():
        with fits.open(str(CORPUS / entry["file"])) as hdul:
            assert len(hdul) >= 3           # PRIMARY + registry + >=1 layer


def test_legacy_tier_shows_the_v10_defects():
    """D-1 grandfathering has to be demonstrable, not asserted."""
    legacy = [e for e in _entries() if e["tier"] == "legacy"]
    assert legacy, "no legacy fixture"
    for entry in legacy:
        assert entry["expected_level"] == "NON-CONFORMANT"
        clauses = set(entry["failing_clauses"])
        assert "S6.2" in clauses, "should show the missing FITA_VIS"
        assert "S6.3" in clauses, "should show the wrapped-alpha defect"


def test_roundtrip_fixture_carries_the_droppable_attributes():
    """The transfusion reference is only useful if it actually holds the
    things a bridge loses -- a hidden layer, an absent depth, a disabled
    adjustment, NaN pixels."""
    import numpy as np
    from fita.io import read, read_adjustments, read_stereo_geometry

    entry = next(e for e in _entries() if e["tier"] == "roundtrip")
    path = str(CORPUS / entry["file"])

    layers = read(path)
    assert any(l.visible is False for l in layers), "no hidden layer"
    assert any(l.zdepth is None for l in layers), "no layer with absent depth"
    assert any(np.isnan(l.flux_data).any() for l in layers), "no NaN pixels"
    assert all(l.uncert_data is not None for l in layers)
    assert all(l.mask_data is not None for l in layers)
    assert len({l.blend_mode for l in layers}) > 1, "blend modes not varied"

    adjustments = read_adjustments(path).adjustments
    assert len(adjustments) == 6
    assert any(a.enabled is False for a in adjustments), "no disabled step"
    assert any(getattr(a, "response_curve", None) is not None
               for a in adjustments), "no variable-length parameter"

    geom = read_stereo_geometry(path)
    assert geom["zdp_scale"] is not None
    assert geom["zdp_ref_explicit"] is True
    # v1.4: FITA_ZAN is retired, so the fixture no longer carries it. What it
    # must carry instead is the field the scale is a percentage of, and the
    # depth unit -- dropping FITA_ZDU silently re-imposes the [0,1] domain and
    # makes a conformant file non-conformant without changing a pixel.
    assert geom["field_dia"] is not None
    assert geom["field_unit"] == "pc"
    assert geom["zdp_unit"] == "pc"
    assert any(l.zdepth is not None and l.zdepth > 1.0 for l in layers), \
        "physical depths not exercised"


def test_survival_spec_is_published():
    spec = _manifest()["survival_spec"]
    assert len(spec) >= 8
    joined = " ".join(spec).lower()
    for expected in ("nan", "visible", "zdepth", "bzero", "tucd"):
        assert expected in joined, "survival spec omits %r" % expected


@pytest.mark.slow
def test_corpus_is_byte_reproducible():
    """Regenerate into a temp tree and compare hashes.

    A citable artifact whose bytes change on every rebuild cannot be cited.
    """
    import sys
    sys.path.insert(0, str(CORPUS))
    try:
        import build_corpus
    finally:
        sys.path.pop(0)
    assert build_corpus.verify(CORPUS) == 0


def test_every_corpus_file_carries_a_verifying_checksum():
    """FITS integrity keywords are what the wider community -- and
    fitsverify -- expect on a delivered file. astropy raises on a bad
    checksum when opened with checksum=True, so this also proves the values
    are correct and not merely present."""
    import warnings
    from astropy.io import fits

    for entry in _entries():
        path = CORPUS / entry["file"]
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            with fits.open(str(path), checksum=True) as hdul:
                for hdu in hdul:
                    assert "CHECKSUM" in hdu.header, \
                        "%s: %s has no CHECKSUM" % (entry["file"], hdu.name)
                    assert "DATASUM" in hdu.header


def test_legacy_alpha_is_genuinely_wrapped():
    """The v1.0 defect must be reproduced in the DATA, not just asserted in a
    header. astropy regenerates BZERO from a uint16 dtype, so a header-only
    fixture would silently heal itself and test nothing."""
    from astropy.io import fits

    path = CORPUS / "legacy" / "v10_as_built.fita"
    with fits.open(str(path), do_not_scale_image_data=True) as hdul:
        alpha = hdul["ALPHA_0001"]
        assert "BZERO" not in alpha.header, "fixture healed itself"
        assert alpha.data.min() < 0, \
            "alpha should carry negative (wrapped) values as v1.0 wrote them"


# ── N-4 regression (ATOP audit, 2026-08-02) ─────────────────────────────────

def _conform_exit(path, *flags):
    """Run `fita conform` in a subprocess and return its exit code."""
    import subprocess, sys
    return subprocess.run(
        [sys.executable, "-m", "fita", "conform", str(path), "--quiet", *flags],
        capture_output=True).returncode


def test_conform_exits_nonzero_on_a_nonconformant_file():
    """N-4: the validator used to exit 0 on a file with dozens of MUST
    violations unless --strict was passed, so `fita conform --quiet` reported
    SILENT SUCCESS in any script. The analysis was right and the wrapper threw
    the verdict away -- this project's characteristic defect occurring inside
    the tool built to catch it. Failure must always propagate."""
    legacy = CORPUS / "legacy" / "v10_as_built.fita"
    assert _conform_exit(legacy) == 2, "non-conformant file must exit 2 by default"
    assert _conform_exit(legacy, "--strict") == 2


def test_conform_exits_zero_on_conformant_files():
    """The converse: a conformant file must never fail by default. CORE is a
    pass; --strict is what additionally demands FULL."""
    core = CORPUS / "conformance" / "core_minimal.fita"
    full = CORPUS / "conformance" / "full_provenanced.fita"
    assert _conform_exit(core) == 0
    assert _conform_exit(core, "--strict") == 1      # CORE but not FULL
    assert _conform_exit(full) == 0
    assert _conform_exit(full, "--strict") == 0


def test_reported_version_is_consistent():
    """N-3: fita.__version__ said 1.0.0 while spec and metadata said 1.3 --
    version drift in a project whose subject is provenance."""
    import fita
    from fita.spec import FITA_VERSION
    assert fita.__version__ == FITA_VERSION
