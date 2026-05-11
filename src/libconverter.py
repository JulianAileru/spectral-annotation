#!/usr/bin/env python3
import subprocess
import os
import argparse
import configparser
import tempfile
import shutil
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

DEFAULT_CONFIG = '/opt/lib2nist/wrapper.ini'


def load_config(path=DEFAULT_CONFIG):
    """Load and return the lib2nist wrapper configuration from an INI file."""
    config = configparser.ConfigParser()
    if not config.read(path):
        raise FileNotFoundError(f"Config not found: {path}")
    return config


def to_wine_path(linux_path):
    """Convert an absolute Linux path to Wine's Z: drive format (``Z:\\path\\to\\file``)."""
    return 'Z:' + linux_path.replace('/', '\\')


def convert(input_path, output_lib, log_file=None, config=None):
    """
    Convert an MSP or SDF spectral file to a NIST library via lib2nist.exe under Wine.

    The input is staged into a temp directory named after the library so that lib2nist
    names its output subdirectory after ``lib_name`` rather than the original filename.

    Args:
        input_path: Path to the ``.msp`` or ``.sdf`` input file.
        output_lib: Destination library path without extension; lib2nist creates a
            subdirectory with this basename inside the parent directory.
        log_file: Path for the lib2nist log (defaults to ``<output_lib>.log``).
        config: Parsed configparser object; loaded from ``DEFAULT_CONFIG`` if not provided.
    """
    if config is None:
        config = load_config()

    lib2nist_exe  = config['LIB2NIST']['exe']
    ini_template  = config['LIB2NIST']['ini_template']
    wine_exe      = config['WINE']['exe']
    prefix_script = config['WINE']['prefix_script']

    input_path = os.path.realpath(input_path)
    ext = os.path.splitext(input_path)[1].lstrip('.').lower()
    if ext not in ('msp', 'sdf'):
        raise ValueError(f"Unsupported input format '.{ext}' (expected .msp or .sdf)")
    if not os.path.isfile(input_path):
        raise FileNotFoundError(f"Input not found: {input_path}")

    output_lib    = os.path.realpath(output_lib)
    lib_name      = os.path.basename(output_lib)
    output_parent = os.path.dirname(output_lib)

    if log_file is None:
        log_file = output_lib + '.log'
    log_file = os.path.realpath(log_file)

    os.makedirs(output_parent, exist_ok=True)
    os.makedirs(os.path.dirname(log_file), exist_ok=True)

    with tempfile.TemporaryDirectory(prefix='lib2nist_') as work_dir:
        # Rename the input so lib2nist names its output subdir after lib_name
        staged_input = os.path.join(work_dir, f'{lib_name}.{ext}')
        try:
            os.link(input_path, staged_input)
        except OSError:
            shutil.copy2(input_path, staged_input)

        wine_input_dir  = to_wine_path(work_dir) + '\\'
        wine_output_dir = to_wine_path(output_parent) + '\\'
        wine_log        = to_wine_path(log_file)
        wine_ini        = to_wine_path(os.path.join(work_dir, 'convert.ini'))
        wine_input_msp  = to_wine_path(staged_input)

        # Prepend [Directory] to the template's [Output] section
        runtime_ini = os.path.join(work_dir, 'convert.ini')
        with open(ini_template) as tmpl, open(runtime_ini, 'w') as out:
            out.write(
                f'[Directory]\n'
                f'Input={wine_input_dir}\n'
                f'Output={wine_output_dir}\n'
                f'NIST={wine_output_dir}\n\n'
            )
            in_output_section = False
            for line in tmpl:
                if line.strip().startswith('[Output]'):
                    in_output_section = True
                if in_output_section:
                    out.write(line)

        cmd = [
            prefix_script, wine_exe, lib2nist_exe,
            '/log9', wine_log, wine_ini, wine_input_msp, wine_output_dir,
        ]
        logger.info('Running: %s', ' '.join(cmd))
        subprocess.run(cmd, check=True)

        lib_subdir = os.path.join(output_parent, lib_name)
        if os.path.isdir(lib_subdir):
            logger.info('Output directory: %s', lib_subdir)
            for fname in os.listdir(lib_subdir):
                logger.info('  %s', fname)


def main():
    """CLI entry point: parse arguments and call ``convert()``."""
    parser = argparse.ArgumentParser(description='Python interface for lib2nist')
    parser.add_argument('--input',  '-in',     required=True, help='Input file (.msp or .sdf)')
    parser.add_argument('--outlib', '-outlib',  required=True, help='Output library path (no extension)')
    parser.add_argument('--log',                               help='Log file path (default: <outlib>.log)')
    parser.add_argument('--config',             default=DEFAULT_CONFIG, help='Path to wrapper.ini')
    args = parser.parse_args()

    config = load_config(args.config)
    convert(args.input, args.outlib, log_file=args.log, config=config)


if __name__ == '__main__':
    main()
