import sqlite3
from typing import List, Optional, Any, Dict
import os
from datetime import datetime

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
    notified_at TEXT
  )""")
  conn.commit()
  conn.close()

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

def add_task(title: str, due: Optional[str]) -> Dict[str, Any]:
  created = datetime.utcnow().isoformat()
  tags = _tags_from(title)
  conn = _connect()
  cur = conn.cursor()
  cur.execute("INSERT INTO tasks(title, due, done, created, tags) VALUES (?, ?, 0, ?, ?)",
              (title, due, created, tags))
  task_id = cur.lastrowid
  conn.commit()
  row = cur.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
  conn.close()
  return dict(row)

def list_memories(limit: int = 100, offset: int = 0, query: Optional[str] = None):
  conn = _connect()
  
  # Build the SQL query based on search parameters
  base_sql = "SELECT * FROM memories"
  count_sql = "SELECT COUNT(*) FROM memories"
  params = []
  
  if query:
    where_clause = " WHERE text LIKE ? OR tags LIKE ?"
    base_sql += where_clause
    count_sql += where_clause
    search_term = f"%{query}%"
    params.extend([search_term, search_term])
  
  # Add ordering and pagination
  base_sql += " ORDER BY id DESC LIMIT ? OFFSET ?"
  params.extend([limit, offset])
  
  # Get the data
  rows = conn.execute(base_sql, params).fetchall()
  
  # Get the total count (for pagination)
  count_params = params[:-2] if query else []  # Remove limit and offset from count query
  total = conn.execute(count_sql, count_params).fetchone()[0]
  
  conn.close()
  
  return {
    "items": [dict(r) for r in rows],
    "total": total
  }

def list_tasks(open_only: bool = False, limit: int = 200):
  conn = _connect()
  if open_only:
    rows = conn.execute("SELECT * FROM tasks WHERE done=0 ORDER BY COALESCE(due, '9999') ASC, id DESC LIMIT ?", (limit,)).fetchall()
  else:
    rows = conn.execute("SELECT * FROM tasks ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
  conn.close()
  return [dict(r) for r in rows]

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
      values.append(value)
    elif field == "done":
      set_clauses.append("done = ?")
      values.append(1 if value else 0)
  
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