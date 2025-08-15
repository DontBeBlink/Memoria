import sqlite3
from typing import List, Optional, Any, Dict
import os
from datetime import datetime, timezone
from dateutil import rrule
from dateutil.parser import parse as parse_date
from dateutil.relativedelta import relativedelta

DB_PATH = os.path.join(os.path.dirname(__file__), "app.db")

def _connect():
  conn = sqlite3.connect(DB_PATH)
  conn.row_factory = sqlite3.Row
  return conn

def init_db():
  conn = _connect()
  cur = conn.cursor()
  cur.execute("""
  CREATE TABLE IF NOT EXISTS memories(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    text TEXT NOT NULL,
    created TEXT NOT NULL,
    tags TEXT DEFAULT ''
  )""")
  cur.execute("""
  CREATE TABLE IF NOT EXISTS tasks(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    due TEXT,
    done INTEGER NOT NULL DEFAULT 0,
    created TEXT NOT NULL,
    tags TEXT DEFAULT '',
    notified_at TEXT,
    rrule TEXT
  )""")
  conn.commit()
  # Ensure schema migration: add rrule column if it doesn't exist (for older DBs)
  cur.execute("PRAGMA table_info(tasks)")
  cols = [r[1] for r in cur.fetchall()]
  if 'rrule' not in cols:
    try:
      cur.execute("ALTER TABLE tasks ADD COLUMN rrule TEXT")
      conn.commit()
    except Exception:
      # If alter fails for any reason, ignore and continue; table may already be correct.
      pass

  conn.close()


def _normalize_due_to_utc(due: Optional[str]) -> Optional[str]:
  """Convert an ISO datetime (naive or with offset) to an ISO UTC string.
     If due is None or empty, returns None.
  """
  if not due:
    return None
  try:
    dt = datetime.fromisoformat(due)
  except Exception:
    return due

  # If naive, assume local timezone
  if dt.tzinfo is None:
    local_tz = datetime.now().astimezone().tzinfo
    dt = dt.replace(tzinfo=local_tz)

  # Convert to UTC and return ISO string
  return dt.astimezone(timezone.utc).isoformat()

def _tags_from(text: str) -> str:
  import re
  ats = re.findall(r'@\w+', text) or []
  hashes = re.findall(r'#\w+', text) or []
  tags = list(dict.fromkeys(ats + hashes))
  return " ".join(tags)

def add_memory(text: str) -> Dict[str, Any]:
  created = datetime.utcnow().isoformat()
  tags = _tags_from(text)
  conn = _connect()
  cur = conn.cursor()
  cur.execute("INSERT INTO memories(text, created, tags) VALUES (?, ?, ?)", (text, created, tags))
  mem_id = cur.lastrowid
  conn.commit()
  row = cur.execute("SELECT * FROM memories WHERE id=?", (mem_id,)).fetchone()
  conn.close()
  return dict(row)

def add_task(title: str, due: Optional[str], rrule: Optional[str] = None) -> Dict[str, Any]:
  created = datetime.utcnow().isoformat()
  tags = _tags_from(title)
  due_norm = _normalize_due_to_utc(due)
  conn = _connect()
  cur = conn.cursor()
  cur.execute("INSERT INTO tasks(title, due, done, created, tags, rrule) VALUES (?, ?, 0, ?, ?, ?)",
              (title, due_norm, created, tags, rrule))
  task_id = cur.lastrowid
  conn.commit()
  row = cur.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
  conn.close()
  return dict(row)

def list_memories(limit: int = 100, offset: int = 0, query: Optional[str] = None, tags: Optional[List[str]] = None, people: Optional[List[str]] = None):
  conn = _connect()
  
  # Build the SQL query based on search parameters
  base_sql = "SELECT * FROM memories"
  count_sql = "SELECT COUNT(*) FROM memories"
  params = []
  where_clauses = []
  
  # Add text search filter
  if query:
    where_clauses.append("(text LIKE ? OR tags LIKE ?)")
    search_term = f"%{query}%"
    params.extend([search_term, search_term])
  
  # Add tags filter (any of the specified tags)
  if tags:
    tag_conditions = []
    for tag in tags:
      # Ensure tag starts with # if it doesn't already
      tag_to_search = tag if tag.startswith('#') else f"#{tag}"
      tag_conditions.append("tags LIKE ?")
      params.append(f"%{tag_to_search}%")
    if tag_conditions:
      where_clauses.append(f"({' OR '.join(tag_conditions)})")
  
  # Add people filter (any of the specified people)
  if people:
    people_conditions = []
    for person in people:
      # Ensure person starts with @ if it doesn't already
      person_to_search = person if person.startswith('@') else f"@{person}"
      people_conditions.append("tags LIKE ?")
      params.append(f"%{person_to_search}%")
    if people_conditions:
      where_clauses.append(f"({' OR '.join(people_conditions)})")
  
  # Combine where clauses
  if where_clauses:
    where_clause = " WHERE " + " AND ".join(where_clauses)
    base_sql += where_clause
    count_sql += where_clause
  
  # Add ordering and pagination
  base_sql += " ORDER BY id DESC LIMIT ? OFFSET ?"
  params.extend([limit, offset])
  
  # Get the data
  rows = conn.execute(base_sql, params).fetchall()
  
  # Get the total count (for pagination)
  count_params = params[:-2]  # Remove limit and offset from count query
  total = conn.execute(count_sql, count_params).fetchone()[0]
  
  conn.close()
  
  return {
    "items": [dict(r) for r in rows],
    "total": total
  }

def _expand_recurring_task(task: Dict[str, Any], start_date: Optional[datetime], end_date: Optional[datetime]) -> List[Dict[str, Any]]:
  """Expand a recurring task into multiple instances based on its RRULE."""
  if not task.get('rrule') or not task.get('due'):
    return [task]
  
  try:
    # Parse the task's due date as the start of recurrence
    due_dt = parse_date(task['due'])
    
    # Ensure due_dt is timezone aware
    if due_dt.tzinfo is None:
      due_dt = due_dt.replace(tzinfo=timezone.utc)
    
    # Parse the RRULE
    rrule_obj = rrule.rrulestr(task['rrule'], dtstart=due_dt)
    
    # Set default date range if not provided
    if not start_date:
      start_date = datetime.now(timezone.utc)
    elif start_date.tzinfo is None:
      start_date = start_date.replace(tzinfo=timezone.utc)
      
    if not end_date:
      # Default to 6 months from start
      end_date = start_date + relativedelta(months=6)
    elif end_date.tzinfo is None:
      end_date = end_date.replace(tzinfo=timezone.utc)
    
    # Generate occurrences within the date range
    occurrences = []
    for occurrence in rrule_obj:
      # Ensure occurrence is timezone aware
      if occurrence.tzinfo is None:
        occurrence = occurrence.replace(tzinfo=timezone.utc)
        
      if occurrence > end_date:
        break
      if occurrence >= start_date:
        # Create a copy of the task with the new due date
        task_copy = task.copy()
        task_copy['due'] = occurrence.isoformat()
        # Add a suffix to the ID to make each occurrence unique
        task_copy['id'] = f"{task['id']}_r_{occurrence.strftime('%Y%m%d_%H%M%S')}"
        task_copy['is_recurring_instance'] = True
        task_copy['parent_task_id'] = task['id']
        occurrences.append(task_copy)
    
    return occurrences if occurrences else []
    
  except Exception as e:
    # If there's an error parsing the RRULE, return the original task
    print(f"Error expanding recurring task {task['id']}: {e}")
    return [task]


def list_tasks(open_only: bool = False, limit: int = 200, start: Optional[str] = None, end: Optional[str] = None):
  conn = _connect()
  
  # Build query with optional date range filtering
  conditions = []
  params = []
  
  if open_only:
    conditions.append("done=0")
  
  # For recurring tasks, we don't apply date filtering at the SQL level
  # We'll handle it after expanding recurring tasks
  where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""
  order_clause = " ORDER BY COALESCE(due, '9999') ASC, id DESC" if open_only else " ORDER BY id DESC"
  
  params.append(limit)
  query = f"SELECT * FROM tasks{where_clause}{order_clause} LIMIT ?"
  
  rows = conn.execute(query, params).fetchall()
  conn.close()
  
  # Convert to list of dicts
  tasks = [dict(r) for r in rows]
  
  # Parse date range for recurring task expansion
  start_date = None
  end_date = None
  if start:
    try:
      start_date = parse_date(start)
      if start_date.tzinfo is None:
        start_date = start_date.replace(tzinfo=timezone.utc)
    except:
      pass
  if end:
    try:
      end_date = parse_date(end)
      if end_date.tzinfo is None:
        end_date = end_date.replace(tzinfo=timezone.utc)
    except:
      pass
  
  # Expand recurring tasks and apply date filtering
  expanded_tasks = []
  for task in tasks:
    if task.get('rrule'):
      # Expand recurring task
      instances = _expand_recurring_task(task, start_date, end_date)
      for instance in instances:
        # Apply date range filtering to instances
        if start_date or end_date:
          instance_due = parse_date(instance['due']) if instance.get('due') else None
          if instance_due:
            # Ensure timezone awareness
            if instance_due.tzinfo is None:
              instance_due = instance_due.replace(tzinfo=timezone.utc)
            if start_date and instance_due < start_date:
              continue
            if end_date and instance_due > end_date:
              continue
        expanded_tasks.append(instance)
    else:
      # Non-recurring task - apply original date filtering
      if start or end:
        task_due = parse_date(task['due']) if task.get('due') else None
        if task_due:
          # Ensure timezone awareness
          if task_due.tzinfo is None:
            task_due = task_due.replace(tzinfo=timezone.utc)
          if start_date and task_due < start_date:
            continue
          if end_date and task_due > end_date:
            continue
      expanded_tasks.append(task)
  
  # Sort again after expansion
  if open_only:
    expanded_tasks.sort(key=lambda x: (x.get('due') or '9999', -int(str(x['id']).split('_')[0])))
  else:
    expanded_tasks.sort(key=lambda x: -int(str(x['id']).split('_')[0]))
  
  return expanded_tasks[:limit]

def mark_done(task_id: int, done: bool):
  conn = _connect()
  cur = conn.cursor()
  cur.execute("UPDATE tasks SET done=? WHERE id=?", (1 if done else 0, task_id))
  conn.commit()
  row = cur.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
  conn.close()
  return dict(row) if row else None

def due_unnotified(now_iso: str):
  conn = _connect()
  rows = conn.execute("""
    SELECT * FROM tasks
    WHERE done=0 AND due IS NOT NULL
      AND due <= ? AND (notified_at IS NULL)
  """, (now_iso,)).fetchall()
  conn.close()
  return [dict(r) for r in rows]

def set_notified(task_id: int, when_iso: str):
  conn = _connect()
  conn.execute("UPDATE tasks SET notified_at=? WHERE id=?", (when_iso, task_id))
  conn.commit()
  conn.close()

def import_memory(memory_data: Dict[str, Any], overwrite: bool = False) -> Dict[str, str]:
  """Import a memory with specific ID. Returns status dict."""
  conn = _connect()
  cur = conn.cursor()
  
  # Check if memory with this ID already exists
  existing = cur.execute("SELECT id FROM memories WHERE id=?", (memory_data['id'],)).fetchone()
  
  if existing and not overwrite:
    conn.close()
    return {"status": "skipped", "reason": "duplicate_id"}
  
  try:
    if existing and overwrite:
      # Update existing memory
      cur.execute("""UPDATE memories 
                     SET text=?, created=?, tags=? 
                     WHERE id=?""", 
                  (memory_data['text'], memory_data['created'], 
                   memory_data.get('tags', ''), memory_data['id']))
      conn.commit()
      conn.close()
      return {"status": "updated"}
    else:
      # Insert new memory with specific ID
      cur.execute("""INSERT INTO memories(id, text, created, tags) 
                     VALUES (?, ?, ?, ?)""",
                  (memory_data['id'], memory_data['text'], 
                   memory_data['created'], memory_data.get('tags', '')))
      conn.commit()
      conn.close()
      return {"status": "inserted"}
  except Exception as e:
    conn.close()
    return {"status": "failed", "reason": str(e)}

def import_task(task_data: Dict[str, Any], overwrite: bool = False) -> Dict[str, str]:
  """Import a task with specific ID. Returns status dict."""
  conn = _connect()
  cur = conn.cursor()
  
  # Check if task with this ID already exists
  existing = cur.execute("SELECT id FROM tasks WHERE id=?", (task_data['id'],)).fetchone()
  
  if existing and not overwrite:
    conn.close()
    return {"status": "skipped", "reason": "duplicate_id"}
  
  try:
    if existing and overwrite:
      # Update existing task
      due_norm = _normalize_due_to_utc(task_data.get('due'))
      cur.execute("""UPDATE tasks 
                     SET title=?, due=?, done=?, created=?, tags=?, notified_at=?, rrule=?
                     WHERE id=?""", 
                  (task_data['title'], due_norm, 
                   task_data.get('done', 0), task_data['created'],
                   task_data.get('tags', ''), task_data.get('notified_at'),
                   task_data.get('rrule'),
                   task_data['id']))
      conn.commit()
      conn.close()
      return {"status": "updated"}
    else:
      # Insert new task with specific ID
      due_norm = _normalize_due_to_utc(task_data.get('due'))
      cur.execute("""INSERT INTO tasks(id, title, due, done, created, tags, notified_at, rrule) 
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                  (task_data['id'], task_data['title'], due_norm,
                   task_data.get('done', 0), task_data['created'],
                   task_data.get('tags', ''), task_data.get('notified_at'),
                   task_data.get('rrule')))
      conn.commit()
      conn.close()
      return {"status": "inserted"}
  except Exception as e:
    conn.close()
    return {"status": "failed", "reason": str(e)}

def get_all_memories():
  """Get all memories without limit for export."""
  conn = _connect()
  rows = conn.execute("SELECT * FROM memories ORDER BY id ASC").fetchall()
  conn.close()
  return [dict(r) for r in rows]

def get_all_tasks():
  """Get all tasks without limit for export."""
  conn = _connect()
  rows = conn.execute("SELECT * FROM tasks ORDER BY id ASC").fetchall()
  conn.close()
  return [dict(r) for r in rows]

def delete_memory(memory_id: int) -> bool:
  conn = _connect()
  cur = conn.cursor()
  cur.execute("DELETE FROM memories WHERE id=?", (memory_id,))
  deleted = cur.rowcount > 0
  conn.commit()
  conn.close()
  return deleted

def delete_task(task_id: int) -> bool:
  conn = _connect()
  cur = conn.cursor()
  cur.execute("DELETE FROM tasks WHERE id=?", (task_id,))
  deleted = cur.rowcount > 0
  conn.commit()
  conn.close()
  return deleted

def update_memory(memory_id: int, **fields) -> Optional[Dict[str, Any]]:
  if not fields:
    return None
  
  conn = _connect()
  cur = conn.cursor()
  
  # Build dynamic update query
  set_clauses = []
  values = []
  for field, value in fields.items():
    if field == "text":
      set_clauses.append("text = ?")
      values.append(value)
      # Update tags when text changes
      set_clauses.append("tags = ?")
      values.append(_tags_from(value))
  
  if not set_clauses:
    conn.close()
    return None
  
  values.append(memory_id)
  query = f"UPDATE memories SET {', '.join(set_clauses)} WHERE id = ?"
  cur.execute(query, values)
  conn.commit()
  
  if cur.rowcount == 0:
    conn.close()
    return None
  
  row = cur.execute("SELECT * FROM memories WHERE id=?", (memory_id,)).fetchone()
  conn.close()
  return dict(row) if row else None

def update_task(task_id: int, **fields) -> Optional[Dict[str, Any]]:
  if not fields:
    return None
  
  conn = _connect()
  cur = conn.cursor()
  
  # Build dynamic update query
  set_clauses = []
  values = []
  for field, value in fields.items():
    if field == "title":
      set_clauses.append("title = ?")
      values.append(value)
      # Update tags when title changes
      set_clauses.append("tags = ?")
      values.append(_tags_from(value))
    elif field == "due":
      set_clauses.append("due = ?")
      values.append(_normalize_due_to_utc(value))
    elif field == "done":
      set_clauses.append("done = ?")
      values.append(1 if value else 0)
    elif field == "rrule":
      set_clauses.append("rrule = ?")
      values.append(value)
  
  if not set_clauses:
    conn.close()
    return None
  
  values.append(task_id)
  query = f"UPDATE tasks SET {', '.join(set_clauses)} WHERE id = ?"
  cur.execute(query, values)
  conn.commit()
  
  if cur.rowcount == 0:
    conn.close()
    return None
  
  row = cur.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
  conn.close()
  return dict(row) if row else None