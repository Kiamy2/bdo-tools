"""Item name <-> ID lookup, from Arsha's full item list, in one or more languages.

Arsha's /util/db ignores any 'name' filter and always returns every item
(~71k, ~4 MB per language), so it is downloaded once per language, cached on
disk for 7 days and searched locally. Never print the whole list.

Names match case-insensitively; if nothing matches exactly, they also match
ignoring accents, 'oe'/'ae' vs 'œ'/'æ', typographic apostrophes and extra spaces
(see fold()), and then ignoring all spaces and punctuation (see compact()).
"""
import difflib
import json
import os
import time
import unicodedata
import urllib.parse

from .net import get_json

API = "https://api.arsha.io"
CACHE_DIR = "/tmp/bdo_tools"
DB_MAX_AGE_S = 7 * 24 * 3600
# Codes Arsha accepted when checked (2026-11-16). Others may exist: Arsha is the judge.
KNOWN_LANGS = ["en", "de", "fr", "ru", "es", "sp", "pt", "jp", "kr", "cn", "tw", "th", "tr", "id"]


class UnknownLanguage(ValueError):
    """Arsha rejected the language code."""


def parse_langs(text):
    """'en,fr' -> ['en', 'fr'] (lower-case, no duplicates, order kept)."""
    langs = [p.strip().lower() for p in (text or "en").split(",") if p.strip()]
    return list(dict.fromkeys(langs)) or ["en"]


def load_db(lang="en", refresh=False):
    """Return [{id, name, grade}, ...] for every item. Raises UnknownLanguage."""
    os.makedirs(CACHE_DIR, exist_ok=True)
    path = os.path.join(CACHE_DIR, f"db_{lang}.json")
    if not refresh and os.path.exists(path) and time.time() - os.path.getmtime(path) < DB_MAX_AGE_S:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    try:
        db = get_json(f"{API}/util/db?lang={urllib.parse.quote(lang)}")
    except RuntimeError as e:
        if "Invalid locale" in str(e):
            raise UnknownLanguage(lang) from None
        raise
    if not isinstance(db, list) or not db:
        raise RuntimeError("item database download returned no items")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(db, f)
    return db


def load_dbs(langs, refresh=False):
    """[db, ...] in the order of `langs`."""
    return [load_db(lang, refresh) for lang in langs]


def unknown_language_message(lang):
    return (f"UNKNOWN LANGUAGE: Arsha rejected --lang {lang!r}. "
            f"Codes known to work: {', '.join(KNOWN_LANGS)}.")


def names_by_id(db):
    return {x["id"]: x["name"] for x in db}


_SUBS = str.maketrans({"œ": "oe", "Œ": "oe", "æ": "ae", "Æ": "ae", "ß": "ss",
                       "’": "'", "‘": "'", " ": " ", " ": " "})


def fold(s):
    """Loose matching key: lower-case, no accents on Latin letters, ligatures
    spelled out, straight apostrophes, single spaces. 'Cœur  de Véll' -> 'coeur de vell'.
    Marks on other scripts (Japanese dakuten, Cyrillic й) are kept."""
    out = []
    for c in unicodedata.normalize("NFKD", s.translate(_SUBS)):
        if unicodedata.combining(c) and out and ord(out[-1]) < 0x0250:
            continue
        out.append(c)
    return " ".join(unicodedata.normalize("NFC", "".join(out)).lower().split())


def compact(s):
    """Loosest matching key: fold() without spaces or punctuation. "Vells Heart" == "Vell's Heart"."""
    return "".join(c for c in fold(s) if c.isalnum())


_INDEX = {}


def _index(db):
    """(lower name -> [ids], folded -> [ids], compacted -> [ids], [(folded name, item)], {id: name})
    for a db, built once."""
    key = id(db)
    if key not in _INDEX:
        lower, folded, compacted, pairs = {}, {}, {}, []
        for x in db:
            f = fold(x["name"])
            c = "".join(ch for ch in f if ch.isalnum())
            lower.setdefault(x["name"].lower(), []).append(x["id"])
            folded.setdefault(f, []).append(x["id"])
            if c:
                compacted.setdefault(c, []).append(x["id"])
            pairs.append((f, x))
        _INDEX[key] = (db, lower, folded, compacted, pairs, names_by_id(db))  # keep db referenced so id() stays unique
    return _INDEX[key][1:]


def search(db, text, limit=200):
    """Items whose name contains `text` (case- and accent-insensitive), sorted by name."""
    t = fold(text)
    hits = sorted((x for f, x in _index(db)[3] if t in f), key=lambda x: x["name"])
    return hits[:limit], len(hits)


def search_any(dbs, text, limit=200):
    """IDs whose name contains `text` in any of the dbs, sorted by name in the first db."""
    t = fold(text)
    ids = {x["id"] for db in dbs for f, x in _index(db)[3] if t in f}
    first = names_by_id(dbs[0])
    hits = sorted(ids, key=lambda i: (first.get(i, ""), i))
    return hits[:limit], len(hits)


def resolve_any(item, dbs):
    """Like resolve(), but a name may be in the language of any of the dbs."""
    if item.strip().isdigit():
        return [int(item)], None
    key, fkey = item.strip().lower(), fold(item)
    keys = (key, fkey, "".join(c for c in fkey if c.isalnum()))
    for tier in (0, 1, 2):  # exact (case-insensitive), then folded, then compacted
        hits = [(i, _index(db)[4][i]) for db in dbs for i in _index(db)[tier].get(keys[tier], [])] if keys[tier] else []
        if not hits:
            continue
        uniq = list(dict.fromkeys(hits))
        if tier > 0 and len({n.lower() for _, n in uniq}) > 1:  # loose match hit different names
            return [], "NOT FOUND - no exact name match. Similar: " + "; ".join(f"{n} (id {i})" for i, n in uniq[:8])
        return list(dict.fromkeys(i for i, _ in uniq)), None
    pairs = [p for db in dbs for p in _index(db)[3]]
    words = fkey.split()
    near = sorted((x for f, x in pairs if fkey in f), key=lambda x: len(x["name"]))
    if not near:  # every word, any order (French and English word orders differ)
        near = sorted((x for f, x in pairs if all(w in f for w in words)), key=lambda x: len(x["name"]))
    if not near:  # typo-tolerant suggestions
        by_fold = {}
        for f, x in pairs:
            by_fold.setdefault(f, x)
        near = [by_fold[n] for n in difflib.get_close_matches(fkey, list(by_fold), n=8, cutoff=0.6)]
    seen, hint = set(), []
    for x in near:
        if x["id"] not in seen and len(hint) < 8:
            seen.add(x["id"])
            hint.append(f"{x['name']} (id {x['id']})")
    return [], f"NOT FOUND - no exact name match. Similar: {'; '.join(hint) or 'no similar names'}"


def resolve(item, db):
    """Return (ids, problem). Numeric string -> [that ID]. Name -> every ID with
    exactly that name (case-insensitive; the game reuses some names), else the IDs
    whose name matches ignoring accents etc. (fold()), else ignoring spaces and
    punctuation too (compact()). A loose match that hits different names is refused.
    If nothing matches: ([], 'NOT FOUND ... Similar: ...')."""
    return resolve_any(item, [db])
