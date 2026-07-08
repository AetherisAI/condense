# UNTESTED -- no Windows machine available to this WP. Written against the documented NSIS
# installer shape tauri-action / build-desktop.yml produces
# (desktop/src-tauri/target/release/bundle/nsis/*-setup.exe), but never actually run on Windows.
# Please report back anything that doesn't match reality (exact asset filename, installer UI,
# silent-install flags, etc. are all best-guess).
#
# Install (or uninstall) the Condense desktop app on Windows.
#
# Resolution order for the installer .exe:
#   1. -File <path>   use this local installer .exe directly.
#   2. the newest GitHub Release asset for AetherisAI/condense (`gh release download` if `gh` is
#      on PATH, else Invoke-WebRequest against the public releases API).
#   3. neither found -> print a clear message pointing at CI artifacts and exit non-zero.
#
# The NSIS installer itself is a normal Windows installer (Program Files, Start Menu shortcut,
# uninstaller entry) -- this script's job is just to find/download it and launch it; Tauri's NSIS
# bundle handles the actual install UI (and, with -Silent, a silent install).
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File scripts\install-windows.ps1
#   powershell -ExecutionPolicy Bypass -File scripts\install-windows.ps1 -File .\Condense_0.4.0_x64-setup.exe
#   powershell -ExecutionPolicy Bypass -File scripts\install-windows.ps1 -Silent
#   powershell -ExecutionPolicy Bypass -File scripts\install-windows.ps1 -Uninstall

[CmdletBinding()]
param(
    [string]$File,
    [switch]$Silent,
    [switch]$Uninstall
)

$ErrorActionPreference = "Stop"
$RepoSlug = "AetherisAI/condense"

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

$SrcInstaller = $null

if ($File) {
    if (-not (Test-Path $File)) {
        Write-Host "error: -File $File not found" -ForegroundColor Red
        exit 1
    }
    $SrcInstaller = (Resolve-Path $File).Path
    Write-Host "==> using local artifact: $SrcInstaller"
} else {
    Write-Host "==> looking for the newest GitHub Release asset ($RepoSlug)"
    $assetUrl = $null
    $assetName = $null

    if (Get-Command gh -ErrorAction SilentlyContinue) {
        try {
            $json = gh release view --repo $RepoSlug --json assets 2>$null | ConvertFrom-Json
            $match = $json.assets | Where-Object { $_.name -like "*.exe" } | Select-Object -First 1
            if ($match) {
                $assetUrl = $match.url
                $assetName = $match.name
            }
        } catch {
            # fall through to the plain REST API below
        }
    }

    if (-not $assetUrl) {
        try {
            $resp = Invoke-RestMethod -Uri "https://api.github.com/repos/$RepoSlug/releases/latest" -ErrorAction Stop
            $match = $resp.assets | Where-Object { $_.name -like "*.exe" } | Select-Object -First 1
            if ($match) {
                $assetUrl = $match.browser_download_url
                $assetName = $match.name
            }
        } catch {
            # no releases yet, or network error -- handled below
        }
    }

    if (-not $assetUrl) {
        Write-Host ""
        Write-Host "error: no installer .exe asset found on a GitHub Release for $RepoSlug yet." -ForegroundColor Red
        Write-Host ""
        Write-Host "The desktop app may not be tagged/released yet. Grab a build from CI instead (Actions ->"
        Write-Host "build-desktop -> feat/desktop-standalone -> artifact condense-desktop-x86_64-pc-windows-msvc),"
        Write-Host "then re-run:"
        Write-Host "    powershell -ExecutionPolicy Bypass -File scripts\install-windows.ps1 -File <path-to-.exe>"
        exit 1
    }

    Write-Host "    downloading $assetName"
    $tmpDir = Join-Path $env:TEMP "condense-installer"
    New-Item -ItemType Directory -Force -Path $tmpDir | Out-Null
    $dest = Join-Path $tmpDir $assetName
    Invoke-WebRequest -Uri $assetUrl -OutFile $dest
    $SrcInstaller = $dest
}

Write-Host "==> launching installer: $SrcInstaller"
if ($Silent) {
    # Tauri's NSIS bundles support a silent mode; flag name has varied across tauri-action/NSIS
    # template versions, so try the modern one first and fall back if it errors.
    try {
        Start-Process -FilePath $SrcInstaller -ArgumentList "/S" -Wait
    } catch {
        Write-Host "    /S failed, retrying without silent flag (installer UI will appear)"
        Start-Process -FilePath $SrcInstaller -Wait
    }
} else {
    Start-Process -FilePath $SrcInstaller
    Write-Host "    installer launched -- follow the setup wizard."
}

Write-Host ""
Write-Host "done. Launch ""Condense"" from the Start Menu once setup completes."
