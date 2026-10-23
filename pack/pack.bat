@echo off
rem ============================================================
rem  yate Windows build wrapper (cmd.exe friendly entry point).
rem  All logic lives in pack.ps1; arguments are passed through.
rem
rem    pack\pack.bat               one-folder build (dist\yate\)
rem    pack\pack.bat --onefile     single-file build (dist\yate.exe)
rem    pack\pack.bat --skip-changelog
rem                                skip refreshing the bundled changelogs
rem    pack\pack.bat --onefile --dist release
rem                                collect artifact into release\yate-<ver>-windows-<arch>\
rem    pack\pack.bat -?            show PowerShell help
rem ============================================================
setlocal

rem Resolve the script path BEFORE the parse loop: cmd's `shift` moves %0
rem along with %1-%9 (unlike bash's $0), so %~dp0 read after the loop would
rem dereference the last consumed argument instead of this script's folder.
set "SCRIPT=%~dp0pack.ps1"

rem Map the documented POSIX-style flags onto the pack.ps1 parameters.
rem `powershell -File` binds "-flag" tokens by parameter name, so kebab-case
rem options never match: "--skip-changelog" aborts with NamedParameterNotFound,
rem and single-word flags like --onefile/--dist only bind because they happen
rem to case-insensitively match OneFile/Dist. Explicit mapping keeps the
rem documented CLI working; unknown flags pass through unchanged.
set "ARGS="
:parse
if "%~1"=="" goto run
set "arg=%~1"
if /i "%arg%"=="--onefile" set "arg=-OneFile"
if /i "%arg%"=="--skip-changelog" set "arg=-SkipChangelog"
if /i "%arg%"=="--dist" set "arg=-Dist"
if /i "%arg%"=="--help" set "arg=-Help"
set "ARGS=%ARGS% "%arg%""
shift
goto parse

:run
powershell -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT%" %ARGS%
exit /b %ERRORLEVEL%
