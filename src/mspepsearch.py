from dataclasses import dataclass
from pathlib import Path
import sys, os, tempfile, concurrent.futures
sys.path.append(os.path.abspath(r"C:\Users\jaileru\Projects\spectral-annotation"))
from src.msp import MspFile, SpectralLibrary
from typing import Optional, Literal
import subprocess
from enum import Enum
from tqdm import tqdm


class SearchAlgorithm(Enum):
    """
    Preset search configurations for MSPepSearch64.exe.

    Each member bundles the positional flag string passed to MSPepSearch and
    whether the algorithm supports high-resolution fragment matching.

    Members:
        IDENTITY_MSMS: Hybrid identity search with precursor and fragment filtering.
        IDENTITY_HIRES: High-resolution identity search (fragment tolerance only, no precursor window).
        SIMILARITY_MSMS_HYBRID: Hybrid similarity search with precursor and fragment filtering.
        SIMILARITY_MSMS_EI: Electron-ionization similarity search (no precursor filter).
    """

    IDENTITY_MSMS          = ("azlGmi", True)
    IDENTITY_HIRES         = ("aulGd", True)
    SIMILARITY_MSMS_HYBRID = ("aylGd", True)
    SIMILARITY_MSMS_EI     = ("Md", False)

    def __init__(self, flags: str, hires: bool):
        self.flags = flags
        self.hires = hires




class MSPepSearch:
    """
    Run NIST MSPepSearch64.exe against one or more spectral libraries via a container.

    Supports parallel chunked searches: the query file is split into ``n_cores`` chunks,
    each searched in a separate container instance, and results are concatenated
    preserving the original TSV header.

    Args:
        query: MSP file of spectra to search.
        library: SpectralLibrary holding the reference MSP files and container config.
        algorithm: Search preset (see SearchAlgorithm).
        lib_paths: Host-side paths to NIST-format library directories.
        runtime: Container runtime — ``'docker'`` or ``'apptainer'``.
        verbose: Print a tqdm progress bar during parallel runs.
        return_best_hits_only: Emit only the top-ranked hit per query spectrum.
        precursor_mz_tol: Precursor mass tolerance in ppm.
        fragment_mz_tol: Fragment ion tolerance in Da.
        ignore_precursor_mz_tol: Window (Da) around the precursor to exclude from fragment matching.
        max_hits: Maximum library hits to report per query spectrum.
        min_match_factor: Minimum match factor (0–999) for a hit to be reported.
        image: Container image tag (Docker) or path to ``.sif`` (Apptainer).
    """

    def __init__(
        self,
        query: MspFile,
        library: SpectralLibrary,
        algorithm: SearchAlgorithm,
        lib_paths: list[str],
        runtime: Literal["docker", "apptainer"] = "docker",
        verbose: bool = True,
        return_best_hits_only: bool = False,
        precursor_mz_tol: float = 20,
        fragment_mz_tol: float = 0.01,
        ignore_precursor_mz_tol: float = 1.6,
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
        self.ignore_precursor_mz_tol = ignore_precursor_mz_tol
        self.fragment_mz_tol = fragment_mz_tol
        self.max_hits = max_hits
        self.min_match_factor = min_match_factor
        self.image = image


    def _build_positional_flags(self) -> str:
        """Return the algorithm's MSPepSearch positional flag string."""
        return self.algorithm.flags

    def _build_cmd(self, input_path: str, lib_paths: list[str], output_path: str, lib_in_mem: bool = True) -> list[str]:
        """
        Construct the MSPepSearch64.exe command for execution inside the container.

        Args:
            input_path: Container-side path to the input MSP file.
            lib_paths: Container-side paths to NIST library directories.
            output_path: Container-side path for the tab-separated results file.
            lib_in_mem: Load libraries into RAM before searching (faster for large query files).
        """
        cmd = ["run_with_wine_prefix.sh", "wine64", "/opt/mspepsearch/MSPepSearch64.exe", self._build_positional_flags()]
        cmd += ["/INP", input_path]
        for lib in lib_paths:
            cmd += ["/LIB", lib]
        if lib_in_mem:
            cmd += ["/LibInMem"]

        if self.algorithm.name == "IDENTITY_MSMS":
            cmd += ["/ZPPM", str(self.precursor_mz_tol)]
            cmd += ["/ZI",str(self.ignore_precursor_mz_tol)]
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

    @staticmethod
    def _to_docker_path(path: str) -> str:
        """Convert a host path to Docker-compatible POSIX format (e.g. ``C:\\foo`` → ``/c/foo`` on Windows)."""
        p = Path(path).resolve()
        if sys.platform == "win32":
            drive, rest = os.path.splitdrive(str(p))
            return "/" + drive[0].lower() + rest.replace("\\", "/")
        return str(p)

    def _build_container_cmd(self, output_path: str) -> list[str]:
        """Build the full Docker/Apptainer command with all volume bindings and the MSPepSearch sub-command."""
        input_path = self._to_docker_path(str(self.query.path))
        output_dir = self._to_docker_path(str(Path(output_path).resolve().parent))

        input_bind = f"{input_path}:/work/input.msp"
        output_bind = f"{output_dir}:/work/output"
        container_output = "/work/output/" + Path(output_path).resolve().name

        container_lib_paths = []
        lib_binds = []
        for i, lib in enumerate(self.lib_paths):
            container_lib = f"/work/lib{i}"
            lib_binds.append(f"{self._to_docker_path(lib)}:{container_lib}")
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

    def run(self, output_path: str, n_cores: int = 1) -> None:
        """
        Execute the spectral search and write results to ``output_path``.

        For ``n_cores > 1`` the query is split into chunks, each searched in a separate
        container instance via ThreadPoolExecutor, and results are concatenated preserving
        the original TSV header.

        Args:
            output_path: Destination for the tab-separated results file.
            n_cores: Number of parallel container workers.
        """
        if n_cores == 1:
            self._run_single(output_path)
            return

        chunks = self.query.chunk(n_cores)
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            chunk_inputs = []
            for i, chunk in enumerate(chunks):
                p = tmpdir_path / f"chunk_{i}.msp"
                p.write_text(chunk.to_msp())
                chunk_inputs.append(p)

            chunk_outputs = [tmpdir_path / f"OUTLIB_{i}" for i in range(len(chunks))]

            def _run_chunk(i: int) -> None:
                worker = MSPepSearch(
                    query=MspFile(path=chunk_inputs[i], ion_mode=self.query.ion_mode),
                    library=self.library,
                    algorithm=self.algorithm,
                    lib_paths=self.lib_paths,
                    runtime=self.runtime,
                    verbose=self.verbose,
                    return_best_hits_only=self.return_best_hits_only,
                    precursor_mz_tol=self.precursor_mz_tol,
                    fragment_mz_tol=self.fragment_mz_tol,
                    max_hits=self.max_hits,
                    min_match_factor=self.min_match_factor,
                    image=self.image,
                )
                worker._run_single(str(chunk_outputs[i]))

            with concurrent.futures.ThreadPoolExecutor(max_workers=len(chunks)) as executor:
                futures = [executor.submit(_run_chunk, i) for i in range(len(chunks))]
                with tqdm(total=len(chunks), desc="searching", unit="chunk") as pbar:
                    for f in concurrent.futures.as_completed(futures):
                        f.result()
                        pbar.update(1)

            self._concat_outlib(chunk_outputs, Path(output_path))

    def _run_single(self, output_path: str) -> None:
        """Execute a single-container MSPepSearch run and write results to ``output_path``."""
        cmd = self._build_container_cmd(output_path)
        env = os.environ.copy()
        env["MSYS_NO_PATHCONV"] = "1"
        subprocess.run(cmd, check=True, env=env)

    @staticmethod
    def _concat_outlib(chunk_outputs: list[Path], output_path: Path) -> None:
        """
        Concatenate per-chunk TSV result files into a single output file.

        The comment header and column header from the first chunk are preserved;
        subsequent chunks contribute only data rows.
        """
        with open(output_path, "w") as out:
            for i, chunk_out in enumerate(chunk_outputs):
                with open(chunk_out) as f:
                    lines = f.readlines()
                if i == 0:
                    out.writelines(lines)
                else:
                    data = [l for l in lines if not l.startswith(">")]
                    out.writelines(data[1:])  # data[0] is the TSV column header
