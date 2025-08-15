#!/usr/bin/env python3
"""
Migration script to add rrule column to tasks table for recurring tasks support.
"""

import os
import sqlite3
import sys

# Add server directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'server'))

DB_PATH = os.path.join(os.path.dirname(__file__), "server", "app.db")

def migrate_rrule():
    """Add rrule column to tasks table if it doesn't exist."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    # Check if rrule column already exists
    cur.execute("PRAGMA table_info(tasks)")
    columns = [row[1] for row in cur.fetchall()]
    
    if 'rrule' not in columns:
        print("Adding rrule column to tasks table...")
        cur.execute("ALTER TABLE tasks ADD COLUMN rrule TEXT")
        conn.commit()
        print("✓ rrule column added successfully")
    else:
        print("✓ rrule column already exists")
    
    conn.close()

if __name__ == "__main__":
    migrate_rrule()