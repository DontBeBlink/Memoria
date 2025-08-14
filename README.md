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

## Run the server (Windows/macOS/Linux)

### Quick start (Windows)
```powershell
# Double-click or run from PowerShell:
scripts\start-server.ps1
```

### Manual setup (all platforms)
```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
# source .venv/bin/activate

pip install -r requirements-server.txt
cp .env.example .env  # then edit AUTH_TOKEN, etc.

python -m uvicorn server.main:app --reload --host 0.0.0.0 --port 8000
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
cloudflared tunnel --url http://localhost:8000
```
Then open the tunnel URL on your phone.

## Voice dictation on PC

### Quick start (Windows)
```powershell
# Double-click or run from PowerShell:
scripts\start-dictation.ps1
```

### Manual setup (all platforms)
```bash
# In the same terminal where server venv is activated:
pip install -r requirements-voice.txt
python stt_hotkey.py
# Press Enter to start recording, Enter to stop.
```
It posts to `/capture`. The server decides memory vs reminder and parses simple times.

## Don’t commit secrets/data
- Keep `.env` and `server/app.db` out of git (already in `.gitignore`).
- Commit `.env.example` only.

## Suggested shortcuts (if you keep Scriptable)
- Memoria: capture memory → passes text to Scriptable
- Promemoria: capture reminder → passes text to Scriptable
- Agenda: parameter `start:low|med|high`
- Focus: `focus:25`, `focus:15`
