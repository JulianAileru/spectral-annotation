#!/usr/bin/env python3
import subprocess
import os
import argparse
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

PREFIX_SCRIPT = '/usr/local/bin/run_with_wine_prefix.sh'
WINE_EXE = 'wine64'
MSPEPSEARCH_EXE = '/opt/mspepsearch/MSPepSearch64.exe'


def to_wine_path(linux_path):
    return 'Z:' + linux_path.replace('/', '\\')


def main():
    parser = argparse.ArgumentParser(description='Python interface for MSPepSearch64')
    parser.add_argument('--flags',            required=True,  help='Positional flags (e.g. mzG)')
    parser.add_argument('--input',  '-in',    required=True,  help='Input MSP file (Linux path)')
    parser.add_argument('--lib',    '-lib',   required=True,  action='append', help='Library path (repeatable)')
    parser.add_argument('--output', '-out',   required=True,  help='Output path, no extension (Linux path)')
    parser.add_argument('--lib-in-mem',       action='store_true')
    parser.add_argument('--precursor-mz-tol', '-Z', type=float)
    parser.add_argument('--fragment-mz-tol',  '-M', type=float)
    parser.add_argument('--hits',             type=int, default=100)
    parser.add_argument('--min-mf',           type=int, default=500)
    parser.add_argument('--match-polarity',   action='store_true')
    parser.add_argument('--match-charge',     action='store_true')
    parser.add_argument('--out-precursor-type', action='store_true')
    parser.add_argument('--out-mw',             action='store_true')
    parser.add_argument('--out-chem-form',      action='store_true')
    parser.add_argument('--out-ik',             action='store_true')
    parser.add_argument('--out-delta-mw',       action='store_true')
    parser.add_argument('--out-num-mp',         action='store_true')
    parser.add_argument('--out-best-hits-only', action='store_true')
    args = parser.parse_args()

    wine_input  = to_wine_path(os.path.realpath(args.input))
    wine_output = to_wine_path(os.path.realpath(args.output))
    wine_libs   = [to_wine_path(os.path.realpath(lib)) for lib in args.lib]

    mspepsearch_cmd = [MSPEPSEARCH_EXE, args.flags]
    mspepsearch_cmd += ['/INP', wine_input]
    for wine_lib in wine_libs:
        mspepsearch_cmd += ['/LIB', wine_lib]
    if args.lib_in_mem:
        mspepsearch_cmd += ['/LibInMem']
    if args.precursor_mz_tol is not None:
        mspepsearch_cmd += ['/Z', str(args.precursor_mz_tol)]
    if args.fragment_mz_tol is not None:
        mspepsearch_cmd += ['/M', str(args.fragment_mz_tol)]
    if args.match_polarity:
        mspepsearch_cmd += ['/MatchPolarity']
    if args.match_charge:
        mspepsearch_cmd += ['/MatchCharge']
    mspepsearch_cmd += ['/OUTTAB', wine_output]
    mspepsearch_cmd += ['/HITS', str(args.hits)]
    mspepsearch_cmd += ['/MinMF', str(args.min_mf)]
    if args.out_precursor_type:
        mspepsearch_cmd += ['/OutPrecursorType']
    if args.out_mw:
        mspepsearch_cmd += ['/OutMW']
    if args.out_chem_form:
        mspepsearch_cmd += ['/OutChemForm']
    if args.out_ik:
        mspepsearch_cmd += ['/OutIK']
    if args.out_delta_mw:
        mspepsearch_cmd += ['/OutDeltaMW']
    if args.out_num_mp:
        mspepsearch_cmd += ['/OutNumMP']
    if args.out_best_hits_only:
        mspepsearch_cmd += ['/OutBestHitsOnly']

    cmd = [PREFIX_SCRIPT, WINE_EXE] + mspepsearch_cmd
    logger.info('Running: %s', ' '.join(cmd))
    subprocess.run(cmd, check=True)


if __name__ == '__main__':
    main()
