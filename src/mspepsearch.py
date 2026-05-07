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
    value_map: dict
    default_val: str
    flag: str = ""
    choices: Optional[Mapping[Any, Any]] = None



class MSPepSearch: 
    _OPTIONS = {"HiResSearch Options":Option(value_map={"generic":"G",
                                                        "peptide":"P",
                                                        "dot":"D"},
                                                        default_val="generic"),
                "LowResSearch Options":Option(value_map={"Identity": "I",
                                                         "SimpleSimilarity":"S",
                                                         "HybridSimiliarity":"H",
                                                         "NeutralLossSimilarity":"L",
                                                         "MsMsEI": "M"
                                                         },
                                                         default_val=None),
                "Presearch Options": Option(value_map={"Standard":"d",
                                                       "Fast":"f",
                                                       "PrecursorIonTol":"m",
                                                       "Sequential":"s"},
                                                       default_val='PrecursorIonTol'),
                "AdditionalHiResSearch Options":Option(value_map={"RejectHits":"j",
                                                                  "AlternativePeakMatching":"a",
                                                                  "IgnorePeakbyZI":"i",
                                                                  },default_val='AlternativePeakMatching'),
                "PrecursorMode Options":Option(value_map={"MsMs":"z",
                                                          "NoMatch":"u",
                                                          "Hybrid":"y"},
                                                          default_val="MsMs"),
                "SearchThreshold Options":Option(value_map={"Low":"l",
                                                            "Medium":"e",
                                                            "High":"h"},
                                                            default_val="Low"),
                "SearchParameters":Option(value_map={"ReverseSearch":"r[2]",
                                                     "PenalizeRareCompounds":"p",
                                                     "NoHitProbOut":"h"},
                                                     default_val=None)
                }

    def __init__(
        self,
        query: MspFile,
        library: SpectralLibrary,
        lib_paths: list[str],
        runtime: Literal["docker", "apptainer"] = "docker",
        resolution: Literal["HiRes","LoRes"] = "HiRes",
        scoring_type: Literal[
            "generic", "peptide", "dot",
            "Identity", "SimpleSimilarity", "HybridSimiliarity",
            "NeutralLossSimilarity", "MsMsEI"
        ] = "generic",
        presearch_algorithm: Literal["Standard", "Fast", "PrecursorIonTol", "Sequential"] = "PrecursorIonTol",
        precursor_mode: Literal["MsMs", "NoMatch", "Hybrid"] = "MsMs",
        search_threshold: Literal["Low", "Medium", "High"] = "Low",
        verbose: bool = True,
        return_best_hits_only: bool = False,
        precursor_mz_tol: float = 20,
        peak_mz_tol: float = 0.01,
        max_hits: int = 100,
        min_match_factor: int = 500,
        image: str = "ghcr.io/julianaileru/spectral-annotation/mspepsearch:latest",
    ):
        self.query = query
        self.library = library
        self.lib_paths = lib_paths
        self.runtime = runtime
        self.resolution = resolution
        self.scoring_type = scoring_type
        self.presearch_algorithm = presearch_algorithm
        self.precursor_mode = precursor_mode
        self.search_threshold = search_threshold
        self.verbose = verbose
        self.return_best_hits_only = return_best_hits_only
        self.precursor_mz_tol = precursor_mz_tol
        self.peak_mz_tol = peak_mz_tol
        self.max_hits = max_hits
        self.min_match_factor = min_match_factor
        self.image = image

    @property
    def is_hires(self) -> bool:
        return self.resolution == "HiRes"

    def _build_positional_flags(self) -> str:
        opts = self._OPTIONS
        presearch = opts["Presearch Options"].value_map[self.presearch_algorithm]

        if self.is_hires:
            additional = (opts["AdditionalHiResSearch Options"].value_map["AlternativePeakMatching"]
                          + opts["AdditionalHiResSearch Options"].value_map["IgnorePeakbyZI"])
            precursor_mode = opts["PrecursorMode Options"].value_map[self.precursor_mode]
            threshold = opts["SearchThreshold Options"].value_map[self.search_threshold]
            scoring = opts["HiResSearch Options"].value_map[self.scoring_type]
            return presearch + additional + precursor_mode + threshold + scoring
        else:
            scoring = opts["LowResSearch Options"].value_map[self.scoring_type]
            return presearch + scoring

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
            cmd += ["/ZPPM", str(self.precursor_mz_tol)]
            cmd += ['/ZI',str(1.6)]
            cmd += ["/M", str(self.peak_mz_tol)]
        cmd += ["/MatchPolarity"]
        cmd += ["/MatchCharge"]

        # --- Output options ---
        cmd += ["/OUTTAB", output_path]
        cmd += ["/HITS", str(self.max_hits)]
        cmd += ["/MinMF", str(self.min_match_factor)]
        cmd += ["/OutPrecursorType",
                "/OutPrecursorMZ",
                "/OutDeltaPrecursorMZ",
                "/OutMW",
                "/OutCAS",
                "/All",
                "/OutChemForm",
                "/OutIK",
                "/OutDeltaMW",
                "/OutNumMP"]
        if self.return_best_hits_only:
            cmd += ["/OutBestHitsOnly"]

        return cmd

    def _build_container_cmd(self, output_path: str) -> list[str]:
        input_path = Path(self.query.path).as_posix()
        output_dir = Path(output_path).parent.as_posix()

        input_bind = f"{input_path}:/work/input.msp"
        output_bind = f"{output_dir}:/work/output"
        container_output = "/work/output/" + Path(output_path).name

        container_lib_paths = []
        lib_binds = []
        for i, lib in enumerate(self.lib_paths):
            container_lib = f"/work/lib{i}"
            lib_binds.append(f"{Path(lib).as_posix()}:{container_lib}")
            container_lib_paths.append(container_lib)

        mspepsearch_cmd = self._build_cmd("/work/input.msp", container_lib_paths, container_output)

        if self.runtime == "docker":
            container_cmd = ["docker", "run", "--rm", "-v", input_bind, "-v", output_bind]
            for bind in lib_binds:
                container_cmd += ["-v", bind]
        else:
            container_cmd = ["apptainer", "exec", "--bind", input_bind, "--bind", output_bind]
            for bind in lib_binds:
                container_cmd += ["--bind", bind]

        return container_cmd + [self.image] + mspepsearch_cmd

    def run(self, output_path: str) -> None:
        cmd = self._build_container_cmd(output_path)
        subprocess.run(cmd, check=True)
