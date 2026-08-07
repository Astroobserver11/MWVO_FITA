"""
fita.lsr -- the Local Standard of Rest is ADOPTED, and this module says so.

Author ruling, 2026-08-03: labelling the LSR "established" is dubious; it is
*adopted*.  An adopted value is one the community agrees to use so results are
comparable, which is a different epistemic act from measuring something.

That distinction is not pedantry.  The Sun's peculiar velocity along Galactic
rotation, V_sun, has moved by more than a factor of two across the refereed
literature, and the single 1998 -> 2010 revision moved it by 7 km/s.  ALMA and
HI cubes are routinely channelised at 0.1-1 km/s, so that revision is 7 to 70
CHANNELS.  A cube whose slice labels were computed under one convention and are
read under another is mislabelled by more than its own resolution.

So a velocity cube that does not record the frame it used is not reproducible:
its labels cannot be recomputed.  This module carries the published spread so a
file can be checked against it rather than against an assumption.

What the FITS standard already provides (adopt these; do not mint twins):

    SPECSYS   spectral reference frame -- 'LSRK', 'BARYCENT', 'TOPOCENT', ...
    VELOSYS   velocity of that frame w.r.t. the observer, m/s
    SSYSOBS   frame the observation was actually taken in, usually 'TOPOCENT'
    RESTFRQ / RESTWAV, CTYPE3 / CRVAL3 / CDELT3

What it does NOT provide, and why FITA_VSE exists (D-17): FITS defines VELOSYS
but no companion UNCERTAINTY keyword.  The standard is silent here, not
contradicted, which is the one condition under which minting a FITA_ name is
justified.

All bibliographic values below were retrieved from NASA ADS on 2026-08-03 and
are quoted as published.  Nothing here is asserted from recall.
"""

from __future__ import annotations

from typing import List, NamedTuple, Optional

# Ruling C, 2026-08-03 -- the epistemic vocabulary, four terms.
ESTABLISHED = "ESTABLISHED"   # fixed by measurement or an external standard
ADOPTED     = "ADOPTED"       # a convention agreed for comparability
INFERRED    = "INFERRED"      # derived from an observable through a model
PROPOSED    = "PROPOSED"      # asserted by the author, awaiting acceptance
VOCABULARY  = (ESTABLISHED, ADOPTED, INFERRED, PROPOSED)

# The epistemic status of the LSR itself.  Stated once, here, so no caller has
# to decide it.
LSR_STATUS = ADOPTED

# FITS WCS Paper III spectral reference frames.
SPECSYS_VALUES = (
    "TOPOCENT", "GEOCENT", "BARYCENT", "HELIOCEN",
    "LSRK", "LSRD", "GALACTOC", "LOCALGRP", "CMBDIPOL", "SOURCE",
)


class Determination(NamedTuple):
    """One published determination of the solar motion w.r.t. the LSR."""
    bibcode: str
    author: str
    year: int
    v_sun: float                  # km/s, along Galactic rotation
    v_err: Optional[float]        # km/s, or None where not quoted as symmetric
    method: str
    note: str = ""

    @property
    def ads_url(self) -> str:
        return "https://ui.adsabs.harvard.edu/abs/" + self.bibcode


# --- V_sun, the contested component -----------------------------------------
#
# Retrieved from ADS 2026-08-03, sorted oldest first so the drift is visible.
DETERMINATIONS: List[Determination] = [
    Determination(
        "1998MNRAS.298..387D", "Dehnen & Binney", 1998, 5.2, None,
        "Hipparcos local stellar kinematics",
        "Value not quoted directly here: Schonrich et al. (2010) state in their "
        "own abstract that V_solar is 7 km/s larger than previously estimated, "
        "and 12.24 - 7 = 5.2. Recorded as DERIVED from a primary source rather "
        "than asserted from recall."),
    Determination(
        "2010MNRAS.403.1829S", "Schonrich, Binney & Dehnen", 2010, 12.24, 0.47,
        "chemodynamical model of local kinematics",
        "The revision. Also gives U = 11.1 (+0.69/-0.75), W = 7.25 (+0.37/-0.36)."),
    Determination(
        "2011MNRAS.412.1237C", "Coskunoglu et al.", 2011, 13.0, None,
        "RAVE survey kinematics",
        "Quoted as favouring values near 13 km/s, explicitly 'in disagreement "
        "with earlier studies'."),
    Determination(
        "2014ApJ...783..130R", "Reid et al. (BeSSeL)", 2014, 14.6, 5.0,
        "VLBI trigonometric parallaxes of high-mass star-forming regions",
        "Theta_0 and V_sun are strongly correlated; only the SUM is well "
        "constrained, at Theta_0 + V_sun = 255.2 +/- 5.1 km/s. That correlation "
        "is why the split is model-dependent, and why the value is adopted "
        "rather than measured."),
]

# --- the quasar-based inertial frame ----------------------------------------
#
# IMPORTANT DISTINCTION, so a caller does not overclaim: quasars establish the
# inertial FRAME and measure the barycentre's ACCELERATION.  They do NOT measure
# the Sun's peculiar velocity w.r.t. the LSR -- that remains stellar kinematics,
# which is where the disagreement above lives.  The frame is rigorous; the LSR
# offset is adopted.  Both belong in a legend and they are not the same fact.
FRAME_REFERENCES = [
    ("2021A&A...649A...9G", "Gaia EDR3 (Klioner et al.)", 2021,
     "Solar System acceleration (2.32 +/- 0.16)e-10 m/s^2 = 7.33 +/- 0.51 "
     "km/s/Myr toward RA 269.1 +/- 5.4 deg, Dec -31.6 +/- 4.1 deg, from quasar "
     "proper motions"),
    ("2011A&A...529A..91T", "Titov et al.", 2011,
     "VLBI measurement of the secular aberration drift -- the precursor technique"),
    ("2017ApJS..233....3T", "Truebenbach & Darling", 2017,
     "VLBA extragalactic proper motion catalogue; independent aberration drift"),
    ("2019A&A...625L..10G", "GRAVITY Collaboration", 2019,
     "Geometric distance to the Galactic centre black hole, R_0 to 0.3 per cent"),
    ("2010MNRAS.402..934M", "McMillan", 2010,
     "'The uncertainty in Galactic parameters' -- the correlated error budget"),
]


def v_sun_spread() -> tuple:
    """(min, max, peak-to-peak) of published V_sun, in km/s.

    The peak-to-peak is the number that matters operationally: it is the
    systematic by which two equally defensible labellings of the same cube can
    differ.
    """
    vs = [d.v_sun for d in DETERMINATIONS]
    return min(vs), max(vs), max(vs) - min(vs)


def channel_width_verdict(velosys_err_kms: Optional[float],
                          channel_width_kms: Optional[float]) -> Optional[str]:
    """Warn when the frame uncertainty is wider than the channel spacing.

    That is the regime in which the slice labels are less certain than their own
    spacing -- the cube resolves velocities it cannot place.  Returns None when
    there is nothing to say, so a caller can treat truthiness as "warn".
    """
    if velosys_err_kms is None or channel_width_kms is None:
        return None
    if channel_width_kms <= 0:
        return None
    if velosys_err_kms > channel_width_kms:
        return ("LSR uncertainty %.3g km/s exceeds the channel width %.3g km/s "
                "(%.1f channels): the slice labels are less certain than their "
                "own spacing" % (velosys_err_kms, channel_width_kms,
                                 velosys_err_kms / channel_width_kms))
    return None


def describe(velosys_kms: Optional[float] = None,
             velosys_err_kms: Optional[float] = None,
             specsys: Optional[str] = None,
             channel_width_kms: Optional[float] = None) -> str:
    """Human-readable account of the frame a cube declares, and its standing."""
    lo, hi, ptp = v_sun_spread()
    lines = [
        "Local Standard of Rest -- status: %s (author ruling 2026-08-03)" % LSR_STATUS,
        "",
        "  frame declared   : %s" % (specsys or "NOT DECLARED -- labels are not recomputable"),
    ]
    if velosys_kms is not None:
        err = "" if velosys_err_kms is None else " +/- %.3g" % velosys_err_kms
        lines.append("  VELOSYS          : %.4g%s km/s" % (velosys_kms, err))
    if velosys_err_kms is None:
        lines.append("  VELOSYS error    : not recorded (FITA_VSE absent)")

    lines += [
        "",
        "  Published V_sun spans %.3g to %.3g km/s (peak-to-peak %.3g km/s):" % (lo, hi, ptp),
    ]
    for d in DETERMINATIONS:
        err = "" if d.v_err is None else " +/- %.3g" % d.v_err
        lines.append("    %-28s %5.4g%-9s km/s  %s" % (d.author + " " + str(d.year),
                                                       d.v_sun, err, d.bibcode))
    warn = channel_width_verdict(velosys_err_kms, channel_width_kms)
    if warn:
        lines += ["", "  WARNING: " + warn]
    lines += [
        "",
        "  Quasars fix the inertial FRAME and the barycentre's ACCELERATION;",
        "  they do not measure the Sun's peculiar velocity w.r.t. the LSR.",
        "  The frame is rigorous, the LSR offset is adopted -- not the same fact.",
    ]
    return "\n".join(lines)
