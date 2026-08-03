"""`fita info` against files that exercise the OPTIONAL keywords -- N-7.

ATOP found `fita info` crashing on every one of the 18 archived files:

    TypeError: unsupported format string passed to NoneType.__format__

The tempting reading is "legacy files are malformed".  It is the wrong one.
S6.2 marks FITA_FMN / FITA_FMX as SHOULD, not MUST, so a file may omit them and
still be fully FITA-CORE conformant -- the CLI was assuming a keyword the
standard makes optional.  That is a defect in the reader, not in the files.

These tests therefore build a *conformant* file with the optional keywords
absent and require `info` to describe it, which is the thing that was never
tested.
"""

import numpy as np
import pytest

pytest.importorskip("astropy")

from astropy.io import fits

from fita.cli import cmd_info
from fita.io import write
from fita.layer import FITALayer


class _Args:
    def __init__(self, path):
        self.fita_file = str(path)


def _file_without_optional_keywords(tmp_path):
    """A written file with FITA_FMN/FITA_FMX stripped from every FLUX HDU.

    Stripping after the write is deliberate: it produces exactly the header a
    third-party writer that exercised its SHOULD-level freedom would produce,
    without depending on this library having a way to decline them.
    """
    path = tmp_path / "no_optional.fita"
    layers = [
        FITALayer.from_array(np.linspace(0, 1, 256, dtype=np.float32).reshape(16, 16),
                             layer_id=1, name="HI-21cm"),
        FITALayer.from_array(np.zeros((16, 16), dtype=np.float32),
                             layer_id=2, name="X-ray"),
    ]
    write(str(path), layers)

    with fits.open(str(path), mode="update") as hdul:
        for hdu in hdul:
            if str(hdu.name).startswith("FLUX"):
                for kw in ("FITA_FMN", "FITA_FMX", "FITA_WCV"):
                    hdu.header.pop(kw, None)
    return path


def test_info_does_not_crash_when_flux_bounds_are_absent(tmp_path, capsys):
    """The N-7 regression: this raised TypeError on every archived file."""
    cmd_info(_Args(_file_without_optional_keywords(tmp_path)))
    out = capsys.readouterr().out
    assert "2 layer(s)" in out
    assert "HI-21cm" in out and "X-ray" in out


def test_absent_flux_bounds_print_as_dash_not_zero(tmp_path, capsys):
    """Absence must read as absence.

    Rendering a missing bound as 0 would be this project's characteristic
    failure again -- a silent substitution that looks like a measurement.  The
    `-` convention is the one `wave` already uses in the same line.
    """
    cmd_info(_Args(_file_without_optional_keywords(tmp_path)))
    out = capsys.readouterr().out
    assert "flux=[-, -]" in out
    assert "wave=-" in out


def test_info_still_reports_bounds_when_they_are_present(tmp_path, capsys):
    """The fix must not blank out real values."""
    path = tmp_path / "with_optional.fita"
    layer = FITALayer.from_array(np.linspace(0, 10, 256, dtype=np.float32).reshape(16, 16),
                                 layer_id=1, name="H-alpha")
    write(str(path), [layer])

    cmd_info(_Args(path))
    out = capsys.readouterr().out
    assert "flux=[-, -]" not in out
    # from_array derives the bounds by percentile, so assert against the
    # layer's own recorded values rather than the array's raw extrema.
    assert f"flux=[{layer.flux_min:.3g}, {layer.flux_max:.3g}]" in out
