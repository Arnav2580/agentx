# AI Hallucination Juror - Windows Installer
# Usage: irm https://raw.githubusercontent.com/Arnav2580/agentx/main/install.ps1 | iex

$ErrorActionPreference = "Stop"
$REPO = "https://github.com/Arnav2580/agentx"
$InstallDir = "$env:USERPROFILE\.juror-app"
$EnvFile = "$env:USERPROFILE\.juror\.env"

Write-Host ""
Write-Host "============================================" -ForegroundColor Green
Write-Host "   AI HALLUCINATION JUROR" -ForegroundColor Green
Write-Host "   Multi-agent verification system" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Green
Write-Host ""

Write-Host "[1/6] Checking prerequisites..." -ForegroundColor Cyan

$Python = Get-Command python -ErrorAction SilentlyContinue
if (-not $Python) {
    Write-Host "ERROR: Python 3 required. Install from https://python.org" -ForegroundColor Red
    exit 1
}
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Host "ERROR: Git required. Install from https://git-scm.com" -ForegroundColor Red
    exit 1
}
Write-Host "     Python: $(python --version)" -ForegroundColor Gray

Write-Host "[2/6] Downloading Juror..." -ForegroundColor Cyan

if (Test-Path "$InstallDir\.git") {
    git -C $InstallDir pull --quiet origin main
} elseif (Test-Path $InstallDir) {
    Remove-Item -Recurse -Force $InstallDir
    git clone --quiet $REPO $InstallDir
} else {
    git clone --quiet $REPO $InstallDir
}
Write-Host "     OK Downloaded to $InstallDir" -ForegroundColor Green

Write-Host "[3/6] Installing Python dependencies..." -ForegroundColor Cyan
Set-Location $InstallDir
python -m pip install -r requirements.txt -q --disable-pip-version-check
Write-Host "     OK Dependencies installed" -ForegroundColor Green

Write-Host "[4/6] Configuring API key..." -ForegroundColor Cyan

$EnvDir = "$env:USERPROFILE\.juror"
New-Item -ItemType Directory -Force -Path $EnvDir | Out-Null

if (-not (Test-Path $EnvFile) -or -not (Select-String -Path $EnvFile -Pattern "^GEMINI_API_KEY=" -Quiet -ErrorAction SilentlyContinue)) {
    Write-Host ""
    Write-Host "     Get a free key at: https://aistudio.google.com/apikey" -ForegroundColor Cyan
    $ApiKey = Read-Host "     Enter Gemini API key" -AsSecureString
    $ApiKeyPlain = [Runtime.InteropServices.Marshal]::PtrToStringAuto(
        [Runtime.InteropServices.Marshal]::SecureStringToBSTR($ApiKey)
    )
    @"
GEMINI_API_KEY=$ApiKeyPlain
MODEL=gemini-2.5-flash
SERVER_PORT=8000
"@ | Set-Content $EnvFile
    Write-Host "     OK Saved to ~/.juror/.env" -ForegroundColor Green
} else {
    Write-Host "     OK Configuration already exists" -ForegroundColor Green
}

Write-Host "[5/6] Installing juror command..." -ForegroundColor Cyan

$BinDir = "$env:USERPROFILE\.local\bin"
New-Item -ItemType Directory -Force -Path $BinDir | Out-Null

$batLines = @(
    '@echo off'
    "for /f ""usebackq tokens=1,* delims=="" %%a in (""$EnvFile"") do set %%a=%%b"
    "cd /d ""$InstallDir"""
    'python -m terminal.cli %*'
)
$batLines | Set-Content "$BinDir\juror.bat"

$UserPath = [Environment]::GetEnvironmentVariable("PATH", "User")
if ($UserPath -notlike "*$BinDir*") {
    [Environment]::SetEnvironmentVariable("PATH", "$UserPath;$BinDir", "User")
    if ([string]::IsNullOrWhiteSpace($env:PATH)) {
        $env:PATH = $BinDir
    } else {
        $env:PATH += ";$BinDir"
    }
}
Write-Host "     OK juror command installed" -ForegroundColor Green

Write-Host "[6/6] Installing VS Code extension..." -ForegroundColor Cyan

$Vsix = "$InstallDir\vscode-extension\ai-hallucination-juror-1.0.0.vsix"
$CodeCmd = Get-Command code -ErrorAction SilentlyContinue
if (-not $CodeCmd) {
    $CodeCmd = Get-Command code-insiders -ErrorAction SilentlyContinue
}

if ($CodeCmd -and (Test-Path $Vsix)) {
    & $CodeCmd.Source --install-extension $Vsix --force 2>&1 | Out-Null
    Write-Host "     OK VS Code extension installed" -ForegroundColor Green
} else {
    Write-Host "     WARN VS Code not found - install manually:" -ForegroundColor Yellow
    Write-Host "        code --install-extension $Vsix" -ForegroundColor Cyan
}

$ChromeDir = "$InstallDir\chrome-extension"
Write-Host ""
Write-Host "============================================" -ForegroundColor Green
Write-Host "   INSTALLATION COMPLETE" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Green
Write-Host ""
Write-Host "  Start server:   juror start" -ForegroundColor Cyan
Write-Host "  Dashboard:      http://localhost:8000" -ForegroundColor Cyan
Write-Host "  Terminal wrap:  juror run claude `"your prompt`"" -ForegroundColor Cyan
Write-Host "  Shortcut:       Ctrl+Shift+J on any AI site" -ForegroundColor Cyan
Write-Host "  Uninstall:      juror uninstall --yes" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Chrome extension (one-time, 30 seconds):" -ForegroundColor Yellow
Write-Host "  1. chrome://extensions -> Developer Mode ON"
Write-Host "  2. Load Unpacked -> $ChromeDir" -ForegroundColor Cyan
Write-Host ""

$Start = Read-Host "  Start the server now? [Y/n]"
if ($Start -eq "" -or $Start -match "^[Yy]") {
    Start-Process "http://localhost:8000"
    & "$BinDir\juror.bat" start
}
