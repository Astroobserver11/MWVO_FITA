# FITA Foundry — the `.exe` domain for community-wide FITA adoption

**Status:** DESIGN **v0.3** (2026-08-02) — *conformed to the **RATIFIED** v1.1 standard*.
**The Foundry itself is PARKed** under the D-3 closure ruling (SHIP = the FITA paper); revival
condition = "after the FITA paper ships." Its **C1 install-robustness component is NOT parked** — it
is the last remaining item on the live Step-2 critical path (§10).
**Normative reference:** `FITA_FORMAT_STANDARD.RATIFIED-2026-08-02.md` + ruling record
`FITA_v1.1_RATIFICATION__2026-08-02.md`. (ATOP's canonical copy still needs the ratified text
applied — it has been Taildropped but not yet installed.)
**Author context:** MWVO / UranoDyne (Ignacio A. Cisneros)
**Scope:** A robust, distributable executable domain that **ingests** data into FITA,
**processes** FITA, and **emits** FITA into the applications the community already uses —
with AI-awareness of the format built in, and a curated migration path into buildable code.

> **v0.1 → v0.2 erratum.** v0.1 was written before the normative standard was available on this
> machine, from a memory digest only. Six of its clauses contradicted the standard's `[CORRECTION]`
> rulings — most consequentially it invented a four-level conformance scheme (L0–L3) where the
> standard defines two (FITA-CORE / FITA-FULL), and it propagated the unregistered MIME type
> `application/fits+alpha`, which §3 forbids emitting. Corrected throughout.
>
> **v0.2 → v0.3 erratum.** v0.2 was drafted concurrently with — and finished minutes after — a
> parallel session that **ratified the standard and shipped most of the repairs this design listed
> as prerequisites**. v0.2 therefore overstated the defect surface: it claimed R1 (alpha wrap)
> "breaks the entire emit ring", when R1, R3, R4 and R5 were fixed in `io.py` and the validator
> `fita conform` was built, the same day. Status corrected in §2.3, §8, §10, §11; the open decisions
> in §12 are now **RATIFIED**, not open. Architecture is unchanged.
>
> **Where this document and the standard disagree, the standard governs.**

---

## 0. Why this document exists

FITA today is a **library** — two Python packages (`fita`, `uranodyne`) with a 7-verb CLI. That
suffices for one author on one machine. It does not suffice for community adoption, and we have
two independent proofs of why:

1. **The IrenBLink episode** — a broken editable install that only imported from one directory
   produced a silent scientific no-op. A community format cannot ship as a `pip install -e .` that
   works from exactly one `cwd`.
2. **Standard §11.5** — *"The suite tests the library's functions and never the file's
   conformance."* 110 green tests coexisted with wrapped alpha in all 18 archived files, invalid
   `BUNIT` in every one, `FITA_META` unreachable through the documented API, and `visible` lost on
   every round trip in every backend.

Those two failures share a root cause: **nothing in the system checks the system**. The Foundry is
the answer — a relocatable, self-describing executable surface with conformance checking as a
first-class verb, that any observatory, pipeline, or AI agent can drop in and use without knowing
the internal package layout.

**Three verbs are the spine:**

```
        INGEST                 PROCESS                  EMIT
   (world → FITA)          (FITA → FITA)            (FITA → world)
   ───────────────        ────────────────         ───────────────
   FITS cube               reselect flux            DS9 / SAMP
   PSD (Photoshop)         blend / composite        qFITSView RGB FITS
   DSS/2MASS/WISE          adjustment layers        Aladin / HiPS / MOC
   SkyView / HiPS          reproject / register     Photoshop / FITS Liberator
   HDF5 / Zarr             SED / photometry         PNG / MP4 / WebGL
   PNG / TIFF / raw        provenance (PACI)        HDF5 / Zarr / VOTable
```

Standard §10.3 already mandates the shape of this: *"the family's shared contract is
**interconversion** — `FITS folder ⇄ FITS-MEF (FITA) ⇄ HDF5 (FITO/FITR)`, round-trip, with any
lossy step **logged**. A conversion that silently loses a property (as `visible` does today) is
non-conformant."* The Foundry's I/P/E bus is the machinery that makes that contract executable and
its logging automatic.

---

## 1. Architecture — three rings

```
                          ┌───────────────────────────────────────────┐
                          │            RING C — SURFACES                │
                          │  fita (CLI)  ·  fitad (service/MCP)  ·      │
                          │  frozen fita.exe  ·  plugin sidecars       │
                          └───────────────┬───────────────────────────┘
                                          │  every surface calls only Ring B
                          ┌───────────────┴───────────────────────────┐
                          │            RING B — THE I/P/E BUS           │
                          │  IngestRegistry · ProcessRegistry ·        │
                          │  EmitRegistry  +  Job/Manifest + validate() │
                          └───────────────┬───────────────────────────┘
                                          │  registries resolve to Ring A ops
                          ┌───────────────┴───────────────────────────┐
                          │        RING A — KERNEL + SCIENCE            │
                          │  fita:  cube layer io blend flux adjustment │
                          │         spec ivoa backends/{hdf5,zarr}       │
                          │         plugins/{ds9,qfitsview}              │
                          │  uranodyne: surveys skyview reproject       │
                          │         register hips edenhofer paci ...     │
                          └───────────────────────────────────────────┘
```

**Ring A exists.** We do not rewrite it — but §2.3 below lists the standard-mandated repairs that
must land in Ring A *before* the bus can honestly claim conformance.

**Ring B — the I/P/E Bus — is the one new abstraction.** It turns the flat pile of Ring A functions
into three *registries* of named, described, versioned **Ops**, plus a `Job` carrying a FITA payload
and its provenance `Manifest`, plus the standard's required `validate()`. A registry can enumerate
and describe itself; a bare function cannot. That is what makes the format discoverable by humans,
CI, and AI agents from one source of truth.

**Ring C — surfaces — are thin,** containing no logic:

1. **`fita` CLI** — the human command line, subparsers generated from the registries.
2. **`fitad` service** — the same bus over HTTP/JSON and as an **MCP server** for AI agents.
3. **Frozen `fita.exe`** — PyInstaller/`shiv` single-file build, no Python environment, no editable
   install. The literal `.exe` domain and the direct fix for install fragility.

Because all logic lives in the bus, CLI, API and agent tools are guaranteed identical in behavior —
a property unattainable when each surface reaches into the library independently.

---

## 2. Conformance — the standard's rules, not ours

### 2.1 Levels (standard §2.1 governs)

The standard defines exactly two levels. **This design adopts them verbatim and defines no others.**

- **FITA-CORE** — every **MUST** in standard §§3–7 satisfied. The minimum for a file to be called
  `.fita`; what any FITA reader may assume.
- **FITA-FULL** — FITA-CORE + every **SHOULD** in §§3–9 + a conformant `FITA_META` provenance HDU.
  The bar for publication, archiving, collaborator delivery, or VO registration.

A level is **not recorded in the file**; it is what a validator reports.

### 2.2 `fita.validate()` is a Foundry verb, not an afterthought

Standard §2.1 requires `fita.validate(path) -> ConformanceReport`. The Foundry exposes it as a
first-class verb on every surface — `fita validate <file>`, an HTTP endpoint, and an MCP tool —
because §11.5 shows that a library which tests only its own functions cannot detect its own
non-conformance. The bus additionally runs `validate()` **automatically after every emit** so a
non-conformant file cannot leave the Foundry unremarked.

### 2.3 Ring A repairs — status as of 2026-08-02

These are not Foundry inventions; each is a `[CORRECTION]` clause. **Most have now shipped.**
Verified live on BTOP 2026-08-02 (`python -m fita conform`, `io.py`, `spec.py`):

| # | Defect (standard §) | Status | Effect on the Foundry |
|---|---|---|---|
| R1 | Alpha signed `int16`, no `BZERO = 32768` (§6.3) | **FIXED** — `io.py` writes `.astype(np.uint16)`, astropy emits `BZERO=32768`; verified range 0..65535 | The emit ring's app-native targets (DS9/QFitsView/Aladin) now receive correct alpha for **newly written** files. Files written before this date still carry the wrap. |
| R2 | `FITA_META` unreachable — `io.write()` has no parameter for it (§9) | **FIXED 2026-08-02** — `write(..., provenance=dict\|BinTableHDU)`; `FITACube.save()` passes through | The ingest provenance contract (§4) is now implementable, and **FITA-FULL is reachable**: a file written through the public API validates FITA-FULL. |
| R3 | `FITA_VIS`; `visible` lost every round trip (§6.2) | **FIXED** — `to_header_dict()` already emitted it; verified `visible` round-trips `[T,F,T]` | Ring B `Job` round-trips no longer drop visibility. |
| R4 | Invalid `BUNIT`: `'alpha16'`, `'same as FLUX'` (§7) | **FIXED** — `alpha16` omitted; `UNCERT` now carries the parent flux unit | Emitted files parse downstream. |
| R5 | `SPLIT16` destructive (§6.4) | **FIXED** — raises on **both** write and read (D-2 ruled DELETE) | The `pack` Op (§5) loses its reason to exist; see §5. |
| R6 | ObsCore overclaim; `TUCDn` never written (§9) | **FIXED 2026-08-02** — D-4 implemented: 32 ObsCore v1.1 columns (32 total), every column carries a `TUCDn`, `access_format = "application/fits"` | The wording is now simply **"ObsCore DM v1.1"** — the claim is earned rather than withdrawn. This is the LVM/VO provenance differentiator made real. |

Also shipped: `fita/validate.py` → `validate(path) -> ConformanceReport` with `.is_core`/`.is_full`/
`.level`, `flux_roundtrip_ok()` for §5.4, exported as `fita.validate` and exposed as **`fita conform`**
(`--quiet`, `--strict`, exit 0/1/2). Suite: **135 passed / 0 failed**, including the two tests §11.5
said were missing (`test_flux_invariant_bit_exact`, `test_written_file_is_core_conformant`) and
`test_split16_is_rejected` replacing the vacuous old round-trip test.

**Grandfathering works as D-1 intended.** Running the validator on a pre-fix file reproduces exactly
the expected failures rather than crashing:

```
FITA conformance: test_sample.fita
  LEVEL: NON-CONFORMANT   (9 MUST failing, 1 SHOULD failing)
  FAIL MUST   S6.2 [FLUX_0001]: required layer keyword FITA_VIS
  FAIL MUST   S6.3 [ALPHA_0001]: ALPHA BZERO=32768 unsigned-16 convention (got None)
  ...
  FAIL SHOULD S9  [FITA_META]: FITA_META provenance HDU present (required for FITA-FULL)
```

`[MEASURED]` R1–R4 and R6 are present in all 18 **archived** files; the fixes apply to new writes,
and the 18 are grandfathered under D-1 rather than rewritten. R5 affected **0 of 18** — no archived
flux is corrupt, and the format's central promise holds bit-for-bit in FLOAT32 (standard §5, §11.3).

**Two live defects found while verifying this section** (neither is a Foundry blocker):
- `validate.py:246` still emits the clause label `"S6.3/§7"` — the surviving `§` renders as
  `S6.3/�7` on the Windows console, the exact failure the ASCII-label convention exists to
  avoid. One-character fix.
- `fita` is **not on PATH**; `python -m fita` is the working invocation. This is component **C1** and
  it is the last item on the live critical path.

### 2.4 Constraints the Foundry inherits

- **Header is authoritative** (§4.3, §2.2). Every Op reads layer metadata from the `FLUX_*` header;
  `FITA_LAYERS` may be used only to enumerate layers. A writer Op must keep them consistent, and
  `validate()` reports discrepancies.
- **No double scaling** (§2.2). No Op may re-apply `BSCALE`/`BZERO` to data a FITS library already
  scaled.
- **Unknown blend code raises** (§8.1). No silent fallback to `NORMAL`.
- **Flux is bit-exact** (§5.3). Any Op that writes back after a display-side operation must
  reproduce `FLUX_*` bit-for-bit, tested per packing mode (§5.4).
- **FITA stays paradigm-free** (§10.3). **No Op may write paradigm tags, `[ESTABLISHED]`/
  `[PROPOSED — MWVO]` fences, or `(input, core, paradigm)` stamps into a `.fita`.** That is FITO's
  territory; the fence between established and proposed physics depends on it.
- **Version bumps are mandatory** (§13). Any Op that adds required or optional structure — the
  proposed `FITA_OPLOG` included — requires a `FITAVER` increment.

---

## 3. The `Op` and the `Job` — Ring B's two nouns

### 3.1 `Op` — a described, versioned operation

```python
@dataclass(frozen=True)
class Op:
    verb: str                 # "ingest" | "process" | "emit"
    name: str                 # "from-fits", "reselect", "to-ds9", ...
    version: str              # semver of THIS op's behavior
    summary: str              # one line, human + agent readable
    params: list[ParamSpec]   # typed, described, with defaults & ranges
    accepts: MediaSpec        # what it consumes
    produces: MediaSpec       # what it yields
    fidelity: str             # "lossless" | "display-lossy" | "app-native" | "sidecar"
    side_effect: str          # pure | writes_file | network | external_app | irreversible
    run: Callable[[Job, dict], Job]
```

The `ParamSpec`/`MediaSpec` metadata is **the same object** that (a) builds the `argparse`
subparser, (b) validates an HTTP request, (c) generates the MCP tool schema, and (d) renders the
docs and the AI Format Card. One description, five consumers — which is how descriptions stop being
prose that rots. Standard §11.5's lesson applied structurally: documentation that is *generated*
from the thing it documents cannot drift from it.

### 3.2 `Job` — the payload that flows through the verbs

```python
@dataclass
class Job:
    cube: FITACube            # the live FITA payload (Ring A object)
    manifest: Manifest        # provenance + op-history (§6)
    scratch: dict             # inter-op handoff, never persisted
```

A pipeline is `emit(process(process(ingest(source))))`. Because the `Job` carries its `Manifest`,
every transformation is recorded as it happens — and every **lossy** step is logged, which is
exactly what standard §10.3 requires of the family's interconversion contract.

---

## 4. INGEST — world → FITA

| Op name        | Source                            | Backed by (Ring A)                     | Status |
|----------------|-----------------------------------|----------------------------------------|--------|
| `from-fits`    | FITS image / cube                 | `fita.io.from_fits_cube`               | exists |
| `from-psd`     | Adobe Photoshop `.psd`            | `fita.psd_import.import_psd`           | exists |
| `from-hdf5`    | HDF5 FITA-family                  | `fita.backends.hdf5.read`              | exists, **unverified** (§8) |
| `from-zarr`    | Zarr store / cloud                | `fita.backends.zarr.read`              | exists, verified |
| `from-survey`  | DSS/2MASS/WISE by position        | `uranodyne.pipeline.surveys`+`skyview` | exists |
| `from-hips`    | Any HiPS survey by (l,b,fov)      | `uranodyne.pipeline.hips`              | exists |
| `from-image`   | PNG/TIFF/JPEG raster              | *new, thin — Pillow → layer*           | **build** |
| `from-votable` | VOTable/CSV catalog → point layer | *new, thin — astropy.table*            | **build** |

**Ingest contract.** Every ingest Op **MUST**:

1. Produce a `FITACube` with ≥1 `FITALayer` that passes `validate()` at **FITA-CORE**.
2. Preserve **raw astrophysical flux** in `FLUX_*` (standard §5.1) — never fold display scaling into
   science data.
3. Write every layer property to the `FLUX_*` header, including the new `FITA_VIS` (§6.2), and keep
   `FITA_LAYERS` consistent.
4. Emit a valid `BUNIT` (§7) — the real unit, never `'same as FLUX'`.
5. Attach provenance sufficient for FITA-FULL via `fita.ivoa.make_meta_hdu`. **Blocked on R2** until
   `io.write()` accepts a provenance HDU.
6. Stamp the **PACI triple** (`CITATION · UNCERTVL/UNCKIND · ANCHORCL`) — survey cutouts default to
   `SCOUTED`, catalogued native-resolution measurements to `MEASURED`. **See the boundary question
   in §11 (D-8): PACI is a `uranodyne` convention in `extra_header`, not a standard §6.2 keyword,
   and `ANCHORCL` is arguably epistemic status — FITO's side of the §10.3 line.** Pending that
   ruling, ingest stamps PACI as today, and the Foundry does *not* promote it into the standard.

**Community extension point.** Third parties register Ops through the entry-point group
`fita.ingest` — a `fita-ingest-lofar` package appears in `fita ingest --list`, the API, and the
agent tool list automatically, with no core edit. This is the single most important adoption lever:
it makes FITA extensible by strangers.

---

## 5. PROCESS — FITA → FITA

| Op name      | What it does                                | Backed by                            | Reversible |
|--------------|---------------------------------------------|--------------------------------------|-----------|
| `reselect`   | Re-derive alpha from new flux range/stretch | `FITACube.reselect_flux_range`       | yes — flux untouched (§5.2) |
| `composite`  | Blend visible layers → display raster       | `fita.blend.composite`               | yes |
| `adjust`     | Push a LEVELS/CURVES/… adjustment layer     | `fita.adjustment.*`                  | yes — persisted as `FITA_ADJ` (D-3) |
| `blend-set`  | Set blend mode / opacity                    | `FITALayer` fields                   | yes |
| `reproject`  | Regrid a layer to target WCS                | `uranodyne.pipeline.reproject`       | no — logged |
| `register`   | Align layers                                | `uranodyne.pipeline.register`        | no — transform logged |
| `sed`        | Extract SED at pixel / aperture from FLUX   | `uranodyne.sed_analysis`             | additive |
| `photometry` | Aperture / stack photometry from FLUX       | `uranodyne.photometry`               | additive |
| `absorb`     | Multiphase X-ray absorption (Edenhofer fg)  | `uranodyne.pipeline.xray_absorption` | additive |
| `pack`       | **FLOAT32 only** — see below                | `fita.flux`                          | n/a |
| `promote`    | Reconcile SCOUTED vs MEASURED → ANCHORED    | `uranodyne.pipeline.paci`            | additive |

**`pack` is now vestigial — recommend dropping it.** D-2 was ruled **DELETE**, and `io.py` already
raises on `SPLIT16` for **both** write and read. Since no archived file uses `SPLIT16` (0 of 18),
there is nothing left to migrate *from* and nothing legal to migrate *to*: the Op has no reachable
input and no legal output. Drop it from the registry rather than ship a verb that can only raise.
(v0.1 listed `pack` as a reversible FLOAT32⇄SPLIT16 converter — non-conformant, withdrawn.)

**Process contract.** Every process Op **MUST**: preserve `FLUX_*` bit-for-bit unless it is
explicitly a resampling Op (`reproject`/`register`, which log the transform); append a
`ManifestEntry`; carry PACI forward, **demoting** the anchor class to the least-trusted input when
combining layers (MEASURED + SCOUTED → SCOUTED). Trust never launders upward silently.

---

## 6. Self-improvement — using capacities already in the design

The directive asks that improvement ride existing FITA capacities. Three of the four do. **One does
not, and v0.1 overstated it.**

### 6.1 The op-log — *half real as of 2026-08-02*

v0.1 claimed "adjustment layers are a reversible op-log" as an existing capacity. Standard §10.2 was
explicit that it was not: *"nothing serialises them. The capability exists in memory and vanishes on
save."* **D-3 was ruled IMPLEMENT and is now built** — `FITA_ADJ` carries `ORDER, ADJ_TYPE, ENABLED,
NAME, LAYER_ID, PARAMS(JSON)`, written at HDU N-1 and read back with parameters intact. Two
consequences:

- **FITR §8's dangling dependency is satisfied.** Its display mathematics delegated to an HDU that
  no file had ever contained; files can now contain it.
- **The display half of the op-log is durable.** Hand-set display state survives a save/load cycle,
  which is what makes "re-run an old file under a newer op version and diff" possible at all.

A latent defect surfaced in the process and is worth recording, because it is the project's
signature failure: the pre-existing `to_records()` emitted `a.params`, a dict **no subclass ever
writes to** — all real state lives in typed dataclass fields. Anything built on it would have
"round-tripped" adjustments back to their *defaults*, silently. Serialisation is now derived by
field introspection, so future adjustment types persist without further work.

**Still open — `FITA_OPLOG`.** `FITA_ADJ` covers *display* state. The bus-level Op history (ingest
source, reprojections, registrations — "what was done to the data") is a different question, and
adding it is a structural change requiring a `FITAVER` increment per §13. The boundary to draw is
**display state (`FITA_ADJ`, done) vs transformation provenance (`FITA_OPLOG`, proposed)**; kept
distinct they are complementary rather than a second competing history mechanism.

### 6.2 PACI anchor promotion — a real learning rule

A `SCOUTED` prior reconciled against a `MEASURED` point is promoted to `ANCHORED`. Re-ingesting a
field as better data arrives monotonically raises the cube's trust. Implemented today in
`uranodyne.pipeline.paci`; the Foundry exposes it as `fita process promote` and can sweep it on a
schedule as surveys publish. (Subject to the D-8 boundary question in §11.)

### 6.3 The manifest as a corpus

Aggregated Op histories reveal which sequences the community actually runs — the empirical prior for
what to optimize, cache, or fuse. Usage of the format improves the tooling for the format.

### 6.4 Versioned conformance is the safe-evolution mechanism

Because files declare `FITAVER` and §13 mandates an increment on any structural change, the format
can tighten — deprecate `SPLIT16`, fix alpha `BZERO`, add `FITA_VIS` — **without breaking old
files**: they declare 1.0, the reader applies the documented 1.0 rules (wrapped alpha, invalid
`BUNIT`), and a migration Op moves them forward with the step logged. This is D-1's recommended
option (a), and it is what makes improvement a spec bump rather than a silent break.

---

## 7. Community-adoption protocols

**P1 — Conformance.** FITA-CORE / FITA-FULL per standard §2.1 (§2.1 above). Tools advertise the
level they emit; consumers advertise the level they need; `validate()` adjudicates.

**P2 — File identification.** Suffix `.fita`; magic `SIMPLE = T`; version keyword `FITAVER`.
**MIME type: `application/fits`.** Standard §3 forbids emitting the unregistered
`application/fits+alpha` into provenance metadata as though it were registered; conformant files
**MUST** declare `access_format = "application/fits"`. A FITA-specific type may be recorded in a
separate non-normative keyword, and may be revisited *if* IANA registration is actually pursued and
granted. (v0.1 asserted the unregistered type as FITA's MIME. Withdrawn.)

**P3 — Plugin entry points.** `fita.ingest` / `fita.process` / `fita.emit`. The adoption lever.

**P4 — VO alignment, stated honestly.** `FITA_META` carries an **ObsCore-derived provenance
subset**, not a compliant ObsCore table: mandatory columns are missing and `TUCDn` is never written
(§9). Column UCDs **MUST** be written as `TUCDn` when this is repaired. The family must also settle
on **one** ObsCore version — FITA declares v1.1, FITR declares v1.2 (D-4). Full conformance is worth
buying if `.fita` is ever to be VO-registered or shown to Alfredo Mejía-Narvaez as an LVM
differentiator, since provenance is one of the five items on that list.

**P5 — Emit fidelity contract.** Each emit target declares `lossless` / `display-lossy` /
`app-native` / `sidecar`, and **every lossy step is logged in the manifest** — standard §10.3's
interconversion clause, made executable. A conversion that silently loses a property is
non-conformant, which today means: **`visible` loss (R3) makes every backend round-trip
non-conformant until `FITA_VIS` lands.**

---

## 8. EMIT — FITA → world

| Op name      | Target                        | Backed by                           | Fidelity | Caveat |
|--------------|-------------------------------|-------------------------------------|----------|--------|
| `to-ds9`     | SAO DS9 live (SAMP/XPA)       | `fita.plugins.ds9.send_to_ds9`      | app-native | warn on legacy files |
| `ds9-plugin` | DS9 analysis-menu `.ana`      | `fita.plugins.ds9`                  | app-native | — |
| `to-rgb`     | qFITSView RGB FITS            | `fita.plugins.qfitsview`            | app-native | warn on legacy files |
| `liberator`  | FITS Liberator sidecar JSON   | `fita.plugins.qfitsview`            | sidecar  | — |
| `to-psd`     | Photoshop layered `.psd`      | *new — inverse of `from-psd`*       | app-native | **build** |
| `to-hdf5`    | HDF5 store                    | `fita.backends.hdf5.write`          | lossless* | ***unverified** — `h5py` absent on ATOP (§10.1); claim confirmed for 2 of 3 backends only* |
| `to-zarr`    | Zarr (cloud/tiled)            | `fita.backends.zarr.write`          | **lossless** (verified, alpha correct) | — |
| `to-hips`    | HiPS tiles + MOC (Aladin)     | `uranodyne.pipeline.hips`           | display-lossy | warn on legacy files |
| `to-png`     | Flat PNG / contact sheet      | `composite` → Pillow                | display-lossy | **build** |
| `to-mp4`     | Spectral/temporal fly-through | `uranodyne.export.animate_stack`    | display-lossy | — |
| `to-votable` | Catalog / SED table           | `astropy` + `sed_analysis`          | lossless (table) | — |

**R1 was the emit ring's critical defect, and it is fixed** (2026-08-02). Standard §6.3: the
library's read path undid the alpha wrap with a matching bug, so the damage was invisible from
inside FITA — but *"a third-party viewer has no such compensating bug"*. DS9, QFitsView and Aladin
are precisely the community doors this design exists to open, and all three were receiving alpha as
signed −32768..32767. `io.py` now writes `uint16` and astropy emits `BZERO=32768`.

**The caveat is now temporal, not structural:** newly written files are correct; the 18 archived
files still carry the wrap and are grandfathered under D-1. An emit Op **SHOULD** therefore run
`validate()` on its input and warn when handing a pre-2026-08-02 file to an app-native target — the
user is about to see wrong transparency in DS9 and has no way to tell from inside FITA.

Notably, **the Zarr backend wrote alpha correctly all along** as `uint16 0..65535` (§10.1) — direct
evidence that `uint16` was always the intended model and the FITS writer was the outlier.

**Community doors:** DS9 (SAMP/XPA), Aladin (HiPS+MOC, SAMP), TOPCAT (VOTable/SAMP), Photoshop
(PSD + Liberator), qFITSView (RGB FITS) — the five covering most of the working astro-imaging + VO
community, hence the emit priority set.

---

## 9. AI-awareness of the format

### 9.1 The FITA Format Card

A machine-readable card (`fita/ai/FITA_FORMAT_CARD.json`, shipped in-package and served by `fitad`)
stating without source-reading: what a `.fita` is, the flux/alpha invariant, the HDU layout, the two
conformance levels, the available Ops with schemas and `side_effect`, **and the known defects R1–R6
with their consequences**. That last part matters: an agent that does not know alpha is wrapped in
v1.0 files will confidently misreport what a third-party viewer will show.

### 9.2 The MCP server

`fitad --mcp` exposes each Ring-B Op as an MCP tool auto-generated from its `ParamSpec` — typed,
described, validated. An agent composes ingest→process→emit without importing Python or knowing the
package layout, and because the schema is generated from the same metadata as the CLI, agent and
human operate an identical surface.

### 9.3 Agent-safety annotations

Each Op carries `side_effect ∈ {pure, writes_file, network, external_app, irreversible}`. The MCP
layer refuses `irreversible` and `external_app` Ops without explicit confirmation and rate-limits
`network` Ops. The format tells the agent which verbs are load-bearing rather than leaving it to
guess.

**Net effect:** an agent handed a bare `.fita` plus the Format Card can correctly answer *what is
this*, *what is trustworthy in it* (PACI anchor class + conformance level), and *what can I safely
do to it* — read-only reasoning unattended, confirmation gate for anything touching the outside
world.

---

## 10. Migration to code — ordinary confection

### Phase 0b — Standard-mandated repairs — **mostly DONE 2026-08-02**
✅ Alpha `BZERO` (R1) · ✅ `FITA_VIS` (R3) · ✅ valid `BUNIT` (R4) · ✅ `SPLIT16` refused both
directions (R5) · ✅ `ZDEPTH` sentinel → NaN (D-5) · ✅ `FITAVER` → 1.1 · ✅ `fita.validate()` +
`fita conform` per §2.1 · ✅ §5.4 bit-exact flux test + CORE-conformance test (**the two tests
§11.5 said were missing**) · 135 passed / 0 failed.
**Remaining:** R2 + R6 — D-4 ObsCore v1.1 (8 mandatory columns, `TUCDn`, and a provenance parameter
on `io.write()`), which together are the only thing standing between the writer and **FITA-FULL**.
Then D-3 `FITA_ADJ`, D-6 `FITA_ZSC`, D-7 guide demotion.

### Phase 0a — Robust install (the IrenBLink lesson) — **the last live blocker**
Now the *trailing* item, not the leading one: `fita` is not on PATH and `python -m fita` is the
working invocation. Proper wheels with console entry points, not editable installs; `pip install
fita uranodyne` working from any `cwd`. Add **`fita doctor`** — verifies the install imports from an
arbitrary directory and that every registered Op resolves. CI matrix (Win/Linux, py3.9–3.13) on a
clean venv. **This is what makes the ratified format and its validator actually reachable by anyone
who is not standing in `C:\Users\astro\fita`** — the same failure mode as IrenBLink, one level up.

### Phase 1 — Ring B: the I/P/E Bus
`Op`, `ParamSpec`, `MediaSpec`, `Job`, `Manifest`, three registries, `validate()` integration.
Wrap existing Ring A functions as Ops (no new science). Wire entry-point discovery.

### Phase 2 — Ring C surface 1: the registry-generated CLI
`fita ingest|process|emit|validate|doctor`, subparsers and help generated from `ParamSpec`. Legacy
7 verbs retained as aliases.

### Phase 3 — Ring C surface 2: `fitad` + MCP + Format Card
HTTP/JSON and MCP, both generated from the registries; Format Card served and shipped.

### Phase 4 — Ring C surface 3: frozen distribution
`fita.exe` via PyInstaller/`shiv`; signed per-platform artifacts.

### Phase 5 — Extension
`FITA_ADJ` and/or `FITA_OPLOG` per D-3 (with the `FITAVER` bump §13 requires); new Ops `to-psd`,
`to-png`, `from-image`, `from-votable`; `h5py` install + HDF5 backend verification to complete the
three-backend equivalence claim.

### Packaging invariants
One source of truth (the `Op` objects) — CLI, API, MCP, docs all generated. The kernel `fita` never
imports `uranodyne`; science Ops register from the `uranodyne` side (already true — preserve it).

---

## 11. Curated critical assembly

| # | Component | Status | Why critical | Depends on |
|---|-----------|--------|--------------|-----------|
| **C2** | Repairs + `fita.validate()` + flux bit-exactness test | **DONE** except R2/R6 | Every conformance and adoption claim was false until these landed. `validate()` is the standard's own answer to §11.5. | D-1, D-2 ✅ |
| **C1** | Wheels + console scripts + `fita doctor` | **DONE 2026-08-02** | No robust install, no `.exe` domain, and no reachable validator. Diagnosis found 5 defects, not 1; wheels verified in a clean venv from the shadowing directory. | — |
| **C2b** | D-4: ObsCore v1.1 + provenance parameter on `io.write()` | **DONE 2026-08-02** | Closed the last gap to **FITA-FULL**; the VO/LVM provenance claim is now earned. | C2 |
| **C3** | Ring B: `Op`/`Job`/`Manifest` + 3 registries | PARKed | The one new abstraction; makes the format discoverable, testable, agent-drivable. | C1 |
| **C4** | Ingest + emit contracts (provenance in, fidelity logged out) | PARKed | Makes standard §10.3's interconversion contract executable. | C2b, C3 |
| **C5** | Registry-generated CLI | PARKed | Proves "one description, many surfaces" before more surfaces are built. | C3 |
| **C6** | Format Card + MCP server | Card drafted (v0.2) | AI-awareness; agents operate FITA safely and correctly, defects included. | C3, C5 |
| **C7** | `FITA_ADJ` serialisation (D-3, ruled IMPLEMENT) | **DONE 2026-08-02** | Unlocked the display half of the self-improvement loop (§6.1) and satisfied FITR §8's dangling dependency. | C2 |
| **C8** | Frozen `fita.exe` | PARKed | The literal distributable; the community drop-in. | C5 |

**v0.2 said "the kernel of the kernel is C1 + C2 — C1 makes it run anywhere, C2 makes it true," and
argued correctness precedes abstraction. That ordering held**: C2 shipped first and C1 is what
remains. The consequence is worth stating plainly — **FITA is now a ratified format with a working
conformance validator that almost nobody can invoke**, because `fita` is not on PATH. For a design
whose entire premise is community adoption, that single gap is the highest-leverage remaining work.

---

## 12. Open decisions

**D-1…D-7 were RATIFIED 2026-08-02** (full standard slate; record:
`FITA_v1.1_RATIFICATION__2026-08-02.md`). They are no longer open. Their resolution and remaining
implementation debt:

| | Ruling | Implementation |
|---|---|---|
| **D-1** version strategy | v1.1 + **grandfather** the 18 files | ✅ `FITA_VERSION = "1.1"` |
| **D-2** SPLIT16 | **DELETE** — writer MUST NOT emit, reader MUST raise | ✅ raises both ways; `pack` Op now vestigial (§5) |
| **D-3** `FITA_ADJ` | **IMPLEMENT** the BINTABLE (serialise `AdjustmentStack`) | ✅ **done 2026-08-02** — FITR §8 unblocked; §6.1 op-log leg now real |
| **D-4** ObsCore | ruled "FULL v1.2" — **but no ObsCore v1.2 exists**; corrected to v1.1 in v1.2.1 (see the erratum) | ✅ implemented; version claim corrected; **completeness unverified** |
| **D-5** absence convention | omission + `TNULL` | ✅ `ZDEPTH` sentinel → NaN |
| **D-6** `FITA_ZSC` | OPTIONAL, renderer-written | ⬜ open, not a blocker |
| **D-7** guide notebook | demote to tutorial + fix 2 false claims | ⬜ open |

Plus four non-optional `[CORRECTION]`s, all ✅: alpha `BZERO=32768`; valid `BUNIT`; required
`FITA_VIS`; header-normative/table-advisory + `FITAVER`-increment discipline. **MIME reverts to
`application/fits` until IANA** — as §7/P2 above already requires.

**D-8 · `[NEW]` — Does PACI belong in FITA at all?** *(raised by this design; recommend a ruling
alongside D-3)*
PACI writes `CITATION · UNCERTVL · UNCKIND · ANCHORCL` into layer `extra_header` from
`uranodyne.pipeline.paci`. It is **not** a standard §6.2 keyword and appears in no conformance
clause. The tension: standard §10.3 puts *"derived physical quantities **and their epistemic
status**"* on FITO's side of the line, and `ANCHORCL` (MEASURED/SCOUTED/ANCHORED) is epistemic
status. Three options:

- **(a)** PACI stays a `uranodyne` convention in `extra_header` — FITA never standardizes it.
  *Recommended.* Keeps FITA paradigm-free and epistemics-free per §10.3; the Foundry's ingest
  contract still stamps it, but as a science-stack convention, not a format requirement.
- **(b)** Promote `CITATION`/`UNCERTVL` (provenance + error, which FITA already half-carries via
  `UNCERT_*`) to standard keywords, leave `ANCHORCL` to FITO.
- **(c)** Full promotion to §6.2 — **not recommended**; it walks trust-classification into the image
  container and puts a crack in the §10.3 fence.

**D-9 · `[NEW]` — Frozen-exe scope.** Kernel-only `fita.exe`, or bundle `uranodyne` (astroquery,
reproject, photutils, dustmaps — large)? **Recommend** a slim `fita.exe` plus an optional
`uranodyne` plugin bundle discovered at runtime via the entry-point groups.

---

*Next physical step: **C1** — put `fita` on PATH via proper wheels + console entry points, with a
`fita doctor` guard. The format is ratified and the validator is built and green; C1 is what makes
them reachable from outside this one directory. Everything else in this document stays PARKed until
the FITA paper ships.*
