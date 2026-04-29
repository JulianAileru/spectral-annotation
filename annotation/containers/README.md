# nist-tools

Docker image bundling **lib2nist64** and **MSPepSearch64** (NIST Windows executables) under Wine on Ubuntu 22.04. Used to convert open spectral library formats (MSP, SDF) to the NIST binary format required by MSPepSearch, and to run spectral library searches.

Designed for local Docker use and Apptainer deployment on Longleaf HPC.

---

## Contents

| Path in image | Description |
|---|---|
| `/opt/lib2nist/` | lib2nist64.exe and supporting files |
| `/opt/lib2nist/convert.ini` | Output options config (editable) |
| `/opt/mspepsearch/2024_03_15_MSPepSearch_x64/` | MSPepSearch64.exe |
| `/opt/wine64/` | Pre-initialized 64-bit Wine prefix (read-only) |
| `/usr/local/bin/lib2nist_convert.sh` | Conversion entrypoint |
| `/usr/local/bin/run_with_wine_prefix.sh` | Wine prefix isolation helper |

---

## Build

```bash
cd nph-processing-pipeline/containers
docker build -t nist-tools:latest .
```

The build context requires these files to exist under `binaries/` before building:

```
binaries/
  lib2nist.zip      # lib2nist64 from NIST
  MSPepSearch.zip   # MSPepSearch64 from NIST
```

---

## Converting a spectral library

`lib2nist_convert.sh` converts an MSP or SDF file to NIST binary format (`.lib`, `.idx`, `.num`).

```
lib2nist_convert.sh <input> <output_library> [log_file]

  input           MSP or SDF file (absolute path inside the container)
  output_library  Output library path without extension
  log_file        Optional. Defaults to <output_library>.log
```

Mount the directory containing your input file to `/work`, then pass container-side paths:

```bash
docker run --rm \
  -v "/path/to/your/data:/work" \
  nist-tools:latest \
  lib2nist_convert.sh /work/input.msp /work/output_library
```

Output files are written back to the mounted host directory:

```
/path/to/your/data/
  output_library.lib
  output_library.idx
  output_library.num
  output_library.log
```

### SDF example (HMDB)

```bash
docker run --rm \
  -v "C:/Users/jaileru/Projects/nph-processing-pipeline/data/HMDB:/work" \
  nist-tools:latest \
  lib2nist_convert.sh /work/structures.sdf /work/HMDBLIB
```

### MSP example

```bash
docker run --rm \
  -v "C:/Users/jaileru/Projects/nph-processing-pipeline/data/MoNA:/work" \
  nist-tools:latest \
  lib2nist_convert.sh /work/MoNA-export.msp /work/MoNA
```

---

## Output options — `convert.ini`

Output behaviour is controlled by `/opt/lib2nist/convert.ini` inside the image. The `[Directory]` section is generated at runtime by `lib2nist_convert.sh`; only `[Output]` needs to be edited.

| Option | Value | Description |
|---|---|---|
| `DB` | `1` | Produce NIST binary library |
| `Text` | `0` | No ASCII text output |
| `TextFileType` | `0` | ASCII format if Text=1: 0=MSP, 1=HP-JCAMP, 2=SDF |
| `CalcMW` | `1` | Recalculate MW from chemical formula |
| `IncludeSynonyms` | `1` | Include synonym names |
| `KeepIDs` | `1` | Preserve compound IDs from input (e.g. HMDB accessions) |
| `LinkMOLfile` | `0` | No MOLfile output |
| `MzAdd` / `MzMpy` | `0` / `1` | m/z passthrough (no transformation) |
| `MsmsOnly` | `1` | Treat spectra as MS/MS — required for LC-MS/MS metabolomics data |
| `Msms2008-Compat` | `0` | Use newer format compatible with MSPepSearch64 |

To change a setting, edit `containers/convert.ini` and rebuild the image.

---

## Running MSPepSearch64

MSPepSearch64 is on `PATH` and can be called directly. Interactive terminal:

```bash
docker run --rm -it \
  -v "/path/to/your/data:/work" \
  nist-tools:latest
```

Then inside the container:

```bash
run_with_wine_prefix.sh MSPepSearch64.exe /h
```

`run_with_wine_prefix.sh` must wrap any Wine executable call. It copies the read-only Wine prefix to a per-process temp directory before execution, which is required for parallel safety on SLURM.

---

## Longleaf (Apptainer) deployment

```bash
# On local machine — save image to tar
docker save nist-tools:latest -o nist-tools.tar

# Transfer to Longleaf
scp nist-tools.tar longleaf:/work/users/j/a/jaileru/containers/

# On Longleaf — convert to SIF
ssh longleaf
apptainer build /work/users/j/a/jaileru/containers/nist-tools.sif \
    docker-archive:///work/users/j/a/jaileru/containers/nist-tools.tar
```

Running a conversion on Longleaf:

```bash
apptainer exec \
  --bind /work/users/j/a/jaileru/data:/work \
  /work/users/j/a/jaileru/containers/nist-tools.sif \
  lib2nist_convert.sh /work/input.msp /work/output_library
```

SLURM provides a fast node-local `$TMPDIR` that `run_with_wine_prefix.sh` uses automatically for the Wine prefix copy.
