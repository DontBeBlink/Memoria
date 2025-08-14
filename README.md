# Memoria Hub

PC‑first hub for memories and reminders with a phone-friendly PWA.

Contents
- `server/` FastAPI + SQLite (local, no fees)
- `web/` PWA client (installable on iPhone; can be published to GitHub Pages)
- `stt_hotkey.py` Local voice dictation on PC using Whisper (offline)
- `scriptable/MemoryAssistant.js` Optional iPhone Scriptable version
- `icons/`, `wallpapers/` Matching Home Screen theme pack
- `.env.example` Copy to `.env` and fill values
- `.github/workflows/pages.yml` Optional: auto-deploy `web/` to Pages

## Quick Start (Windows)

**One-line setup with scripts:**
```powershell
# Start server (creates venv, installs deps, starts server)
.\scripts\start-server.ps1

# In another terminal, start dictation (optional)
.\scripts\start-dictation.ps1
```

**PowerShell Execution Policy:** If you get a script execution error, run one of these first:
```powershell
# Option 1: Allow for current session only (recommended)
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force

# Option 2: Allow for current user permanently
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned -Force
```

## Manual Setup (Windows/macOS/Linux)

**Server only (recommended for most users):**
```bash
python -m venv .venv
# Windows:
. .venv/Scripts/activate
# macOS/Linux:
# source .venv/bin/activate

pip install -r requirements-server.txt
cp .env.example .env  # then edit AUTH_TOKEN, etc.

uvicorn server.main:app --reload --host 0.0.0.0 --port 8000
```

**With voice dictation (optional):**
```bash
# After server setup above, install voice dependencies:
pip install -r requirements-voice.txt

# Run dictation in a separate terminal:
python stt_hotkey.py
```

Open:
- PC: http://127.0.0.1:8000
- iPhone (same Wi‑Fi): http://YOUR_PC_LAN_IP:8000 (find with `ipconfig`)
- In the top bar, set Passcode = your `AUTH_TOKEN` from `.env`.

Data lives in `server/app.db` (gitignored).

## Optional: publish just the web UI

If your repo is public, enable GitHub Pages:
- Settings → Pages → Source “GitHub Actions”
- The included workflow publishes the `web/` folder.
- The web app will call your local/tunnelled server (CORS is open in `server/main.py`).

To use away from home, run a tunnel:
```bash
# Install cloudflared and run tunnel
cloudflared tunnel --url http://localhost:8000
```

**Important for HTTPS:** GitHub Pages serves over HTTPS, but your local server runs on HTTP. Modern browsers require HTTPS-to-HTTPS calls, so you need the HTTPS tunnel URL from cloudflared.

Then open the tunnel URL on your phone or use it as the API endpoint in your deployed Pages app.

## Voice dictation on PC

Offline & accurate (requires voice dependencies):
```bash
# Install voice dependencies first
pip install -r requirements-voice.txt

# Then run dictation
python stt_hotkey.py
# Press Enter to start recording, Enter to stop.
```
It posts to `/capture`. The server decides memory vs reminder and parses simple times.

**Windows shortcut:** Use `.\scripts\start-dictation.ps1` to install deps and start dictation automatically.

## Backup and Data Migration

Memoria includes backup functionality to export and import your data:

### Export Data
- Visit the **Backup** page from the header link
- Click "Download Backup" to export all memories and tasks as JSON
- File format: `{"memories": [...], "tasks": [...]}`

### Import Data
- Use the same Backup page to upload a JSON backup file
- Choose "Overwrite existing items" to update records with same IDs
- Leave unchecked to skip duplicates (safer option)
- Import reports show counts of inserted/updated/skipped/failed records

### API Endpoints
- `GET /export` - Returns JSON with all memories and tasks
- `POST /import?overwrite=false` - Imports JSON data, accepts overwrite flag

### Use Cases
- **Backup**: Regular exports for data safety
- **Migration**: Move data between instances
- **Testing**: Delete database, import backup to restore
## Don’t commit secrets/data
- Keep `.env` and `server/app.db` out of git (already in `.gitignore`).
- Commit `.env.example` only.

## Suggested shortcuts (if you keep Scriptable)
- Memoria: capture memory → passes text to Scriptable
- Promemoria: capture reminder → passes text to Scriptable
- Agenda: parameter `start:low|med|high`
- Focus: `focus:25`, `focus:15`
