# Start dictation with voice dependencies
Write-Host "Starting Memoria Dictation..." -ForegroundColor Green

# Assume venv exists and activate it
if (-not (Test-Path ".venv")) {
    Write-Host "Virtual environment not found. Run start-server.ps1 first." -ForegroundColor Red
    exit 1
}

Write-Host "Activating virtual environment..." -ForegroundColor Yellow
. .\.venv\Scripts\Activate.ps1

# Install voice dependencies
Write-Host "Installing voice dependencies..." -ForegroundColor Yellow
python -m pip install -r requirements-voice.txt

# Start dictation
Write-Host "Starting voice dictation. Press Enter to record, Enter again to stop..." -ForegroundColor Green
python .\stt_hotkey.py