#!/bin/bash
# Converts an MSP or SDF file to NIST binary library format (.lib/.idx/.num)
# using lib2nist64.exe under Wine. Output options are controlled by convert.ini;
# [Directory] paths are injected at runtime.
#
# Usage:
#   lib2nist_convert.sh <input.msp|input.sdf> <output_library> [log_file]
#
#   input            - absolute Linux path to source MSP or SDF file
#   output_library   - absolute Linux path for output library (no extension)
#   log_file         - (optional) absolute Linux path for conversion log
#                      defaults to <output_library>.log
#
# Output:
#   <output_library>.lib, <output_library>.idx, <output_library>.num

set -euo pipefail

LIB2NIST_EXE="/opt/lib2nist/lib2nist64.exe"
INI_TEMPLATE="/opt/lib2nist/convert.ini"

to_wine_path() {
    # /absolute/linux/path -> Z:\absolute\linux\path
    echo "Z:$(echo "$1" | sed 's|/|\\|g')"
}

usage() {
    echo "Usage: $(basename "$0") <input.msp|input.sdf> <output_library> [log_file]" >&2
    exit 1
}

[[ $# -lt 2 ]] && usage

INPUT_MSP="$(realpath "$1")"
INPUT_EXT="${INPUT_MSP##*.}"
OUTPUT_LIB="$(realpath -m "$2")"

case "${INPUT_EXT,,}" in
    msp|sdf) ;;
    *) echo "Error: unsupported input format '.${INPUT_EXT}' (expected .msp or .sdf)" >&2; exit 1 ;;
esac
LOG_FILE="${3:-${OUTPUT_LIB}.log}"
LOG_FILE="$(realpath -m "$LOG_FILE")"

[[ ! -f "$INPUT_MSP" ]] && { echo "Error: input not found: $INPUT_MSP" >&2; exit 1; }

mkdir -p "$(dirname "$OUTPUT_LIB")"
mkdir -p "$(dirname "$LOG_FILE")"

LIB_NAME=$(basename "$OUTPUT_LIB")
OUTPUT_PARENT=$(dirname "$OUTPUT_LIB")

# Workdir for temp INI and renamed input MSP (Wine accesses it via Z:)
WORK_DIR=$(mktemp -d "${TMPDIR:-/tmp}/lib2nist_XXXXXX")
trap 'rm -rf "$WORK_DIR"' EXIT

# lib2nist names the output subdir after the input file stem, so rename accordingly
# while preserving the original extension so lib2nist detects the format correctly.
ln "$INPUT_MSP" "$WORK_DIR/${LIB_NAME}.${INPUT_EXT}" 2>/dev/null \
    || cp "$INPUT_MSP" "$WORK_DIR/${LIB_NAME}.${INPUT_EXT}"

# Wine-style directory paths (trailing backslash required by lib2nist)
WINE_INPUT_DIR="$(to_wine_path "$WORK_DIR")\\"
WINE_OUTPUT_DIR="$(to_wine_path "$OUTPUT_PARENT")\\"
WINE_LOG="$(to_wine_path "$LOG_FILE")"
WINE_INI="$(to_wine_path "$WORK_DIR/convert.ini")"
WINE_INPUT_MSP="$(to_wine_path "$WORK_DIR/${LIB_NAME}.${INPUT_EXT}")"

# Generate runtime INI: prepend [Directory] with actual paths, then carry over
# [Output] section from the template (which users can edit to change options).
{
    printf '[Directory]\nInput=%s\nOutput=%s\nNIST=%s\n\n' \
        "$WINE_INPUT_DIR" "$WINE_OUTPUT_DIR" "$WINE_OUTPUT_DIR"
    awk '/^\[Output\]/{found=1} found{print}' "$INI_TEMPLATE"
} > "$WORK_DIR/convert.ini"

run_with_wine_prefix.sh wine64 "$LIB2NIST_EXE" \
    /log9 "$WINE_LOG" "$WINE_INI" "$WINE_INPUT_MSP" "$WINE_OUTPUT_DIR"

# lib2nist outputs to OUTPUT_PARENT/LIB_NAME/{LIB_NAME.lib,.idx,.num}
# Flatten to match our interface: OUTPUT_LIB.{lib,idx,num}
LIB_SUBDIR="$OUTPUT_PARENT/$LIB_NAME"
if [[ -d "$LIB_SUBDIR" ]]; then
    for f in "$LIB_SUBDIR"/*; do
        [[ -e "$f" ]] || continue
        mv "$f" "${OUTPUT_LIB}.${f##*.}"
    done
    rmdir "$LIB_SUBDIR"
fi
