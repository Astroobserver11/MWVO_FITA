"""
The FLOAT32 ruling (P.I., 2026-11-14) and the three defects found with it.

Context, so a later reader knows what these guard against. Measured 2026-11-11 on
fita 1.5: FITA would *write* a float64 FLUX array as BITPIX=-64 -- a file its own
validator called NON-CONFORMANT (S6.1 MUST) -- and then silently truncate it back
to float32 on read. Max relative error 3.3e-08, and two pixels held distinct on
disk collapsed into a single value. Worse, `flux_roundtrip_ok()`, the function whose
whole job is to prove the sacred-flux invariant, cast BOTH sides to float32 before
comparing and so returned True on exactly that broken round trip.

The ruling: FITA enforces float32. The writer raises rather than casting, so losing
calibrated precision is always the caller's explicit decision.
"""
import numpy as np
import pytest
from astropy.io import fits

import fita
from fita import FITALayer, FITAPrecisionWarning
from fita.flux import auto_range, luminance_from_flux, luminance_to_alpha16
from fita.validate import validate, flux_roundtrip_ok


def _layer_with_dtype(dtype, name="PROBE"):
    """Build a layer with a flux array of exactly `dtype`, bypassing from_array().

    from_array() casts to float32 by design, so it cannot be used to construct the
    non-conformant case. The dataclass applies no cast -- which is how float64 got
    in originally.
    """
    rng = np.random.default_rng(1234)
    flux = (rng.random((12, 12)) * 1e-17).astype(dtype)
    lo, hi = auto_range(flux.astype(np.float32))
    alpha = luminance_to_alpha16(
        luminance_from_flux(flux.astype(np.float32), lo, hi, "asinh"))
    return FITALayer(
        flux_data=flux, alpha_data=alpha, layer_id=1, name=name,
        flux_min=float(lo), flux_max=float(hi), alpha_src="LUM",
    )


# ── the ruling: the writer refuses anything but float32 ──────────────────────

@pytest.mark.parametrize("dtype", [np.float64, np.float16, np.int16, np.int32])
def test_write_refuses_non_float32_flux(tmp_path, dtype):
    """S6.1 requires BITPIX=-32. The writer must raise, not quietly comply."""
    layer = _layer_with_dtype(dtype)
    with pytest.raises(ValueError, match="FLUX must be float32"):
        fita.write(str(tmp_path / "bad.fita"), [layer], overwrite=True)


def test_write_refusal_names_the_dtype_and_the_remedy(tmp_path):
    """An error that does not say what to do next just moves the confusion."""
    layer = _layer_with_dtype(np.float64)
    with pytest.raises(ValueError) as e:
        fita.write(str(tmp_path / "bad.fita"), [layer], overwrite=True)
    msg = str(e.value)
    assert "float64" in msg                      # what was wrong
    assert "S6.1" in msg                         # which clause
    assert "astype('float32')" in msg            # how to proceed deliberately


def test_the_exact_file_that_used_to_be_written_is_non_conformant(tmp_path):
    """Proves the writer and the validator used to disagree.

    Write BITPIX=-64 the way the old code path did -- straight through astropy,
    bypassing fita.write -- and confirm FITA's own validator rejects it. This is
    the file the library used to produce.
    """
    layer = _layer_with_dtype(np.float32)
    path = tmp_path / "f64.fita"
    fita.write(str(path), [layer], overwrite=True)

    with fits.open(str(path), mode="update") as hdul:
        for h in hdul:
            if h.name.startswith("FLUX"):
                h.data = h.data.astype(np.float64)   # recreate the old output

    rep = validate(str(path))
    assert not rep.is_core
    assert any("S6.1" in str(f) for f in rep.failures()), rep.failures()


def test_float32_still_writes_and_round_trips_bit_exact(tmp_path):
    """The ruling must not cost the legitimate path anything."""
    layer = _layer_with_dtype(np.float32)
    path = tmp_path / "ok.fita"
    fita.write(str(path), [layer], overwrite=True)

    with fits.open(str(path)) as hdul:
        flux_hdus = [h for h in hdul if h.name.startswith("FLUX")]
        assert flux_hdus and all(h.header["BITPIX"] == -32 for h in flux_hdus)

    back = fita.read(str(path))
    assert back[0].flux_data.dtype == np.float32
    assert np.array_equal(back[0].flux_data, layer.flux_data)


def test_big_endian_float32_is_accepted(tmp_path):
    """'>f4' off a FITS read is float32. Byte order is not precision."""
    layer = _layer_with_dtype(np.dtype(">f4"))
    fita.write(str(tmp_path / "be.fita"), [layer], overwrite=True)   # must not raise


# ── defect 3: the invariant check was blind to the loss it exists to catch ───

def test_roundtrip_check_no_longer_blesses_a_lossy_layer(tmp_path):
    """The regression that matters most.

    Before the fix this returned True for a float64 layer: both sides were cast
    to float32 before comparison, so the truncation was invisible to the check.
    It must now refuse to report success -- either by failing or by the write
    raising. Silently returning True is the one unacceptable outcome.
    """
    layer = _layer_with_dtype(np.float64)
    try:
        ok = flux_roundtrip_ok([layer], tmp_path=str(tmp_path / "rt.fita"))
    except ValueError:
        return          # the writer refused: correct, and the loss never happened
    assert ok is False, "the round-trip check reported success on a lossy layer"


def test_roundtrip_check_still_passes_a_genuine_float32_layer(tmp_path):
    """Fixing the blindness must not make the check paranoid."""
    layer = _layer_with_dtype(np.float32)
    assert flux_roundtrip_ok([layer], tmp_path=str(tmp_path / "rt32.fita")) is True


def test_roundtrip_check_does_not_cast_its_inputs():
    """Guards the specific line that caused it: `dtype=np.float32` on both sides."""
    import inspect
    src = inspect.getsource(flux_roundtrip_ok)
    # Comments must be excluded: the fix left a comment quoting the offending line
    # verbatim to explain what went wrong, and a naive substring search trips on it.
    offending = [
        ln for ln in src.splitlines()
        if "dtype=np.float32" in ln and not ln.strip().startswith("#")
    ]
    assert not offending, (
        "flux_roundtrip_ok is casting its inputs again -- that is exactly what made "
        "it return True on a float64 round trip that lost precision"
    )


# ── defect 4: the silent ingest downcast now announces itself ────────────────

def test_from_array_warns_when_it_downcasts_float64():
    rng = np.random.default_rng(7)
    data = (rng.random((8, 8)) * 1e-17).astype(np.float64)
    with pytest.warns(FITAPrecisionWarning, match="float32"):
        layer = FITALayer.from_array(data)
    assert layer.flux_data.dtype == np.float32     # the cast itself is correct


def test_from_array_is_silent_on_lossless_input(recwarn):
    """float32 and big-endian float32 lose nothing, so they must not warn."""
    for dt in (np.float32, np.dtype(">f4")):
        FITALayer.from_array(np.zeros((4, 4), dtype=dt))
    assert [w for w in recwarn if issubclass(w.category, FITAPrecisionWarning)] == []


# ── the separate defect: SPLIT16 was still reachable via the backends ────────

def test_zarr_backend_refuses_split16(tmp_path):
    """D-2 deleted SPLIT16, but this backend went on encoding it (measured)."""
    zb = pytest.importorskip("fita.backends.zarr")
    pytest.importorskip("zarr")
    layer = _layer_with_dtype(np.float32)
    with pytest.raises(ValueError, match="SPLIT16"):
        zb.write(str(tmp_path / "s.zarr"), [layer], pack="SPLIT16", overwrite=True)


def test_hdf5_backend_refuses_split16(tmp_path):
    hb = pytest.importorskip("fita.backends.hdf5")
    pytest.importorskip("h5py")
    layer = _layer_with_dtype(np.float32)
    with pytest.raises(ValueError, match="SPLIT16"):
        hb.write(str(tmp_path / "s.h5"), [layer], pack="SPLIT16", overwrite=True)
