#!/usr/bin/env bash
#
# Build a standalone yate executable for Linux with PyInstaller.
#
# Usage:
#   ./pack/pack.sh               one-folder build -> dist/yate/yate
#   ./pack/pack.sh --onefile     single self-extracting file -> dist/yate
#   ./pack/pack.sh -h            show this help
#
# The preferred interpreter is .venv/bin/python; if PyInstaller is missing it
# is installed automatically via  pip install -e '.[build]'.
#
# PyInstaller cannot cross-compile: run this script ON Linux to produce a
# Linux binary (use pack/pack.bat or pack/pack.ps1 on Windows for an exe).

set -euo pipefail

show_help() {
    sed -n '2,14p' "$0" | sed 's/^# \{0,1\}//'
    exit 0
}

onefile=0
for arg in "$@"; do
    case "$arg" in
        --onefile|-1)
            onefile=1
            ;;
        -h|--help)
            show_help
            ;;
        *)
            echo "unknown argument: $arg (see -h)" >&2
            exit 2
            ;;
    esac
done

# Always build from the repository root regardless of the caller's directory.
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
root="$(cd "$script_dir/.." && pwd)"
cd "$root"

# Prefer the project virtual environment; fall back to a system python3.
if [ -x "$root/.venv/bin/python" ]; then
    py="$root/.venv/bin/python"
else
    py="python3"
fi

if ! "$py" --version >/dev/null 2>&1; then
    echo "Python 3 interpreter not found ('$py'). Create .venv or put python3 on PATH." >&2
    exit 1
fi

# Make sure the build extra (PyInstaller) is available.
if ! "$py" -c "import PyInstaller" >/dev/null 2>&1; then
    echo "PyInstaller not found; installing the build extra (pip install -e '.[build]') ..." >&2
    "$py" -m pip install -e '.[build]'
fi

# The mode flag picks the spec; the spec alone defines the bundle layout.
if [ "$onefile" -eq 1 ]; then
    spec="pack/yate-onefile.spec"
    artifact="dist/yate"
    mode="onefile (single self-extracting binary)"
else
    spec="pack/yate.spec"
    artifact="dist/yate/yate"
    mode="one-folder (faster startup)"
fi

echo
echo "Building yate for Linux [$mode]"
echo "  spec:     $spec"
echo "  python:   $py"
echo

"$py" -m PyInstaller --noconfirm --clean --distpath dist --workpath build "$spec"

if [ ! -f "$artifact" ]; then
    echo "Build reported success but expected artifact is missing: $artifact" >&2
    exit 1
fi

size_kb="$(du -k "$artifact" | cut -f1)"
size_mb="$(awk "BEGIN { printf \"%.1f\", $size_kb / 1024 }")"
echo
echo "Build OK -> $root/$artifact  (${size_mb} MB)"
if [ "$onefile" -eq 0 ]; then
    echo "Copy the whole dist/yate folder to a Linux machine (no Python install required)."
else
    echo "Copy this single file to a Linux machine (no Python install required)."
fi
