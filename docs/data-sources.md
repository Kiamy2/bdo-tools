# Data sources and internals

For anyone changing the code or debugging odd results. Last researched 2026-11-13.

## Arsha.io (the source used)

A free community **cached wrapper** around the official BDO Central Market API. According to its (outdated) docs, values are cached for 30 minutes and dropped depending on usage frequency. No "cached only" option is known.

| Endpoint (v2) | Used by | Notes |
|---|---|---|
| `GET /util/db?lang=en` | `bdo/items.py` | Every item, `[{id, name, grade}]`, about 71k entries and 4 MB. **It ignores any `name=` filter** and always returns everything, so it's cached to disk and searched locally. |
| `GET /v2/{region}/GetWorldMarketSubList?id=1,2,...&lang=en` | `bdo/market.py` | Current market data; comma-separated IDs batch fine (we use 20 per request). One entry per item, or per enhancement band (`sid`) for gear. Fields: `name, id, sid, minEnhance, maxEnhance, basePrice, currentStock, totalTrades, priceMin, priceMax, lastSoldPrice, lastSoldTime` (seconds). |
| `GET /v2/{region}/GetMarketPriceInfo?id=1,2&sid=0,0&lang=en` | `bdo/market.py` | 90 daily prices per (id, sid): `history: {"<ms at 00:00 UTC>": price}`. Batches like the above. The newest point lags 1–2 days. |

Behaviour to know:
- **Frequent temporary errors:** `{"status":500,"message":"...probably blocked by Imperva..."}`. Arsha fetches from the official market, which is behind Imperva bot protection, and gets throttled in bursts; uncached items fail for everyone for a while. `bdo/net.py` retries 5 times (2/4/8/16 s), `bdo/market.py` then retries a failed batch item by item and makes a last pass after 20 s.
- **Untradeable items** come back with `basePrice 0` and `totalTrades 0`.
- **Unknown IDs** come back with `name "NONAME"`.
- Other v2 endpoints exist but aren't used here: search list, bidding info (pre-orders), wait list (registration queue), hot list, category lists, pearl items.
- Docs: <https://documenter.getpostman.com/view/4028519/TzK2bEVg> (marked outdated by Arsha). The linked source host `git.arsha.io` returned 404 in Nov 2026.

## Other sources researched

| Source | Findings |
|---|---|
| **bdomarket** (PyPI, Fizzor96/bdomarket, v0.3.2, **GPL-3.0**) | A Python client for Arsha. It has no retry handling and has renamed its API between versions. Extras not from Arsha: a client for `api.blackdesertmarket.com` (server-side name search, item details, item stats per enhancement level; status unverified), boss timers (scraped from mmotimer.com), Pig Cave status, item icons (official image server). A good reference for endpoint parameters. Its code must not be copied into this MIT repo (see CONTRIBUTING). |
| **bdoworkshop.com** | Market prices from `/market-prices/2/{serverId}` (NA = server 2), using a cookie session and an `X-Market-Prices-Token` header taken from the page's `data-page` JSON (`props.marketPricesToken`). Same prices as Arsha. Its FS cost and Valks estimates are computed in the browser. No license stated. |
| **bdolytics.com** | Prices are rendered by JavaScript, so a plain HTTP fetch returns no data. |
| **garmoth.com** | Refuses automated fetches. Has a Failstack Optimizer (up to 350 FS). |
| **Official site** (naeu.playblackdesert.com, blackdesert.pearlabyss.com) | Incapsula bot protection blocks automated reads. |
