$ErrorActionPreference = "Stop"

Write-Host "Installing AI Hallucination Juror..."

$jurorHome = Join-Path $HOME ".juror"
New-Item -ItemType Directory -Force -Path $jurorHome | Out-Null

python -m pip install -e .

if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
}

Write-Host ""
Write-Host "If needed, add GROK_API_KEY to .env before the first full LLM-backed run."
Write-Host "Installing auto-start task..."
juror install-service
Write-Host "Install complete."
