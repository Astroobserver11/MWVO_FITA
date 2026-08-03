"""Tests for `fita doctor` -- the install-integrity self-check.

These guard the failure mode that has bitten this project twice: an install
that imports without error but is subtly wrong.  The point of doctor is that
it fails loudly; a doctor that silently passes on a broken install is worse
than none, so the tests below assert on the *detection*, not just the run.
"""

import sys
import types

import pytest

from fita import doctor as doc


def test_run_checks_returns_results():
    results = doc.run_checks()
    assert results, "doctor produced no checks at all"
    assert all(isinstance(r, doc.Result) for r in results)
    assert all(r.status in (doc.OK, doc.WARN, doc.FAIL, doc.INFO)
               for r in results)


def test_core_checks_pass_in_the_test_environment():
    """If the suite can import fita, doctor must agree that it can."""
    by_name = {r.name: r for r in doc.run_checks()}
    for name in ("import fita", "public API", "dep: numpy", "dep: astropy"):
        assert by_name[name].status == doc.OK, (
            "%s reported %s: %s" % (name, by_name[name].status,
                                    by_name[name].detail))


def test_roundtrip_selftest_passes():
    """The write->read->validate self-test must succeed on a good install."""
    r = doc._check_roundtrip()
    assert r.status == doc.OK, r.detail


def test_namespace_shadow_is_detected(monkeypatch):
    """A namespace package (__file__ is None) must be reported as FAIL.

    This is the IrenBLink signature: the import succeeds, so only an explicit
    __file__ check catches it.
    """
    shadow = types.ModuleType("fita")
    shadow.__path__ = ["/somewhere/fita"]
    shadow.__file__ = None                      # the tell-tale
    monkeypatch.setitem(sys.modules, "fita", shadow)

    r = doc._check_package_is_real("fita")
    assert r.status == doc.FAIL
    assert "NAMESPACE" in r.detail
    assert r.remedy, "a failure this confusing must carry a remedy"


def test_missing_package_is_detected(monkeypatch):
    def boom(name):
        raise ImportError("No module named %r" % name)
    monkeypatch.setattr(doc.importlib, "import_module", boom)

    r = doc._check_package_is_real("definitely_not_installed")
    assert r.status == doc.FAIL


def test_doctor_returns_an_exit_code(capsys):
    code = doc.doctor()
    capsys.readouterr()
    assert code in (0, 1, 2)


@pytest.mark.parametrize("status,expected", [
    (doc.OK, 0), (doc.WARN, 1), (doc.FAIL, 2),
])
def test_verdict_severity_ordering(status, expected, monkeypatch, capsys):
    """Exit code must reflect the worst finding, not the last one."""
    monkeypatch.setattr(doc, "run_checks",
                        lambda: [doc.Result(doc.OK, "fine"),
                                 doc.Result(status, "under test")])
    code = doc.doctor()
    capsys.readouterr()
    assert code == expected


# ── ruling 2026-08-02 S5.1: name the directory, do not just report the fault ──

def test_missing_console_script_names_the_directory_to_add(monkeypatch, tmp_path):
    """ATOP lost a session to 'not on PATH' without a directory to add.

    The wheel was correct, the entry point was correct, and neither Scripts
    directory was on PATH.  A diagnostic that states a fault it can localise
    but does not localise it is only half a diagnostic.
    """
    import os
    exe = "fita.exe" if os.name == "nt" else "fita"
    scripts = tmp_path / "Scripts"
    scripts.mkdir()
    (scripts / exe).write_text("")

    monkeypatch.setattr(doc.shutil, "which", lambda _n: None)
    monkeypatch.setattr(doc, "_script_dirs", lambda: [str(scripts)])

    r = doc._check_console_script()
    assert r.status == doc.WARN
    assert str(scripts) in r.remedy


def test_missing_console_script_says_where_it_looked(monkeypatch, tmp_path):
    """When the entry point genuinely is not installed, the remedy is
    different -- reinstall, not edit PATH -- so the two must not be conflated."""
    monkeypatch.setattr(doc.shutil, "which", lambda _n: None)
    monkeypatch.setattr(doc, "_script_dirs", lambda: [str(tmp_path / "nowhere")])

    r = doc._check_console_script()
    assert r.status == doc.WARN
    assert "nowhere" in r.detail
    assert "reinstall" in r.remedy


def test_version_drift_is_detected(monkeypatch):
    """N-3 was version drift, and the check that displays both numbers
    returned OK regardless -- it could never have caught it."""
    import importlib.metadata as md
    monkeypatch.setattr(md, "version", lambda _n: "1.2.0")
    r = doc._check_versions()
    assert r.status == doc.WARN
    assert "DRIFT" in r.detail


def test_matching_versions_pass(monkeypatch):
    """A patch-level difference is not drift: S13 makes FITAVER major.minor."""
    import importlib.metadata as md
    from fita.spec import FITA_VERSION
    monkeypatch.setattr(md, "version", lambda _n: FITA_VERSION + ".7")
    assert doc._check_versions().status == doc.OK
