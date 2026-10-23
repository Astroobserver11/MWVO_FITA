# 07. UBC 525 / PSR B1259-63 Deep Dive: Gaia, Pulsar, and ISM Tracers

**Date:** 2026-10-23
**Stage:** 7 of 7 (final)
**Question:** Investigate UBC 525 and PSR B1259-63 with Gaia kinematics and ISM radial-velocity tracers (HI, CO, optical absorption), focusing on systems within 1 kpc where Gaia is most reliable.

*Full report also saved as:* `docs/UBC525_B1259-63_kinematics_ISM_tracers.md` *(commit d88e09cf)*

---

## 7.1 UBC 525 cluster parameters (Gaia DR3)

| Parameter | Value |
|---|---|
| Galactic longitude | 304.2 deg |
| Galactic latitude | -1.0 deg |
| Distance | 2.26 +- 0.07 kpc (parallax 0.44 mas) |
| Proper motion (mu_alpha*, mu_delta) | -4.14, -1.20 mas/yr |
| Age | ~11.7 Myr |
| Mass | ~414 solar masses |
| Max stellar mass | ~7.5 solar masses |
| Environment | Sagittarius Arm; Cen OB1 complex at ~2.6 kpc |

Modest cluster: low mass, intermediate age. Value is positional — rich, multi-arm line of sight with well-characterized gas layers.

## 7.2 PSR B1259-63 / LS 2883 kinematics

- Pulsar: 47.7 ms, eccentric orbit (e~0.87), period 1236.7 days
- Companion: LS 2883, Be star, ~16.8 solar masses (Gaia-updated)
- Distance: VLBI 2.6 kpc; Gaia 2.26 kpc
- Systemic RV: ~0 km/s heliocentric (assumption, H-alpha zero-point)
- Galactic components: U=-72, V=-49, W=-3 km/s
- Peculiar velocity: 26+-8 km/s (LSR); 34+-13 km/s (Cen OB1)
- Drift over 300 kyr: ~8 pc
- 2025 census: 145 pulsars vs 3,000 clusters; 19 likely open-cluster births; B1259-63->UBC 525 flagged as compelling
- Caveat: pulsar RVs unknown; systemic RV is an assumption

## 7.3 Three ISM kinematic layers

### Layer 1: HI shell GSH 305+01-24
- Tracer: HI 21 cm
- Dynamical distance: 2.2 +- 0.6 kpc
- V_LSR: -26 km/s; expansion ~8 km/s
- Approaching: -34 km/s; receding: -17 km/s
- Shell distance overlaps UBC 525 within uncertainties

### Layer 2: IRDC G304.74+01.32 (~0.5 deg away)
- Tracer: C17O (mean -26.7 km/s), 13CO (blue-asymmetric = infall)
- Trans-to-supersonic non-thermal motions; most clumps gravitationally bound
- Velocity centroid matches HI shell to ~1 km/s -> dynamically coupled

### Layer 3: Na I / Ca II toward LS 2883
- Low-positive: Southern Coalsack
- Negative complex: -14 to -36 km/s (Sagittarius Arm)
- Most negative peak beyond HI shell's -34 km/s edge -> system behind shell
- Background stars: ~-50 km/s (Norma-Centaurus Arm)

## 7.4 The key inference: 26 km/s star-gas offset

Stars: systemic RV ~0. Gas: V~-26 to -27 km/s. **~26 km/s radial-velocity offset** between the stellar system and its immediate gaseous environment. The system is moving *through* the gas, not with it. Open question: does this drive shocks (SiO, 13CO line wings) or is it Sagittarius Arm geometry?

## 7.5 Outstanding questions

1. Joint reference frame: pulsar timing + HI/CO + Gaia, never done for any open cluster
2. Direct pulsar RV (not assumed)
3. VLBI vs Gaia distance resolution
4. Shock diagnostics at the star-gas interface
5. HST/JWST sub-mas proper motions in the dusty core
6. Dusty-plasma: does relative star-gas motion seed or suppress plasma-dust coupling processes?

---

*Stage 7 complete. Investigation series finished.*
