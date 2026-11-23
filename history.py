"""Change log for the M4, kept in %APPDATA%\\XtrfyM4 as JSON lines plus the last profile the app saw."""
import json
import os
import time

DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "XtrfyM4")
LOG = os.path.join(DIR, "history.jsonl")
SNAPSHOT = os.path.join(DIR, "last-seen.m4")

SRC_MOUSE = "Mouse button"
SRC_APP = "This app"
SRC_RESTORE = "Restore"
SRC_OFFLINE = "While app was closed"


class History:
    def __init__(self):
        os.makedirs(DIR, exist_ok=True)

    def add(self, source, changes):
        if not changes:
            return []
        t = time.strftime("%Y-%m-%d %H:%M:%S")
        rows = [{"time": t, "source": source, "change": c} for c in changes]
        with open(LOG, "a", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        return rows

    def entries(self):
        try:
            with open(LOG, encoding="utf-8") as f:
                return [json.loads(line) for line in f if line.strip()]
        except (OSError, ValueError):
            return []

    def clear(self):
        try:
            os.remove(LOG)
        except FileNotFoundError:
            pass

    def last_seen(self):
        try:
            with open(SNAPSHOT, "rb") as f:
                return f.read()
        except OSError:
            return None

    def remember(self, mem):
        with open(SNAPSHOT, "wb") as f:
            f.write(mem)
