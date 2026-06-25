"""
Daily limits tracking — in-memory for ephemeral GitHub Actions runners.

Since GitHub Actions runners are ephemeral (fresh filesystem each run),
file-based limit tracking (temp/daily_limits.json) doesn't persist between runs.
We use an in-memory counter instead. Limits are now PER-RUN, not per-day.

If you need persistent daily tracking, commit daily_limits.json to git or
use a cloud-based counter (e.g., GitHub Actions cache, or Google Drive).
"""
import os
import json
from datetime import datetime

LIMITS_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "temp", "daily_limits.json")

MAX_DOWNLOADS = 5
MAX_EDITS = 5
MAX_UPLOADS = 5

# In-memory counter (resets each process invocation — perfect for GitHub Actions)
_in_memory = {
    "downloads": 0,
    "edits": 0,
    "uploads": 0,
}


def _load_limits():
    """Load limits. Tries file first (for local runs), falls back to in-memory."""
    today = datetime.utcnow().date().isoformat()

    # Try file-based (works for local persistent runs)
    if os.path.exists(LIMITS_FILE):
        try:
            with open(LIMITS_FILE, "r") as f:
                data = json.load(f)
                if data.get("date") == today:
                    # Merge file counts with in-memory counts (take max to avoid double-counting)
                    return {
                        "date": today,
                        "downloads": max(data.get("downloads", 0), _in_memory["downloads"]),
                        "edits": max(data.get("edits", 0), _in_memory["edits"]),
                        "uploads": max(data.get("uploads", 0), _in_memory["uploads"]),
                    }
        except Exception as e:
            print(f"Error loading limits: {e}")

    # Fallback: in-memory for ephemeral runners
    return {
        "date": today,
        "downloads": _in_memory["downloads"],
        "edits": _in_memory["edits"],
        "uploads": _in_memory["uploads"],
    }


def _save_limits(data):
    """Save limits to file if possible (won't fail on ephemeral runners)."""
    _in_memory["downloads"] = data["downloads"]
    _in_memory["edits"] = data["edits"]
    _in_memory["uploads"] = data["uploads"]

    try:
        os.makedirs(os.path.dirname(LIMITS_FILE), exist_ok=True)
        with open(LIMITS_FILE, "w") as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        # File save is best-effort — in-memory always works
        pass


# Downloader API
def can_download() -> bool:
    data = _load_limits()
    return data.get("downloads", 0) < MAX_DOWNLOADS


def increment_download():
    data = _load_limits()
    data["downloads"] = data.get("downloads", 0) + 1
    _save_limits(data)
    print(f"Daily Downloads count updated: {data['downloads']}/{MAX_DOWNLOADS}")


# Editor API
def can_edit() -> bool:
    data = _load_limits()
    return data.get("edits", 0) < MAX_EDITS


def increment_edit():
    data = _load_limits()
    data["edits"] = data.get("edits", 0) + 1
    _save_limits(data)
    print(f"Daily Edits count updated: {data['edits']}/{MAX_EDITS}")


# Uploader API
def can_upload() -> bool:
    data = _load_limits()
    return data.get("uploads", 0) < MAX_UPLOADS


def increment_upload():
    data = _load_limits()
    data["uploads"] = data.get("uploads", 0) + 1
    _save_limits(data)
    print(f"Daily Uploads count updated: {data['uploads']}/{MAX_UPLOADS}")
