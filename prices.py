#!/usr/bin/env python3
"""prices.py - Black Desert Central Market prices (Arsha.io), default region NA.

  python3 -I prices.py "Vell's Heart" "Kabua's Artifact" 4998
  python3 -I prices.py --tax "Sharp Black Crystal Shard"   # + after_tax column (Value Pack)
  python3 -I prices.py --latest "Vell's Heart"            # most recent sale, any age
  python3 -I prices.py --avg 30 "Vell's Heart"            # 30-day average
  python3 -I prices.py --details "Vell's Heart"           # + base/max/last sale/stock/trades

Default price: last sale if < 24 h old, else 7-day average, else base price (flagged).
Exit codes: 0 ok; 2 some rows NOT FOUND / UNKNOWN ID / FETCH FAILED; 3 network blocked.
"""
import argparse
import datetime as dt
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # repo root (works with python3 -I)
from bdo import items, market  # noqa: E402
from bdo.net import NetworkBlocked, blocked_message  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description="BDO Central Market prices (Arsha.io)")
    ap.add_argument("items", nargs="+", help="exact item names (quoted) or numeric IDs")
    ap.add_argument("--region", default="na", help="na (default), eu, sea, mena, kr, ru, jp, th, tw, sa, console_na, console_eu, console_asia")
    ap.add_argument("--lang", default="en")
    ap.add_argument("--sid", type=int, default=None, help="gear: only this enhancement band (0 = base)")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--latest", action="store_true", help="price = most recent sale, whatever its age")
    g.add_argument("--avg", type=int, metavar="DAYS", help="price = average of the last DAYS daily prices (1-90)")
    ap.add_argument("--fallback-days", type=int, default=7, help="days averaged when the last sale is over 24 h old (default 7)")
    ap.add_argument("--tax", action="store_true", help="add after_tax column (seller keeps 84.5%% with Value Pack)")
    ap.add_argument("--no-vp", action="store_true", help="with --tax: no Value Pack (seller keeps 65%%)")
    ap.add_argument("--details", action="store_true", help="add base/max price, last sale, stock, trades")
    ap.add_argument("--json", action="store_true", help="JSON output")
    ap.add_argument("--refresh-db", action="store_true", help="re-download the item list")
    a = ap.parse_args()
    if a.avg is not None and not 1 <= a.avg <= 90:
        ap.error("--avg must be between 1 and 90")
    try:
        return run(a)
    except NetworkBlocked as e:
        print(blocked_message("api.arsha.io", e), file=sys.stderr)
        return 3


def run(a):
    region = a.region.lower()
    db = items.load_db(a.lang, a.refresh_db) if any(not s.strip().isdigit() for s in a.items) else []
    names = items.names_by_id(db)
    keep = market.TAX_NO_VP if a.no_vp else market.TAX_VP
    mode = "latest" if a.latest else ("avg" if a.avg else "auto")

    resolved = [(q, *items.resolve(q, db)) for q in a.items]
    ids = [i for _, found, _ in resolved for i in found if i not in market.FIXED_VALUES]
    prices, errors = market.get_prices(ids, region, a.lang, mode, a.avg, a.fallback_days, a.sid)

    def row(q, iid, e):
        if e.get("name") == "NONAME":
            return {"query": q, "id": iid, "note": "UNKNOWN ID - no item with this ID"}
        r = {"query": q, "id": iid, "sid": e.get("sid", 0), "name": e.get("name") or names.get(iid, ""), "note": ""}
        if market.is_untradeable(e):
            r["note"] = "NOT ON MARKET - no market price; value it another way"
            return r
        r["price"], r["basis"] = e["price"], e["basis"]
        if a.tax:
            r["after_tax"] = round(e["price"] * keep)
        if a.details:
            r.update(base=e.get("basePrice"), max=e.get("priceMax"), last_sold=e.get("lastSoldPrice"),
                     last_sold_utc=market.fmt_time(e.get("lastSoldTime")), stock=e.get("currentStock"),
                     trades=e.get("totalTrades"))
        return r

    rows, failed = [], False
    for q, found, problem in resolved:
        if problem:
            rows.append({"query": q, "note": problem}); failed = True; continue
        item_rows = []
        for iid in found:
            if iid in market.FIXED_VALUES:
                v = market.FIXED_VALUES[iid]
                r = {"query": q, "id": iid, "sid": 0, "name": names.get(iid, str(iid)), "price": v,
                     "basis": "fixed NPC value", "note": ""}
                if a.tax:
                    r["after_tax"] = v  # NPC sale: no market tax
                item_rows.append(r)
            elif iid not in prices:
                failed = True
                item_rows.append({"query": q, "id": iid, "name": names.get(iid, ""),
                                  "note": f"FETCH FAILED after retries - rerun later: {errors.get(iid, 'no data returned')[:160]}"})
            else:
                item_rows += [row(q, iid, e) for e in prices[iid]]
        if len(found) > 1:
            hidden = sorted({r["id"] for r in item_rows if r["note"].startswith("NOT ON MARKET")})
            shown = [r for r in item_rows if r["id"] not in hidden]
            if shown and hidden:
                item_rows = shown
                rows.append({"query": q, "note": f"SAME NAME, {len(found)} IDs - hid untradeable copies {hidden}"})
            else:
                rows.append({"query": q, "note": f"SAME NAME, {len(found)} IDs: {found} - check which one you need"})
        rows += item_rows

    failed = failed or any(r["note"].startswith("UNKNOWN ID") for r in rows)
    fetched = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    tax_txt = f"after_tax = price x {keep}" if a.tax else "prices before tax"
    if a.json:
        print(json.dumps({"region": region, "fetched": fetched, "tax": tax_txt, "rows": rows}, indent=1))
        return 2 if failed else 0
    print(f"# region={region} fetched={fetched} source=api.arsha.io silver, {tax_txt}")
    cols = ["id", "name", "price"] + (["after_tax"] if a.tax else []) + ["basis"]
    if a.sid is None and any(r.get("sid") for r in rows):
        cols.insert(1, "sid")
    if a.details:
        cols += ["base", "max", "last_sold", "last_sold_utc", "stock", "trades"]
    cols.append("note")
    print("\t".join(cols))
    money = {"price", "after_tax", "base", "max", "last_sold", "trades"}
    for r in rows:
        out = [f"{r[c]:,}" if isinstance(r.get(c), int) and c in money else str(r.get(c) if r.get(c) is not None else "")
               for c in cols]
        if not r.get("id"):
            out[cols.index("name")] = r["query"]
        print("\t".join(out).rstrip("\t"))
    return 2 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
