#!/usr/bin/env python3
"""items.py - Black Desert item name <-> ID lookup (no prices).

  python3 -I items.py "Vell's Heart" 4998        # resolve exact names / IDs
  python3 -I items.py --search "Advice of Valks"  # names containing the text
  python3 -I items.py --lang fr "Coeur de Vell"   # French names (accents optional)
  python3 -I items.py --lang en,fr "Pierre noire" # translate: one name column per language

Exit codes: 0 ok; 2 some item NOT FOUND / unknown ID, or UNKNOWN LANGUAGE; 3 network blocked.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # repo root (works with python3 -I)
from bdo import items  # noqa: E402
from bdo.net import NetworkBlocked, blocked_message  # noqa: E402


def main():
    if hasattr(sys.stdout, "reconfigure"):  # item names in any script, even when piped on Windows
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="BDO item name <-> ID lookup")
    ap.add_argument("items", nargs="*", help="item names (quoted) or numeric IDs")
    ap.add_argument("--search", metavar="TEXT", help="list items whose name contains TEXT")
    ap.add_argument("--limit", type=int, default=50, help="max results for --search (default 50)")
    ap.add_argument("--lang", default="en", help="name language(s), comma-separated: en (default), fr, en,fr... "
                    "Names given are matched in any of them; output has one name column per language")
    ap.add_argument("--refresh-db", action="store_true", help="re-download the item list")
    a = ap.parse_args()
    if not a.items and not a.search:
        ap.error("give item names/IDs or --search TEXT")
    langs = items.parse_langs(a.lang)
    try:
        dbs = items.load_dbs(langs, a.refresh_db)
    except NetworkBlocked as e:
        print(blocked_message("api.arsha.io", e), file=sys.stderr)
        return 3
    except items.UnknownLanguage as e:
        print(items.unknown_language_message(e.args[0]), file=sys.stderr)
        return 2
    names = [items.names_by_id(db) for db in dbs]
    blank = "\t" * len(langs)
    failed = False
    print("\t".join(["id"] + (["name"] if len(langs) == 1 else [f"name_{l}" for l in langs]) + ["note"]))
    if a.search:
        hits, total = items.search_any(dbs, a.search, a.limit)
        for iid in hits:
            print("\t".join([str(iid)] + [n.get(iid, "") for n in names]))
        if total > len(hits):
            print(f"{blank}\t{total - len(hits)} more matches not shown (use --limit)")
    for q in a.items:
        found, problem = items.resolve_any(q, dbs)
        if problem:
            failed = True
            print(f"\t{q}{blank[1:]}\t{problem}")
            continue
        for iid in found:
            if iid in names[0]:
                note = f"SAME NAME, {len(found)} IDs" if len(found) > 1 else ""
                print("\t".join([str(iid)] + [n.get(iid, "") for n in names] + [note]).rstrip("\t"))
            else:
                failed = True
                print(f"{iid}{blank}\tUNKNOWN ID")
    return 2 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
