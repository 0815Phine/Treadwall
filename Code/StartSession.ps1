# ============================================================
# StartSession.ps1 - Treadwall session launcher
#
# Usage: double-click StartSession.bat
# Or from a PowerShell terminal: .\Code\StartSession.ps1
# ============================================================

# -- Configuration (edit once) --------------------------------
$MATLAB_EXE  = "C:\Program Files\MATLAB\R2024a\bin\matlab.exe"
$PYTHON_EXE  = "C:\Users\TomBombadil\anaconda3\python.exe"
$DATA_BASE   = "D:\Animals"    # Base folder for all behavioural data (no cohort subfolder)
# -------------------------------------------------------------

$ErrorActionPreference = "Stop"

# Script paths relative to this launcher (Code\)
$CAMERA_SCRIPT = Join-Path $PSScriptRoot "Camera\VideoAquisition.py"
$NOTES_SCRIPT  = Join-Path $PSScriptRoot "SessionNotes.py"

try {
    Write-Host ""
    Write-Host "=============================================" -ForegroundColor Cyan
    Write-Host "      Treadwall Session Launcher" -ForegroundColor Cyan
    Write-Host "=============================================" -ForegroundColor Cyan
    Write-Host ""

    # -- Collect session info ---------------------------------
    $ANIMAL_ID  = Read-Host "Animal ID"
    $SESSION_ID = Read-Host "Session ID"

    Write-Host ""
    Write-Host "Select Bpod Protocol:" -ForegroundColor Yellow
    Write-Host "  1   Treadwall_scrambled"
    Write-Host "  2   Treadwall_predictable"
    Write-Host "  3   Treadwall_Baseline"
    Write-Host "  4   Treadwall_Habituation_1"
    Write-Host "  5   Treadwall_Habituation_2"
    Write-Host ""

    $CHOICE = Read-Host "Protocol (1-5)"

    $PROTOCOLS = @{
        "1" = "Treadwall_scrambled"
        "2" = "Treadwall_predictable"
        "3" = "Treadwall_Baseline"
        "4" = "Treadwall_Habituation_1"
        "5" = "Treadwall_Habituation_2"
    }

    if (-not $PROTOCOLS.ContainsKey($CHOICE)) {
        Write-Host "Invalid protocol choice. Exiting." -ForegroundColor Red
        exit 1
    }

    $PROTOCOL = $PROTOCOLS[$CHOICE]

    # -- Generate datetime once -- used for ALL file naming ---
    $DATETIME_STR = Get-Date -Format "yyyyMMdd_HHmm"
    $BASE_NAME    = "${ANIMAL_ID}_${DATETIME_STR}_${SESSION_ID}"
    $SESSION_DIR  = Join-Path $DATA_BASE "$ANIMAL_ID\$SESSION_ID"

    Write-Host ""
    Write-Host "Session:  $BASE_NAME" -ForegroundColor Green
    Write-Host "Protocol: $PROTOCOL"
    Write-Host ""

    # -- Confirm before launching -----------------------------
    $confirm = Read-Host "Start session? (y/n)"
    if ($confirm -ne "y") {
        Write-Host "Aborted." -ForegroundColor Red
        exit 0
    }

    # Ensure session directory exists
    New-Item -ItemType Directory -Force -Path $SESSION_DIR | Out-Null

    Write-Host ""

    # -- 1. Start Camera --------------------------------------
    Write-Host "Starting camera..." -ForegroundColor Yellow
    Start-Process -FilePath $PYTHON_EXE `
        -ArgumentList "`"$CAMERA_SCRIPT`" `"$SESSION_DIR`" `"$ANIMAL_ID`" `"$SESSION_ID`" `"$DATETIME_STR`""

    # -- 2. Start Session Notes (new window, stays open on error)
    Write-Host "Opening session notes..." -ForegroundColor Yellow
    $notes_bat = Join-Path $env:TEMP "session_notes.bat"
    $bat_lines = @(
        '@echo off',
        "title Session Notes - $BASE_NAME",
        "`"$PYTHON_EXE`" `"$NOTES_SCRIPT`" `"$ANIMAL_ID`" `"$DATETIME_STR`" `"$SESSION_ID`" `"$SESSION_DIR`"",
        'if errorlevel 1 pause'
    )
    ($bat_lines -join "`r`n") | Out-File -FilePath $notes_bat -Encoding ASCII -Force
    Start-Process -FilePath "cmd.exe" -ArgumentList "/c `"$notes_bat`""

    # -- 3. Start WaveSurfer in its own MATLAB instance -------
    Write-Host "Launching WaveSurfer..." -ForegroundColor Yellow
    $WS_SCRIPT   = Join-Path $PSScriptRoot "Wavesurfer\StartWaveSurfer.m"
    $WS_FOLDER   = Join-Path $PSScriptRoot "Wavesurfer"
    $WSP_FILE    = Join-Path $WS_FOLDER "Treadwall.wsp"
    $ws_cmd = "addpath('$WS_FOLDER'); StartWaveSurfer('$WSP_FILE','$SESSION_DIR','$BASE_NAME')"
    Start-Process -FilePath $MATLAB_EXE -ArgumentList "-nosplash -r `"$ws_cmd`""

    # -- 4. Start MATLAB/Bpod ---------------------------------
    Write-Host "Launching MATLAB/Bpod..." -ForegroundColor Yellow
    $matlab_cmd = "StartBpodSession('$ANIMAL_ID','$SESSION_ID','$DATETIME_STR','$PROTOCOL')"
    Start-Process -FilePath $MATLAB_EXE -ArgumentList "-nosplash -r `"$matlab_cmd`""

    Write-Host ""
    Write-Host "All processes launched:" -ForegroundColor Green
    Write-Host "  Camera         -- live stream will appear once triggered"
    Write-Host "  Session Notes  -- type notes during the experiment"
    Write-Host "  WaveSurfer     -- output folder and filename pre-filled"
    Write-Host "  MATLAB/Bpod    -- loading protocol"
    Write-Host ""
    Write-Host "When everything shows ready: press Record in WaveSurfer." -ForegroundColor Yellow
    Write-Host ""

} catch {
    Write-Host ""
    Write-Host "ERROR: $_" -ForegroundColor Red
    Write-Host ""
} finally {
    Read-Host "Press Enter to close this launcher"
}
