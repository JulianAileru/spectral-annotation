from pathlib import Path
import sys,os
sys.path.append(os.path.abspath(r"C:\Users\jaileru\Projects\spectral-annotation"))
from src.msp import MspFile, SpectralLibrary
from src.mspepsearch import MSPepSearch

query = MspFile(r'../spectral_libraries/HMDB/QUERY/msms_spectrum.msp',ion_mode='P')
pos = MspFile(r"../spectral_libraries/HMDB/MSP/hmdb_experimental_P.msp", ion_mode="P")
neg = MspFile(r"../spectral_libraries/HMDB/MSP/hmdb_experimental_N.msp", ion_mode="N")
library = SpectralLibrary(library_name="HMDB", files=[pos],image="ghcr.io/julianaileru/spectral-annotation/nist-tools:latest")

obj = MSPepSearch(query=query,
            library=library,
            lib_paths=[r'../spectral_libraries/HMDB/NIST-MS-Positive/hmdb_experimental_P'],
            runtime='docker',
            scoring_type='generic',
            precursor_filtering='match_with_tol',
            presearch_algorithm='PrecursorTol'
            )

obj.run(output_path='./QUERYLIB')