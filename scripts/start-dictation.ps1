# Windows PowerShell script to start Memoria voice dictation
# Bypasses execution policy issues and installs voice dependencies

Write-Host "Starting Memoria voice dictation..." -ForegroundColor Green

# Check if Python is available
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host "Error: Python not found. Please install Python and add it to PATH." -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

# Check if virtual environment exists
if (-not (Test-Path ".venv")) {
    Write-Host "Error: Virtual environment not found. Please run start-server.ps1 first." -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

# Activate virtual environment (Windows)
Write-Host "Activating virtual environment..." -ForegroundColor Yellow
& ".\.venv\Scripts\Activate.ps1"

# Install voice dependencies
Write-Host "Installing voice dependencies..." -ForegroundColor Yellow
python -m pip install -r requirements-voice.txt

# Check if .env exists
if (-not (Test-Path ".env")) {
    Write-Host "Error: .env file not found. Please run start-server.ps1 first to create it." -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

# Start voice dictation
Write-Host "Starting voice dictation..." -ForegroundColor Green
Write-Host "Press Enter to start recording, Enter again to stop" -ForegroundColor Yellow
Write-Host "Press Ctrl+C to exit the dictation tool" -ForegroundColor Yellow
python stt_hotkey.py