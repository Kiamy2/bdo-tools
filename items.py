#!/usr/bin/env python3
"""items.py - Black Desert item name <-> ID lookup (no prices).

  python3 -I items.py "Vell's Heart" 4998        # resolve exact names / IDs
  python3 -I items.py --search "Advice of Valks"  # names containing the text

Exit codes: 0 ok; 2 some item NOT FOUND / unknown ID; 3 network blocked.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # repo root (works with python3 -I)
from bdo import items  # noqa: E402
from bdo.net import NetworkBlocked, blocked_message  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description="BDO item name <-> ID lookup")
    ap.add_argument("items", nargs="*", help="exact item names (quoted) or numeric IDs")
    ap.add_argument("--search", metavar="TEXT", help="list items whose name contains TEXT")
    ap.add_argument("--limit", type=int, default=50, help="max results for --search (default 50)")
    ap.add_argument("--lang", default="en")
    ap.add_argument("--refresh-db", action="store_true", help="re-download the item list")
    a = ap.parse_args()
    if not a.items and not a.search:
        ap.error("give item names/IDs or --search TEXT")
    try:
        db = items.load_db(a.lang, a.refresh_db)
    except NetworkBlocked as e:
        print(blocked_message("api.arsha.io", e), file=sys.stderr)
        return 3
    names = items.names_by_id(db)
    failed = False
    print("id\tname\tnote")
    if a.search:
        hits, total = items.search(db, a.search, a.limit)
        for x in hits:
            print(f"{x['id']}\t{x['name']}")
        if total > len(hits):
            print(f"\t\t{total - len(hits)} more matches not shown (use --limit)")
    for q in a.items:
        found, problem = items.resolve(q, db)
        if problem:
            failed = True
            print(f"\t{q}\t{problem}")
            continue
        for iid in found:
            if iid in names:
                note = f"SAME NAME, {len(found)} IDs" if len(found) > 1 else ""
                print(f"{iid}\t{names[iid]}\t{note}".rstrip("\t"))
            else:
                failed = True
                print(f"{iid}\t\tUNKNOWN ID")
    return 2 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
