<#
.SYNOPSIS
    Build a standalone yate executable for Windows with PyInstaller.

.DESCRIPTION
    Selects the spec deterministically (never mixes CLI bundle flags with a
    spec) and runs it from the repository root:
      default       one-folder build -> dist\yate\yate.exe (+ runtime files)
      -OneFile      single self-extracting file -> dist\yate.exe

    Before PyInstaller runs, the bundled bilingual changelogs are refreshed
    with `python -m tools.changelog generate --bundle-only` (best-effort: a
    checkout without git history keeps the last committed resources copies;
    pass -SkipChangelog to skip the refresh).

    The preferred interpreter is .venv\Scripts\python.exe; if PyInstaller is
    missing it is installed automatically via  pip install -e ".[build]".

    PyInstaller cannot cross-compile: run this script on Windows to produce a
    Windows executable (use pack/pack.sh on Linux for a Linux binary).

.EXAMPLE
    .\pack\pack.ps1
    .\pack\pack.ps1 -OneFile
    .\pack\pack.ps1 -SkipChangelog
    .\pack\pack.bat --onefile --skip-changelog
#>

[CmdletBinding()]
param(
    [Alias("1")]
    [switch]$OneFile,

    [switch]$SkipChangelog,

    [Alias("h", "?")]
    [switch]$Help
)

$ErrorActionPreference = "Stop"

if ($Help) {
    Get-Help $MyInvocation.MyCommand.Path -Detailed
    exit 0
}

# Always build from the repository root regardless of the caller's directory.
$root = Split-Path -Parent $PSScriptRoot

try {
    Push-Location $root

    # Prefer the project virtual environment; fall back to a system python.
    $pythonExe = Join-Path $root ".venv\Scripts\python.exe"
    if (-not (Test-Path $pythonExe)) {
        $pythonExe = "python"
    }

    function Stop-WithMessage($text) {
        Write-Host $text -ForegroundColor Red
        exit 1
    }

    & $pythonExe --version 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Stop-WithMessage "Python interpreter not found ('$pythonExe'). Create .venv or put python on PATH."
    }

    # Make sure the build extra (PyInstaller) is available.
    & $pythonExe -c "import PyInstaller" 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "PyInstaller not found; installing the build extra (pip install -e `".[build]`") ..." -ForegroundColor Yellow
        & $pythonExe -m pip install -e ".[build]"
        if ($LASTEXITCODE -ne 0) {
            Stop-WithMessage "Failed to install build dependencies."
        }
    }

    # The mode flag picks the spec; the spec alone defines the bundle layout.
    if ($OneFile) {
        $spec = "pack\yate-onefile.spec"
        $artifact = "dist\yate.exe"
        $mode = "onefile (single self-extracting exe)"
    } else {
        $spec = "pack\yate.spec"
        $artifact = "dist\yate\yate.exe"
        $mode = "one-folder (faster startup)"
    }

    Write-Host ""
    Write-Host "Building yate for Windows [$mode]" -ForegroundColor Cyan
    Write-Host "  spec:     $spec"
    Write-Host "  python:   $pythonExe"
    Write-Host ""

    # Refresh the bundled bilingual changelogs (best-effort: a checkout
    # without git history keeps the last committed resources copies).
    if (-not $SkipChangelog) {
        Write-Host "Refreshing changelogs ..." -ForegroundColor Cyan
        & $pythonExe -m tools.changelog generate --bundle-only
        if ($LASTEXITCODE -ne 0) {
            Write-Host "WARNING: changelog generation failed; continuing with shipped files." -ForegroundColor Yellow
        }
        Write-Host ""
    }

    & $pythonExe -m PyInstaller --noconfirm --clean --distpath dist --workpath build $spec
    if ($LASTEXITCODE -ne 0) {
        Stop-WithMessage "PyInstaller build failed."
    }

    if (-not (Test-Path $artifact)) {
        Stop-WithMessage "Build reported success but expected artifact is missing: $artifact"
    }

    # The refresh may have updated the shipped resources copies. Whether to
    # commit them is a release decision — surface it, never auto-checkout.
    if (-not $SkipChangelog -and (Test-Path (Join-Path $root ".git"))) {
        $dirty = git -C $root status --porcelain -- `
            yate/resources/changelog.en.md yate/resources/changelog.zh.md
        if ($dirty) {
            Write-Host "NOTE: resources/changelog.*.md were refreshed and differ from the committed copies; commit them if this is a release." -ForegroundColor Yellow
        }
    }

    $built = Get-Item $artifact
    $sizeMb = [math]::Round($built.Length / 1MB, 1)
    Write-Host ""
    Write-Host "Build OK -> $($built.FullName)  (${sizeMb} MB)" -ForegroundColor Green
    Write-Host "Copy this file" -NoNewline
    if (-not $OneFile) {
        Write-Host " together with the whole dist\yate folder " -NoNewline
    }
    Write-Host " to a Windows machine (no Python install required)."
}
finally {
    Pop-Location
}
