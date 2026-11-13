"""Item name <-> ID lookup, from Arsha's full item list.

Arsha's /util/db ignores any 'name' filter and always returns every item
(~71k, ~4 MB), so it is downloaded once, cached on disk for 7 days and
searched locally. Never print the whole list.
"""
import difflib
import json
import os
import time
import urllib.parse

from .net import get_json

API = "https://api.arsha.io"
CACHE_DIR = "/tmp/bdo_tools"
DB_MAX_AGE_S = 7 * 24 * 3600


def load_db(lang="en", refresh=False):
    """Return [{id, name, grade}, ...] for every item."""
    os.makedirs(CACHE_DIR, exist_ok=True)
    path = os.path.join(CACHE_DIR, f"db_{lang}.json")
    if not refresh and os.path.exists(path) and time.time() - os.path.getmtime(path) < DB_MAX_AGE_S:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    db = get_json(f"{API}/util/db?lang={urllib.parse.quote(lang)}")
    if not isinstance(db, list) or not db:
        raise RuntimeError("item database download returned no items")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(db, f)
    return db


def names_by_id(db):
    return {x["id"]: x["name"] for x in db}


def search(db, text, limit=200):
    """Items whose name contains `text` (case-insensitive), sorted by name."""
    t = text.lower()
    hits = sorted((x for x in db if t in x["name"].lower()), key=lambda x: x["name"])
    return hits[:limit], len(hits)


def resolve(item, db):
    """Return (ids, problem). Numeric string -> [that ID]. Name -> every ID with
    exactly that name (case-insensitive; the game reuses some names).
    If nothing matches: ([], 'NOT FOUND ... Similar: ...')."""
    if item.strip().isdigit():
        return [int(item)], None
    key = item.strip().lower()
    exact = [x["id"] for x in db if x["name"].lower() == key]
    if exact:
        return exact, None
    near = [x for x in db if key in x["name"].lower()][:8]
    if not near:  # typo-tolerant suggestions
        by_lower = {}
        for x in db:
            by_lower.setdefault(x["name"].lower(), x)
        near = [by_lower[n] for n in difflib.get_close_matches(key, list(by_lower), n=8, cutoff=0.6)]
    hint = "; ".join(f"{x['name']} (id {x['id']})" for x in near) or "no similar names"
    return [], f"NOT FOUND - no exact name match. Similar: {hint}"
