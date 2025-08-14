param(
    [int]$Port = 8000
)

# Bypass execution policy for this process only
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force

Write-Host "Starting Memoria Server..." -ForegroundColor Green

# Create .venv if missing
if (-not (Test-Path ".venv")) {
    Write-Host "Creating virtual environment..." -ForegroundColor Yellow
    py -3 -m venv .venv
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Failed to create virtual environment. Make sure Python 3 is installed." -ForegroundColor Red
        exit 1
    }
}

# Activate virtual environment
Write-Host "Activating virtual environment..." -ForegroundColor Yellow
. .\.venv\Scripts\Activate.ps1

# Upgrade pip and install server dependencies
Write-Host "Installing/upgrading dependencies..." -ForegroundColor Yellow
python -m pip install --upgrade pip
python -m pip install -r requirements-server.txt

# Copy .env.example to .env if missing
if (-not (Test-Path ".env")) {
    Write-Host "Creating .env from .env.example..." -ForegroundColor Yellow
    Copy-Item ".env.example" ".env"
    Write-Host "IMPORTANT: Edit .env and set AUTH_TOKEN to a secure random string!" -ForegroundColor Red
}

# Start the server
Write-Host "Starting server on http://127.0.0.1:$Port..." -ForegroundColor Green
python -m uvicorn server.main:app --reload --host 0.0.0.0 --port $Port