# 02. Anderson et al.: Star Cluster Kinematics Papers, Animations, and Datasets

**Date:** 2026-10-23
**Stage:** 2 of 7
**Question:** What are Jay Anderson's key publications on star cluster kinematics, what animations has he presented, and what datasets are associated with his work?

---

## 2.1 Foundational paper: Anderson & van der Marel 2010

- **Title:** New Limits on an Intermediate Mass Black Hole in Omega Centauri
- **Journal:** Astrophysical Journal, Volume 710
- **arXiv:** 0905.0627
- **Data:** GO-9442, GO-10252, GO-10775; ACS/WFC and WFC3
- **Baseline:** 2.5-4 years
- **Catalog:** 1.2 million stars over a 10'x10' field, down to ~0.35 solar masses
- **Proper motions:** ~100,000 total; 53,000 high-quality in the central 2'
- **Key results:**
  - No dispersion cusp at the center
  - No runaway stars
  - First measurement in any globular of how velocity dispersion varies with mass along the main sequence
  - Cluster is **not in equipartition** (see Stage 3)
- **Animation:** ESA/Hubble release heic1017a, "Motion of stars in Omega Centauri" — 56-second zoom from ground-based image into WFC3 core, then simulation projecting positions 10,000 years forward; streaks = 600 years of motion, dots every 30 years. Available on ESA/Hubble site and YouTube (HubbleWebbESA channel); NASA asset page offers MP4 at 640x360 and 1280x720.
- **Interview:** heic1017c, 2 min 50 s, Anderson and van der Marel discussing analysis and weakened black hole case.

## 2.2 HSTPROMO series

Collaboration: Bellini, Anderson, van der Marel, Watkins, et al. Page: stsci.edu/~marel/hstpromo.html

| Paper | Journal/Vol | Content |
|---|---|---|
| 1 (2014) | ApJ 797 | 1.3M+ stars, 22 clusters; M15 catalog released (77,837 stars, central 2.4') |
| 2 (2015) | ApJ 803 | Kinematic profiles and maps for all 22; cores isotropic to 1% |
| 3 (2015) | ApJ 812 | Dynamical distances for 15 clusters; agree with photometric to ~2% |

Data: ACS/WFC, ACS/HRC, WFC3/UVIS archival multi-epoch data. Median 60,000 stars per cluster. Velocity errors ~1 km/s.

## 2.3 oMEGACat (Omega Centauri)

- 500+ HST images spanning 2002-2023
- 2024: 7 fast-moving central stars suggesting IMBH >= 8,200 solar masses
- July 2025 (Whitaker et al.): first stellar-mass black hole in any globular — oMEGACat BH-2, ~4.5 solar masses, detected via 21-year astrometric wobble; Webb refined the orbit. Longest-period black hole binary known.

## 2.4 Young/embedded cluster catalogs

| Target | Year | Stars | Notes |
|---|---|---|---|
| Arches | 2022 | ~35,000 | Near Galactic center; ICRF-tied via background stars |
| Quintuplet | 2022 | ~40,000 | Same as Arches |
| Orion Nebula Cluster | (Anderson+Kim) | 701 | 6'x6' field; ACS, WFPC2, WFC3/IR + Keck NIRC2 |
| Westerlund 1 | 2025 | 10,000+ | Gaussian mixture model membership probabilities |

## 2.5 Datasets and software

- **ACS Survey of Galactic Globular Clusters** (PI Sarajedini 2007): Anderson's pipeline did the reductions; catalogs anchor HSTPROMO reference frames. Access via MAST (mast.stsci.edu), proposal ID 10775, or Sarajedini et al. 2007 papers.
- **Anderson's pixel-based CTE corrections and PSF-fitting code:** not a single public download; embedded in published catalogs and described in methods sections. Re-reducing raw frames requires rebuilding from methods.
- **MAST HLA:** https://hla.stsci.edu

## 2.6 Anderson's stated research interests (STScI profile)

Multiple populations, high-precision proper motions, cluster evolution, astrometric black hole detection.

---

*Stage 2 complete. Next: energy equipartition in Omega Centauri.*
