[CmdletBinding()]
param(
    [string]$InstallDir = (Join-Path $env:LOCALAPPDATA "linkedin-apply-assistant"),
    [string]$Ref = "main",
    [switch]$InstallBrowser,
    [switch]$NoPath,
    [switch]$Update,
    [switch]$CheckOnly
)

Set-StrictMode -Version 3.0
$ErrorActionPreference = "Stop"

$RepoOwner = "MohammedGhazal09"
$RepoName = "linkedin-apply-assistant"

function Write-Step {
    param([string]$Message)
    Write-Host "[linkedin-apply-assistant] $Message"
}

function Get-ArchiveUrl {
    param([string]$SourceRef)

    if ($SourceRef -match "^refs/heads/") {
        return "https://github.com/$RepoOwner/$RepoName/archive/$SourceRef.zip"
    }
    if ($SourceRef -match "^refs/tags/") {
        return "https://github.com/$RepoOwner/$RepoName/archive/$SourceRef.zip"
    }
    if ($SourceRef -match "^v?\d+\.\d+\.\d+") {
        return "https://github.com/$RepoOwner/$RepoName/archive/refs/tags/$SourceRef.zip"
    }
    return "https://github.com/$RepoOwner/$RepoName/archive/refs/heads/$SourceRef.zip"
}

function Get-Python {
    $candidates = @(
        @{ Command = "py"; Args = @("-3.11") },
        @{ Command = "py"; Args = @("-3") },
        @{ Command = "python"; Args = @() },
        @{ Command = "python3"; Args = @() }
    )

    foreach ($candidate in $candidates) {
        $command = $candidate.Command
        $prefixArgs = [string[]]$candidate.Args
        try {
            & $command @prefixArgs -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)" *> $null
            if ($LASTEXITCODE -eq 0) {
                return $candidate
            }
        }
        catch {
            continue
        }
    }

    throw "Python 3.11 or newer was not found. Install Python 3.11+ and rerun this script."
}

function Invoke-Python {
    param(
        [hashtable]$Python,
        [string[]]$Arguments
    )

    & $Python.Command @([string[]]$Python.Args + $Arguments)
    if ($LASTEXITCODE -ne 0) {
        throw "Python command failed: $($Python.Command) $($Arguments -join ' ')"
    }
}

function Add-UserPathEntry {
    param([string]$PathEntry)

    $current = [Environment]::GetEnvironmentVariable("Path", "User")
    $parts = @()
    if ($current) {
        $parts = $current -split [IO.Path]::PathSeparator
    }
    if ($parts -contains $PathEntry) {
        return
    }

    $next = if ($current) {
        "$PathEntry$([IO.Path]::PathSeparator)$current"
    }
    else {
        $PathEntry
    }
    [Environment]::SetEnvironmentVariable("Path", $next, "User")

    if (($env:Path -split [IO.Path]::PathSeparator) -notcontains $PathEntry) {
        $env:Path = "$PathEntry$([IO.Path]::PathSeparator)$env:Path"
    }
}

$python = Get-Python
$archiveUrl = Get-ArchiveUrl -SourceRef $Ref
$installRoot = [IO.Path]::GetFullPath($InstallDir)
$sourceDir = Join-Path $installRoot "source"
$venvDir = Join-Path $installRoot ".venv"
$binDir = Join-Path $installRoot "bin"
$tempDir = Join-Path ([IO.Path]::GetTempPath()) ("linkedin-apply-assistant-" + [guid]::NewGuid())
$zipPath = Join-Path $tempDir "source.zip"

if ($CheckOnly) {
    Write-Step "Installer source: $archiveUrl"
    Write-Step "Install directory: $installRoot"
    Write-Step "Ref: $Ref"
    Write-Host ""
    Write-Host "Run update:"
    Write-Host "  powershell -NoProfile -ExecutionPolicy Bypass -File .\install.ps1 -Update"
    exit 0
}

try {
    $action = if ($Update) { "Updating" } else { "Installing" }
    Write-Step "$action from $archiveUrl"
    New-Item -ItemType Directory -Force -Path $tempDir | Out-Null
    New-Item -ItemType Directory -Force -Path $installRoot | Out-Null

    Invoke-WebRequest -UseBasicParsing -Uri $archiveUrl -OutFile $zipPath
    Expand-Archive -LiteralPath $zipPath -DestinationPath $tempDir -Force

    $expanded = Get-ChildItem -LiteralPath $tempDir -Directory |
        Where-Object { $_.Name -like "$RepoName-*" } |
        Select-Object -First 1
    if ($null -eq $expanded) {
        throw "Could not find extracted package directory in $tempDir"
    }

    if (Test-Path -LiteralPath $sourceDir) {
        Remove-Item -LiteralPath $sourceDir -Recurse -Force
    }
    Move-Item -LiteralPath $expanded.FullName -Destination $sourceDir

    Write-Step "Creating virtual environment"
    Invoke-Python -Python $python -Arguments @("-m", "venv", $venvDir)

    $venvPython = Join-Path $venvDir "Scripts\python.exe"
    if (-not (Test-Path -LiteralPath $venvPython)) {
        throw "Virtual environment Python was not created at $venvPython"
    }

    Write-Step "Installing Python package"
    & $venvPython -m pip install --upgrade pip
    if ($LASTEXITCODE -ne 0) { throw "pip upgrade failed" }
    & $venvPython -m pip install $sourceDir
    if ($LASTEXITCODE -ne 0) { throw "Package install failed" }

    if ($InstallBrowser) {
        Write-Step "Installing Playwright Chromium"
        & $venvPython -m playwright install chromium
        if ($LASTEXITCODE -ne 0) { throw "Playwright Chromium install failed" }
    }

    New-Item -ItemType Directory -Force -Path $binDir | Out-Null
    $psShim = Join-Path $binDir "linkedin-apply-assistant.ps1"
    $cmdShim = Join-Path $binDir "linkedin-apply-assistant.cmd"

@"
param([Parameter(ValueFromRemainingArguments = `$true)][string[]]`$RemainingArgs)
`$env:LINKEDIN_APPLY_ASSISTANT_INSTALL_CHANNEL = "powershell"
`$env:LINKEDIN_APPLY_ASSISTANT_INSTALL_DIR = "$installRoot"
`$env:LINKEDIN_APPLY_ASSISTANT_INSTALL_REF = "$Ref"
& "$venvPython" -m linkedin_apply_assistant.cli @RemainingArgs
exit `$LASTEXITCODE
"@ | Set-Content -LiteralPath $psShim -Encoding UTF8

    @"
@echo off
set "LINKEDIN_APPLY_ASSISTANT_INSTALL_CHANNEL=powershell"
set "LINKEDIN_APPLY_ASSISTANT_INSTALL_DIR=$installRoot"
set "LINKEDIN_APPLY_ASSISTANT_INSTALL_REF=$Ref"
"$venvPython" -m linkedin_apply_assistant.cli %*
"@ |
        Set-Content -LiteralPath $cmdShim -Encoding ASCII

    if (-not $NoPath) {
        Add-UserPathEntry -PathEntry $binDir
    }

    Write-Step "Installed to $installRoot"
    Write-Host ""
    Write-Host "Try it now:"
    Write-Host "  linkedin-apply-assistant --help"
    Write-Host "  linkedin-apply-assistant config check"
    if (-not $InstallBrowser) {
        Write-Host ""
        Write-Host "For visible-browser workflows, install Chromium later with:"
        Write-Host "  & `"$venvPython`" -m playwright install chromium"
    }
}
finally {
    if (Test-Path -LiteralPath $tempDir) {
        Remove-Item -LiteralPath $tempDir -Recurse -Force
    }
}
