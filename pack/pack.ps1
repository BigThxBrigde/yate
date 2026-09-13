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
    missing it is installed automatically via  pip install -e ".[build,ts]".

    PyInstaller cannot cross-compile: run this script on Windows to produce a
    Windows executable (use pack/pack.sh on Linux for a Linux binary).

.EXAMPLE
    .\pack\pack.ps1
    .\pack\pack.ps1 -OneFile
    .\pack\pack.ps1 -SkipChangelog
    .\pack\pack.ps1 --dist release
    .\pack\pack.ps1 -OneFile -Dist D:\releases\yate
    .\pack\pack.bat --onefile --skip-changelog
#>

[CmdletBinding()]
param(
    [Alias("1")]
    [switch]$OneFile,

    [switch]$SkipChangelog,

    [Alias("d")]
    [string]$Dist = "",

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

    # Interpreter MUST come from the project virtual environment. Falling
    # back to a system python would let `pip install -e '.[build,ts]'` write
    # the yate entry script into the global Scripts/ directory, polluting
    # the user's global Python install.
    $pythonExe = Join-Path $root ".venv\Scripts\python.exe"

    function Stop-WithMessage($text) {
        Write-Host $text -ForegroundColor Red
        exit 1
    }

    if (-not (Test-Path $pythonExe)) {
        Stop-WithMessage (
            ".venv not found at '$pythonExe'. " +
            "Run 'python -m venv .venv' then '.\.venv\Scripts\Activate.ps1; pip install -e `"[build,ts]`"' first. " +
            "Falling back to system python is disabled to avoid installing the yate " +
            "entry script into the global Scripts/ directory."
        )
    }

    & $pythonExe --version 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Stop-WithMessage "Python interpreter not found ('$pythonExe'). Activate your .venv and try again."
    }

    # Make sure the build extra (PyInstaller) is available. The [ts] extra
    # (tree-sitter + python/bash grammar packs) is installed too so the
    # standalone executable ships the tree-sitter highlighting backend.
    & $pythonExe -c "import PyInstaller" 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "PyInstaller not found; installing build+ts extras (pip install -e `".[build,ts]`") ..." -ForegroundColor Yellow
        & $pythonExe -m pip install -e ".[build,ts]"
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

    # --dist <dir>: collect the freshly built artifact into a versioned
    # subdirectory for direct pick-up (local copy only, no upload).
    if ($Dist -ne "") {
        $distRoot = [System.IO.Path]::GetFullPath((Join-Path $root $Dist))

        $version = (& $pythonExe -c "from yate import __version__; print(__version__)").Trim()
        if (-not $version) {
            Stop-WithMessage "Failed to read yate __version__; cannot name the dist directory."
        }

        $arch = if ($env:PROCESSOR_ARCHITECTURE -eq 'ARM64') { 'arm64' } else { 'x64' }
        $name = "yate-$version-windows-$arch"
        $stage = Join-Path $distRoot $name

        try {
            New-Item -ItemType Directory -Force $distRoot | Out-Null
        } catch {
            Stop-WithMessage "Cannot create dist root '$distRoot': $_"
        }
        if (Test-Path $stage) {
            Remove-Item -Recurse -Force $stage
        }

        try {
            New-Item -ItemType Directory -Force $stage | Out-Null
            if ($OneFile) {
                Copy-Item $artifact (Join-Path $stage 'yate.exe')
            } else {
                Copy-Item -Recurse (Join-Path $root 'dist\yate\*') $stage
            }
        } catch {
            Stop-WithMessage "Failed to copy build artifact into '$stage': $_"
        }

        $exe = Join-Path $stage 'yate.exe'
        $hash = (Get-FileHash $exe -Algorithm SHA256).Hash.ToLower()
        "$hash  yate.exe" | Set-Content -Encoding ascii (Join-Path $stage 'SHA256SUMS.txt')

        $smoke = & $exe --version 2>&1
        if ($LASTEXITCODE -ne 0 -or ($smoke -join ' ') -notlike "*$version*") {
            Stop-WithMessage "Smoke test failed ('$exe --version' did not report $version). Stage kept at: $stage"
        }

        $stageSizeMb = [math]::Round((Get-ChildItem $stage -Recurse -File | Measure-Object Length -Sum).Sum / 1MB, 1)
        Write-Host ""
        Write-Host "Collected -> $stage  (${stageSizeMb} MB)" -ForegroundColor Green
        Write-Host "  SHA256 yate.exe: $hash"
    }
}
finally {
    Pop-Location
}
