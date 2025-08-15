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

## Deleting memories and tasks

Each memory and task has a trash icon (🗑️) button for deletion:
- Click the delete button to get a confirmation dialog
- Deleted items are permanently removed (hard delete)
- API returns 404 for unknown IDs; UI shows "Item already gone" message
- Works with keyboard navigation (Tab to focus, Enter/Space to activate)

## Recurring Tasks and Calendar Integration

Memoria supports recurring tasks with RRULE (RFC 5545) and iCalendar export:

### Creating Recurring Tasks
1. **Add a task** with a due date (e.g., "Daily standup tomorrow 9am")
2. **Click the 🔁 Repeat button** to show recurrence options
3. **Select repeat pattern**:
   - Daily, Weekly, Monthly
   - Custom RRULE for advanced patterns
4. **Add the task** - it will show 🔁 Recurring badge

### Viewing Recurring Tasks
- **Original task**: Shows 🔁 Recurring badge
- **Recurring instances**: Show ↻ Instance badge with green color
- **Agenda views**: Display all instances within the date range
- **Task management**: Each instance can be marked done independently

### iCalendar Export
Export your tasks to Google Calendar, Apple Calendar, or other calendar apps:

```bash
# Get your calendar feed (requires AUTH_TOKEN)
GET /calendar.ics
# With authentication header: X-Auth-Token: your_token

# Optional filters:
GET /calendar.ics?q=meeting          # Filter by keyword
GET /calendar.ics?priority=high      # Filter by priority
```

**Calendar Features:**
- **VEVENT entries** for all scheduled tasks
- **RRULE support** for recurring tasks
- **UTC timestamps** for proper timezone handling
- **Unique UIDs** for each task instance
- **Status tracking** (NEEDS-ACTION/COMPLETED)

**Usage in Calendar Apps:**
1. Copy the calendar URL: `https://your-server/calendar.ics`
2. Add authentication: `?token=your_auth_token` (if using URL-based auth)
3. Import or subscribe in your calendar app
4. Tasks appear as calendar events with recurrence

### Bulk Operations for Memories

The enhanced Memories page supports bulk operations:
- **Bulk selection**: Check individual memory checkboxes or use "Select All"
- **Bulk delete**: Select multiple memories and use "Delete Selected" for efficient cleanup
- **Confirmation dialog**: Bulk deletes require confirmation to prevent accidents

## Enhanced Memories Page

The dedicated Memories page (`/web/memories.html`) provides advanced filtering and management:

### Search and Filtering
- **Text search**: Search across memory content and tags using the search box (supports Enter key)
- **Tag filtering**: Click on tag chips (#hashtag) to filter memories by specific tags  
- **People filtering**: Click on people chips (@person) to filter memories by mentioned people
- **Combined filtering**: Use multiple filters together (search + tags + people)
- **CSV filtering**: Backend supports comma-separated values for tags and people parameters

### Interactive Features
- **Filter chips**: Clickable chips show available tags and people from current results
- **Active filters**: Applied filters show with × buttons to remove them
- **Clear all**: "Clear" button removes all active filters and search terms

### Inline Editing
- **Edit in place**: Click the ✏️ edit button to edit memory text inline
- **Keyboard shortcuts**: Save with Enter, cancel with Escape, or use ✓/✕ buttons
- **Auto-tag update**: Tags are automatically extracted and updated when memory text changes
- **Visual feedback**: Editing state is clearly indicated with border highlighting

### Pagination
- **Server-side pagination**: Efficient handling of large memory collections
- **Page info**: Shows current page, total pages, and total item count
- **Navigation**: Previous/Next buttons with proper disable states

### Error Handling
- **Success banners**: Green banners confirm successful operations (add, edit, delete)
- **Error banners**: Red banners show error messages for failed operations
- **Auto-dismiss**: Banners automatically disappear after a few seconds

### API Enhancements

The `/memories` endpoint now supports enhanced filtering:
```bash
# Search with text query
GET /memories?q=search+term&limit=20&offset=0

# Filter by tags (CSV)
GET /memories?tags=ai,project&limit=20&offset=0

# Filter by people (CSV)  
GET /memories?people=john,mary&limit=20&offset=0

# Combined filtering
GET /memories?q=meeting&tags=work&people=john&limit=20&offset=0
```

Response format:
```json
{
  "items": [...],
  "total": 42
}
```

**Backward Compatibility**: When no filtering parameters are provided, the endpoint returns just the items array as before.

## Web-based voice dictation

The web interface includes a built-in voice dictation feature:

- **🎤 Mic button** in the header for voice recording
- **Hold-to-record**: Press and hold the mic button to record, release to stop and transcribe
- **Automatic memory creation**: Transcribed text is automatically saved as a memory
- **Error handling**: Shows clear error messages for permission issues or transcription failures

**Setup:**
1. Install voice dependencies: `pip install -r requirements-voice.txt`
2. Configure in `.env`:
   ```bash
   WHISPER_MODEL=small.en          # Base, small, medium, large-v3, etc.
   TRANSCRIPTION_LANGUAGE=en       # Language code or 'auto'
   WHISPER_DEVICE=cpu              # 'cpu' or 'cuda' (if GPU available)
   ```
3. Grant microphone permission when prompted

**Features:**
- Works on Chrome/Edge (Windows) and Chrome (macOS)
- Offline transcription using faster-whisper
- Respects AUTH_TOKEN authentication
- Visual feedback during recording and transcription

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
=======
## Deleting memories and tasks

Each memory and task has a trash icon (🗑️) button for deletion:
- Click the delete button to get a confirmation dialog
- Deleted items are permanently removed (hard delete)
- API returns 404 for unknown IDs; UI shows "Item already gone" message
- Works with keyboard navigation (Tab to focus, Enter/Space to activate)

## Web-based voice dictation

The web interface includes a built-in voice dictation feature:

- **🎤 Mic button** in the header for voice recording
- **Hold-to-record**: Press and hold the mic button to record, release to stop and transcribe
- **Automatic memory creation**: Transcribed text is automatically saved as a memory
- **Error handling**: Shows clear error messages for permission issues or transcription failures

**Setup:**
1. Install voice dependencies: `pip install -r requirements-voice.txt`
2. Configure in `.env`:
   ```bash
   WHISPER_MODEL=small.en          # Base, small, medium, large-v3, etc.
   TRANSCRIPTION_LANGUAGE=en       # Language code or 'auto'
   WHISPER_DEVICE=cpu              # 'cpu' or 'cuda' (if GPU available)
   ```
3. Grant microphone permission when prompted

**Features:**
- Works on Chrome/Edge (Windows) and Chrome (macOS)
- Offline transcription using faster-whisper
- Respects AUTH_TOKEN authentication
- Visual feedback during recording and transcription

## PWA and Offline Support

Memoria is a fully-featured Progressive Web App (PWA) with offline capabilities:

### Installation
- **Mobile**: Add to Home Screen from your browser
- **Desktop**: Use the "Install App" button or browser's install prompt
- **Works offline**: Core functionality available when disconnected

### Offline Features
- **Cached pages**: All app pages (Hub, Memories, Agenda, Backup, Settings) work offline
- **Offline creation**: Create memories and tasks when offline - they're automatically queued
- **Background sync**: Queued items are sent to server when connection is restored
- **Visual feedback**: 
  - Orange toast notification when offline: "You are offline. New items will be queued"
  - Queue indicator in header shows pending items count
  - Success messages when items are queued vs. saved immediately

### Technical Details
- **Service Worker**: Enhanced caching and request queueing using IndexedDB
- **Request interception**: POST requests to `/memories` and `/tasks` are queued when offline
- **Auto-retry**: Queued requests are automatically retried when online
- **No data loss**: Items created offline are safely stored until they can be synchronized

### Browser Support
- **Recommended**: Chrome, Edge, Safari (modern versions)
- **Service Worker required**: For offline functionality
- **IndexedDB required**: For offline request queueing
## Don’t commit secrets/data
- Keep `.env` and `server/app.db` out of git (already in `.gitignore`).
- Commit `.env.example` only.

## Suggested shortcuts (if you keep Scriptable)
- Memoria: capture memory → passes text to Scriptable
- Promemoria: capture reminder → passes text to Scriptable
- Agenda: parameter `start:low|med|high`
- Focus: `focus:25`, `focus:15`
