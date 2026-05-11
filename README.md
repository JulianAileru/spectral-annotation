# spectral-annotation

A pipeline for annotating MS/MS spectra against spectral libraries. Converts MSP spectral libraries to NIST binary format and searches query spectra using NIST MSPepSearch64 — driven from Python with Docker or Apptainer for cross-platform compatibility.

---

## Overview

```
MSP File  (any spectral library in MSP format)
    ↓  SpectralLibrary.build_nist_library  →  lib2nist-container
NIST Binary Library
    ↓  MSPepSearch.run  →  mspepsearch-container
TSV Results  (Name, Score, Dot Product, InChIKey, Formula, ...)
```

---

## Requirements

- Python 3.10+
- Docker (or Apptainer on HPC)
- NIST binary tools (`lib2nist64.exe`, `MSPepSearch64.exe`) — **not distributed here**; place them in `lib2nist-container/binaries/` before building the image (see [lib2nist-container/README.md](lib2nist-container/README.md))

Python dependencies:

```
tqdm
```

---

## Project Structure

```
spectral-annotation/
├── src/
│   ├── msp.py              # Spectrum / MspFile / SpectralLibrary classes
│   ├── mspepsearch.py      # MSPepSearch wrapper + parallel search
│   └── libconverter.py     # lib2nist Wine wrapper (runs inside the container)
├── notebooks/
│   └── build_msp_parser.ipynb   # MSPepSearch usage examples
├── lib2nist-container/     # Docker image for lib2nist64 (see its own README)
└── mspepsearch-container/  # Docker image for MSPepSearch64
```

---

## Step 1 — Build NIST Library

```python
from src.msp import MspFile, SpectralLibrary

pos = MspFile("spectral_libraries/my_library_P.msp", ion_mode="P")
library = SpectralLibrary(
    library_name="my_library",
    runtime="docker",
    image="ghcr.io/julianaileru/spectral-annotation/nist-tools:latest",
    files=[pos],
)

library.build_nist_library(
    ion_mode="P",
    output_lib="spectral_libraries/NIST/my_library_P",
)
# Creates:  spectral_libraries/NIST/my_library_P/
#               PEAK.DBU, REGISTRY.INU, USER.DBU, ...
```

For container build instructions see [lib2nist-container/README.md](lib2nist-container/README.md).

---

## Step 2 — Search Query Spectra

```python
from src.msp import MspFile, SpectralLibrary
from src.mspepsearch import MSPepSearch, SearchAlgorithm

query   = MspFile("example/INPUT/query.msp", ion_mode="P")
library = SpectralLibrary(library_name="my_library", files=[pos])

search = MSPepSearch(
    query=query,
    library=library,
    algorithm=SearchAlgorithm.IDENTITY_MSMS,
    lib_paths=["spectral_libraries/NIST/my_library_P"],
    runtime="docker",
    min_match_factor=500,
)

search.run("example/OUTPUT/results.txt", n_cores=4)
```

Results are written as a tab-separated file readable with pandas:

```python
import pandas as pd
df = pd.read_table("example/OUTPUT/results.txt", sep="\t", header=3)
```

Output columns include: `Unknown`, `Rank`, `Score`, `Dot Product`, `Library`, `Id`, `InChIKey`, `Formula`, `Prec.Type`, `DeltaMW`, `Nreps`.

---

## Search Algorithms

| Algorithm | Description | Precursor filter | Fragment filter |
|---|---|---|---|
| `IDENTITY_MSMS` | Hybrid identity search for LC-MS/MS data | ppm window | Da window |
| `IDENTITY_HIRES` | High-resolution identity search | — | Da window |
| `SIMILARITY_MSMS_HYBRID` | Hybrid similarity search | ppm window | Da window |
| `SIMILARITY_MSMS_EI` | Electron-ionization similarity search | — | — |

### Key parameters

| Parameter | Default | Description |
|---|---|---|
| `precursor_mz_tol` | `20` ppm | Precursor mass tolerance |
| `fragment_mz_tol` | `0.01` Da | Fragment ion tolerance |
| `ignore_precursor_mz_tol` | `1.6` Da | Window around precursor excluded from fragment matching |
| `max_hits` | `100` | Maximum hits reported per query spectrum |
| `min_match_factor` | `500` | Minimum match factor (0–999) to report a hit |
| `return_best_hits_only` | `False` | Emit only the top-ranked hit per spectrum |

---

## Parallel Search

`MSPepSearch.run(output_path, n_cores=N)` splits the query into `N` equal chunks, launches `N` container instances concurrently via `ThreadPoolExecutor`, and merges the results into a single output file. A tqdm progress bar tracks chunk completion.

---

## HPC (Apptainer / Longleaf)

Set `runtime="apptainer"` and point `image` at a `.sif` file. See [lib2nist-container/README.md](lib2nist-container/README.md) for instructions on building the SIF and running on Longleaf SLURM.

---

## Notes

- NIST library flags for custom NIST library references are planned for a future release.
