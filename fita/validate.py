"""
fita.validate — the FITA conformance checker (v1.1 RATIFIED).

This module is *normative infrastructure*: FITA_FORMAT_STANDARD.md §2.1 requires a
`fita.validate(path) -> ConformanceReport`, and §5.4 requires a bit-for-bit flux
round-trip test per packing mode. A format is only "established" when a machine can say
whether a file conforms — this is that machine.

It is deliberately dependency-light (astropy + numpy only, no uranodyne) so it can ship
as the reference tool and the paper's released software.

Conformance levels (standard §2.1)
----------------------------------
FITA-CORE : every MUST in §§3-7 is satisfied. Minimum for a file to be called .fita.
FITA-FULL : FITA-CORE + every SHOULD in §§3-9 + a conformant FITA_META provenance HDU.

Usage
-----
    from fita import validate
    report = validate("ngc1068.fita")
    print(report)                 # human summary + level
    if not report.is_core:
        for f in report.failures():
            print(f.clause, f.message)
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

import numpy as np

try:
    from astropy.io import fits
    from astropy import units as u
    _ASTROPY = True
except ImportError:  # pragma: no cover - astropy is a hard dependency in practice
    _ASTROPY = False

from .spec import (
    KW_VERSION, KW_PACK, KW_NLAYERS,
    PACK_FLOAT32, PACK_SPLIT16,
    EXTNAME_LAYERS, EXTNAME_META, EXTNAME_ADJ,
    BLEND_CODES, flux_extname, alpha_extname,
)

# The version this checker enforces. Files may declare an older minor version;
# the checker reads them best-effort but reports required v1.1 corrections.
ENFORCED_VERSION = "1.3"

# Severity levels.
MUST = "MUST"      # violation => not conformant at the stated level
SHOULD = "SHOULD"  # violation => conformant at CORE but not FULL
INFO = "INFO"      # advisory only


@dataclass
class Finding:
    """One conformance observation, tied to a clause of the standard."""
    clause: str          # e.g. "S6.3" — where in the standard this comes from
    severity: str        # MUST | SHOULD | INFO
    ok: bool             # True = satisfied, False = violated
    message: str         # human-readable detail
    where: str = ""      # HDU name / keyword the finding is about

    def __str__(self) -> str:
        mark = "PASS" if self.ok else "FAIL"
        loc = f" [{self.where}]" if self.where else ""
        return f"  {mark} {self.severity:6s} {self.clause}{loc}: {self.message}"


@dataclass
class ConformanceReport:
    """The result of validating one .fita file."""
    path: str
    findings: List[Finding] = field(default_factory=list)
    fatal: Optional[str] = None   # set if the file could not even be opened as FITS

    # ── recording ────────────────────────────────────────────────────────────
    def add(self, clause, severity, ok, message, where=""):
        self.findings.append(Finding(clause, severity, ok, message, where))

    def check(self, clause, severity, condition, message, where=""):
        """Convenience: record a pass/fail from a boolean condition."""
        self.add(clause, severity, bool(condition), message, where)
        return bool(condition)

    # ── queries ──────────────────────────────────────────────────────────────
    def failures(self, severity=None):
        return [f for f in self.findings
                if not f.ok and (severity is None or f.severity == severity)]

    @property
    def is_core(self) -> bool:
        """FITA-CORE: no failed MUST, and the file opened as FITS."""
        return self.fatal is None and not self.failures(MUST)

    @property
    def is_full(self) -> bool:
        """FITA-FULL: CORE plus no failed SHOULD (which includes the FITA_META check)."""
        return self.is_core and not self.failures(SHOULD)

    @property
    def level(self) -> str:
        if self.fatal is not None:
            return "NOT-FITS"
        if self.is_full:
            return "FITA-FULL"
        if self.is_core:
            return "FITA-CORE"
        return "NON-CONFORMANT"

    # ── presentation ─────────────────────────────────────────────────────────
    def __str__(self) -> str:
        head = f"FITA conformance: {self.path}\n  LEVEL: {self.level}"
        if self.fatal:
            return head + f"\n  FATAL: {self.fatal}"
        n_must = len(self.failures(MUST))
        n_should = len(self.failures(SHOULD))
        head += f"   ({n_must} MUST failing, {n_should} SHOULD failing)"
        body = "\n".join(str(f) for f in self.findings if not f.ok) or "  (all checks passed)"
        return head + "\n" + body


# ── individual section checks ───────────────────────────────────────────────

def _bunit_is_valid(value) -> bool:
    """S7: BUNIT must parse as a FITS unit. Empty / dimensionless is allowed."""
    if value is None:
        return True
    s = str(value).strip()
    if s == "":
        return True
    try:
        u.Unit(s, parse_strict="raise")
        return True
    except Exception:
        return False


def _check_identification(hdul, r):
    """S3 File identification, §4.2 PRIMARY keywords."""
    phdr = hdul[0].header
    r.check("S3", MUST, phdr.get("SIMPLE", False) is True,
            "PRIMARY SIMPLE = T", "PRIMARY")
    ver = phdr.get(KW_VERSION)
    r.check("S4.2", MUST, ver is not None, f"{KW_VERSION} present", "PRIMARY")
    if ver is not None and str(ver) != ENFORCED_VERSION:
        r.add("S13", INFO, True,
              f"{KW_VERSION}={ver!r}; checker enforces v{ENFORCED_VERSION} rules", "PRIMARY")
    pack = phdr.get(KW_PACK)
    r.check("S4.2", MUST, pack is not None, f"{KW_PACK} present", "PRIMARY")
    r.check("S4.2", MUST, phdr.get(KW_NLAYERS) is not None, f"{KW_NLAYERS} present", "PRIMARY")
    # §3 MIME/access_format overclaim is checked in §9 (it lives in FITA_META).
    return pack


def _check_pack(hdul, r, pack):
    """S6.4 packing modes: SPLIT16 is deprecated and MUST NOT be present."""
    r.check("S6.4", MUST, pack != PACK_SPLIT16,
            f"{KW_PACK} is not the deprecated {PACK_SPLIT16!r} (use {PACK_FLOAT32!r})",
            "PRIMARY")


def _iter_flux_hdus(hdul):
    for hdu in hdul:
        if str(hdu.name).startswith("FLUX_"):
            try:
                idx = int(str(hdu.name).split("_")[1])
            except (IndexError, ValueError):
                continue
            yield idx, hdu


def _check_layout(hdul, r, pack):
    """S4.1 canonical layout, §4.2 layer count consistency."""
    names = [str(h.name) for h in hdul]
    r.check("S4.1", MUST, EXTNAME_LAYERS in names,
            f"{EXTNAME_LAYERS} registry HDU present", EXTNAME_LAYERS)

    flux_idx = [idx for idx, _ in _iter_flux_hdus(hdul)]
    nl = hdul[0].header.get(KW_NLAYERS)
    if nl is not None:
        r.check("S4.2", MUST, len(flux_idx) == int(nl),
                f"{KW_NLAYERS}={nl} matches {len(flux_idx)} FLUX extensions found", "PRIMARY")

    # S4.2 -- ORPHAN TRAILING BYTES.  Failure instance #11, ATOP 2026-08-03:
    # an interrupted re-write left Frame15 of the 130@G archive with 19 of its
    # 26 FLUX extensions, EXACTLY the same byte size as the fourteen good
    # copies, valid FITS, and passing verify().  It was caught only because the
    # dead writer left FITANL stale at 26.  Measured here: had FITANL been
    # updated to match the truncated content, the file would validate CORE+
    # with ZERO MUST failures -- identical size, internally consistent, a third
    # of the science gone.
    #
    # The one signal that survives that repair is bytes beyond the last HDU:
    # astropy mentions it only as "Unexpected extra padding at the end of the
    # file", a warning nobody reads.  Promote it to a finding, because a
    # truncate-then-pad is otherwise invisible to content inspection.
    try:
        fname = getattr(hdul, "filename", lambda: None)()
        if fname and os.path.exists(fname):
            end = max(hd.fileinfo()["datLoc"] + hd.fileinfo()["datSpan"]
                      for hd in hdul)
            trailing = os.path.getsize(fname) - int(end)
            r.check("S4.2", MUST, trailing <= 0,
                    f"no orphan bytes after the last HDU (found {trailing} = "
                    f"{trailing // 2880} FITS blocks); a file padded past its "
                    f"last extension is the signature of an interrupted write",
                    "FILE")
    except Exception:
        pass
    # ascending, contiguous 1..n
    r.check("S4.1", MUST, flux_idx == sorted(flux_idx),
            "FLUX extensions in ascending layer order", "FLUX_*")
    for idx in flux_idx:
        aname = alpha_extname(idx)
        r.check("S4.1", MUST, aname in names,
                f"paired {aname} present for {flux_extname(idx)}", aname)


def _check_layers(hdul, r, pack):
    """S5, §6.2, §6.3, §7, §8 per-layer checks."""
    # PRIMARY-level declaration that governs the per-layer FITA_ZDP domain
    # (v1.4, N-1).  Read once: it is a property of the file, not of a layer.
    from .spec import KW_ZDEPTH_U
    _zdu = hdul[0].header.get(KW_ZDEPTH_U, None)
    zdp_unit = None if _zdu is None else str(_zdu).strip() or None

    for idx, fhdu in _iter_flux_hdus(hdul):
        fh = fhdu.header
        where = flux_extname(idx)

        # §6.2 required layer keywords (header is normative, §4.3)
        for kw in ("FITA_LID", "FITA_LNM", "FITA_BLD", "FITA_OPC", "FITA_ALS", "FITA_VIS"):
            r.check("S6.2", MUST, kw in fh, f"required layer keyword {kw}", where)

        # §8.1 blend mode must be a known code
        bld = fh.get("FITA_BLD")
        if bld is not None:
            r.check("S8.1", MUST, str(bld) in BLEND_CODES,
                    f"FITA_BLD={bld!r} is a defined blend code", where)

        # §6.1 / §5 FLUX dtype under FLOAT32 must be float32
        if pack == PACK_FLOAT32:
            r.check("S6.1", MUST, fh.get("BITPIX") == -32,
                    f"FLUX BITPIX=-32 (float32) under FLOAT32 packing (got {fh.get('BITPIX')})",
                    where)

        # §7 FLUX BUNIT (if present) must be a valid unit
        r.check("S7", SHOULD, _bunit_is_valid(fh.get("BUNIT")),
                f"FLUX BUNIT parseable (got {fh.get('BUNIT')!r})", where)

        # §8.2 FITA_ZDP domain + §4.3/§8.2 no -1 sentinel
        #
        # v1.4 (N-1): the [0,1] domain applies only when PRIMARY declares no
        # FITA_ZDU.  With a unit present, FITA_ZDP carries a physical depth --
        # the archived Edenhofer cubes hold parsecs -- and constraining it to
        # [0,1] would condemn correct science data for a missing declaration
        # that is now declarable.  Absence stays the strict case, so no
        # existing conformant file changes meaning.
        if "FITA_ZDP" in fh:
            try:
                z = float(fh["FITA_ZDP"])
                if zdp_unit is None:
                    r.check("S8.2", MUST, 0.0 <= z <= 1.0,
                            f"FITA_ZDP in [0,1] (got {z}); absence must omit the keyword, "
                            f"not use a sentinel", where)
                else:
                    r.check("S8.2", MUST, bool(np.isfinite(z)),
                            f"FITA_ZDP is a finite depth in {zdp_unit!r} (got {z})", where)
            except (TypeError, ValueError):
                domain = "a float in [0,1]" if zdp_unit is None else f"a float in {zdp_unit!r}"
                r.check("S8.2", MUST, False, f"FITA_ZDP is {domain}", where)

        # §6.3 ALPHA encoding: unsigned-16 via BZERO=32768, no 'alpha16' BUNIT
        aname = alpha_extname(idx)
        try:
            ahdu = hdul[aname]
        except KeyError:
            continue  # missing pair already reported in §4.1
        ah = ahdu.header
        r.check("S6.3", MUST, ah.get("BITPIX") == 16,
                f"ALPHA BITPIX=16 (got {ah.get('BITPIX')})", aname)
        r.check("S6.3", MUST, ah.get("BZERO") == 32768,
                f"ALPHA BZERO=32768 unsigned-16 convention (got {ah.get('BZERO')})", aname)
        r.check("S6.3", MUST, ah.get("BSCALE", 1) in (1, 1.0),
                f"ALPHA BSCALE=1 (got {ah.get('BSCALE')})", aname)
        r.check("S6.3/S7", MUST, str(ah.get("BUNIT", "")).strip().lower() != "alpha16",
                "ALPHA header does not declare the invalid BUNIT 'alpha16'", aname)

        # §7 UNCERT BUNIT must be a real unit, not the note 'same as FLUX'
        uname = fh.get("FITA_UNC")
        if uname:
            try:
                uh = hdul[str(uname)].header
                bad = str(uh.get("BUNIT", "")).strip().lower() == "same as flux"
                r.check("S7", MUST, not bad,
                        "UNCERT BUNIT is a real unit, not the note 'same as FLUX'", str(uname))
                r.check("S7", SHOULD, _bunit_is_valid(uh.get("BUNIT")),
                        f"UNCERT BUNIT parseable (got {uh.get('BUNIT')!r})", str(uname))
            except KeyError:
                r.check("S6.5", MUST, False,
                        f"FITA_UNC points to missing extension {uname!r}", where)


def _check_spectral_frame(hdul, r):
    """S8.5 -- the spectral reference frame of a velocity cube (v1.5).

    Author ruling, 2026-08-03: the LSR is ADOPTED, not established. Published
    V_sun spans 5.2 to 14.6 km/s while ALMA and HI cubes are channelised at
    0.1-1 km/s, so a cube whose labels were computed under one convention and
    are read under another is mislabelled by more than its own resolution. A
    cube that does not declare its frame is therefore not reproducible: its
    labels cannot be recomputed. See fita.lsr.
    """
    from .spec import (KW_SPECSYS, KW_VELOSYS, KW_VELOSYS_E, KW_ZDEPTH_U,
                       KW_ZDEPTH_EP, KW_CDELT3, KW_CUNIT3)
    from .lsr import SPECSYS_VALUES, VOCABULARY, channel_width_verdict

    hdr = hdul[0].header
    where = "PRIMARY"

    specsys = hdr.get(KW_SPECSYS)
    has_velosys = KW_VELOSYS in hdr
    has_vse = KW_VELOSYS_E in hdr

    # A frame velocity with no frame named is not interpretable.
    if has_velosys:
        r.check("S8.5", MUST, specsys is not None,
                f"{KW_VELOSYS} present requires {KW_SPECSYS}: a frame velocity "
                f"with no frame named is not interpretable", where)

    # Same reasoning as FITA_ZSC-without-FITA_FDI: an uncertainty on nothing.
    if has_vse:
        r.check("S8.5", MUST, has_velosys,
                f"{KW_VELOSYS_E} is the uncertainty on {KW_VELOSYS} and "
                f"requires it; an uncertainty on nothing is not a measurement",
                where)

    if specsys is not None:
        r.check("S8.5", SHOULD, str(specsys).strip().upper() in SPECSYS_VALUES,
                f"{KW_SPECSYS}={specsys!r} is a FITS WCS Paper III frame "
                f"({', '.join(SPECSYS_VALUES)})", where)

    # Ruling A: the epistemic label is an AXIS property, and its vocabulary is
    # closed (Ruling C added ADOPTED as the fourth term).
    if KW_ZDEPTH_EP in hdr:
        val = str(hdr[KW_ZDEPTH_EP]).strip().upper()
        r.check("S8.5", MUST, val in VOCABULARY,
                f"{KW_ZDEPTH_EP}={val!r} is one of {', '.join(VOCABULARY)}", where)

    # A velocity-valued depth axis without a declared frame: the labels exist
    # but cannot be recomputed under a different convention.
    zdu = hdr.get(KW_ZDEPTH_U)
    if zdu is not None and specsys is None:
        try:
            from astropy import units as u
            is_velocity = u.Unit(str(zdu)).is_equivalent(u.km / u.s)
        except Exception:
            is_velocity = False
        if is_velocity:
            r.check("S8.5", SHOULD, False,
                    f"{KW_ZDEPTH_U}={zdu!r} is a velocity but no {KW_SPECSYS} "
                    f"is declared; the slice labels cannot be recomputed under "
                    f"another convention, so the cube is not reproducible", where)

    # The error bar entering the pipeline: warn when the frame uncertainty is
    # wider than the channel spacing -- the cube resolves velocities it cannot
    # place. The historical revisions land squarely in this regime.
    if has_vse and KW_CDELT3 in hdr:
        try:
            from astropy import units as u
            cu = u.Unit(str(hdr.get(KW_CUNIT3) or "m/s"))
            width = abs(float(hdr[KW_CDELT3])) * cu.to(u.km / u.s)
            vse = abs(float(hdr[KW_VELOSYS_E])) * u.Unit("m/s").to(u.km / u.s)
            msg = channel_width_verdict(vse, width)
            r.check("S8.5", SHOULD, msg is None,
                    msg or "LSR uncertainty is within the channel width", where)
        except Exception:
            pass


def _check_zdp_scale(hdul, r):
    """S8.2 / D-6 stereo geometry -- OPTIONAL, but meaningful when present."""
    from .spec import (KW_ZSCALE, KW_ZREF, KW_ZANG, KW_DEPTH,
                       KW_FIELD_DIA, KW_FIELD_UNI, KW_ZDEPTH_U)

    hdr = hdul[0].header

    def _finite(kw):
        """(present, value, is_finite) for a numeric keyword."""
        if kw not in hdr:
            return False, None, True
        try:
            v = float(hdr[kw])
            return True, v, bool(np.isfinite(v))
        except (TypeError, ValueError):
            return True, None, False

    has_scale, scale, scale_ok = _finite(KW_ZSCALE)
    has_ref, ref, ref_ok = _finite(KW_ZREF)
    has_ang, ang, ang_ok = _finite(KW_ZANG)
    has_dia, dia, dia_ok = _finite(KW_FIELD_DIA)

    for kw, present, ok in ((KW_ZSCALE, has_scale, scale_ok),
                            (KW_ZREF, has_ref, ref_ok),
                            (KW_ZANG, has_ang, ang_ok),
                            (KW_FIELD_DIA, has_dia, dia_ok)):
        if present:
            r.check("S8.2", MUST, ok,
                    f"{kw} is a finite number (got {hdr[kw]!r})", "PRIMARY")

    # v1.4: the units must be real FITS units, or the "practical to the
    # subject" half of the ruling records a string nobody can act on.
    for kw in (KW_FIELD_UNI, KW_ZDEPTH_U):
        if kw in hdr:
            r.check("S8.2", MUST, _bunit_is_valid(hdr[kw]),
                    f"{kw} is a valid FITS unit string (got {hdr[kw]!r})", "PRIMARY")

    # A declared field diameter must be a real extent.  Zero or negative would
    # make the parallax formula divide the depth budget into nothing.
    if has_dia and dia_ok:
        r.check("S8.2", MUST, dia > 0,
                f"{KW_FIELD_DIA}={dia:g} is a positive diameter", "PRIMARY")
        r.check("S8.2", SHOULD, KW_FIELD_UNI in hdr,
                f"{KW_FIELD_DIA} is accompanied by {KW_FIELD_UNI}; a number "
                "without a unit is not a measure practical to the subject",
                "PRIMARY")

    if has_ref and ref_ok:
        # The reference plane names a point on the ZDP axis, so it has to lie
        # on it; otherwise every layer is pushed to one side of the screen.
        r.check("S8.2", SHOULD, 0.0 <= ref <= 1.0,
                f"{KW_ZREF}={ref:g} lies within the ZDP domain [0,1]", "PRIMARY")

    if not has_scale or not scale_ok:
        return

    # ── the clause that enforces the ruling ──────────────────────────────────
    # FITA_ZSC is a PERCENTAGE of FITA_FDI (v1.4).  Without the field it is a
    # percentage of nothing, which is not a measurement -- the exact failure
    # the pixel-count convention had, restated.  MUST, not SHOULD: a stereo
    # record that cannot be converted to a physical separation does not record
    # a stimulus at all.
    r.check("S8.2", MUST, has_dia,
            f"{KW_ZSCALE} is present, so {KW_FIELD_DIA} MUST be too: "
            f"{KW_ZSCALE} is a percentage of the field diameter and a "
            "percentage of nothing is not a measurement", "PRIMARY")
    r.check("S8.2", MUST, KW_FIELD_UNI in hdr,
            f"{KW_ZSCALE} is present, so {KW_FIELD_UNI} MUST be too: the field "
            "diameter must be stated in a unit practical to the subject",
            "PRIMARY")

    # A parallax scale with nothing to scale records a stimulus that was never
    # applied.  Not fatal -- it may be a renderer default on a flat cube --
    # but it should not pass silently.
    has_depth = any(KW_DEPTH in h.header for h in hdul
                    if str(h.name).startswith("FLUX_"))
    r.check("S8.2", SHOULD, has_depth or scale == 0.0,
            f"{KW_ZSCALE}={scale:g} but no layer carries {KW_DEPTH}; "
            "the recorded parallax applies to nothing", "PRIMARY")

    # FITA_ZAN is RETIRED in v1.4, by dissolution.  The old check required an
    # angular measure or a WCS to deduce one from; that requirement is gone,
    # because FITA_FDI/FITA_FDU now carry the absolute half of the metric chain
    # in whatever unit suits the subject.  Files written before v1.4 still
    # carry FITA_ZAN and MUST still read (D-1), so its presence is not an
    # error -- but a writer emitting it now is producing a keyword the
    # standard no longer defines.
    if has_ang:
        r.check("S8.2", SHOULD, False,
                f"{KW_ZANG} is retired in v1.4 (dissolved: the separation "
                f"follows from {KW_FIELD_DIA}/{KW_FIELD_UNI} by arithmetic). "
                "Readers must still accept it; writers should not emit it",
                "PRIMARY")


def _check_adjustments(hdul, r):
    """S8 FITA_ADJ -- optional, but if present it MUST be well formed.

    The stack is display state, so a malformed table costs no flux; it does,
    however, cost the reproducibility of how a figure was made, which is the
    reason D-3 ruled to serialise it in the first place.  An adjustment that
    cannot be reconstructed is indistinguishable from one that was never
    applied.
    """
    names = [str(h.name) for h in hdul]
    if EXTNAME_ADJ not in names:
        return                              # absence is legal at every level

    adj = hdul[EXTNAME_ADJ]
    cols = set(getattr(adj.columns, "names", []) or [])
    required = {"ORDER", "ADJ_TYPE", "ENABLED", "NAME", "LAYER_ID", "PARAMS"}
    missing = sorted(required - cols)
    r.check("S8", MUST, not missing,
            "FITA_ADJ has the required columns"
            + (f"; missing: {', '.join(missing)}" if missing else ""),
            EXTNAME_ADJ)
    if missing:
        return

    try:
        from .adjustment import ADJ_REGISTRY
        types = [str(v).strip() for v in np.atleast_1d(adj.data["ADJ_TYPE"])]
    except Exception:
        return
    unknown = sorted({t for t in types if t and t not in ADJ_REGISTRY})
    r.check("S8", MUST, not unknown,
            "every ADJ_TYPE is a known adjustment code"
            + (f"; unknown: {', '.join(unknown)}" if unknown else ""),
            EXTNAME_ADJ)

    # PARAMS must be parseable, or the adjustment cannot be rebuilt.
    bad = []
    try:
        for i, raw in enumerate(np.atleast_1d(adj.data["PARAMS"])):
            text = str(raw).strip()
            if not text:
                continue
            try:
                json.loads(text)
            except Exception:
                bad.append(str(i))
    except Exception:
        return
    r.check("S8", MUST, not bad,
            "every PARAMS cell is valid JSON"
            + (f"; unparseable rows: {', '.join(bad)}" if bad else ""),
            EXTNAME_ADJ)


def _check_provenance(hdul, r):
    """S9 FITA_META — required only at FITA-FULL, so recorded as SHOULD."""
    names = [str(h.name) for h in hdul]
    present = EXTNAME_META in names
    r.check("S9", SHOULD, present,
            f"{EXTNAME_META} provenance HDU present (required for FITA-FULL)", EXTNAME_META)
    if not present:
        return
    meta = hdul[EXTNAME_META]
    cols = set(getattr(meta.columns, "names", []) or [])
    # ObsCore v1.1 mandatory columns (D-4 full-conformance target).
    # ObsCore DM v1.1 mandatory columns -- 30, as read from Table 1 of the
    # Recommendation by ATOP (BTOP could not extract the table from the REC
    # PDF and does not claim to have verified it independently).
    #
    # There is NO ObsCore v1.2; see ERRATUM__ObsCore_version__2026-08-02.md.
    # pol_xel and t_resolution were absent here until ATOP's audit found them.
    obscore_mandatory = {
        "dataproduct_type", "calib_level", "obs_collection", "obs_id",
        "obs_publisher_did", "access_url", "access_format", "access_estsize",
        "target_name", "s_ra", "s_dec", "s_fov", "s_region", "s_resolution",
        "s_xel1", "s_xel2", "t_min", "t_max", "t_exptime", "t_resolution",
        "t_xel", "em_min", "em_max", "em_res_power", "em_xel", "o_ucd",
        "pol_states", "pol_xel", "facility_name", "instrument_name",
    }
    missing = sorted(obscore_mandatory - cols)
    r.check("S9", SHOULD, not missing,
            f"ObsCore v1.1 mandatory columns present"
            + (f"; missing: {', '.join(missing)}" if missing else ""),
            EXTNAME_META)
    # §9 semantic annotation: per-column UCDs must be written as TUCDn.
    has_tucd = any(k.startswith("TUCD") for k in meta.header.keys())
    r.check("S9", SHOULD, has_tucd,
            "per-column UCDs written as TUCDn keywords", EXTNAME_META)
    # §3 MIME honesty: access_format must not claim the unregistered type.
    try:
        af = meta.data["access_format"]
        bad = any(str(v).strip() == "application/fits+alpha" for v in np.atleast_1d(af))
        r.check("S3", MUST, not bad,
                "access_format is not the unregistered 'application/fits+alpha'", EXTNAME_META)
    except Exception:
        pass


# ── public entry point ───────────────────────────────────────────────────────

def validate(path: str | Path) -> ConformanceReport:
    """Validate a .fita file against FITA_FORMAT_STANDARD.md v1.1 and return a report."""
    r = ConformanceReport(path=str(path))
    if not _ASTROPY:
        r.fatal = "astropy is required for validation: pip install astropy"
        return r
    try:
        hdul = fits.open(str(path))
    except Exception as e:
        r.fatal = f"could not open as FITS: {e}"
        return r
    try:
        # §1.2 a conformant .fita MUST be a valid FITS file.
        try:
            hdul.verify("exception")
            r.add("S1.2", MUST, True, "valid FITS (verify passed)", "file")
        except Exception as e:
            r.add("S1.2", MUST, False, f"FITS verify failed: {e}", "file")

        pack = _check_identification(hdul, r)
        _check_pack(hdul, r, pack)
        _check_layout(hdul, r, pack)
        _check_layers(hdul, r, pack)
        _check_zdp_scale(hdul, r)
        _check_spectral_frame(hdul, r)
        _check_adjustments(hdul, r)
        _check_provenance(hdul, r)
    finally:
        hdul.close()
    return r


def flux_roundtrip_ok(layers, pack=PACK_FLOAT32, tmp_path: str | Path = None) -> bool:
    """
    §5.4: the flux/alpha invariant MUST be enforced by a bit-for-bit flux comparison
    across a write/read cycle, for every packing mode the implementation offers.

    Returns True iff every layer's FLUX_* array is reproduced exactly (array_equal).
    Under FLOAT32 this MUST hold. (SPLIT16 is deprecated and is expected to fail /
    raise — that failure is the point.)
    """
    from .io import write, read  # local import to avoid a cycle at module load
    import tempfile, os

    cleanup = False
    if tmp_path is None:
        fd, tmp_path = tempfile.mkstemp(suffix=".fita")
        os.close(fd)
        cleanup = True
    try:
        write(tmp_path, layers, pack=pack, overwrite=True)
        back = read(tmp_path)
        if len(back) != len(layers):
            return False
        by_id = {l.layer_id: l for l in back}
        for src in layers:
            dst = by_id.get(src.layer_id)
            if dst is None:
                return False
            a = np.asarray(src.flux_data, dtype=np.float32)
            b = np.asarray(dst.flux_data, dtype=np.float32)
            if a.shape != b.shape:
                return False
            # Bit-exact, but NaN-aware: real astronomical images carry blanked pixels,
            # and NaN != NaN would make a plain array_equal fail on every such file.
            # NaN must land on NaN, and every other pixel must match exactly.
            both_nan = np.isnan(a) & np.isnan(b)
            if not np.array_equal(np.isnan(a), np.isnan(b)):
                return False
            if not np.array_equal(a[~both_nan], b[~both_nan]):
                return False
        return True
    finally:
        if cleanup:
            try:
                os.remove(tmp_path)
            except OSError:
                pass
