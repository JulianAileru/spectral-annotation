#!/bin/bash
# run_with_wine_prefix.sh
#
# Copies the pre-initialized 64-bit Wine prefix from the read-only image
# location to a writable per-process temp directory, then execs the given
# wine command. Required for parallel safety: multiple concurrent Wine
# processes sharing a single prefix will corrupt it.
#
# Usage:
#   run_with_wine_prefix.sh <command...>
#
# Example:
#   run_with_wine_prefix.sh wine64 MSPepSearch64.exe /h

set -euo pipefail

# Use $TMPDIR if set (SLURM provides a fast node-local one); otherwise /tmp.
WORK_TMPDIR="${TMPDIR:-/tmp}"
PREFIX_DIR=$(mktemp -d "${WORK_TMPDIR}/wine_XXXXXX")
cleanup() {
    # Kill wineserver immediately rather than waiting (-w) for it to flush. The
    # prefix is deleted right after, so a graceful registry save is irrelevant.
    # Using -w here would block the container exit because wineserver lingers.
    WINEPREFIX="$PREFIX_DIR" wineserver -k 2>/dev/null || true
    rm -rf "$PREFIX_DIR"
}
trap cleanup EXIT

# rsync is faster than cp -r for the many-small-files Wine prefix tree
rsync -a /opt/wine64/ "$PREFIX_DIR/"

export WINEPREFIX="$PREFIX_DIR"
export WINEARCH=win64
export WINEDEBUG="${WINEDEBUG:--all}"
# Suppress Wine's menu-builder from trying to write desktop entries.
export WINEDLLOVERRIDES="${WINEDLLOVERRIDES:-winemenubuilder.exe=d}"

# cd into the exe's directory so Wine resolves sibling DLLs and data files
# (e.g. lib2nist's HPTRANS.TBL) that live alongside the executable.
EXE_PATH=""
for arg in "$@"; do
    if [[ "$arg" == *.exe ]]; then
        EXE_PATH="$arg"
        break
    fi
done
if [[ -n "$EXE_PATH" ]]; then
    cd "$(dirname "$EXE_PATH")"
fi

# Wrap with xvfb-run if available and no DISPLAY is set.
# lib2nist is a GUI application; it needs a virtual display even in CLI mode.
if [[ -z "${DISPLAY:-}" ]] && command -v xvfb-run &>/dev/null; then
    xvfb-run --auto-servernum "$@" \
        2> >(grep -Ev "^X connection to|^wineserver: could not save registry" >&2)
    RC=$?
    # Kill wineserver before exiting so it releases its fd on the process
    # substitution pipe above — otherwise grep never sees EOF and the shell hangs.
    WINEPREFIX="$PREFIX_DIR" wineserver -k 2>/dev/null || true
    exit $RC
fi

"$@"
