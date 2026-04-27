# Metabolomics Annotation Pipeline — Design Document

**Status:** Architecture finalized; module specification in progress
**Framework:** Nextflow (DSL2), nf-core template structure
**Target:** Publishable, portable LC-MS/MS metabolomics pipeline from raw mzML to annotated peak tables

---

## 1. Pipeline overview

A Nextflow pipeline that takes raw LC-MS/MS data (mzML) and a sample sheet as input, performs peak detection and alignment, runs batch effect correction and annotation in parallel, and produces both a curated final output set and an uncorrected intermediate set for users who prefer their own correction methods.

### Tool stack

| Stage | Tool | Language / runtime |
|-------|------|-------------------|
| Peak detection (per file) | IDSL.IPA | R |
| Alignment, grouping, composite MS2 | IDSL.CSA | R |
| Batch effect correction | serrf-py (custom port) | Python |
| RSD filtering | custom | Python |
| Library format conversion | lib2nist.exe | Windows binary (Wine) |
| Spectral library matching | MSPepSearch64.exe | Windows binary (Wine) |

---

## 2. Pipeline DAG

```
                    mzML files + sample sheet
                              │
                              ▼
                       ┌─────────────┐
                       │ INPUT_CHECK │
                       └──────┬──────┘
                              │
                              ▼
                       ┌─────────────┐
                       │  IDSL.IPA   │  per-sample peak detection
                       │ (parallel)  │  (Nextflow fan-out)
                       └──────┬──────┘
                              │
                              ▼
                       ┌─────────────┐
                       │  IDSL.CSA   │  alignment, grouping,
                       │ (aggregate) │  composite MS2 spectra
                       └──────┬──────┘
                              │
                  ┌───────────┴────────────┐
                  │                        │
       feature_table.tsv            features.msp
       (all features)               (all features)
                  │                        │
        ┌─────────┴─────────┐    ┌─────────┴─────────┐
        │                   │    │                   │
        ▼                   │    ▼                   │
 ┌──────────────┐           │  ┌──────────────┐      │
 │ SERRF        │           │  │ MSPEPSEARCH  │      │
 │ batch corr.  │           │  │ × N libs     │      │
 └──────┬───────┘           │  │ (parallel)   │      │
        │                   │  └──────┬───────┘      │
        ▼                   │         │              │
 ┌──────────────┐           │         ▼              │
 │ RSD_FILTER   │           │  ┌──────────────┐      │
 └──────┬───────┘           │  │ MERGE_LIB_   │      │
        │                   │  │ HITS         │      │
        │                   │  └──────┬───────┘      │
        │                   │         │              │
        └────────┬──────────┴─────────┴──────────────┘
                 │
                 ▼
        ┌──────────────────┐
        │  FINAL_MERGE     │  filter MSP and annotations to
        │                  │  features surviving SERRF + RSD
        └────────┬─────────┘
                 │
                 ▼
       ┌──────────────────┐
       │  REPORT          │  MultiQC-style summary
       └──────────────────┘
```

The library preparation workflow (`prepare_libraries.nf`) is **separate** from the main pipeline and runs once per library version, with outputs cached via `storeDir`.

---

## 3. Inputs

### 3.1 Sample sheet schema

```csv
sample,mzml,polarity,batch,sample_type
S001,/abs/path/S001.mzML,pos,batch01,biological
QC001,/abs/path/QC001.mzML,pos,batch01,QC
BLK001,/abs/path/BLK001.mzML,pos,batch01,blank
```

| Column | Type | Allowed values | Required |
|--------|------|----------------|----------|
| `sample` | string | unique sample ID | yes |
| `mzml` | path | absolute path to mzML | yes |
| `polarity` | string | `pos`, `neg` | yes |
| `batch` | string | batch identifier | yes |
| `sample_type` | string | `biological`, `QC`, `blank` | yes |

The pipeline does **not** include nuisance variables like instrument, timepoint, or experimental group in the sample sheet. Users with non-standard study designs supply their own metadata to downstream tools (or substitute their own correction method using the intermediate output files).

### 3.2 Other inputs

- **Library configuration** (separate config): list of NIST-format libraries to search against, with paths.
- **Raw source libraries** (one-time, for library prep workflow): MSP files from MoNA, MassBank, GNPS, NIST23, etc., to be converted via lib2nist.

---

## 4. Outputs

The pipeline produces **six output files in two tiers**.

### 4.1 Final outputs (publication-ready)

Restricted to features that survive SERRF batch correction AND RSD filtering.

| File | Description |
|------|-------------|
| `final_peak_table.tsv` | SERRF-corrected, RSD-filtered intensities (samples × features) |
| `final_features.msp` | MS2 spectra for surviving features |
| `final_annotations.tsv` | MSPepSearch hits per surviving feature |

### 4.2 Intermediate outputs (full transparency)

Contains every feature CSA produced. Allows users to apply their own correction methods or audit dropped features.

| File | Description |
|------|-------------|
| `intermediate_peak_table.tsv` | Uncorrected CSA feature table (all features) |
| `intermediate_features.msp` | All MS2 spectra from CSA |
| `intermediate_annotations.tsv` | MSPepSearch hits for all features |

**Design rationale:** Producing both tiers makes the pipeline scientifically honest and broadly useful. Users with standard study designs use the final tier; users with non-standard designs (multi-instrument, drug-response time courses, etc.) take the intermediate tier and supply their own correction. The pipeline never makes correction decisions on the user's behalf without also exposing the raw data.

---

## 5. Module list

| # | Module | Purpose | Container |
|---|--------|---------|-----------|
| 1 | `INPUT_CHECK` | Validate sample sheet schema, check file existence | python |
| 2 | `IDSL_IPA` | Per-sample peak detection (parallel) | r-idsl |
| 3 | `IDSL_CSA` | Alignment, grouping, composite MS2 (aggregate) | r-idsl |
| 4 | `SERRF_BATCH_CORRECTION` | Batch effect correction using QC samples | python-serrf |
| 5 | `RSD_FILTER` | Drop features with QC RSD above threshold | python |
| 6 | `MSPEPSEARCH` | Spectral library matching, fan out × libraries | nist-tools (Wine) |
| 7 | `MERGE_LIBRARY_HITS` | Combine annotation hits across libraries per feature | python |
| 8 | `FINAL_MERGE` | Filter MSP and annotations to surviving feature set | python |
| 9 | `REPORT` | MultiQC-style summary | multiqc |

Plus separate library prep workflow:

| Module | Purpose | Container |
|--------|---------|-----------|
| `LIB2NIST` | Convert source MSPs to NIST binary library format | nist-tools (Wine) |

---

## 6. Containers

| Image | Purpose | Base |
|-------|---------|------|
| `r-idsl` | IDSL.IPA + IDSL.CSA | rocker/r-ver |
| `python-serrf` | serrf-py + pandas + sklearn | python:3.11 |
| `nist-tools` | Wine + lib2nist.exe + MSPepSearch64.exe | ubuntu:22.04 |

The `nist-tools` container has the Wine prefix pre-initialized at build time (`wineboot --init` baked into the image) to avoid race conditions when many parallel processes start up. At runtime, each process copies the prefix to `$TMPDIR` for write isolation.

---

## 7. Library preparation (separate workflow)

`prepare_libraries.nf` is a one-time workflow that converts source MSP files to NIST binary format using lib2nist. Output is cached to `/proj/<lab>/lib_cache/` via Nextflow's `storeDir` directive, so subsequent pipeline runs skip this step entirely.

```
source_libs/
  ├── MoNA-LCMSMS-Pos.msp        ─┐
  ├── MoNA-LCMSMS-Neg.msp         │
  ├── MassBank_NA.msp             ├── lib2nist.exe (Wine) ──→  NIST binary libraries
  ├── GNPS-LIBRARY.msp            │                               (cached, indexed)
  └── inhouse_sumner_v2024.msp   ─┘
```

Library version bumps (e.g., NIST23 → NIST24) trigger a rebuild only for affected libraries.

---

## 8. Open questions

These need to be resolved before module implementation begins.

### 8.1 IDSL.CSA output formats

Need to confirm directly from CSA documentation or test runs:

- Feature table file format (TSV / CSV / RDS / parquet)
- MSP file format and metadata fields included
- Feature ID convention (e.g., `FT0001`, `mz123.4567_RT2.34`, sequential integer, UUID)
- Whether MSP file is keyed identically to feature table (must be true for downstream merge)

### 8.2 lib2nist CLI behavior

Need to verify by interactive testing inside the `nist-tools` container:

- Whether lib2nist runs as 32-bit or 64-bit under Wine (affects `WINEARCH`)
- Exact command-line flags (documentation is sparse)
- Whether GUI mode is required for some operations (would need `xvfb-run`)

### 8.3 serrf-py packaging

`serrf-py` lives in a private GitHub repository. For the container build:

- Pinning strategy: tag, commit SHA, or branch
- Whether to include credentials in the container build (private repo) or vendor the source
- Public release timeline (would simplify container reproducibility)

---

## 9. Decisions made (locked in)

The following decisions are settled and not under active debate:

1. **Two-stream parallel architecture.** Batch correction and annotation run in parallel after CSA, joining only at the final merge.

2. **Annotation runs on all CSA features**, not just survivors of SERRF + RSD. Wasted compute on dropped features is preferable to losing parallelism. Side benefit: enables diagnostic reporting on annotation quality of dropped features.

3. **Six-file output** (three final, three intermediate) with content overlap accepted for the surviving feature set. Disk redundancy is preferable to forcing users to do post-hoc filtering.

4. **Sample sheet does not include nuisance variables.** Pipeline produces intermediate uncorrected output for users with non-standard designs.

5. **Library preparation is a separate, cached workflow.** Not part of the main per-study pipeline.

6. **Wine in containers, not conda or bare metal.** Container build pre-initializes the Wine prefix.

7. **nf-core template structure.** Pipeline targets nf-core conventions for modules, configs, sample sheet validation, and reporting.

---

## 10. Next steps

1. Confirm IDSL.CSA output formats (open question 8.1)
2. Confirm lib2nist CLI invocation under Wine (open question 8.2)
3. Pin serrf-py packaging approach (open question 8.3)
4. Generate nf-core template skeleton via `nf-core create`
5. Implement and test modules in dependency order:
   - `INPUT_CHECK` (no dependencies)
   - `IDSL_IPA` → `IDSL_CSA` (upstream)
   - `LIB2NIST` (independent, run once)
   - `MSPEPSEARCH` and `MERGE_LIBRARY_HITS` (annotation stream)
   - `SERRF_BATCH_CORRECTION` and `RSD_FILTER` (correction stream)
   - `FINAL_MERGE` (joins streams)
   - `REPORT` (consumes everything)
