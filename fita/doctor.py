"""
fita.doctor -- does this installation actually work from where you are standing?

Why this module exists
----------------------
FITA has been bitten twice by the same class of failure, and both times the
symptom was silence rather than an error:

  * The IrenBLink episode: an editable install that only resolved when the
    working directory happened to be the repo root.  Everything imported,
    nothing raised, and the science silently did not happen.

  * The 110-green-tests episode (standard S11.5): the suite tested the
    library's *functions* and never the *file's* conformance, so a writer
    defect present in every archived file went undetected for months.

`fita.validate()` answers "is this FILE correct?".  `fita doctor` answers the
question that comes before it: "is this INSTALL correct, from here?"  A
validator you cannot invoke, or that imports a hollow namespace package, is
not a validator.

The checks below are deliberately paranoid about import resolution, because
that is the failure mode that does not announce itself.

Exit codes:  0 = all good   1 = warnings only   2 = at least one failure
"""

from __future__ import annotations

import importlib
import os
import shutil
import sys
from pathlib import Path

OK, WARN, FAIL, INFO = "OK", "WARN", "FAIL", "INFO"

_GLYPH = {OK: "[ OK ]", WARN: "[WARN]", FAIL: "[FAIL]", INFO: "[ .. ]"}


class Result:
    """One diagnostic line, plus an optional remedy the user can act on."""

    __slots__ = ("status", "name", "detail", "remedy")

    def __init__(self, status, name, detail="", remedy=""):
        self.status = status
        self.name = name
        self.detail = detail
        self.remedy = remedy

    def render(self, verbose=False):
        line = "%s %-28s %s" % (_GLYPH[self.status], self.name, self.detail)
        out = [line.rstrip()]
        if self.remedy and (verbose or self.status in (WARN, FAIL)):
            out.append("         -> %s" % self.remedy)
        return "\n".join(out)


# --------------------------------------------------------------------------
# Import integrity -- the IrenBLink checks
# --------------------------------------------------------------------------

def _check_package_is_real(modname):
    """A namespace package has __file__ = None and executes no __init__.

    This is the exact IrenBLink failure: when the current directory contains a
    folder named `fita`, Python's path finder turns it into a namespace package
    and that SHADOWS the installed one.  Imports appear to succeed; the public
    API is missing; nothing raises until something reaches for a name.
    """
    try:
        mod = importlib.import_module(modname)
    except Exception as exc:
        return Result(FAIL, "import %s" % modname,
                      "%s: %s" % (type(exc).__name__, exc),
                      "the package is not installed for this interpreter "
                      "(%s)" % sys.executable)

    if getattr(mod, "__file__", None) is None:
        portions = list(getattr(mod, "__path__", []) or [])
        return Result(
            FAIL, "import %s" % modname,
            "resolved to a NAMESPACE package (no __init__ executed): %s"
            % (portions or "unknown location"),
            "a directory named '%s' in the current working directory (%s) is "
            "shadowing the installed package. cd elsewhere, or install a real "
            "(non-editable) wheel so the regular package wins the import."
            % (modname, os.getcwd()))

    return Result(OK, "import %s" % modname, mod.__file__)


def _check_public_api():
    """Importing the module is not the same as the API being reachable."""
    try:
        from fita import FITACube, FITALayer          # noqa: F401
    except Exception as exc:
        return Result(FAIL, "public API",
                      "%s: %s" % (type(exc).__name__, exc),
                      "fita imported but FITACube/FITALayer are missing -- "
                      "almost always the namespace-shadow failure above")
    return Result(OK, "public API", "FITACube, FITALayer importable")


def _check_shadowing():
    """Report a shadow only when it actually wins.

    A directory named `fita` in the cwd is a hazard, not a fault: whether it
    shadows depends on how the package is installed.  A doctor that warns
    every time you stand next to the repo gets ignored, so defer to what the
    import actually resolved to.
    """
    hits = [n for n in ("fita", "uranodyne") if Path.cwd().joinpath(n).is_dir()]
    if not hits:
        return Result(OK, "cwd shadowing", "no shadowing directories here")

    try:
        import fita
        won = getattr(fita, "__file__", None) is not None
    except Exception:
        won = False

    if won:
        return Result(OK, "cwd shadowing",
                      "%s/ present but the installed package wins the import"
                      % ", ".join(hits))
    return Result(
        FAIL, "cwd shadowing",
        "%s/ in cwd is SHADOWING the installed package" % ", ".join(hits),
        "cd elsewhere, install a real wheel, or reinstall editable with "
        "--config-settings editable_mode=compat so the regular package wins")


_GENERIC_NAMES = ("pipeline", "plugins", "instrument_db", "backends", "tests")


def _check_namespace_pollution():
    """Generic top-level names leaking out of this project onto sys.path.

    A flat-layout package whose pyproject sits inside the package directory
    can publish its own SUBDIRECTORIES as top-level modules.  `import
    pipeline` then silently resolves to this project's pipeline in any
    unrelated script on the machine.
    """
    leaked = []
    for name in _GENERIC_NAMES:
        try:
            spec = importlib.util.find_spec(name)
        except Exception:
            continue
        if spec is None:
            continue
        origin = spec.origin or ""
        paths = list(getattr(spec, "submodule_search_locations", None) or [])
        where = origin if origin and origin != "namespace" else (
            paths[0] if paths else "")
        if where and ("fita" in where or "uranodyne" in where):
            leaked.append(name)

    if not leaked:
        return Result(OK, "namespace hygiene", "no generic names leaked")
    return Result(
        WARN, "namespace hygiene",
        "top-level %s resolve into this project" % ", ".join(leaked),
        "an editable install is exposing package subdirectories as top-level "
        "modules; the built wheel is clean, so this affects the dev "
        "environment only")


def _check_console_script():
    path = shutil.which("fita")
    if path:
        return Result(OK, "console script", path)
    return Result(
        WARN, "console script", "'fita' is not on PATH",
        "the entry point exists but its directory is not on PATH; use "
        "'python -m fita' meanwhile, or add the interpreter's Scripts "
        "directory to PATH")


# --------------------------------------------------------------------------
# Versions, dependencies, data files
# --------------------------------------------------------------------------

def _check_versions():
    try:
        from fita.spec import FITA_VERSION
    except Exception as exc:
        return Result(FAIL, "format version",
                      "cannot read fita.spec.FITA_VERSION (%s)" % exc)
    try:
        from importlib.metadata import version
        dist = version("fita")
    except Exception:
        dist = "(not installed as a distribution)"
    return Result(OK, "versions",
                  "format FITAVER=%s | package fita==%s" % (FITA_VERSION, dist))


def _check_dep(modname, label, required, remedy):
    try:
        importlib.import_module(modname)
    except Exception:
        return Result(FAIL if required else WARN, label, "missing", remedy)
    return Result(OK, label, "present")


def _check_data_files():
    try:
        import fita
        if getattr(fita, "__file__", None) is None:
            return Result(FAIL, "package data",
                          "cannot locate package -- fita is a namespace shadow",
                          "fix the import failure above first; this check "
                          "cannot mean anything until it resolves")
        root = Path(fita.__file__).parent
    except Exception as exc:
        return Result(FAIL, "package data", "cannot locate package (%s)" % exc)

    missing = []
    if not list(root.glob("instrument_db/*.json")):
        missing.append("instrument_db/*.json")
    if not list(root.glob("ai/*.json")):
        missing.append("ai/FITA_FORMAT_CARD.json")
    if missing:
        return Result(WARN, "package data", "missing: %s" % ", ".join(missing),
                      "declare these under [tool.setuptools.package-data] so "
                      "they are carried into the wheel")
    return Result(OK, "package data", "instrument_db + AI format card present")


# --------------------------------------------------------------------------
# The self-test: can this install actually make a conformant file?
# --------------------------------------------------------------------------

def _check_roundtrip():
    """Write a real .fita, read it back, and validate it.

    This is the check that would have caught the writer defects: it exercises
    the whole path (build -> write -> read -> validate) rather than any single
    function, and it asserts the standard's core invariant (S5) bit-for-bit.
    """
    import tempfile

    try:
        import numpy as np
        from fita.layer import FITALayer
        from fita.io import write, read
        from fita.validate import validate
    except Exception as exc:
        return Result(FAIL, "write/read self-test",
                      "cannot import the I/O path: %s" % exc)

    try:
        rng = np.arange(64 * 64, dtype=np.float32).reshape(64, 64) * 1e-3
        rng[0, 0] = np.nan                       # blanked pixels are normal
        layer = FITALayer.from_array(rng, layer_id=1, name="doctor-selftest")

        tmp = Path(tempfile.gettempdir()) / "fita_doctor_selftest.fita"
        write(str(tmp), [layer], overwrite=True)
        back = read(str(tmp))
        report = validate(str(tmp))
        try:
            tmp.unlink()
        except OSError:
            pass
    except Exception as exc:
        return Result(FAIL, "write/read self-test",
                      "%s: %s" % (type(exc).__name__, exc))

    got = back[0].flux_data
    # S5.4 bit-exactness must be NaN-aware: NaN != NaN, so array_equal is
    # False whenever a blanked pixel is present -- and real astronomical
    # images are full of them.  Compare the NaN masks and the finite pixels
    # separately, exactly as the standard's flux_roundtrip_ok() does.
    nan_ok = bool((np.isnan(got) == np.isnan(rng)).all())
    finite = ~np.isnan(rng)
    flux_ok = nan_ok and bool((got[finite] == rng[finite]).all())

    if not flux_ok:
        return Result(FAIL, "write/read self-test",
                      "FLUX IS NOT BIT-EXACT across a round trip "
                      "(violates standard S5.3) -- do not trust this install",
                      "this is the format's central invariant; stop and "
                      "investigate the writer before producing science")

    if not report.is_core:
        return Result(FAIL, "write/read self-test",
                      "round trip OK but the file this install writes is "
                      "NOT FITA-CORE conformant",
                      "run 'fita conform <file>' for the failing clauses")

    level = "FITA-FULL" if report.is_full else "FITA-CORE"
    return Result(OK, "write/read self-test",
                  "flux bit-exact (NaN-aware); fresh write is %s" % level)


def _check_provenance_path():
    """Can this install actually reach FITA-FULL?

    FITA-FULL needs a conformant FITA_META HDU, and until v1.1 there was no
    way to get one into a file through the public API: make_meta_hdu() worked
    but io.write() could not accept its result.  A check that the provenance
    argument exists is not enough -- write a file and ask the validator.
    """
    import tempfile

    try:
        import numpy as np
        from fita.layer import FITALayer
        from fita.io import write
        from fita.validate import validate
    except Exception as exc:
        return Result(FAIL, "provenance path",
                      "cannot import the I/O path: %s" % exc)

    try:
        layer = FITALayer.from_array(
            np.zeros((8, 8), dtype=np.float32),
            layer_id=1, name="doctor-provenance", wave_cval=656e-9)
        tmp = Path(tempfile.gettempdir()) / "fita_doctor_provenance.fita"
        write(str(tmp), [layer], overwrite=True,
              provenance={"obs_id": "FITA-DOCTOR"})
        report = validate(str(tmp))
        try:
            tmp.unlink()
        except OSError:
            pass
    except TypeError as exc:
        return Result(FAIL, "provenance path",
                      "io.write() rejected provenance: %s" % exc,
                      "this build predates D-4/R2; FITA-FULL is unreachable")
    except Exception as exc:
        return Result(FAIL, "provenance path",
                      "%s: %s" % (type(exc).__name__, exc))

    if not report.is_full:
        failed = [str(f) for f in getattr(report, "findings", [])
                  if getattr(f, "severity", "") == "SHOULD"
                  and not getattr(f, "ok", True)]
        return Result(WARN, "provenance path",
                      "wrote FITA_META but the file is %s" % report.level,
                      "; ".join(failed[:2]) or "run 'fita conform' for detail")

    return Result(OK, "provenance path",
                  "ObsCore v1.2 FITA_META written; reaches FITA-FULL")


def _check_adjustment_path():
    """Does display state actually survive a save/load cycle? (S8, D-3)

    Before v1.1 the adjustment classes worked but nothing serialised them, so
    a stack could be built, applied, and saved -- and be gone on reload.  The
    check writes a stack with non-default parameters and asserts they come
    back, because an adjustment restored with default parameters looks like a
    successful round trip and is not one.
    """
    import tempfile

    try:
        import numpy as np
        from fita.layer import FITALayer
        from fita.adjustment import AdjustmentStack, LevelsAdjustment
        from fita.io import write, read_adjustments
    except Exception as exc:
        return Result(FAIL, "adjustment path",
                      "cannot import the adjustment path: %s" % exc)

    try:
        layer = FITALayer.from_array(np.zeros((8, 8), dtype=np.float32),
                                     layer_id=1, name="doctor-adj")
        stack = AdjustmentStack([LevelsAdjustment(gamma=2.2, in_black=0.125)])
        tmp = Path(tempfile.gettempdir()) / "fita_doctor_adj.fita"
        write(str(tmp), [layer], overwrite=True, adjustments=stack)
        back = read_adjustments(str(tmp)).adjustments
        try:
            tmp.unlink()
        except OSError:
            pass
    except TypeError as exc:
        return Result(FAIL, "adjustment path",
                      "io.write() rejected adjustments: %s" % exc,
                      "this build predates D-3; display state is not persisted")
    except Exception as exc:
        return Result(FAIL, "adjustment path",
                      "%s: %s" % (type(exc).__name__, exc))

    if not back:
        return Result(FAIL, "adjustment path",
                      "FITA_ADJ written but nothing read back")
    if abs(getattr(back[0], "gamma", 0.0) - 2.2) > 1e-6:
        return Result(FAIL, "adjustment path",
                      "adjustment restored with DEFAULT parameters "
                      "(gamma=%r, expected 2.2)" % getattr(back[0], "gamma", None),
                      "parameters are being dropped in serialisation")

    return Result(OK, "adjustment path",
                  "FITA_ADJ round-trips with parameters intact")


def _check_cli_wiring():
    """Every advertised subcommand must actually resolve to an importable
    function -- a verb in --help that raises on use is worse than no verb."""
    try:
        from fita import cli
    except Exception as exc:
        return Result(FAIL, "CLI wiring", "cannot import fita.cli (%s)" % exc)

    cmds = sorted(n[4:].replace("_", "-")
                  for n in dir(cli) if n.startswith("cmd_"))
    if not cmds:
        return Result(WARN, "CLI wiring", "no subcommands found")
    return Result(OK, "CLI wiring",
                  "%d subcommands: %s" % (len(cmds), ", ".join(cmds)))


# --------------------------------------------------------------------------

def run_checks():
    results = [
        _check_package_is_real("fita"),
        _check_public_api(),
        _check_shadowing(),
        _check_namespace_pollution(),
        _check_console_script(),
        _check_versions(),
        _check_cli_wiring(),
        _check_dep("numpy", "dep: numpy", True, "pip install numpy"),
        _check_dep("astropy", "dep: astropy", True, "pip install astropy"),
        _check_dep("h5py", "backend: HDF5", False,
                   "pip install h5py -- without it the HDF5 backend cannot be "
                   "used OR verified (standard S10.1 leaves it unconfirmed)"),
        _check_dep("zarr", "backend: Zarr", False, "pip install zarr numcodecs"),
        _check_dep("psd_tools", "optional: PSD import", False,
                   "pip install 'fita[psd]'"),
        _check_data_files(),
        _check_package_is_real("uranodyne"),
        _check_roundtrip(),
        _check_provenance_path(),
        _check_adjustment_path(),
    ]
    return results


def doctor(verbose=False, stream=None):
    """Run every check, print a report, and return an exit code (0/1/2)."""
    out = stream or sys.stdout
    results = run_checks()

    print("FITA installation diagnostics", file=out)
    print("  interpreter : %s" % sys.executable, file=out)
    print("  cwd         : %s" % os.getcwd(), file=out)
    print("", file=out)

    for r in results:
        print(r.render(verbose=verbose), file=out)

    fails = [r for r in results if r.status == FAIL]
    warns = [r for r in results if r.status == WARN]

    print("", file=out)
    if fails:
        print("VERDICT: %d failure(s), %d warning(s) -- this install is not "
              "safe to rely on." % (len(fails), len(warns)), file=out)
        return 2
    if warns:
        print("VERDICT: usable, with %d warning(s)." % len(warns), file=out)
        return 1
    print("VERDICT: healthy.", file=out)
    return 0
