# SLATE ADDENDUM 1 — the phased stereogram, and a defect in v1.4

**Prepared by:** BTOP, 2026-08-03
**Extends:** `FITA_DECISION_SLATE__stereo_metrology__2026-08-02.md`
**Contains:** one defect in shipped v1.4 text, three new decisions (D-14…D-16), one publication
directive registered.

---

## 1. A defect in the v1.4 clause I wrote yesterday

The framework says: for a velocity distribution, the horizontal shift **cannot** be assigned to an
effective apparent distance in model space.

**v1.4 permits exactly that claim, and its clause text asserts it.** ▣ Measured:

```
FITA_ZDU = 'km/s', depths -40 / 0 / +40, field 1200 pc
  conformance : CORE+          MUST failures : 0
```

A velocity cube validates cleanly — the *mechanism* is right, because `FITA_ZDU` only governs
normalisation and never propagates into `dx`. But §8.2.3 says:

> *"`FITA_ZDP` carries a **physical depth** in `FITA_ZDU`"*

and `spec.py` repeats it. **For `km/s` that sentence is false**, and nothing in the file marks the
difference. A reader cannot tell whether the parallax it computes is recoverable as a distance or
is a presentation device with no distance claim in it.

This is the N-1 shape, one turn later: the values are right, the *declaration* is missing. I
generalised `FITA_ZDU` to "any valid FITS unit" and then described it as though every unit were a
length. Owning it plainly — the wording shipped yesterday and should be corrected in whatever
version carries these decisions.

### Why this matters more than a wording fix

The `phased stereo` document states the open question exactly:

> *"whether the perceived depth of data so arranged is a presentation of the data flux or a capture
> of the form of nature, is a verification that must emerge from the scientific consensus."*

That is the right epistemic position, and **the format must not be able to prejudge it.** A
velocity cube that silently reports an "effective apparent distance" would be asserting, in a
header, the very thing said to await consensus — that spectral shift encodes spatial distribution.
The non-metric marking is therefore not bookkeeping. **It is the guardrail that keeps the file
honest about an unresolved question**, and it belongs in the standard for that reason.

---

## 2. D-14 · The z-axis is one of three kinds, and it is derivable

Not two kinds but three. ▣ Measured against `astropy.units`:

| `FITA_ZDU` | dimension | What the parallax means |
|---|---|---|
| `pc` `km` `AU` `m` | **length** | **Effective apparent distance in model space** — recoverable, algebraically or trigonometrically, from the expected distance to the phenomena |
| `deg` `arcsec` | **angle** | Sky-projected separation; a distance only once a distance is supplied |
| `km/s` `Hz` `MHz` | **neither** | **Apparent z only** — presentable against the frame scale at the distance where science places the phenomena; **no distance claim** |
| *absent* | dimensionless | v1.2 `[0,1]` behaviour, unchanged |

**Recommend: derive, do not store.** `astropy.units` already resolves this from `FITA_ZDU`
(`u.Unit(zdu).is_equivalent(u.m)`), astropy is a hard dependency, and storing a kind alongside the
unit records the same fact twice — the `DISTANPC` defect, which is what this project keeps
tripping on. Consistent with D-12.

One exception needs an escape hatch: a cube whose axis is *in* parsecs but where the parsec is a
proxy rather than a measured distance. Recommend an optional `FITA_ZKN` override, absent by
default, used only to *demote* a length axis to non-metric — never to promote.

**Validator consequence:** a renderer or legend **MUST NOT** report an effective apparent distance
in model space for a non-length axis. `fita stereo legend` reports "apparent z, no distance claim"
instead.

---

## 3. D-15 · Phased stereo — what carries the depth? **Cannot be guessed**

The profile modulates keywords FITA already has. `FITA_XOF` / `FITA_YOF` are the per-layer lateral
offsets; a phased stereogram makes them **periodic** rather than static. That is a good sign for
the design — it extends an existing mechanism instead of building a parallel one.

What is not determined by anything on record is **which property of the oscillation encodes depth**:

| Option | Reading | Consequence |
|---|---|---|
| (a) **Amplitude** ∝ depth, common phase | Wiggle/parallax animation; depth from differential excursion | `FITA_ZSC` already *is* this amplitude — no new keyword for x |
| (b) **Phase** offset ∝ depth, common amplitude | Literally "phased"; depth from temporal ordering | Needs a phase keyword; amplitude becomes a single global |
| (c) Both | Amplitude sets the budget, phase sets the traversal | Richest, most keywords, matches the §8.4 "boxcar traversal" sketch |

The name *phased*, and *"the phasing of data channels of increasing energy"*, point away from pure
(a). But the statement that *"these periodic displacements can be resolved to an effective apparent
distance"* reads as amplitude-carried. **Not guessing between them** — the answer determines the
keyword set, and a wrong guess would put structure in code ahead of the standard for the fourth
time.

Draft keywords, subject to D-15:

| Keyword | Meaning |
|---|---|
| `FITA_ZSC` | x amplitude, % of `FITA_FDI` — **exists** |
| `FITA_PAY` | y amplitude, % of `FITA_FDI` — the isometric axis |
| `FITA_PPD` | period of the traversal |
| `FITA_PPH` | phase offset — **only if (b) or (c)** |

---

## 4. D-16 · The isometric presentation, and what the y axis simulates

Periodic **y** displacement gives an **isometric** presentation. In the Edenhofer exercises x and y
were both varied, and they simulate two different things:

- **x** — variable interpupillary separation (the yesterday's 4.70 pc baseline, made to breathe)
- **y** — the observer's **vertical position relative to the galactic plane**

That second one is not a display trick; it is an observer-placement claim. A viewer rising above
and settling below the plane is being shown a viewpoint no instrument occupies. By the same logic
that requires the interpupillary expansion to be declared, **the y excursion should be declared in
the subject's units** — how far above and below the plane the synthetic observer travels.

**Recommend:** `FITA_PAY` as a percentage of `FITA_FDI`, exactly parallel to `FITA_ZSC`, so the
legend can report it as a physical excursion in `FITA_FDU`.

### Why the profile exists at all — worth stating in the clause

The framework's comparative claim belongs in the standard's rationale, because it is the reason to
implement a second stereo mode rather than one:

> The depth stimulus is as strong as cross-stereo and as LBAS. **LBAS must contend with apparent
> vertical exaggeration at large convergence angles; the phased stereogram has no convergence
> angle, so it does not.**

And the efficiency claim, which is the practical case: the phased approach substituted the heavy
voxel computation such stimuli would otherwise need, and runs **live in HTML or a Jupyter
notebook**. For velocity cubes the perceptual result is reported as far superior to studying slices
in a grid — which is precisely the presentation A&A and ApJ use for CO velocity slices, and the
problem the method was invented to solve.

---

## 5. Registered — publication priority

> *"note to MWVO publisher: those exercises are top priority for academic publication."*

Registered against BTOP's publication remit. Source located: `ISM_Motion_new/phased stereo.odt`
(4,439 words, open at time of reading — read-only, untouched).

What it contains that a paper needs, and what it still needs:

**Has.** The origin — phased stereo arose from radio velocity diagrams published as contour grids
in A&A and ApJ. The method — luminance-masked wavelength composition of the ISM at scale, velocity
cube by slices conforming to dense dust, corroborated against ionised HII density along the line of
sight. The corroboration — phasing channels of increasing energy, hence increasing penetration
through dust-dense arms; demonstrated with ROSAT, Fermi and BAT flux. The lineage — Disney's 1937
multiplane camera through matte/keyhole compositing, NTSC switchers and AMPEX, chroma key, then
luminance-modulated chroma key. And, importantly, a correctly stated open question rather than an
overclaim.

**Needs, before submission.**
1. **Attribution check.** Two influences are named — David Malin (secure) and "Daphny Halas" (I
   cannot verify this spelling or identity). An academic paper cannot carry an unverified personal
   attribution; worth confirming who is meant.
2. The Doppler/medium argument in §2 of that document is a **paradigm claim**, not a
   presentation claim. It belongs with [[project_unphysics]], and mixing it into a methods paper
   would give a reviewer a reason to reject the method for the framing. Recommend separating:
   the method paper stands on the perceptual and corroboration results alone.
3. Figures require the metrology this slate defines — a phased stereogram figure without its
   declared baseline, excursion and z-kind is the undeclared-geometry defect in print.

**Recommendation on sequencing:** the exercises cannot be published as figures until D-14 is ruled,
because a velocity-cube figure that implies a distance is the error this addendum exists to
prevent. D-14 is cheap to rule and unblocks the publication track.

---

## 6. What is asked

Added to the slate's D-9…D-13:

- **D-14** — z-axis kind: three-way, derived from `FITA_ZDU`; `FITA_ZKN` as demote-only override.
  *Recommended, and it gates the publication track.*
- **D-15** — phased depth carried by amplitude, phase, or both. **Blocking; not guessable.**
- **D-16** — `FITA_PAY` for the isometric/observer-elevation axis, declared as a physical excursion.

Still nothing implemented. The v1.4 wording defect in §1 is the only item that is not a proposal —
that one is a correction owed regardless of how the decisions land.
