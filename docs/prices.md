# prices.py: Central Market prices

Live Black Desert Online Central Market prices from [Arsha.io](https://api.arsha.io), for any region (default `na`).

```
python3 -I prices.py "Vell's Heart" "Kabua's Artifact" 4998
```

- Items are names in double quotes, or numeric item IDs. Names are matched like in [`items.py`](items.md): case-insensitive, then ignoring accents, spaces and punctuation. Don't know the exact name? Use `items.py --search`.
- Names can be in another language with `--lang` (see below).
- Pass **all items in one run**: requests are batched (20 items each), which is faster and less often blocked.
- A run usually takes 1–30 s. Retries during API hiccups can stretch it to about 2 minutes, so give it a long timeout.
- Needs network access to `api.arsha.io`. The item name list (about 4 MB) is cached in `/tmp/bdo_tools/` for 7 days. Don't print it.

## Default price rule

For each item (and each enhancement band of gear):
1. the **last sold price**, if the last sale was under 24 h ago;
2. otherwise the **7-day average** of Arsha's daily prices (change the window with `--fallback-days N`);
3. otherwise, if the history request fails, the **base price**, flagged `BASE PRICE - history unavailable`.

Why not the base price? In-demand items often only sell at their max price, which is above base (e.g. Vell's Heart: base 15.4B, sells at 16.5B).

The daily history has one value per day. It looks like a daily average (the values aren't round), but Arsha doesn't document this. The newest point lags 1–2 days behind today; the `basis` column gives its date.

## Options

| Option | Effect |
|---|---|
| `--tax` | Adds an `after_tax` column: what the seller keeps (84.5% with a Value Pack). Add `--no-vp` for 65%. |
| `--latest` | Price = the most recent sale, whatever its age (most up to date). |
| `--avg N` | Price = average of the last N daily prices (1–90) for every item. |
| `--details` | Adds base price, max price, last sale and its time (UTC), stock, total trades. |
| `--sid N` | Gear only: just one enhancement band (0 = base). Otherwise gear gets one row per band. |
| `--lang L` | Name language(s), comma-separated (default `en`): `--lang fr` takes and prints French names, `--lang en,fr` takes either and prints both (`name_en`, `name_fr` columns). Codes and matching: see [items.md](items.md). Prices are the same whatever the language. |
| `--region R` | `na` (default), `eu`, `sea`, `mena`, `kr`, `ru`, `jp`, `th`, `tw`, `sa`, `console_na`, `console_eu`, `console_asia`. |
| `--json` | JSON output. |
| `--refresh-db` | Re-download the item name list. |

## Output

Tab-separated (UTF-8): `id`, (`sid` for gear), `name` (or one `name_<lang>` column per language), `price`, (`after_tax`), `basis`, `note`. The first line gives the region, the fetch time (UTC) and the tax mode. Prices are in silver.

| `note` | Meaning |
|---|---|
| *(empty)* | OK. |
| `NOT ON MARKET` | The item can't be traded (event items, boxes, coupons, Advice of Valks...), so it has no market price. Value it another way; don't count it as 0 silently. |
| `NOT FOUND ... Similar: ...` | No exact name match. Pick from the suggestions, or use `items.py --search`. |
| `SAME NAME ... hid untradeable copies` | Several items share the name; the tradeable one is shown. |
| `SAME NAME ... check which one you need` | Several items share the name and all are shown. |
| `UNKNOWN ID` | No item has this ID. |
| `FETCH FAILED` | Arsha stayed blocked despite retries (temporary). Rerun the failed items a minute later. |

Gold bars have `basis` = `fixed NPC value` (1G = 10k, 10G = 100k, 100G = 1M, 1,000G = 10M, 10,000G = 100M silver). They're never taxed, since they're sold to an NPC.

Exit codes: `0` OK · `2` some rows NOT FOUND, UNKNOWN ID or FETCH FAILED, or `UNKNOWN LANGUAGE` · `3` network blocked (the message says which domain to allow).
