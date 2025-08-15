import os
import threading
import time
import tempfile
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Tuple

from fastapi import FastAPI, Depends, HTTPException, Header, UploadFile, File, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
import requests

from . import storage
from .schemas import MemoryIn, MemoryPatch, TaskIn, TaskPatch, CaptureIn, TranscriptionResponse
import json

load_dotenv()

AUTH_TOKEN = os.getenv("AUTH_TOKEN", "")
NTFY_TOPIC = os.getenv("NTFY_TOPIC", "")
NTFY_SERVER = os.getenv("NTFY_SERVER", "https://ntfy.sh").rstrip("/")
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "small.en")
TRANSCRIPTION_LANGUAGE = os.getenv("TRANSCRIPTION_LANGUAGE", "en")
WHISPER_DEVICE = os.getenv("WHISPER_DEVICE", "cpu")
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
def get_memories(q: Optional[str] = None, tags: Optional[str] = None, people: Optional[str] = None, limit: Optional[int] = None, offset: Optional[int] = None, auth=Depends(require_auth)):
  # Determine if we're using new functionality (pagination/search/filters)
  using_new_features = q is not None or limit is not None or offset is not None or tags is not None or people is not None
  
  # Set defaults
  actual_limit = limit if limit is not None else (50 if using_new_features else 100)
  actual_offset = offset if offset is not None else 0
  
  # Parse CSV parameters
  tags_list = [tag.strip() for tag in tags.split(',')] if tags else None
  people_list = [person.strip() for person in people.split(',')] if people else None
  
  result = storage.list_memories(limit=actual_limit, offset=actual_offset, query=q, tags=tags_list, people=people_list)
  
  # For backward compatibility, if no new parameters are provided, return just the items
  if not using_new_features:
    return result["items"]
  
  return result

@app.post("/memories")
def post_memory(mem: MemoryIn, auth=Depends(require_auth)):
  return storage.add_memory(mem.text)

@app.patch("/memories/{memory_id}")
def patch_memory(memory_id: int, mem: MemoryPatch, auth=Depends(require_auth)):
  # Prepare fields to update
  fields = {}
  if mem.text is not None:
    fields["text"] = mem.text
  
  if not fields:
    raise HTTPException(status_code=400, detail="No fields to update")
  
  result = storage.update_memory(memory_id, **fields)
  if not result:
    raise HTTPException(status_code=404, detail="Memory not found")
  
  return result

@app.delete("/memories/{memory_id}", status_code=204)
def delete_memory(memory_id: int, auth=Depends(require_auth)):
  deleted = storage.delete_memory(memory_id)
  if not deleted:
    raise HTTPException(status_code=404, detail="Not found")
  return None

@app.get("/tasks")
def get_tasks(open_only: bool = False, start: Optional[str] = None, end: Optional[str] = None, auth=Depends(require_auth)):
  return storage.list_tasks(open_only=open_only, start=start, end=end)

@app.post("/tasks")
def post_task(task: TaskIn, auth=Depends(require_auth)):
  # Extract due date from title if not explicitly provided
  due = task.due
  if not due:
    cleaned_title, extracted_due = _extract_due(task.title)
    if extracted_due:
      due = extracted_due
      # Use cleaned title without date information
      return storage.add_task(cleaned_title, due)
  
  return storage.add_task(task.title, due)

@app.patch("/tasks/{task_id}")
def patch_task(task_id: int, task: TaskPatch, auth=Depends(require_auth)):
  # Prepare fields to update
  fields = {}
  if task.title is not None:
    fields["title"] = task.title
  if task.due is not None:
    fields["due"] = task.due
  if task.done is not None:
    fields["done"] = task.done
  
  if not fields:
    raise HTTPException(status_code=400, detail="No fields to update")
  
  result = storage.update_task(task_id, **fields)
  if not result:
    raise HTTPException(status_code=404, detail="Task not found")
  
  return result

@app.delete("/tasks/{task_id}", status_code=204)
def delete_task(task_id: int, auth=Depends(require_auth)):
  deleted = storage.delete_task(task_id)
  if not deleted:
    raise HTTPException(status_code=404, detail="Not found")
  return None

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

@app.post("/transcribe", response_model=TranscriptionResponse)
async def transcribe_audio(audio: UploadFile = File(...), auth=Depends(require_auth)):
    """Transcribe audio file using faster-whisper"""
    # Check file type
    if not audio.content_type or not audio.content_type.startswith('audio/'):
        raise HTTPException(status_code=400, detail="File must be an audio file")
    
    try:
        # Import here to allow server to start even if faster-whisper isn't available
        from faster_whisper import WhisperModel
        
        # Create a temporary file to save the uploaded audio
        with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as tmp_file:
            content = await audio.read()
            tmp_file.write(content)
            tmp_file_path = tmp_file.name
        
        try:
            # Initialize Whisper model (this will be cached)
            if not hasattr(transcribe_audio, '_whisper_model'):
                try:
                    transcribe_audio._whisper_model = WhisperModel(
                        WHISPER_MODEL, 
                        device=WHISPER_DEVICE, 
                        compute_type="auto",
                        local_files_only=False  # Allow downloading models
                    )
                except Exception as model_error:
                    # Provide helpful error message if model can't be loaded
                    error_msg = str(model_error)
                    if "internet connection" in error_msg.lower() or "network" in error_msg.lower():
                        raise HTTPException(status_code=500, detail="Cannot download Whisper model. Please check internet connection and try again.")
                    elif "local_files_only" in error_msg:
                        raise HTTPException(status_code=500, detail="Whisper model not found. Please ensure internet connection for first-time model download.")
                    else:
                        raise HTTPException(status_code=500, detail=f"Failed to initialize Whisper model: {error_msg}")
            
            model = transcribe_audio._whisper_model
            
            # Transcribe the audio
            segments, info = model.transcribe(
                tmp_file_path, 
                language=TRANSCRIPTION_LANGUAGE if TRANSCRIPTION_LANGUAGE != 'auto' else None,
                vad_filter=True,
                vad_parameters=dict(min_silence_duration_ms=300)
            )
            
            # Extract text from segments
            text = " ".join(seg.text.strip() for seg in segments).strip()
            
            if not text:
                raise HTTPException(status_code=400, detail="No speech detected in audio")
                
            return TranscriptionResponse(text=text)
            
        finally:
            # Clean up the temporary file
            if os.path.exists(tmp_file_path):
                os.unlink(tmp_file_path)
            
    except ImportError:
        raise HTTPException(status_code=500, detail="Speech recognition not available. Install voice dependencies with: pip install -r requirements-voice.txt")
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Transcription failed: {str(e)}")

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
  m = re.search(r"\bin\s*(\d{1,3})\s*(minutes?|mins?|m|hours?|hrs?|h|days?|d)\b", text, flags=re.I)
  if m and not due:
    num = int(m.group(1)); unit = m.group(2).lower()
    d = now
    if unit.startswith("min") or unit == "m": d += timedelta(minutes=num)
    elif unit.startswith("hour") or unit.startswith("hr") or unit == "h": d += timedelta(hours=num)
    elif unit.startswith("day") or unit == "d": d += timedelta(days=num)
    due = d; text = text.replace(m.group(0), " ")

  # tomorrow [at time] or tomorrow [morning/afternoon/evening/night]
  m = re.search(r"\btomorrow(?:\s+(?:at\s+)?(\d{1,2})(?::(\d{2}))?\s*(am|pm)?|\s+(morning|afternoon|evening|night))?\b", text, flags=re.I)
  if m and not due:
    d = now + timedelta(days=1)
    if m.group(1):  # specific time like "tomorrow at 3pm"
      d = set_time(d, int(m.group(1)), int(m.group(2) or 0), m.group(3))
    elif m.group(4):  # time of day like "tomorrow evening"
      time_of_day = m.group(4).lower()
      if time_of_day == "morning": d = set_time(d, 9, 0, None)
      elif time_of_day == "afternoon": d = set_time(d, 14, 0, None)
      elif time_of_day == "evening": d = set_time(d, 18, 0, None)
      elif time_of_day == "night": d = set_time(d, 21, 0, None)
    else:
      d = set_time(d, 9, 0, None)
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

  # weekday with time (e.g., "Mon 9a", "Tuesday 3:30pm")
  m = re.search(r"\b(sun|mon|tue|wed|thu|fri|sat|sunday|monday|tuesday|wednesday|thursday|friday|saturday)(?:day)?\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm|a|p)?\b", text, flags=re.I)
  if m and not due:
    wd_map = {'sun':6,'mon':0,'tue':1,'wed':2,'thu':3,'fri':4,'sat':5,
              'sunday':6,'monday':0,'tuesday':1,'wednesday':2,'thursday':3,'friday':4,'saturday':5}
    weekday_str = m.group(1).lower()
    target = wd_map[weekday_str]
    
    # Calculate days until target weekday
    delta = (target - now.weekday()) % 7
    if delta == 0:  # If it's the same weekday, assume next week unless time is in the future
      time_hour = int(m.group(2))
      ap = m.group(4)
      if ap and ap.lower() in ['pm', 'p'] and time_hour < 12: time_hour += 12
      if ap and ap.lower() in ['am', 'a'] and time_hour == 12: time_hour = 0
      
      if time_hour < now.hour or (time_hour == now.hour and int(m.group(3) or 0) <= now.minute):
        delta = 7  # Next week
    
    d = now + timedelta(days=delta)
    d = set_time(d, int(m.group(2)), int(m.group(3) or 0), m.group(4))
    due = d; text = text.replace(m.group(0), " ")

  # on [Month] [Day][st/nd/rd/th] [time] (e.g., "September 1st 11am", "October 15th at 2pm")
  m = re.search(r"\bon\s+(january|february|march|april|may|june|july|august|september|october|november|december)\s+(\d{1,2})(?:st|nd|rd|th)?(?:\s+(?:at\s+)?(\d{1,2})(?::(\d{2}))?\s*(am|pm|a|p)?)?\b", text, flags=re.I)
  if m and not due:
    month_map = {'january':1,'february':2,'march':3,'april':4,'may':5,'june':6,
                 'july':7,'august':8,'september':9,'october':10,'november':11,'december':12}
    month_name = m.group(1).lower()
    mo = month_map[month_name]
    da = int(m.group(2))
    
    # Determine year - use current year if month hasn't passed, otherwise next year
    current_year = now.year
    d = datetime(current_year, mo, da, 9, 0, 0)
    if d < now.replace(hour=0, minute=0, second=0, microsecond=0):
      d = d.replace(year=current_year + 1)
    
    # Handle time if provided
    if m.group(3):
      d = set_time(d, int(m.group(3)), int(m.group(4) or 0), m.group(5))
    
    due = d; text = text.replace(m.group(0), " ")

  # [Month] [Day][st/nd/rd/th] [time] (without "on", e.g., "September 1st 11am")
  m = re.search(r"\b(january|february|march|april|may|june|july|august|september|october|november|december)\s+(\d{1,2})(?:st|nd|rd|th)?(?:\s+(?:at\s+)?(\d{1,2})(?::(\d{2}))?\s*(am|pm|a|p)?)?\b", text, flags=re.I)
  if m and not due:
    month_map = {'january':1,'february':2,'march':3,'april':4,'may':5,'june':6,
                 'july':7,'august':8,'september':9,'october':10,'november':11,'december':12}
    month_name = m.group(1).lower()
    mo = month_map[month_name]
    da = int(m.group(2))
    
    # Determine year - use current year if month hasn't passed, otherwise next year
    current_year = now.year
    d = datetime(current_year, mo, da, 9, 0, 0)
    if d < now.replace(hour=0, minute=0, second=0, microsecond=0):
      d = d.replace(year=current_year + 1)
    
    # Handle time if provided
    if m.group(3):
      d = set_time(d, int(m.group(3)), int(m.group(4) or 0), m.group(5))
    
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