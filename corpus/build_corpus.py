#!/usr/bin/env python
"""
Build the FITA conformance corpus.

Why a generator and not a folder of files
-----------------------------------------
A corpus of opaque blobs cannot be reviewed, cannot be regenerated when the
standard moves, and cannot explain itself.  This script is the corpus; the
files are its output.  Both are committed, because the archived artifact
should contain the actual bytes a third-party implementer will test against,
and both must agree -- `--verify` checks exactly that.

The four tiers
--------------
conformance/  Tiny synthetic files, in positive/negative pairs, one per clause
              the validator enforces.  This is the tier a third-party
              implementation is scored against.
legacy/       Files deliberately carrying the v1.0 defects, so "grandfathered"
              (D-1) is demonstrable rather than asserted.
science/      One small multi-band cube with WCS -- what the format is FOR.
roundtrip/    Files carrying every attribute a format transfusion could
              silently drop.  Built for the ImageJ2 bridge, but useful against
              any second implementation.

Determinism
-----------
Every array is analytic, no RNG state escapes, and no timestamps are written.
Regenerating on any machine must produce byte-identical files, or the corpus
cannot be a stable citable artifact.  `--verify` enforces this too.

Usage
-----
    python corpus/build_corpus.py            # write the corpus
    python corpus/build_corpus.py --verify   # regenerate, compare, validate
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import tempfile
from pathlib import Path

import numpy as np
from astropy.io import fits
from astropy.wcs import WCS

from fita.adjustment import (
    AdjustmentStack, LevelsAdjustment, CurvesAdjustment, BrightnessAdjustment,
    FluxStretchAdjustment, BandMapAdjustment, FluxNormAdjustment,
)
from fita.io import write as _fita_write
from fita.layer import FITALayer
from fita.spec import FITA_VERSION, KW_ZSCALE, KW_ZREF
from fita.validate import validate

ROOT = Path(__file__).resolve().parent

# Fixed on purpose. io.write() defaults DATE to "now", which is the one value
# that would stop this corpus regenerating byte-identically -- and a citable
# artifact whose bytes change on every rebuild cannot be cited.
CORPUS_DATE = "2026-08-02T00:00:00"


def write(*args, **kw):
    """io.write() with the corpus's deterministic provenance pinned."""
    kw.setdefault("date", CORPUS_DATE)
    kw.setdefault("creator", "fita-corpus %s" % FITA_VERSION)
    kw.setdefault("origin", "MWVO / UranoDyne")
    return _fita_write(*args, **kw)
TIERS = ("conformance", "legacy", "science", "roundtrip")

# Records what each file is FOR, so the manifest explains itself.
_ENTRIES: list[dict] = []


# ── deterministic synthetic data ────────────────────────────────────────────

def _field(h=32, w=32, seed=0, blank=False):
    """An analytic 'sky': smooth gradient + a couple of Gaussian sources.

    Analytic rather than random so the bytes are reproducible everywhere.
    """
    y, x = np.mgrid[0:h, 0:w].astype(np.float64)
    img = 10.0 + 0.05 * (x + y)                      # sky gradient
    for i, (cy, cx, amp, sig) in enumerate(
            [(h * 0.30, w * 0.35, 800.0, 2.2), (h * 0.70, w * 0.65, 300.0, 3.1)]):
        cy += seed * 0.7
        cx -= seed * 0.5
        img += amp * np.exp(-(((y - cy) ** 2 + (x - cx) ** 2) / (2 * sig ** 2)))
    if blank:
        # Real images are full of blanked pixels; a corpus without NaN would
        # let a NaN-unaware implementation pass.
        img[0, 0] = np.nan
        img[h // 2, w // 2 - 1] = np.nan
    return img.astype(np.float32)


def _wcs(h=32, w=32):
    wcs = WCS(naxis=2)
    wcs.wcs.crpix = [w / 2.0, h / 2.0]
    wcs.wcs.cdelt = [-0.001, 0.001]                  # 3.6 arcsec/px
    wcs.wcs.crval = [299.9015, 22.7211]              # M27
    wcs.wcs.ctype = ["RA---TAN", "DEC--TAN"]
    return wcs


def _provenance(obs_id, **kw):
    base = dict(
        obs_id=obs_id, facility="SYNTHETIC", instrument="FITA-CORPUS",
        target="corpus-fixture", ra=299.9015, dec=22.7211,
        calib_level=2, estsize_kb=64,
        extra={"obs_publisher_did": "ivo://mwvo/fita-corpus?" + obs_id,
               "obs_collection": "FITA-CORPUS",
               "s_region": "POLYGON ICRS 299.85 22.67 299.95 22.67 "
                           "299.95 22.77 299.85 22.77",
               "s_fov": 0.032},
    )
    base.update(kw)
    return base


def _record(path: Path, purpose: str, clause: str, expect: str):
    """Register a file in the manifest, with what a validator should say."""
    report = validate(str(path))
    failing = sorted({f.clause for f in report.findings if not f.ok})
    _ENTRIES.append({
        "file": str(path.relative_to(ROOT)).replace("\\", "/"),
        "tier": path.parent.name,
        "purpose": purpose,
        "clause": clause,
        "expected_level": expect,
        "actual_level": report.level,
        "failing_clauses": failing,
        "bytes": path.stat().st_size,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    })
    if report.level != expect:
        raise SystemExit(
            "FIXTURE DISAGREES WITH ITS OWN LABEL: %s\n"
            "  expected %s, validator says %s (failing: %s)"
            % (path.name, expect, report.level, ", ".join(failing) or "none"))


def _corrupt(path: Path, fn):
    """Apply a header edit in place -- how negative fixtures are made.

    Negative fixtures are built by writing a *conformant* file and then
    breaking one thing, so each isolates exactly one clause.
    """
    with fits.open(str(path), memmap=False) as opened:
        hdul = fits.HDUList([h.copy() for h in opened])
    fn(hdul)
    # Pass 1: materialise the edit. An in-place change to a table's .data does
    # not update the HDU's cached datasum, so checksumming here would certify
    # the PRE-corruption bytes -- observed, and exactly the kind of silent
    # disagreement this corpus exists to catch.
    hdul.writeto(str(path), overwrite=True)

    # Pass 2: checksum what is actually on disk, with the comment pinned so the
    # fixture stays byte-reproducible (astropy would otherwise stamp a
    # wall-clock time into the card).
    with fits.open(str(path), memmap=False) as opened:
        final = fits.HDUList([h.copy() for h in opened])
    for h in final:
        h.add_checksum(when="updated %s" % CORPUS_DATE)
    final.writeto(str(path), overwrite=True)



def _wrap_alpha_as_v10(hdul, idx=1):
    """Replace an ALPHA plane with a genuine v1.0 wrapped-int16 plane.

    Popping BZERO from the header is not enough: astropy regenerates it from
    the uint16 dtype on write, so the defect would silently heal. v1.0 cast
    alpha to int16 WITHOUT BZERO, so everything above 32767 -- i.e. more than
    half-opaque -- stored negative. This reproduces that array, which is what
    a third-party viewer would actually have been handed.
    """
    name = "ALPHA_%04d" % idx
    old = hdul[name]
    vals = np.asarray(old.data).astype(np.int32)
    wrapped = np.where(vals > 32767, vals - 65536, vals).astype(np.int16)
    hdr = old.header.copy()
    for kw in ("BZERO", "BSCALE"):
        hdr.pop(kw, None)
    new = fits.ImageHDU(data=wrapped, header=hdr)
    new.name = name
    hdul[hdul.index_of(name)] = new


# ── tier 1: conformance fixtures ────────────────────────────────────────────

def build_conformance(out: Path):
    out.mkdir(parents=True, exist_ok=True)

    def base_layers(n=2, blank=True):
        waves = [656.3e-9, 2.2e-6]
        return [
            FITALayer.from_array(_field(seed=i, blank=blank), layer_id=i + 1,
                                 name="band%d" % (i + 1), wave_cval=waves[i],
                                 wcs=_wcs())
            for i in range(n)
        ]

    # ---- positive -------------------------------------------------------
    p = out / "core_minimal.fita"
    write(str(p), base_layers(1), overwrite=True)
    _record(p, "Smallest file that satisfies every MUST", "S3-S7", "FITA-CORE")

    p = out / "full_provenanced.fita"
    write(str(p), base_layers(2), overwrite=True,
          provenance=_provenance("CORPUS-FULL"))
    _record(p, "FITA-FULL: ObsCore v1.2 provenance present", "S9", "FITA-FULL")

    p = out / "full_with_adjustments.fita"
    stack = AdjustmentStack([
        LevelsAdjustment(in_black=0.1, in_white=0.9, gamma=2.2, name="levels"),
        CurvesAdjustment(control_points=[(0.0, 0.0), (0.3, 0.6), (1.0, 1.0)]),
        FluxStretchAdjustment(stretch_mode="log", asinh_a=0.25),
    ])
    write(str(p), base_layers(2), overwrite=True, adjustments=stack,
          provenance=_provenance("CORPUS-ADJ"))
    _record(p, "FITA_ADJ display stack, typed columns", "S8.3", "FITA-FULL")

    p = out / "full_with_stereo.fita"
    layers = base_layers(2)
    layers[0].zdepth, layers[1].zdepth = 0.0, 1.0
    write(str(p), layers, overwrite=True, zdp_scale=24.0, zdp_ref=0.5,
          zdp_angular=86.4, provenance=_provenance("CORPUS-STEREO"))
    _record(p, "Stereo geometry: ZSC + ZRF + ZAN", "S8.2", "FITA-FULL")

    p = out / "full_with_uncert_mask.fita"
    layers = base_layers(2)
    for l in layers:
        l.uncert_data = (np.abs(np.nan_to_num(l.flux_data)) * 0.05).astype(np.float32)
        m = np.zeros(l.flux_data.shape, dtype=np.uint8)
        m[0, :] = 1                                   # bad row
        m[1, :] = 2                                   # saturated row
        l.mask_data = m
    write(str(p), layers, overwrite=True, provenance=_provenance("CORPUS-UNC"))
    _record(p, "Companion UNCERT_* and MASK_* planes", "S6.5", "FITA-FULL")

    # ---- negative -------------------------------------------------------
    # Each breaks exactly one clause, starting from a conformant file.
    neg = [
        ("neg_missing_fita_vis.fita", "S6.2",
         "Layer keyword FITA_VIS removed",
         lambda h: h["FLUX_0001"].header.pop("FITA_VIS", None)),
        ("neg_alpha_no_bzero.fita", "S6.3",
         "ALPHA carries genuine v1.0 wrapped int16 data and no BZERO",
         _wrap_alpha_as_v10),
        ("neg_alpha_bunit_alpha16.fita", "S7",
         "ALPHA declares the invalid unit 'alpha16'",
         lambda h: h["ALPHA_0001"].header.__setitem__("BUNIT", "alpha16")),
        ("neg_bad_blend_code.fita", "S8",
         "Unknown FITA_BLD blend code",
         lambda h: h["FLUX_0001"].header.__setitem__("FITA_BLD", "NOTAMODE")),
        ("neg_nlayers_mismatch.fita", "S4.2",
         "FITANL disagrees with the number of FLUX extensions",
         lambda h: h[0].header.__setitem__("FITANL", 7)),
        ("neg_split16_declared.fita", "S6.4",
         "FITAPACK declares the deleted SPLIT16 mode",
         lambda h: h[0].header.__setitem__("FITAPACK", "SPLIT16")),
        ("neg_zsc_not_finite.fita", "S8.2",
         "FITA_ZSC is not a number",
         lambda h: h[0].header.__setitem__(KW_ZSCALE, "not-a-number")),
    ]
    for name, clause, purpose, breaker in neg:
        p = out / name
        write(str(p), base_layers(1), overwrite=True,
              zdp_scale=24.0 if "zsc" in name else None)
        _corrupt(p, breaker)
        _record(p, purpose, clause, "NON-CONFORMANT")

    # access_format overclaim: needs provenance to exist before it can lie.
    p = out / "neg_access_format_overclaim.fita"
    write(str(p), base_layers(1), overwrite=True,
          provenance=_provenance("CORPUS-MIME"))
    _corrupt(p, lambda h: h["FITA_META"].data.__setitem__(
        "access_format", np.array(["application/fits+alpha"])))
    _record(p, "access_format claims the unregistered '+alpha' MIME type",
            "S3", "NON-CONFORMANT")

    # FITA_ADJ corruption: unknown type, and unparseable PARAMS.
    p = out / "neg_adj_unknown_type.fita"
    write(str(p), base_layers(1), overwrite=True, adjustments=stack)
    _corrupt(p, lambda h: h["FITA_ADJ"].data.field("ADJ_TYPE").__setitem__(0, "BOGUS"))
    _record(p, "FITA_ADJ carries an unknown ADJ_TYPE", "S8", "NON-CONFORMANT")

    p = out / "neg_adj_bad_json.fita"
    write(str(p), base_layers(1), overwrite=True, adjustments=stack)
    _corrupt(p, lambda h: h["FITA_ADJ"].data.field("PARAMS").__setitem__(1, "{not json"))
    _record(p, "FITA_ADJ PARAMS cell is not parseable JSON", "S8",
            "NON-CONFORMANT")


# ── tier 2: legacy / grandfathered ──────────────────────────────────────────

def build_legacy(out: Path):
    """A file as v1.0 actually wrote them, so D-1 grandfathering is testable.

    All 18 archived files on ATOP look like this. The point of the tier is
    that a reader must be able to OPEN these without crashing while a
    validator declines to certify them.
    """
    out.mkdir(parents=True, exist_ok=True)
    p = out / "v10_as_built.fita"
    layers = [FITALayer.from_array(_field(seed=i, blank=True), layer_id=i + 1,
                                   name="band%d" % (i + 1),
                                   wave_cval=[656.3e-9, 2.2e-6][i], wcs=_wcs())
              for i in range(2)]
    write(str(p), layers, overwrite=True)

    def as_v10(hdul):
        hdul[0].header["FITAVER"] = "1.0"
        for i in (1, 2):
            hdul["FLUX_%04d" % i].header.pop("FITA_VIS", None)   # R3
            _wrap_alpha_as_v10(hdul, i)                           # R1
            hdul["ALPHA_%04d" % i].header["BUNIT"] = "alpha16"    # R4
    _corrupt(p, as_v10)
    _record(p, "A v1.0 file as actually written: wrapped alpha, invalid BUNIT, "
               "no FITA_VIS. Opens cleanly; must NOT certify.",
            "D-1", "NON-CONFORMANT")


# ── tier 3: science exemplar ────────────────────────────────────────────────

def build_science(out: Path):
    """Three bands, WCS, depth, provenance -- the format doing its job."""
    out.mkdir(parents=True, exist_ok=True)
    p = out / "three_band_field.fita"
    spec = [("Halpha", 656.3e-9, 0.5, "SCREEN"),
            ("J", 1.25e-6, 0.25, "ADD"),
            ("K", 2.2e-6, 0.0, "ADD")]
    layers = []
    for i, (name, wave, zdp, blend) in enumerate(spec):
        l = FITALayer.from_array(_field(64, 64, seed=i, blank=True),
                                 layer_id=i + 1, name=name, wave_cval=wave,
                                 wave_bwid=wave * 0.05, blend_mode=blend,
                                 opacity=1.0 - 0.1 * i, wcs=_wcs(64, 64))
        l.zdepth = zdp
        l.uncert_data = (np.abs(np.nan_to_num(l.flux_data)) * 0.03).astype(np.float32)
        layers.append(l)
    write(str(p), layers, overwrite=True,
          adjustments=AdjustmentStack([
              FluxStretchAdjustment(stretch_mode="asinh", asinh_a=0.1),
              BandMapAdjustment(channel="R", layer_id=1),
              BandMapAdjustment(channel="G", layer_id=2),
              BandMapAdjustment(channel="B", layer_id=3)]),
          zdp_scale=16.0, zdp_ref=0.25,
          provenance=_provenance("CORPUS-SCIENCE", target="M27-like field"))
    _record(p, "Three-band field with depth, blend modes, uncertainty, "
               "false-colour band mapping and stereo geometry",
            "showcase", "FITA-FULL")


# ── tier 4: round-trip / transfusion ────────────────────────────────────────

# Everything a format bridge can silently lose. Named here so the expectation
# is explicit rather than folklore.
SURVIVAL_SPEC = [
    "flux bit-exact (NaN-aware: compare NaN masks and finite pixels separately)",
    "alpha values in 0..65535 with BZERO=32768 -- not signed and wrapped",
    "per-layer visible flag, including False",
    "per-layer blend_mode and opacity",
    "per-layer zdepth, including ABSENT (must not become 0.0)",
    "companion UNCERT_* and MASK_* planes",
    "FITA_ADJ order, enabled flags, and typed parameter values",
    "FITA_ADJ variable-length parameters (curve points, response arrays)",
    "stereo FITA_ZSC / FITA_ZRF / FITA_ZAN",
    "ObsCore provenance columns and their TUCDn annotations",
]


def build_roundtrip(out: Path):
    """One file carrying every droppable attribute at once.

    Built for the ImageJ2 / PyImageJ bridge, but it scores any second
    implementation. If a transfusion returns this file intact, the bridge is
    lossless; if not, the manifest says exactly which attribute went missing.
    """
    out.mkdir(parents=True, exist_ok=True)
    p = out / "transfusion_reference.fita"

    layers = []
    for i, (name, blend, opac, vis, zdp) in enumerate([
            ("visible-front", "SCREEN", 1.00, True, 1.0),
            ("hidden-mid", "MULTIPLY", 0.50, False, 0.5),   # visible=False
            ("no-depth", "ADD", 0.75, True, None),          # zdepth absent
    ]):
        l = FITALayer.from_array(_field(seed=i, blank=True), layer_id=i + 1,
                                 name=name, blend_mode=blend, opacity=opac,
                                 wave_cval=[656.3e-9, 1.25e-6, 2.2e-6][i],
                                 wcs=_wcs())
        l.visible = vis
        l.zdepth = zdp
        l.uncert_data = (np.abs(np.nan_to_num(l.flux_data)) * 0.07).astype(np.float32)
        m = np.zeros(l.flux_data.shape, dtype=np.uint8)
        m[2, :] = 4                                   # cosmic-ray bit
        l.mask_data = m
        layers.append(l)

    stack = AdjustmentStack([
        LevelsAdjustment(in_black=0.125, in_white=0.875, gamma=2.2, name="lv"),
        CurvesAdjustment(control_points=[(0.0, 0.0), (0.25, 0.4),
                                         (0.75, 0.9), (1.0, 1.0)]),
        BrightnessAdjustment(brightness=0.2, contrast=-0.3),
        FluxStretchAdjustment(stretch_mode="log", asinh_a=0.25, power_exp=0.7),
        BandMapAdjustment(channel="G", layer_id=2),
        FluxNormAdjustment(response_curve=np.linspace(1.0, 0.4, 24),
                           wavelengths=np.linspace(6e-7, 2.4e-6, 24),
                           wave_cval=1.25e-6),
    ])
    stack.adjustments[3].enabled = False              # a disabled step

    write(str(p), layers, overwrite=True, adjustments=stack,
          zdp_scale=24.0, zdp_ref=0.5, zdp_angular=86.4,
          provenance=_provenance("CORPUS-TRANSFUSION"))
    _record(p, "Carries every attribute a transfusion could silently drop; "
               "see survival_spec in the manifest",
            "roundtrip", "FITA-FULL")


# ── manifest ────────────────────────────────────────────────────────────────

def _toolchain():
    """The libraries whose byte-level output the corpus depends on.

    FITS serialisation is stable in MEANING across astropy versions but not in
    BYTES: card formatting and padding shift between releases. Recording the
    toolchain is what lets `--verify` tell "the corpus changed" apart from
    "astropy changed".
    """
    import platform
    import astropy
    return {
        "python": platform.python_version(),
        "numpy": np.__version__,
        "astropy": astropy.__version__,
    }


def write_manifest(out: Path):
    manifest = {
        "corpus": "FITA conformance corpus",
        "format_version": FITA_VERSION,
        "toolchain": _toolchain(),
        "generator": "corpus/build_corpus.py",
        "regenerate": "python corpus/build_corpus.py",
        "verify": "python corpus/build_corpus.py --verify",
        "note": ("Files are generated deterministically: regenerating with the "
                 "recorded toolchain produces byte-identical output. A different "
                 "astropy version may serialise the same content to different "
                 "bytes, which is why the toolchain is recorded -- the SEMANTIC "
                 "checks (conformance level and failing clauses) hold across "
                 "versions and are always enforced. Each entry records the level "
                 "a conformant validator MUST report."),
        "tiers": {
            "conformance": "positive/negative pairs, one per enforced clause",
            "legacy": "v1.0 files as actually written; grandfathered under D-1",
            "science": "small multi-band exemplar -- what the format is for",
            "roundtrip": "every attribute a format bridge could silently drop",
        },
        "survival_spec": SURVIVAL_SPEC,
        "counts": {t: sum(1 for e in _ENTRIES if e["tier"] == t) for t in TIERS},
        "files": sorted(_ENTRIES, key=lambda e: e["file"]),
    }
    (out / "MANIFEST.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def build_all(root: Path):
    _ENTRIES.clear()
    build_conformance(root / "conformance")
    build_legacy(root / "legacy")
    build_science(root / "science")
    build_roundtrip(root / "roundtrip")
    return write_manifest(root)


# ── verification ────────────────────────────────────────────────────────────

def verify(root: Path) -> int:
    """Regenerate into a temp tree and prove the committed corpus matches.

    Checks two things a citable artifact needs: that the bytes are
    reproducible, and that every file still validates to its recorded level.
    """
    committed = json.loads((root / "MANIFEST.json").read_text(encoding="utf-8"))
    tmp = Path(tempfile.mkdtemp(prefix="fita_corpus_"))
    try:
        global ROOT
        original, ROOT = ROOT, tmp
        try:
            fresh = build_all(tmp)
        finally:
            ROOT = original

        problems = []
        old = {e["file"]: e for e in committed["files"]}
        new = {e["file"]: e for e in fresh["files"]}

        recorded = committed.get("toolchain") or {}
        current = fresh.get("toolchain") or {}
        same_toolchain = recorded == current
        if not same_toolchain:
            print("toolchain differs from the one that generated this corpus:")
            for k in sorted(set(recorded) | set(current)):
                if recorded.get(k) != current.get(k):
                    print("  %-8s recorded %s, running %s"
                          % (k, recorded.get(k, "?"), current.get(k, "?")))
            print("byte comparison skipped; semantic checks still enforced.")
            print()

        for name in sorted(set(old) | set(new)):
            if name not in old:
                problems.append("%s: present in fresh build, not committed" % name)
            elif name not in new:
                problems.append("%s: committed but no longer generated" % name)
            elif same_toolchain and old[name]["sha256"] != new[name]["sha256"]:
                problems.append("%s: NOT reproducible (sha256 differs)" % name)
            elif old[name]["actual_level"] != new[name]["actual_level"]:
                problems.append("%s: level changed %s -> %s"
                                % (name, old[name]["actual_level"],
                                   new[name]["actual_level"]))
            elif old[name]["failing_clauses"] != new[name]["failing_clauses"]:
                problems.append("%s: failing clauses changed %s -> %s"
                                % (name, old[name]["failing_clauses"],
                                   new[name]["failing_clauses"]))

        for name, e in sorted(new.items()):
            if e["actual_level"] != e["expected_level"]:
                problems.append("%s: expected %s, validator says %s"
                                % (name, e["expected_level"], e["actual_level"]))

        if problems:
            print("CORPUS VERIFICATION FAILED")
            for p in problems:
                print("  -", p)
            return 1
        print("Corpus verified: %d files, all levels and failing clauses as "
              "recorded%s." % (len(new),
                               ", byte-reproducible" if same_toolchain
                               else " (bytes not compared: toolchain differs)"))
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Build the FITA conformance corpus")
    ap.add_argument("--verify", action="store_true",
                    help="regenerate and check reproducibility + levels")
    args = ap.parse_args(argv)

    if args.verify:
        return verify(ROOT)

    manifest = build_all(ROOT)
    total = sum(e["bytes"] for e in manifest["files"])
    print("FITA corpus v%s" % manifest["format_version"])
    for tier in TIERS:
        n = manifest["counts"][tier]
        print("  %-12s %2d file(s)" % (tier, n))
    print("  %-12s %2d file(s), %.1f KB total"
          % ("TOTAL", len(manifest["files"]), total / 1024))
    return 0


if __name__ == "__main__":
    sys.exit(main())
