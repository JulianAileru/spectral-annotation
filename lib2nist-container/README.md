# nist-tools

Docker image bundling **lib2nist64** and **MSPepSearch64** (NIST Windows executables) under Wine on Ubuntu 22.04. Used to convert open spectral library formats (MSP, SDF) to the NIST binary format required by MSPepSearch, and to run spectral library searches.

Designed for local Docker use and Apptainer deployment on Longleaf HPC.

---

## Contents

| Path in image | Description |
|---|---|
| `/opt/lib2nist/` | lib2nist64.exe and supporting files |
| `/opt/lib2nist/convert.ini` | Output options config (editable) |
| `/opt/lib2nist/wrapper.ini` | Python wrapper config (exe paths) |
| `/opt/mspepsearch/2024_03_15_MSPepSearch_x64/` | MSPepSearch64.exe |
| `/opt/wine64/` | Pre-initialized 64-bit Wine prefix (read-only) |
| `/usr/local/bin/libconverter.py` | Conversion entrypoint (Python) |
| `/usr/local/bin/run_with_wine_prefix.sh` | Wine prefix isolation helper |

---

## Build

Build from the **project root** so both `lib2nist-container/` and `src/` are in the build context:

```bash
docker build -f lib2nist-container/Dockerfile -t nist-tools:latest .
```

The build context requires these files to exist under `lib2nist-container/binaries/` before building:

```
lib2nist-container/binaries/
  lib2nist.zip      # lib2nist64 from NIST
  MSPepSearch.zip   # MSPepSearch64 from NIST
```

---

## Converting a spectral library

`libconverter.py` converts an MSP or SDF file to NIST binary format. It can be used as a CLI tool inside the container or imported as a Python module.

```
libconverter.py --input <file> --outlib <path> [--log <file>] [--config <ini>]

  --input    MSP or SDF file (absolute path inside the container)
  --outlib   Output library path (no extension)
  --log      Optional log file path. Defaults to <outlib>.log
  --config   Optional path to wrapper.ini. Defaults to /opt/lib2nist/wrapper.ini
```

Mount your data directory to `/work`, then pass container-side paths:

```bash
docker run --rm \
  --mount type=bind,source="/path/to/your/data",target=/work \
  nist-tools:latest \
  python3 /usr/local/bin/libconverter.py --input /work/input.msp --outlib /work/output_library
```

Output is written to a subdirectory named after the library:

```
/path/to/your/data/
  output_library/
    PEAK.DBU
    PEAK.INU
    REGISTRY.INU
    USER.DBU
    ...
  output_library.log
```

### MSP example (HMDB)

```bash
docker run --rm \
  --mount type=bind,source="${PWD}/spectral_libraries/HMDB/QUERY",target=/work \
  nist-tools:latest \
  python3 /usr/local/bin/libconverter.py --input /work/msms_spectrum.msp --outlib /work/hmdb
```

### SDF example

```bash
docker run --rm \
  --mount type=bind,source="${PWD}/spectral_libraries/MoNA",target=/work \
  nist-tools:latest \
  python3 /usr/local/bin/libconverter.py --input /work/MoNA-export.sdf --outlib /work/mona
```

### Interactive session

```bash
docker run --rm -it \
  --mount type=bind,source="${PWD}/spectral_libraries",target=/work \
  nist-tools:latest
```

---

## Configuration

### `convert.ini` — output options

Controls what lib2nist produces. The `[Directory]` section is generated at runtime by `libconverter.py`; only `[Output]` needs editing.

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

To change a setting, edit `lib2nist-container/convert.ini` and rebuild the image.

### `wrapper.ini` — executable paths

Tells `libconverter.py` where to find the executables inside the container. Only needs editing if the image layout changes.

```ini
[LIB2NIST]
exe          = /opt/lib2nist/lib2nist64.exe
ini_template = /opt/lib2nist/convert.ini

[WINE]
exe           = wine64
prefix_script = /usr/local/bin/run_with_wine_prefix.sh
```

---

## Running MSPepSearch64

MSPepSearch64 is on `PATH` and can be called directly via the Wine helper:

```bash
run_with_wine_prefix.sh MSPepSearch64.exe /h
```

`run_with_wine_prefix.sh` must wrap any Wine executable call. It copies the read-only Wine prefix to a per-process temp directory before execution, which is required for parallel safety on SLURM.

---

## Registry

The image is published to GitHub Container Registry:

```bash
docker pull ghcr.io/julianaleru/nist-tools:latest
```

To push a new version after rebuilding:

```bash
docker tag nist-tools:latest ghcr.io/julianaleru/nist-tools:latest
docker push ghcr.io/julianaleru/nist-tools:latest
```

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

Or pull directly from GHCR:

```bash
apptainer pull docker://ghcr.io/julianaleru/nist-tools:latest
```

Running a conversion on Longleaf:

```bash
apptainer exec \
  --bind /work/users/j/a/jaileru/data:/work \
  /work/users/j/a/jaileru/containers/nist-tools.sif \
  python3 /usr/local/bin/libconverter.py --input /work/input.msp --outlib /work/output_library
```

SLURM provides a fast node-local `$TMPDIR` that `run_with_wine_prefix.sh` uses automatically for the Wine prefix copy.
