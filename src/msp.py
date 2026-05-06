from __future__ import annotations
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Optional, Tuple, Mapping, Any
import subprocess

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
    def __init__(self, path: Optional[Path | str], ion_mode: Literal["P", "N"], spectra: Optional[list[Spectrum]] = None):
        self.path = Path(path) if path else None
        self.ion_mode = ion_mode
        self.spectra: list[Spectrum] = spectra if spectra is not None else self._read_msp_file(self.path, ion_mode)

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
                    elif key_lower in self._KEY_MAP:
                        current[self._KEY_MAP[key_lower]] = val.strip()

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
    def chunk(self, n_cores: int = 8) -> list[MspFile]:
        size = math.ceil(len(self.spectra) / n_cores)
        return [
            MspFile(path=None, ion_mode=self.ion_mode, spectra=self.spectra[i : i + size])
            for i in range(0, len(self.spectra), size)
        ]

    _MSP_FIELD_NAMES = {
        "Name": "Name",
        "Formula": "Formula",
        "MW": "ExactMass",
        "PrecursorMz": "PrecursorMZ",
        "IonMode": "Ion_mode",
        "NumPeaks": "Num Peaks",
        "Comments": "Comments",
        "CollisionEnergy": "Collision_energy",
    }

    def to_msp(self) -> str:
        blocks: list[str] = []
        for s in self.spectra:
            lines: list[str] = []
            for attr, msp_key in self._MSP_FIELD_NAMES.items():
                val = getattr(s, attr)
                if val is None:
                    continue
                if attr == "NumPeaks":
                    lines.append(f"{msp_key}: {len(s.Peaks)}")
                    for mz, intensity in s.Peaks:
                        lines.append(f"{mz} {intensity}")
                else:
                    lines.append(f"{msp_key}: {val}")
            blocks.append("\n".join(lines))
        return "\n\n".join(blocks) + "\n"


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
class SpectralLibrary:
    library_name: str 
    runtime: Literal['docker','apptainer'] = 'docker'
    image: str = "/spectral-annotation/lib2nist-container/apptainer-files/nist-tools-latest.sif"
    files: list[MspFile] = field(default_factory=list)
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
    def _build_container_cmd(self, input_path: str, output_lib: str) -> list[str]:
        output_dir = str(Path(output_lib).parent)
        input_bind = f"{input_path}:/work/input.msp"
        output_bind = f"{output_dir}:/work/output"
        container_outlib = "/work/output/" + Path(output_lib).name

        if self.runtime == "docker":
            return ["docker", "run", "--rm",
                    "-v", input_bind, "-v", output_bind,
                    self.image, "python3", "/usr/local/bin/libconverter.py",
                    "--input", "/work/input.msp", "--outlib", container_outlib]
        else:
            print("Please Load Apptainer Module")
            return ["apptainer", "exec",
                    "--bind", input_bind, "--bind", output_bind,
                    self.image, "python3", "/usr/local/bin/libconverter.py",
                    "--input", "/work/input.msp", "--outlib", container_outlib]
    def build_nist_library(self,ion_mode:Literal["P","N"],output_lib:str):
        for msp_file in self.files:
            if msp_file.ion_mode == ion_mode:
                cmd = self._build_container_cmd(str(msp_file.path),output_lib)
                subprocess.run(cmd,check=True)
            else:
                continue


