# 01. Imaging Spectrographs for Star Cluster Kinematics

**Date:** 2026-10-23
**Stage:** 1 of 7
**Question:** Which imaging spectrographs exist for mapping stellar and gaseous kinematics in star clusters, and have any been applied to globular clusters?

---

## 1.1 Integral Field Units (IFUs)

IFUs slice a two-dimensional field into hundreds of simultaneous spectra. They are the primary tool for mapping velocity fields and line ratios across extended objects.

| Instrument | Telescope | Type | Key capability |
|---|---|---|---|
| MUSE | VLT (UT4) | Optical IFU, 1'x1' field | 4800-9300 A, R~3000, 24x24 spaxels (0.2"), superb for nebulae and galaxy centers |
| KCWI | Keck II | Optical IFU, configurable slicer | Blue (3500-5600 A) and red (5300-10500 A) channels; high spatial resolution |
| MaNGA | Sloan 2.5m | IFU survey instrument | 10,000 galaxies; not for star clusters per se but demonstrates IFU survey methodology |
| SITELLE | CFHT 3.6m | Imaging Fourier transform spectrometer | 4'x4' field, R up to ~10,000 tunable; see Section 1.3 |

## 1.2 Fabry-Perot Imagers

- **GHaFaS** (Galaxy H-alpha Fabry-Perot System) on the William Herschel Telescope: tunes a narrow bandpass across the field step by step, building a data cube. Used for H-alpha kinematics of nearby galaxies and HII regions.
- Fabry-Perot systems trade field of view and spectral coverage for high spectral resolution at a single wavelength. Complementary to IFUs for narrow-line work.

## 1.3 SITELLE on CFHT — detailed treatment

SITELLE (Spectro-Imageur a Transformee de Fourier pour l'Etude en Longueur d'onde de l'Environnement) is an imaging Fourier transform spectrometer at the Canada-France-Hawaii Telescope. Key properties:

- **Field:** 11' x 11' (SITELLE's full field is 4'x4' for the highest resolution mode; the full 11'x11' is available at lower spectral resolution).
- **Principle:** Michelson interferometer scanned in optical path difference; each pixel yields a spectrum via Fourier transform.
- **Filters:** SN1 (363-386 nm), SN2 (482-513 nm), SN3 (651-685 nm), C1/C2 continuum filters.
- **Spectral resolution:** tunable, R up to ~10,000 in SN3.
- **Multiplex advantage:** all wavelengths measured simultaneously per pixel — excellent for emission-line work.
- **Multiplex disadvantage:** for continuum-dominated sources, every scan step pays for the entire spectrum; inefficient compared to dispersive spectrographs for absorption-line work.

### 1.3.1 Published SITELLE science targets

From the SITELLE calibration and early-science papers, published targets include:

- Nebulae: Eagle Nebula (M16), Crab Nebula (M1)
- M31 nucleus
- Planetary nebulae
- Galaxy clusters at moderate redshift: Abell 2390, Abell 2465, Cl0016
- Open cluster: IC 348 (science verification; an open cluster with an HII region, not a globular)

Star clusters appear in the calibration paper only generically, as cases where phase computation falls back on sky background.

### 1.3.2 Has SITELLE been used on globular clusters?

**No published SITELLE study of a globular cluster was found.** The physical reason is the multiplex disadvantage on continuum sources: globular clusters are dense fields of continuum-dominated stars with absorption-line spectra. SITELLE was designed for emission lines (H-alpha, [O III], [S II]). A globular's light is mostly stellar continua, so the Fourier approach spends enormous telescope time for marginal gain over multi-object spectrographs.

**Standard tools for globular cluster kinematics/chemistry remain:** DEIMOS (Keck) and GMOS-MOS (Gemini) multi-object spectrographs.

### 1.3.3 Closest SITELLE-like precedent on globulars

MUSE pointings on Omega Centauri and 47 Tucanae have been used for exactly this purpose — mapping central kinematics where an intermediate-mass black hole might reside. MUSE's IFU architecture handles the continuum problem better than an FTS because each spaxel's spectrum is built from a single exposure sequence, not a path-difference scan.

## 1.4 Relevance to ISM / dusty-plasma work

For interstellar medium studies, SITELLE's large field and tunable resolution make it valuable for mapping ionized gas (HII regions, planetary nebulae, supernova remnants) across wide areas. Its SN3 filter covers H-alpha and the [N II]/[S II] lines critical for shock diagnostics. For molecular gas, ALMA and single-dish millimeter telescopes remain the tools of choice; SITELLE does not observe below ~360 nm or in the infrared.

## 1.5 Open questions

1. Could SITELLE's SN2 filter (covering H-beta and [O III]) be used on a globular cluster's planetary nebula population for a crude kinematic census?
2. Has any group proposed an FTS-style instrument optimized for continuum sources (e.g., with a larger beam or different scan strategy)?
3. What is the current status of SITELLE's data archive and public data releases?

---

*Stage 1 complete. Next: Anderson et al. star cluster kinematics papers, animations, and datasets.*
