#!/usr/bin/env bash
#
# Build a standalone yate executable for Linux with PyInstaller.
#
# Usage:
#   ./pack/pack.sh               one-folder build -> dist/yate/yate
#   ./pack/pack.sh --onefile     single self-extracting file -> dist/yate
#   ./pack/pack.sh --skip-changelog
#                                skip refreshing the bundled changelogs
#   ./pack/pack.sh --dist DIR    collect artifact into DIR/yate-<ver>-linux-<arch>/
#   ./pack/pack.sh -h            show this help
#
# Before PyInstaller runs, the bundled bilingual changelogs are refreshed
# with `python -m tools.changelog generate --bundle-only` (best-effort: a
# checkout without git history keeps the last committed resources copies).
#
# The interpreter MUST be .venv/bin/python (no system-python fallback, which
# would pollute the global bin/ via pip install -e). If PyInstaller is missing
# it is installed automatically via  pip install -e '.[build,ts]'.
#
# PyInstaller cannot cross-compile: run this script ON Linux to produce a
# Linux binary (use pack/pack.bat or pack/pack.ps1 on Windows for an exe).

set -euo pipefail

show_help() {
    sed -n '2,19p' "$0" | sed 's/^# \{0,1\}//'
    exit 0
}

onefile=0
skip_changelog=0
dist_arg=""
while [ $# -gt 0 ]; do
    case "$1" in
        --onefile|-1)
            onefile=1
            ;;
        --skip-changelog)
            skip_changelog=1
            ;;
        --dist|-d)
            [ $# -ge 2 ] || { echo "error: --dist requires a directory argument" >&2; exit 2; }
            dist_arg="$2"
            shift
            ;;
        --dist=*)
            dist_arg="${1#--dist=}"
            ;;
        -d=*)
            dist_arg="${1#-d=}"
            ;;
        -h|--help)
            show_help
            ;;
        *)
            echo "unknown argument: $1 (see -h)" >&2
            exit 2
            ;;
    esac
    shift
done

# Always build from the repository root regardless of the caller's directory.
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
root="$(cd "$script_dir/.." && pwd)"
cd "$root"

# Interpreter MUST come from the project virtual environment. Falling back
# to a system python3 would let `pip install -e '.[build,ts]'` write the yate
# entry script into the global bin/ directory, polluting the global install.
py="$root/.venv/bin/python"
if [ ! -x "$py" ]; then
    echo "error: .venv not found at '$py'." >&2
    echo "       Run 'python3 -m venv .venv && . .venv/bin/activate && pip install -e '.[build,ts]' first." >&2
    echo "       Falling back to system python is disabled to avoid installing the yate" >&2
    echo "       entry script into the global bin/ directory." >&2
    exit 1
fi

if ! "$py" --version >/dev/null 2>&1; then
    echo "Python 3 interpreter not found ('$py'). Activate your .venv and try again." >&2
    exit 1
fi

# Make sure the build extra (PyInstaller) is available. The [ts] extra
# (tree-sitter + python/bash grammar packs) is installed too so the
# standalone executable ships the tree-sitter highlighting backend.
if ! "$py" -c "import PyInstaller" >/dev/null 2>&1; then
    echo "PyInstaller not found; installing build+ts extras (pip install -e '.[build,ts]') ..." >&2
    "$py" -m pip install -e '.[build,ts]'
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

# Refresh the bundled bilingual changelogs (best-effort: a checkout without
# git history keeps the last committed resources copies).
if [ "$skip_changelog" -eq 0 ]; then
    echo "Refreshing changelogs ..."
    if ! "$py" -m tools.changelog generate --bundle-only; then
        echo "WARNING: changelog generation failed; continuing with shipped files." >&2
    fi
    echo
fi

"$py" -m PyInstaller --noconfirm --clean --distpath dist --workpath build "$spec"

if [ ! -f "$artifact" ]; then
    echo "Build reported success but expected artifact is missing: $artifact" >&2
    exit 1
fi

# The refresh may have updated the shipped resources copies. Whether to
# commit them is a release decision — surface it, never auto-checkout.
if [ "$skip_changelog" -eq 0 ] && [ -d .git ] && command -v git >/dev/null 2>&1; then
    if [ -n "$(git status --porcelain -- yate/resources/changelog.en.md yate/resources/changelog.zh.md)" ]; then
        echo "NOTE: resources/changelog.*.md were refreshed and differ from the committed copies; commit them if this is a release." >&2
    fi
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

# --dist DIR: collect the freshly built artifact into a versioned
# subdirectory for direct pick-up (local copy only, no upload).
if [ -n "$dist_arg" ]; then
    dist_root="$(cd "$root" && realpath -m -- "$dist_arg")"

    version="$("$py" -c 'from yate import __version__; print(__version__)')"
    if [ -z "$version" ]; then
        echo "error: failed to read yate __version__; cannot name the dist directory." >&2
        exit 1
    fi

    arch="$(uname -m)"
    case "$arch" in
        x86_64)  arch="x64" ;;
        aarch64) arch="arm64" ;;
    esac
    name="yate-$version-linux-$arch"
    stage="$dist_root/$name"

    mkdir -p "$dist_root" || { echo "error: cannot create dist root '$dist_root'" >&2; exit 1; }
    [ -e "$stage" ] && rm -rf "$stage"

    if [ "$onefile" -eq 1 ]; then
        mkdir -p "$stage"
        cp -a "dist/yate" "$stage/yate"
        chmod 0755 "$stage/yate"
    else
        mkdir -p "$stage"
        cp -a "dist/yate/." "$stage/"
    fi

    ( cd "$stage" && sha256sum yate > SHA256SUMS.txt )

    if ! "$stage/yate" --version 2>&1 | grep -q "$version"; then
        echo "error: smoke test failed ('$stage/yate --version' did not report $version). Stage kept at: $stage" >&2
        exit 1
    fi

    stage_size_kb="$(du -sk "$stage" | cut -f1)"
    stage_size_mb="$(awk "BEGIN { printf \"%.1f\", $stage_size_kb / 1024 }")"
    echo
    echo "Collected -> $stage  (${stage_size_mb} MB)"
    sed 's/^/  SHA256 yate: /' "$stage/SHA256SUMS.txt"
fi
