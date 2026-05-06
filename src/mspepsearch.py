from dataclasses import dataclass
from pathlib import Path
import sys,os
sys.path.append(os.path.abspath(r"C:\Users\jaileru\Projects\spectral-annotation"))
from src.msp import MspFile, SpectralLibrary
from typing import Any, Mapping, Optional, Literal
import subprocess
import logging


@dataclass
class Option:
    flag: str
    value_map: dict
    default_val: str
    choices: Optional[Mapping[Any, Any]] = None


class MSPepSearch:
    _HIRES_TYPES = {"peptide", "generic", "dot"}

    _OPTIONS = {
        "scoring_type": Option(
            flag="",
            value_map={
                # HiRes
                "peptide": "P",
                "generic": "G",
                "dot": "D",
                # LoRes
                "identity": "I",
                "quick_identity": "Q",
                "simple_similarity": "S",
                "hybrid": "H",
                "neutral_loss": "L",
                "msms_ei": "M",
            },
            default_val="generic",
        ),
        "precursor_filtering": Option(
            flag="",
            value_map={
                "match_with_tol": "z",
                "ignore": "u",
                "hybrid": "y",
            },
            default_val="match_with_tol",
        ),
        "presearch_algorithm": Option(
            flag="",
            value_map={
                "Standard": "d",
                "Fast": "f",
                "PrecursorTol": "m",
                "All": "s",
            },
            default_val="Standard",
        ),
    }

    def __init__(
        self,
        query: MspFile,
        library: SpectralLibrary,
        lib_paths: list[str],
        runtime: Literal["docker", "apptainer"] = "docker",
        scoring_type: Literal[
            "peptide", "generic", "dot",
            "identity", "quick_identity", "simple_similarity",
            "hybrid", "neutral_loss", "msms_ei"
        ] = "generic",
        precursor_filtering: Literal["match_with_tol", "ignore", "hybrid"] = "match_with_tol",
        presearch_algorithm: Literal["Standard", "Fast", "PrecursorTol", "All"] = "Standard",
        verbose: bool = True,
        return_best_hits_only: bool = False,
        precursor_mz_tol: float = 1.6,
        fragment_mz_tol: float = 0.6,
        max_hits: int = 100,
        min_match_factor: int = 500,
        image: str = "ghcr.io/julianaileru/spectral-annotation/mspepsearch:latest",
    ):
        self.query = query
        self.library = library
        self.lib_paths = lib_paths
        self.runtime = runtime
        self.scoring_type = scoring_type
        self.precursor_filtering = precursor_filtering
        self.presearch_algorithm = presearch_algorithm
        self.verbose = verbose
        self.return_best_hits_only = return_best_hits_only
        self.precursor_mz_tol = precursor_mz_tol
        self.fragment_mz_tol = fragment_mz_tol
        self.max_hits = max_hits
        self.min_match_factor = min_match_factor
        self.image = image

    @property
    def is_hires(self) -> bool:
        return self.scoring_type in self._HIRES_TYPES

    def _build_positional_flags(self) -> str:
        opts = self._OPTIONS
        presearch = opts["presearch_algorithm"].value_map[self.presearch_algorithm]
        scoring = opts["scoring_type"].value_map[self.scoring_type]

        flags = presearch
        if self.is_hires:
            flags += opts["precursor_filtering"].value_map[self.precursor_filtering]
        flags += scoring
        return flags

    def _build_cmd(self, input_path: str, lib_paths: list[str], output_path: str, lib_in_mem: bool = True) -> list[str]:
        cmd = ["MSPepSearch64.exe", self._build_positional_flags()]

        # --- Presearch options ---
        cmd += ["/INP", input_path]
        for lib in lib_paths:
            cmd += ["/LIB", lib]
        if lib_in_mem:
            cmd += ["/LibInMem"]

        # --- HiRes / LoRes search options ---
        if self.is_hires:
            cmd += ["/Z", str(self.precursor_mz_tol)]
            cmd += ["/M", str(self.fragment_mz_tol)]
        cmd += ["/MatchPolarity"]
        cmd += ["/MatchCharge"]

        # --- Output options ---
        cmd += ["/OUTTAB", output_path]
        cmd += ["/HITS", str(self.max_hits)]
        cmd += ["/MinMF", str(self.min_match_factor)]
        cmd += ["/OutPrecursorType",
                "/OutMW",
                "/OutChemForm",
                "/OutIK",
                "/OutDeltaMW",
                "/OutNumMP"]
        if self.return_best_hits_only:
            cmd += ["/OutBestHitsOnly"]

        return cmd

    def _build_container_cmd(self, output_path: str) -> list[str]:
        input_path = str(self.query.path)
        output_dir = str(Path(output_path).parent)

        input_bind = f"{input_path}:/work/input.msp"
        output_bind = f"{output_dir}:/work/output"
        container_output = "/work/output/" + Path(output_path).name

        container_lib_paths = []
        lib_binds = []
        for i, lib in enumerate(self.lib_paths):
            container_lib = f"/work/lib{i}"
            lib_binds.append(f"{lib}:{container_lib}")
            container_lib_paths.append(container_lib)

        mspepsearch_cmd = self._build_cmd("/work/input.msp", container_lib_paths, container_output)

        if self.runtime == "docker":
            container_cmd = ["docker", "run", "--rm", "-v", input_bind, "-v", output_bind]
            for bind in lib_binds:
                container_cmd += ["-v", bind]
        else:
            if self.runtime == "apptainer":
                print("Please Load Apptainer Module")
            container_cmd = ["apptainer", "exec", "--bind", input_bind, "--bind", output_bind]
            for bind in lib_binds:
                container_cmd += ["--bind", bind]

        return container_cmd + [self.image] + mspepsearch_cmd

    def run(self, output_path: str) -> None:
        cmd = self._build_container_cmd(output_path)
        subprocess.run(cmd, check=True)
