# FITR — Flexible Interferometric Transfer Record
### Format Specification  v0.1 DRAFT  (2026-05-25)

---

## 1. Scope

FITR is the radio/interferometry sibling of FITA.  Where FITA stores
calibrated sky images with per-layer compositing metadata, FITR stores
**complex visibilities and derived data products** from radio aperture-
synthesis telescopes (ALMA, VLA, LOFAR, MeerKAT, ngVLA, SKA-Mid/Low).

FITR is designed to be:

- **HDF5-native** (not FITS-wrapped).  Radio datasets routinely exceed the
  2 GB FITS single-HDU limit.  HDF5 chunking and parallel I/O are required.
- **uv-space first**.  Visibilities, weights, and flags are the primary
  products; cleaned images are secondary.
- **Provenance-compatible with FITA**.  The FITR provenance schema is a
  strict superset of the FITA provenance model so a pipeline can trace
  a FITA layer back to its FITR visibility source.
- **IVOA-aligned**.  Dataset attributes follow ObsCore DM v1.2 and
  RadioVis DM v0.3 vocabularies.

---

## 2. File Identification

| Property       | Value                              |
|----------------|------------------------------------|
| File suffix    | `.fitr`                            |
| MIME type      | `application/x-fitr+hdf5`         |
| HDF5 signature | `/FITR_VERSION` root attribute     |
| Magic bytes    | HDF5 native (`\x89HDF\r\n\x1a\n`) |

---

## 3. Root Group Attributes  (mandatory)

| Attribute        | Type    | Description                                      |
|------------------|---------|--------------------------------------------------|
| `FITR_VERSION`   | str     | Format version, e.g. `"0.1"`                    |
| `FITA_VERSION`   | str     | Linked FITA format version (`"1.0"`)             |
| `FITR_ORIGIN`    | str     | Telescope/array identifier (e.g. `"ALMA"`)       |
| `FITR_PROJECT`   | str     | Project code / PI name                           |
| `FITR_FREQ_REF`  | float64 | Reference frequency (Hz)                         |
| `FITR_FREQ_BW`   | float64 | Total bandwidth (Hz)                             |
| `FITR_NPOL`      | int32   | Number of polarisation products                  |
| `FITR_NSPW`      | int32   | Number of spectral windows                       |
| `FITR_NVIS`      | int64   | Total number of visibilities                     |
| `FITR_RA`        | float64 | Phase centre RA  (degrees, ICRS)                 |
| `FITR_DEC`       | float64 | Phase centre Dec (degrees, ICRS)                 |
| `FITR_EPOCH`     | str     | Observation epoch (ISO-8601 UTC)                 |
| `FITR_PIPELINE`  | str     | Reduction software + version                     |

---

## 4. Group Layout

```
/                             root
  .attrs                      (see §3)
  /vis/                       visibility data group
    data        Dataset       complex64, shape (Nvis, Nspw, Nchan, Npol)
    uvw         Dataset       float64,   shape (Nvis, 3)             [metres]
    time        Dataset       float64,   shape (Nvis,)               [MJD UTC]
    ant1        Dataset       int32,     shape (Nvis,)
    ant2        Dataset       int32,     shape (Nvis,)
    weight      Dataset       float32,   shape (Nvis, Npol)
    flag        Dataset       uint8,     shape (Nvis, Nspw, Nchan, Npol)
  /spw/                       spectral window group
    0000/                     one sub-group per SPW
      .attrs                  freq_ref, bandwidth, nchan, pol_products
      freq        Dataset     float64, shape (Nchan,)                [Hz]
  /antenna/                   antenna table
    .attrs                    array_name, n_antenna
    position    Dataset       float64, shape (Nant, 3)  ECEF [m]
    name        Dataset       str,     shape (Nant,)
    diameter    Dataset       float64, shape (Nant,)    [m]
  /image/                     optional: CLEAN / deconvolved images
    0001/                     one sub-group per image plane
      .attrs                  FITA-compatible layer metadata
                              (FITA_LID, FITA_LNM, FITA_WCV, FITA_WBW,
                               FITA_BLD, FITA_OPC, FITA_ZDP, BUNIT, ...)
      flux        Dataset     float32, (H, W) — Jy/beam or Jy/pixel
      alpha       Dataset     uint16,  (H, W) — FITA-standard alpha
      uncert      Dataset     float32, (H, W) — noise map [optional]
      mask        Dataset     uint8,   (H, W) — clean mask [optional]
      beam_major  attr        float64  [arcsec]
      beam_minor  attr        float64  [arcsec]
      beam_pa     attr        float64  [degrees]
      wcs_header  Dataset     str      JSON-serialised FITS WCS
  /cal/                       calibration tables
    bandpass    Dataset       complex64, shape (Nant, Nspw, Nchan, Npol)
    gain        Dataset       complex64, shape (Ntime, Nant, Npol)
  /provenance/                FITA-compatible provenance group
    .attrs                    IVOA ObsCore DM v1.2 columns as attributes
    history     Dataset       str array — pipeline processing log
```

---

## 5. Visibility Data Encoding

Complex visibilities are stored as **complex64** (2 × float32).  This is
the native representation in NumPy (`numpy.complex64`) and maps directly
to the HDF5 compound type `{re: float32, im: float32}`.

Flags follow CASA convention: **0 = good, bit-mask for failure modes**.
Bit definitions:

| Bit | Meaning                        |
|-----|--------------------------------|
| 0   | RFI flagged                    |
| 1   | Antenna offline                |
| 2   | Shadow / cross-talk            |
| 3   | Amplitude outlier (> N sigma)  |
| 4-7 | Reserved                       |

---

## 6. Provenance — FITA Compatibility Bridge

The `/provenance/` group carries the same attributes as the `FITA_META`
BINTABLE in a `.fita` file.  Any tool that reads FITA provenance can read
FITR provenance with zero modification.  Additional radio-specific columns:

| Attribute         | Type    | Description                          |
|-------------------|---------|--------------------------------------|
| `FITR_CLEAN_ALG`  | str     | Deconvolution algorithm (HOGBOM/MSCLEAN/...) |
| `FITR_ROBUST`     | float32 | Briggs robust weighting parameter    |
| `FITR_TAPER_UV`   | float64 | UV taper (metres)                    |
| `FITR_NITER`      | int32   | CLEAN iterations                     |
| `FITR_THRESHOLD`  | float32 | CLEAN threshold (Jy/beam)            |
| `FITR_CELL_ARCSEC`| float64 | Image pixel scale (arcsec)           |

---

## 7. Image Planes — FITA Layer Subset

Image planes in `/image/` carry the **exact same metadata attributes**
as FITA FLUX extension headers.  This means:

1. A FITR image plane can be extracted and stored directly as a FITA layer
   with no metadata translation.
2. A FITA pipeline can ingest FITR image planes without modification.
3. All FITA blend modes (`NORMAL`, `ADD`, `SCREEN`, ...) apply to FITR
   image planes for multi-frequency radio composites.

The stereo-depth keyword `FITA_ZDP` is **preserved** in FITR image planes
so that multi-frequency radio cubes can be rendered as phased stereograms
with the same renderer used for optical FITA cubes.

---

## 8. What FITR Is NOT

FITR does **not** define:

- Display mathematics (stretch, tone curve, colour mapping) — these live
  in the FITA `FITA_ADJ` adjustment-layer stack.
- Photometric calibration curves — these live in `uranodyne.calibration`.
- Source catalogues — use FITS BINTABLE or VOTable wrapped separately.
- Image reconstruction algorithms — FITR stores inputs and outputs, not
  the algorithm itself.

---

## 9. Reference Implementations

| Library       | Language | FITR support         |
|---------------|----------|----------------------|
| `fita`        | Python   | `fita.backends.hdf5` read/write of `/image/` planes |
| `uranodyne`   | Python   | FITR→FITA bridge via `from_fitr_image()` (planned v1.1) |
| CASA 6.x      | Python   | Native MS; FITR export via `exportfitr` task (planned) |
| WSClean 3.x   | C++      | Direct FITR output (planned, RFC stage)  |

---

## 10. Version History

| Version | Date       | Changes                            |
|---------|------------|------------------------------------|
| 0.1     | 2026-05-25 | Initial draft; uv+image+cal layout |

---

*FITR is developed in the UranoDyne / FITA project at*
*C:\Users\astro\fita  —  contact: Ignacio A. Cisneros*
