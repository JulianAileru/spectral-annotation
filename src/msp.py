from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Optional,Tuple


@dataclass
class Spectrum:
    Name: str = ""
    Formula: str = ""
    MW: float = 0.0
    PrecursorMz: float = 0.0
    IonMode: Literal["P", "N"] = "P"
    NumPeaks: int = 0
    Peaks: list[tuple[float, float]] = field(default_factory=list)
    Comments: Optional[str] = None
    CollisionEnergy: Optional[str] = None


class MspFile:
    _KEY_MAP = {
    "name": "Name",
    "formula": "Formula",
    "exactmass": "MW",
    "precursormz": "PrecursorMz",
    "ion_mode": "IonMode",
    "num peaks": "NumPeaks",
    "comments": "Comments",
    "collision_energy": "CollisionEnergy",
}
    def __init__(self, path: Path, ion_mode: Literal["P", "N"]):
        self.path = Path(path)
        self.ion_mode = ion_mode
        self.spectra: list[Spectrum] = self._read_msp_file(self.path, ion_mode)

    def _read_msp_file(self, path: Path, ion_mode: Literal["P", "N"]) -> list[Spectrum]:
        spectra: list[Spectrum] = []
        current: dict = {}
        reading_peaks = False

        with open(path, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    if current:
                        spectra.append(self._build_spectrum(current, ion_mode))
                        current = {}
                        reading_peaks = False
                    continue
                if reading_peaks:
                    if line[0].isdigit():
                        mz, intensity = line.split()[:2]
                        current["peaks"].append((float(mz), float(intensity)))
                    continue
                if ":" in line:
                    key, _, val = line.partition(":")
                    key_lower = key.strip().lower()
                    if key_lower == "num peaks":
                        current["NumPeaks"] = int(val.strip())
                        current.setdefault("peaks", [])
                        reading_peaks = True
                    elif key_lower in _KEY_MAP:
                        current[_KEY_MAP[key_lower]] = val.strip()

        if current:
            spectra.append(self._build_spectrum(current, ion_mode))

        return spectra
    def _read_xml_file(self,path:Path,ion_mode: Literal["P","N"]):
        spectra: list[Spectrum] = []
        current: dict = {}
        reading_peaks = False
        if current:
            spectra.append(self.build_sepctrum(current,ion_mode))
        pass

    def _build_spectrum(self, raw: dict, ion_mode: Literal["P", "N"]) -> Spectrum:
        return Spectrum(
            Name=raw.get("Name", ""),
            Formula=raw.get("Formula", ""),
            MW=float(raw.get("MW", 0.0)),
            PrecursorMz=float(raw.get("PrecursorMz", 0.0)),
            IonMode=ion_mode,
            NumPeaks=int(raw.get("NumPeaks", 0)),
            Peaks=raw.get("peaks", []),
            Comments=raw.get("Comments"),
            CollisionEnergy=raw.get("CollisionEnergy"),
        )

    def __len__(self) -> int:
        return len(self.spectra)

    def __iter__(self):
        return iter(self.spectra)

@dataclass
class Option:
    flag: Optional[str] = None
    choices: Optional[Mapping[Any,Any]] = None
    takes_value: bool  = True

class MSPepSearch:
    _OPTIONS = {
        "resolution": Option(
            "",value_map={"high": "HiRes",
                          "low":"LoRes"}
        ),
        "scoring_type": Option(
            "",
            value_map={
                "peptide": "p",
                "generic": "g",
                "dot": "d",
            }
        ),
        "precursor_filtering": Option(
            "/Z",
            value_map={
                "match_with_tol": "match_with_tol",
                "ignore": "u",
                "hybrid": "y",
            }
        ),
        "precursor_algorithm": Option(
            "",
            value_map={
                "Standard":"d",
                "Fast":"f",
                "PrecursorTol": "m",
                "RetentionTimeTol":"d",
                "All":"s",

            }
        )
    }
    def __init__(self,
                 query: MspFile,
                 library: SpectralLibrary,
                 resolution:Literal['high','low'],
                 scoring_type:Literal['peptide','generic','dot'],
                 precursor_filtering: Literal['match_with_tol','ignore','hybrid'],
                 presearch_algorithm: Literal['Standard','Fast','PrecursorTol','RetentionTimeTol','All'],
                 max_hits: Optional[int|None] = 100,
                 min_match_factor: Optional[int] = 500
                 ):
        self.resolution = resolution
        self.scoring_type = scoring_type
        self.precursor_filtering = precursor_filtering
        self.presearch_algorithm = presearch_algorithm
        self.max_hits = max_hits
        self.min_match_factor = min_match_factor
        self.library = library
    def _write_executable(self):
        pass





@dataclass
class SpectralLibrary:
    library_name: str = ""
    files: list[MspFile] = field(default_factory=list)
    presearch_algorithm: str = "RetentionTimeTol"
    retention_time_tolerance: Optional[Tuple[float,float]]
    @property
    def positive(self) -> Optional[MspFile]:
        return next((f for f in self.files if f.ion_mode == "P"), None)

    @property
    def negative(self) -> Optional[MspFile]:
        return next((f for f in self.files if f.ion_mode == "N"), None)

    def __len__(self) -> int:
        return len(self.files)

    def __iter__(self):
        return iter(self.files)

