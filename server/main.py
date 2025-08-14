import os
import threading
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Tuple

from fastapi import FastAPI, Depends, HTTPException, Header, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
import requests

from . import storage
from .schemas import MemoryIn, TaskIn, CaptureIn
import json

load_dotenv()

AUTH_TOKEN = os.getenv("AUTH_TOKEN", "")
NTFY_TOPIC = os.getenv("NTFY_TOPIC", "")
NTFY_SERVER = os.getenv("NTFY_SERVER", "https://ntfy.sh").rstrip("/")
WEB_DIR = os.path.join(os.path.dirname(__file__), "..", "web")

app = FastAPI(title="Memoria Server")

app.add_middleware(
  CORSMiddleware,
  allow_origins=["*"],
  allow_credentials=True,
  allow_methods=["*"],
  allow_headers=["*"],
)

# Mount static files for web interface
app.mount("/web", StaticFiles(directory=WEB_DIR), name="web")

def require_auth(x_auth_token: Optional[str] = Header(None)):
  if not AUTH_TOKEN:
    return True
  if x_auth_token != AUTH_TOKEN:
    raise HTTPException(status_code=401, detail="Unauthorized")
  return True

@app.on_event("startup")
def on_start():
  storage.init_db()
  threading.Thread(target=_notifier_loop, daemon=True).start()

@app.get("/")
def root():
  index_path = os.path.join(WEB_DIR, "index.html")
  if os.path.exists(index_path):
    return FileResponse(index_path)
  return {"ok": True, "app": "Memoria Server"}

@app.get("/manifest.json")
def get_manifest():
  manifest_path = os.path.join(WEB_DIR, "manifest.json")
  if os.path.exists(manifest_path):
    return FileResponse(manifest_path, media_type="application/json")
  raise HTTPException(status_code=404, detail="Manifest not found")

@app.get("/service-worker.js")
def get_service_worker():
  sw_path = os.path.join(WEB_DIR, "service-worker.js")
  if os.path.exists(sw_path):
    return FileResponse(sw_path, media_type="application/javascript")
  raise HTTPException(status_code=404, detail="Service worker not found")

@app.get("/favicon.svg")
def get_favicon():
  favicon_path = os.path.join(WEB_DIR, "favicon.svg")
  if os.path.exists(favicon_path):
    return FileResponse(favicon_path, media_type="image/svg+xml")
  raise HTTPException(status_code=404, detail="Favicon not found")

@app.get("/icons/{icon_name}")
def get_icon(icon_name: str):
  # Only allow specific icon files for security
  if icon_name not in ["icon-192.png", "icon-512.png"]:
    raise HTTPException(status_code=404, detail="Icon not found")
  
  icon_path = os.path.join(WEB_DIR, "icons", icon_name)
  if os.path.exists(icon_path):
    return FileResponse(icon_path, media_type="image/png")
  raise HTTPException(status_code=404, detail="Icon not found")

@app.get("/memories")
def get_memories(auth=Depends(require_auth)):
  return storage.list_memories()

@app.post("/memories")
def post_memory(mem: MemoryIn, auth=Depends(require_auth)):
  return storage.add_memory(mem.text)

@app.get("/tasks")
def get_tasks(open_only: bool = False, auth=Depends(require_auth)):
  return storage.list_tasks(open_only=open_only)

@app.post("/tasks")
def post_task(task: TaskIn, auth=Depends(require_auth)):
  return storage.add_task(task.title, task.due)

@app.post("/tasks/{task_id}/done")
def done_task(task_id: int, done: bool = True, auth=Depends(require_auth)):
  row = storage.mark_done(task_id, done)
  if not row:
    raise HTTPException(status_code=404, detail="Not found")
  return row

@app.post("/capture")
def capture(data: CaptureIn, auth=Depends(require_auth)):
  parsed = _parse_input(data.text)
  if parsed["kind"] == "task":
    row = storage.add_task(parsed["text"], parsed["due"])
    return {"type": "task", "item": row}
  else:
    row = storage.add_memory(parsed["text"])
    return {"type": "memory", "item": row}

@app.get("/export")
def export_data(auth=Depends(require_auth)):
  """Export all memories and tasks as JSON."""
  memories = storage.get_all_memories()
  tasks = storage.get_all_tasks()
  return {"memories": memories, "tasks": tasks}

@app.post("/import")
def import_data(data: dict, overwrite: bool = False, auth=Depends(require_auth)):
  """Import memories and tasks from JSON. Returns counts of operations."""
  if not isinstance(data, dict) or "memories" not in data or "tasks" not in data:
    raise HTTPException(status_code=400, detail="Invalid data format. Expected {memories: [...], tasks: [...]}")
  
  results = {
    "memories": {"inserted": 0, "updated": 0, "skipped": 0, "failed": 0},
    "tasks": {"inserted": 0, "updated": 0, "skipped": 0, "failed": 0}
  }
  
  # Import memories
  for memory in data.get("memories", []):
    result = storage.import_memory(memory, overwrite=overwrite)
    status = result["status"]
    if status in results["memories"]:
      results["memories"][status] += 1
  
  # Import tasks
  for task in data.get("tasks", []):
    result = storage.import_task(task, overwrite=overwrite)
    status = result["status"]
    if status in results["tasks"]:
      results["tasks"][status] += 1
  
  return results

# --------- helpers

def _strip_prefixes(s: str) -> str:
  import re
  s = re.sub(r"^remind\s+me\s+(to|that)\s*", "", s, flags=re.I)
  s = re.sub(r"^remember\s+(that)?\s*", "", s, flags=re.I)
  s = re.sub(r"^note\s*:\s*", "", s, flags=re.I)
  return s.strip()

def _extract_due(s: str) -> Tuple[str, Optional[str]]:
  import re
  text = f" {s} "
  due: Optional[datetime] = None
  now = datetime.now()

  def set_time(d: datetime, hh: int, mm: int = 0, ap: Optional[str] = None):
    H = int(hh); M = int(mm or 0)
    if ap:
      ap = ap.lower()
      if ap == "pm" and H < 12: H += 12
      if ap == "am" and H == 12: H = 0
    return d.replace(hour=H, minute=M, second=0, microsecond=0)

  # in X minutes/hours/days
  m = re.search(r"\bin\s+(\d{1,3})\s*(minutes?|mins?|hours?|hrs?|days?)\b", text, flags=re.I)
  if m and not due:
    num = int(m.group(1)); unit = m.group(2).lower()
    d = now
    if unit.startswith("min"): d += timedelta(minutes=num)
    elif unit.startswith("hour") or unit.startswith("hr"): d += timedelta(hours=num)
    elif unit.startswith("day"): d += timedelta(days=num)
    due = d; text = text.replace(m.group(0), " ")

  # tomorrow [at time]
  m = re.search(r"\btomorrow(?:\s+at\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?)?\b", text, flags=re.I)
  if m and not due:
    d = now + timedelta(days=1)
    if m.group(1): d = set_time(d, int(m.group(1)), int(m.group(2) or 0), m.group(3))
    else: d = set_time(d, 9, 0, None)
    due = d; text = text.replace(m.group(0), " ")

  # today at hh:mm
  m = re.search(r"\btoday\s+at\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\b", text, flags=re.I)
  if m and not due:
    d = set_time(now, int(m.group(1)), int(m.group(2) or 0), m.group(3))
    due = d; text = text.replace(m.group(0), " ")

  # next weekday
  m = re.search(r"\bnext\s+(sunday|monday|tuesday|wednesday|thursday|friday|saturday)(?:\s+at\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?)?\b", text, flags=re.I)
  if m and not due:
    wd_map = {'sunday':6,'monday':0,'tuesday':1,'wednesday':2,'thursday':3,'friday':4,'saturday':5}
    target = wd_map[m.group(1).lower()]
    delta = (target - now.weekday() + 7) % 7
    if delta == 0: delta = 7
    d = now + timedelta(days=delta)
    if m.group(2): d = set_time(d, int(m.group(2)), int(m.group(3) or 0), m.group(4))
    else: d = set_time(d, 9, 0, None)
    due = d; text = text.replace(m.group(0), " ")

  # on YYYY-MM-DD [HH:MM]
  m = re.search(r"\bon\s+(\d{4})-(\d{1,2})-(\d{1,2})(?:\s+(\d{1,2})(?::(\d{2}))?)?\b", text, flags=re.I)
  if m and not due:
    y, mo, da = int(m.group(1)), int(m.group(2)), int(m.group(3))
    hh, mm = m.group(4), m.group(5)
    d = datetime(y, mo, da, 9, 0, 0)
    if hh: d = d.replace(hour=int(hh), minute=int(mm or 0))
    due = d; text = text.replace(m.group(0), " ")

  # at hh:mm (today)
  m = re.search(r"\bat\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\b", text, flags=re.I)
  if m and not due:
    d = set_time(now, int(m.group(1)), int(m.group(2) or 0), m.group(3))
    due = d; text = text.replace(m.group(0), " ")

  cleaned = " ".join(text.split())
  return cleaned, due.isoformat() if due else None

def _parse_input(raw: str) -> Dict[str, Any]:
  text = raw.strip()
  looks_reminder = any(k in text.lower() for k in ["remind me", "tomorrow", "today", "next ", " at ", " in "])
  text = _strip_prefixes(text)
  cleaned, due = _extract_due(text)
  kind = "task" if (looks_reminder or due) else "memory"
  return {"kind": kind, "text": cleaned, "due": due}

def _notify_ntfy(title: str, body: str):
  if not NTFY_TOPIC:
    return
  try:
    url = f"{NTFY_SERVER}/{NTFY_TOPIC}"
    requests.post(url, data=body.encode("utf-8"), headers={
      "Title": title,
      "Tags": "bell",
      "Priority": "4",
    }, timeout=5)
  except Exception:
    pass

def _notifier_loop():
  while True:
    try:
      now_iso = datetime.utcnow().isoformat()
      due = storage.due_unnotified(now_iso)
      for t in due:
        _notify_ntfy("Reminder", t["title"])
        storage.set_notified(t["id"], now_iso)
    except Exception:
      pass
    time.sleep(30)