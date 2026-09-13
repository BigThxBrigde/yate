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

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0pack.ps1" %*
exit /b %ERRORLEVEL%
