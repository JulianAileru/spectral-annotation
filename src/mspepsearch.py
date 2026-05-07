from dataclasses import dataclass
from pathlib import Path
import sys,os
sys.path.append(os.path.abspath(r"C:\Users\jaileru\Projects\spectral-annotation"))
from src.msp import MspFile, SpectralLibrary
from typing import Any, Mapping, Optional, Literal
import subprocess
import logging

from dataclasses import dataclass
from typing import ClassVar, Literal
from enum import Enum


class SearchAlgorithm(Enum):
    IDENTITY_MSMS          = ("azlGmi", True)
    IDENTITY_HIRES         = ("aulGd", True)
    SIMILARITY_MSMS_HYBRID = ("aylGd", True)
    SIMILARITY_MSMS_EI     = ("Md", False)

    def __init__(self, flags: str, hires: bool):
        self.flags = flags
        self.hires = hires




class MSPepSearch:
    def __init__(
        self,
        query: MspFile,
        library: SpectralLibrary,
        algorithm: SearchAlgorithm,
        lib_paths: list[str],
        runtime: Literal["docker", "apptainer"] = "docker",
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
        self.algorithm = algorithm
        self.lib_paths = lib_paths
        self.runtime = runtime
        self.verbose = verbose
        self.return_best_hits_only = return_best_hits_only
        self.precursor_mz_tol = precursor_mz_tol
        self.fragment_mz_tol = fragment_mz_tol
        self.max_hits = max_hits
        self.min_match_factor = min_match_factor
        self.image = image


    def _build_positional_flags(self) -> str:
        return self.algorithm.flags

    def _build_cmd(self, input_path: str, lib_paths: list[str], output_path: str, lib_in_mem: bool = True) -> list[str]:
        cmd = ["MSPepSearch64.exe", self._build_positional_flags()]
        cmd += ["/INP", input_path]
        for lib in lib_paths:
            cmd += ["/LIB", lib]
        if lib_in_mem:
            cmd += ["/LibInMem"]

        if self.algorithm.name == "IDENTITY_MSMS":
            cmd += ["/ZPPM", str(self.precursor_mz_tol)]
            cmd += ["/ZI",1.6]
            cmd += ["/M", str(self.fragment_mz_tol)]
        elif self.algorithm.name == "IDENTITY_HIRES":
            cmd += ["/M",str(self.fragment_mz_tol)]
        elif self.algorithm.name == "SIMILARITY_MSMS_HYBRID":
            cmd += ['/ZPPM',str(self.precursor_mz_tol)]
            cmd += ["/M",str(self.fragment_mz_tol)]
        elif self.algorithm.name == 'SIMILARITY_MSMS_EI':
            pass 
        else:
            raise ValueError("Algorithm Not Found")
        
        
        cmd += ["/MatchPolarity", "/MatchCharge"]
        cmd += ["/OUTTAB", output_path]
        cmd += ["/HITS", str(self.max_hits)]
        cmd += ["/All"]
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
