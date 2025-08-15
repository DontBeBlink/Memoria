# migrate_due.py
from server import storage
from datetime import datetime, timezone

def normalize_iso_to_utc(iso_str: str) -> str:
    dt = datetime.fromisoformat(iso_str)
    if dt.tzinfo is None:
        # assume local timezone for naive datetimes
        local_tz = datetime.now().astimezone().tzinfo
        dt = dt.replace(tzinfo=local_tz)
    return dt.astimezone(timezone.utc).isoformat()

tasks = storage.get_all_tasks()
updated = 0

for t in tasks:
    due = t.get("due")
    if not due:
        continue
    # Skip already-offset strings (quick heuristic: contains '+' or 'Z' or timezone info)
    if '+' in due or due.endswith('Z') or (len(due) > 19 and (due[19] in ['+','-'])):
        continue
    try:
        new_due = normalize_iso_to_utc(due)
        # Use the storage update method so tags/other logic is preserved
        storage.update_task(t["id"], due=new_due)
        updated += 1
    except Exception as e:
        print(f"Skipping id={t['id']} due={due} error={e}")

print(f"Migration done. Updated {updated} tasks.")