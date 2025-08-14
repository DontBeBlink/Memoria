# Windows PowerShell script to start Memoria server
# Bypasses execution policy issues and creates venv if needed

Write-Host "Starting Memoria Hub server..." -ForegroundColor Green

# Check if Python is available
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host "Error: Python not found. Please install Python and add it to PATH." -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

# Create virtual environment if it doesn't exist
if (-not (Test-Path ".venv")) {
    Write-Host "Creating virtual environment..." -ForegroundColor Yellow
    python -m venv .venv
}

# Activate virtual environment (Windows)
Write-Host "Activating virtual environment..." -ForegroundColor Yellow
& ".\.venv\Scripts\Activate.ps1"

# Install server dependencies
Write-Host "Installing server dependencies..." -ForegroundColor Yellow
python -m pip install --upgrade pip
python -m pip install -r requirements-server.txt

# Copy .env.example if .env doesn't exist
if (-not (Test-Path ".env")) {
    if (Test-Path ".env.example") {
        Write-Host "Creating .env from template..." -ForegroundColor Yellow
        Copy-Item ".env.example" ".env"
        Write-Host "Please edit .env file and set your AUTH_TOKEN" -ForegroundColor Cyan
    }
}

# Start server using python -m to avoid PATH issues
Write-Host "Starting server on http://127.0.0.1:8000" -ForegroundColor Green
Write-Host "Press Ctrl+C to stop the server" -ForegroundColor Yellow
python -m uvicorn server.main:app --reload --host 0.0.0.0 --port 8000