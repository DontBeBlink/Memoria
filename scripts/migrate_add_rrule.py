#!/usr/bin/env python3
import sqlite3
from pathlib import Path

DB = Path(__file__).resolve().parents[1] / 'server' / 'app.db'
print('DB path:', DB)
conn = sqlite3.connect(DB)
try:
    cols = [r[1] for r in conn.execute("PRAGMA table_info(tasks)").fetchall()]
    print('Existing columns:', cols)
    if 'rrule' not in cols:
        print('Adding rrule column...')
        conn.execute('ALTER TABLE tasks ADD COLUMN rrule TEXT')
        conn.commit()
        print('Added rrule column')
    else:
        print('rrule column already present')
finally:
    conn.close()
