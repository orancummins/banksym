<#
.SYNOPSIS
    BankSym run script (Windows PowerShell).
.DESCRIPTION
    Manages the BankSym dev server: creates a virtual environment, installs dependencies,
    and starts/stops the server using a PID file so it is not started twice.
.PARAMETER Action
    start | stop | restart | status   (default: start)
.EXAMPLE
    .\run.ps1 start
    .\run.ps1 stop
#>
[CmdletBinding()]
param(
    [ValidateSet('start', 'stop', 'restart', 'status')]
    [string]$Action = 'start'
)

$ErrorActionPreference = 'Stop'

# --- Configuration -----------------------------------------------------------
$BankSymHost = if ($env:BANKSYM_HOST) { $env:BANKSYM_HOST } else { '127.0.0.1' }
$Port = if ($env:BANKSYM_PORT) { $env:BANKSYM_PORT } else { '8000' }
$App = 'banksym.api.app:app'

# Run relative to this script's directory.
Set-Location -Path $PSScriptRoot

$VenvDir = '.venv'
$Py = Join-Path $VenvDir 'Scripts\python.exe'
$PidFile = '.banksym.pid'
$LogFile = 'banksym.log'
$DepsStamp = Join-Path $VenvDir '.deps-installed'

# --- Helpers -----------------------------------------------------------------
function Test-Running {
    if (-not (Test-Path $PidFile)) { return $false }
    $procId = (Get-Content $PidFile -ErrorAction SilentlyContinue | Select-Object -First 1)
    if (-not $procId) { return $false }
    $proc = Get-Process -Id ([int]$procId) -ErrorAction SilentlyContinue
    return [bool]$proc
}

function Get-RunningPid {
    return [int](Get-Content $PidFile | Select-Object -First 1)
}

function Initialize-Venv {
    if (-not (Test-Path $Py)) {
        Write-Host "Creating virtual environment in $VenvDir ..."
        $python = Get-Command python -ErrorAction SilentlyContinue
        if (-not $python) { $python = Get-Command py -ErrorAction SilentlyContinue }
        if (-not $python) { throw 'Python was not found on PATH. Install Python 3.12+ first.' }
        & $python.Source -m venv $VenvDir
    }
}

function Install-Dependencies {
    $needsInstall = $true
    if (Test-Path $DepsStamp) {
        $stamp = (Get-Item $DepsStamp).LastWriteTimeUtc
        $proj = (Get-Item 'pyproject.toml').LastWriteTimeUtc
        if ($stamp -ge $proj) { $needsInstall = $false }
    }
    if ($needsInstall) {
        Write-Host 'Installing dependencies ...'
        & $Py -m pip install --quiet --upgrade pip
        & $Py -m pip install --quiet -e '.[dev]'
        New-Item -ItemType File -Path $DepsStamp -Force | Out-Null
    }
}

# --- Commands ----------------------------------------------------------------
function Start-BankSym {
    if (Test-Running) {
        Write-Host "BankSym is already running (PID $(Get-RunningPid)) at http://${BankSymHost}:${Port}"
        return
    }
    Initialize-Venv
    Install-Dependencies
    Write-Host "Starting BankSym at http://${BankSymHost}:${Port} ..."
    $args = @('-m', 'uvicorn', $App, '--host', $BankSymHost, '--port', $Port)
    $proc = Start-Process -FilePath $Py -ArgumentList $args `
        -RedirectStandardOutput $LogFile -RedirectStandardError "$LogFile.err" `
        -WindowStyle Hidden -PassThru
    $proc.Id | Out-File -FilePath $PidFile -Encoding ascii
    Start-Sleep -Seconds 1
    if (Test-Running) {
        Write-Host "Started (PID $($proc.Id)). Logs: $LogFile  |  Docs: http://${BankSymHost}:${Port}/docs"
    }
    else {
        Write-Warning "Failed to start. Check $LogFile / $LogFile.err"
        if (Test-Path $LogFile) { Get-Content $LogFile -Tail 20 }
        Remove-Item $PidFile -ErrorAction SilentlyContinue
        exit 1
    }
}

function Stop-BankSym {
    if (-not (Test-Running)) {
        Write-Host 'BankSym is not running.'
        Remove-Item $PidFile -ErrorAction SilentlyContinue
        return
    }
    $procId = Get-RunningPid
    Write-Host "Stopping BankSym (PID $procId) ..."
    Stop-Process -Id $procId -ErrorAction SilentlyContinue
    for ($i = 0; $i -lt 10; $i++) {
        if (-not (Test-Running)) { break }
        Start-Sleep -Milliseconds 500
    }
    if (Test-Running) {
        Write-Host 'Process did not exit; forcing ...'
        Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
    }
    Remove-Item $PidFile -ErrorAction SilentlyContinue
    Write-Host 'Stopped.'
}

function Get-Status {
    if (Test-Running) {
        Write-Host "BankSym is running (PID $(Get-RunningPid)) at http://${BankSymHost}:${Port}"
    }
    else {
        Write-Host 'BankSym is not running.'
    }
}

switch ($Action) {
    'start' { Start-BankSym }
    'stop' { Stop-BankSym }
    'restart' { Stop-BankSym; Start-BankSym }
    'status' { Get-Status }
}
