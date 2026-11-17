@echo off
REM Launch the Condense engine from this bundle on Windows (D63 "API only" download).
REM
REM BEST-EFFORT, UNTESTED (2026-07-06): this was written to mirror run.sh's behavior but has not
REM been run on a real Windows machine tonight (this host is Linux-only) -- the engine bundle
REM itself is also Linux-only so far (see packaging/README.md); this script is here for when a
REM Windows PyInstaller build exists (CI, D63) so the bundle layout is already Windows-ready.
REM Known risk spots if something breaks: the naive ".env" line parser below (no quoting/escaping
REM support -- values with "=" past the first one, or spaces, may not round-trip correctly) and
REM whether engine\sift-engine.exe is the exact name the Windows PyInstaller build produces.

setlocal enabledelayedexpansion
cd /d "%~dp0"

if exist .env (
    set "ENV_FILE=.env"
) else (
    set "ENV_FILE=env.example"
    echo no .env found - using env.example as-is ^(INGEST_TOKEN=CHANGE-ME^)
)

for /f "usebackq eol=# tokens=1,* delims==" %%A in ("%ENV_FILE%") do (
    if not "%%A"=="" set "%%A=%%B"
)

if not exist data mkdir data

engine\sift-engine.exe
