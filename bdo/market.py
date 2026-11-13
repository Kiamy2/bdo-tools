"""Central Market data from Arsha.io and the agreed price rule.

Default price rule (user's decision):
  1. last sold price if the last sale was < 24 h ago;
  2. else the average of the last 7 daily prices (Arsha history, lags 1-2 days);
  3. else the base price, flagged.
"""
import datetime as dt
import time

from .net import NetworkBlocked, get_json

API = "https://api.arsha.io"
RECENT_SALE_S = 24 * 3600
TAX_VP, TAX_NO_VP = 0.845, 0.65   # share of the sale price the seller keeps

# Items with a fixed NPC silver value (never sold on the Central Market, no tax).
FIXED_VALUES = {
    2: 10_000,          # Gold Bar 1G
    3: 100_000,         # Gold Bar 10G
    4: 1_000_000,       # Gold Bar 100G
    5: 10_000_000,      # Gold Bar 1,000G
    8: 100_000_000,     # Gold Bar 10,000G
}


def batched(keys, endpoint, region="na", lang="en", chunk=20):
    """Call an Arsha v2 endpoint for many (id, sid) keys, `chunk` per request
    (comma-separated id= / sid= lists). A failing batch is retried one key at a
    time, then anything still missing gets a last pass after 20 s.
    GetWorldMarketSubList -> ({id: [entries]}, {id: error})
    GetMarketPriceInfo    -> ({(id, sid): [entries]}, {(id, sid): error})"""
    out, errors = {}, {}
    use_sid = endpoint == "GetMarketPriceInfo"
    key_of = (lambda k: k) if use_sid else (lambda k: k[0])

    def get(part):
        q = f"id={','.join(str(k[0]) for k in part)}"
        if use_sid:
            q += f"&sid={','.join(str(k[1]) for k in part)}"
        data = get_json(f"{API}/v2/{region}/{endpoint}?{q}&lang={lang}")
        for e in (data if isinstance(data, list) else [data]):
            k = (e.get("id"), e.get("sid", 0)) if use_sid else e.get("id")
            out.setdefault(k, []).append(e)

    keys = list(dict.fromkeys(keys))
    for i in range(0, len(keys), chunk):
        part = keys[i:i + chunk]
        try:
            get(part)
        except NetworkBlocked:
            raise
        except Exception:
            for k in part:
                try:
                    get([k])
                except NetworkBlocked:
                    raise
                except Exception as e:
                    errors[key_of(k)] = str(e)
                time.sleep(0.5)
    missing = [k for k in keys if key_of(k) not in out]
    if missing:
        time.sleep(20)
        for k in missing:
            try:
                get([k])
                errors.pop(key_of(k), None)
            except NetworkBlocked:
                raise
            except Exception as e:
                errors[key_of(k)] = str(e)
    return out, errors


def current(ids, region="na", lang="en"):
    """Current market entries per item ID (gear: one entry per enhancement band)."""
    return batched([(i, 0) for i in ids], "GetWorldMarketSubList", region, lang)


def history(keys, region="na", lang="en"):
    """90 daily prices per (id, sid): entry['history'] = {'<ms 00:00 UTC>': price}."""
    return batched(keys, "GetMarketPriceInfo", region, lang)


def history_avg(entry, days):
    """Average of the last `days` daily prices -> (avg, n_points, 'YYYY-MM-DD' of newest) or None."""
    pts = sorted((int(k), v) for k, v in (entry.get("history") or {}).items() if v)
    if not pts:
        return None
    last = pts[-days:]
    avg = round(sum(v for _, v in last) / len(last))
    day = dt.datetime.fromtimestamp(last[-1][0] / 1000, dt.timezone.utc).strftime("%Y-%m-%d")
    return avg, len(last), day


def is_untradeable(e):
    return not e.get("basePrice") and not e.get("totalTrades")


def sold_recently(e, now=None):
    t = e.get("lastSoldTime")
    return bool(t) and (now or time.time()) - t < RECENT_SALE_S


def fmt_age(seconds):
    return f"{seconds / 3600:.0f}h" if seconds < 2 * 86400 else f"{seconds / 86400:.0f}d"


def fmt_time(ts):
    return dt.datetime.fromtimestamp(ts, dt.timezone.utc).strftime("%Y-%m-%d %H:%M") if ts else "-"


def get_prices(ids, region="na", lang="en", mode="auto", avg_days=None, fallback_days=7, sid=None):
    """Price every market entry of the given item IDs (gold bars excluded - use FIXED_VALUES).

    mode: 'auto' (default rule), 'latest' (last sale, any age), 'avg' (avg_days-day average).
    Returns ({id: [priced entries]}, {id: fetch error}). Each priced entry is the raw Arsha
    entry plus 'price' and 'basis' ('price' is None for untradeable or unknown items).
    """
    now = time.time()
    cur, cur_err = current(ids, region, lang) if ids else ({}, {})
    for iid in list(cur):
        cur[iid] = [e for e in cur[iid] if sid is None or e.get("sid") == sid]
    valid = [(iid, e) for iid, es in cur.items() for e in es
             if e.get("name") != "NONAME" and not is_untradeable(e)]
    need = [] if mode == "latest" else [
        (iid, e.get("sid", 0)) for iid, e in valid if mode == "avg" or not sold_recently(e, now)]
    hist, _ = history(need, region, lang) if need else ({}, {})
    days = avg_days if mode == "avg" else fallback_days
    for iid, e in valid:
        if mode == "latest" or (mode == "auto" and sold_recently(e, now)):
            t = e.get("lastSoldTime")
            e["price"] = e.get("lastSoldPrice")
            e["basis"] = f"last sale {fmt_age(now - t)} ago" if t else "last sale (time unknown)"
            continue
        h = hist.get((iid, e.get("sid", 0)))
        res = history_avg(h[0], days) if h else None
        if res:
            e["price"], e["basis"] = res[0], f"{res[1]}-day avg to {res[2]}"
        else:
            e["price"], e["basis"] = e.get("basePrice"), "BASE PRICE - history unavailable"
    return cur, cur_err
