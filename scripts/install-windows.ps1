# UNTESTED -- no Windows machine available when this script was written. Written against the
# documented NSIS installer shape Condense's release automation produces
# (desktop/src-tauri/target/release/bundle/nsis/*-setup.exe) and the condense-server-<triple>.zip
# server bundle, but never actually run on Windows. Please report back anything that doesn't
# match reality (exact asset filenames, installer UI, silent-install flags, etc. are all
# best-guess).
#
# Install (or uninstall) Condense on Windows -- the desktop app by default, or the headless
# server-only bundle with -ServerOnly.
#
# Resolution order for the artifact:
#   1. -File <path>     use this local artifact directly.
#   2. the newest GitHub Release asset for AetherisAI/condense, via the public,
#      unauthenticated Releases API (Invoke-RestMethod -- no `gh` CLI or token required).
#   3. neither found -> print a clear message pointing at CI artifacts and the repo, and exit
#      non-zero. This script never half-installs: if it can't find or fetch a real artifact, it
#      does nothing to your machine.
#
# The desktop path: the NSIS installer itself is a normal Windows installer (Program Files,
# Start Menu shortcut, uninstaller entry) -- this script's job is just to find/download it and
# launch it; Tauri's NSIS bundle handles the actual install UI (and, with -Silent, a silent
# install).
#
# The -ServerOnly path: downloads condense-server-x86_64-pc-windows-msvc.zip and unpacks it to
# %LOCALAPPDATA%\condense-server (no admin rights, no installer) -- the headless engine + agent
# CLI, no UI.
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File scripts\install-windows.ps1
#   powershell -ExecutionPolicy Bypass -File scripts\install-windows.ps1 -ServerOnly
#   powershell -ExecutionPolicy Bypass -File scripts\install-windows.ps1 -File .\Condense_x64-setup.exe
#   powershell -ExecutionPolicy Bypass -File scripts\install-windows.ps1 -Silent
#   powershell -ExecutionPolicy Bypass -File scripts\install-windows.ps1 -Uninstall
#
# For Linux/macOS, use scripts/install.sh instead.

[CmdletBinding()]
param(
    [string]$File,
    [switch]$Silent,
    [switch]$Uninstall,
    [switch]$ServerOnly
)

$ErrorActionPreference = "Stop"
$RepoSlug = "AetherisAI/condense"
$ServerDir = Join-Path $env:LOCALAPPDATA "condense-server"

function Find-InstalledCondense {
    # Tauri's NSIS bundle registers a normal uninstall entry under the identifier
    # (ai.aetheris.condense) / product name (Condense). Check both HKCU and HKLM uninstall keys
    # (per-user vs per-machine installs), since which one gets used depends on the NSIS install
    # mode chosen at install time.
    $roots = @(
        "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall",
        "HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall",
        "HKLM:\Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"
    )
    foreach ($root in $roots) {
        if (-not (Test-Path $root)) { continue }
        Get-ChildItem $root | ForEach-Object {
            $p = Get-ItemProperty $_.PSPath -ErrorAction SilentlyContinue
            if ($p.DisplayName -eq "Condense") { return $p }
        }
    }
    return $null
}

if ($Uninstall) {
    Write-Host "==> Condense uninstaller"

    if ($ServerOnly) {
        if (Test-Path $ServerDir) {
            Remove-Item -Recurse -Force $ServerDir
            Write-Host "    removed $ServerDir"
        } else {
            Write-Host "    $ServerDir already absent"
        }
        Write-Host "done."
        exit 0
    }

    $entry = Find-InstalledCondense
    if ($null -eq $entry) {
        Write-Host "    no Condense install found in the Windows uninstall registry."
        exit 0
    }
    if ($entry.UninstallString) {
        Write-Host "    running: $($entry.UninstallString)"
        Start-Process -FilePath "cmd.exe" -ArgumentList "/c", $entry.UninstallString -Wait
        Write-Host "done."
    } else {
        Write-Host "error: found a Condense registry entry but no UninstallString -- remove it by hand via 'Add or remove programs'." -ForegroundColor Red
        exit 1
    }
    exit 0
}

# --- pick the asset pattern for this mode ------------------------------------------------------
if ($ServerOnly) {
    $kind = "server bundle"
    $assetPattern = "condense-server-*windows*.zip"
} else {
    # Matched strictly against the "Condense_*" desktop-app naming convention, not just any .exe
    # in the release, so this never mistakes an unrelated or legacy asset (e.g. the old v0.3.0
    # sift-agent-*.exe bundles) for the actual desktop installer.
    $kind = "desktop app"
    $assetPattern = "Condense*.exe"
}

$SrcArtifact = $null

if ($File) {
    if (-not (Test-Path $File)) {
        Write-Host "error: -File $File not found" -ForegroundColor Red
        exit 1
    }
    $SrcArtifact = (Resolve-Path $File).Path
    Write-Host "==> using local artifact: $SrcArtifact"
} else {
    Write-Host "==> looking for the newest GitHub Release $kind asset ($RepoSlug)"
    $assetUrl = $null
    $assetName = $null

    try {
        $resp = Invoke-RestMethod -Uri "https://api.github.com/repos/$RepoSlug/releases/latest" -ErrorAction Stop
        $match = $resp.assets | Where-Object { $_.name -like $assetPattern } | Select-Object -First 1
        if ($match) {
            $assetUrl = $match.browser_download_url
            $assetName = $match.name
        }
    } catch {
        # 404 (no releases yet) or a network error -- handled below either way.
    }

    if (-not $assetUrl) {
        Write-Host ""
        Write-Host "No published $kind release found yet for $RepoSlug." -ForegroundColor Yellow
        Write-Host ""
        Write-Host "Condense's install artifacts (Condense_*.AppImage/.deb/.dmg/.exe and"
        Write-Host "condense-server-*.tar.gz/.zip) ship starting with the v0.4.0 release. Until the"
        Write-Host "first tagged release lands, you have two options:"
        Write-Host ""
        Write-Host "  1. Grab a build from CI:"
        Write-Host "       https://github.com/$RepoSlug/actions"
        Write-Host ""
        Write-Host "  2. Build it yourself (see packaging/README.md and desktop/README.md in the repo):"
        Write-Host "       https://github.com/$RepoSlug"
        Write-Host ""
        $extra = if ($ServerOnly) { " -ServerOnly" } else { "" }
        Write-Host "Then install the local file directly:"
        Write-Host "    powershell -ExecutionPolicy Bypass -File scripts\install-windows.ps1 -File <path-to-artifact>$extra"
        Write-Host ""
        Write-Host "Nothing was installed."
        exit 1
    }

    Write-Host "    downloading $assetName"
    $tmpDir = Join-Path $env:TEMP "condense-installer"
    New-Item -ItemType Directory -Force -Path $tmpDir | Out-Null
    $dest = Join-Path $tmpDir $assetName
    Invoke-WebRequest -Uri $assetUrl -OutFile $dest
    $SrcArtifact = $dest
}

# --- server-only: unpack the zip and stop ------------------------------------------------------
if ($ServerOnly) {
    Write-Host "==> installing server bundle to $ServerDir"
    if (Test-Path $ServerDir) { Remove-Item -Recurse -Force $ServerDir }
    New-Item -ItemType Directory -Force -Path $ServerDir | Out-Null

    # condense-server-<triple>.zip contains one top-level "condense-server-<triple>/" directory
    # (same layout as the .tar.gz used on Linux/macOS) -- expand then flatten it into $ServerDir.
    $expandTmp = Join-Path $env:TEMP "condense-server-expand-$([guid]::NewGuid())"
    Expand-Archive -Path $SrcArtifact -DestinationPath $expandTmp -Force
    $inner = Get-ChildItem $expandTmp | Select-Object -First 1
    if ($inner -and $inner.PSIsContainer) {
        Copy-Item -Path (Join-Path $inner.FullName "*") -Destination $ServerDir -Recurse -Force
    } else {
        Copy-Item -Path (Join-Path $expandTmp "*") -Destination $ServerDir -Recurse -Force
    }
    Remove-Item -Recurse -Force $expandTmp -ErrorAction SilentlyContinue

    Write-Host ""
    Write-Host "done. condense-server installed to $ServerDir"
    $runBat = Join-Path $ServerDir "run.bat"
    if (Test-Path $runBat) {
        Write-Host "Run it with:"
        Write-Host "  $runBat"
    } else {
        Write-Host "See $ServerDir\README.md to run the engine directly."
    }
    exit 0
}

# --- desktop app: launch the NSIS installer -----------------------------------------------------
Write-Host "==> launching installer: $SrcArtifact"
if ($Silent) {
    # Tauri's NSIS bundles support a silent mode; flag name has varied across tauri-action/NSIS
    # template versions, so try the modern one first and fall back if it errors.
    try {
        Start-Process -FilePath $SrcArtifact -ArgumentList "/S" -Wait
    } catch {
        Write-Host "    /S failed, retrying without silent flag (installer UI will appear)"
        Start-Process -FilePath $SrcArtifact -Wait
    }
} else {
    Start-Process -FilePath $SrcArtifact
    Write-Host "    installer launched -- follow the setup wizard."
}

Write-Host ""
Write-Host "done. Launch ""Condense"" from the Start Menu once setup completes."
