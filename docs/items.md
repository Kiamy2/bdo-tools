# items.py: item name ↔ ID lookup

No prices; just names and IDs (e.g. to find an exact name for `prices.py`, or an ID for a wiki or database page).

```
python3 -I items.py "Vell's Heart" 4998          # resolve exact names and/or IDs
python3 -I items.py --search "Advice of Valks"    # every item whose name contains the text
```

- Names are matched exactly (case-insensitive). If there's no match, the closest names are suggested (typos too).
- Some names are shared by several items (often untradeable event copies). All of them are listed, with a `SAME NAME` note.
- `--search` shows up to 50 results (`--limit N` to change that).
- The item list (about 71k items from Arsha.io, 4 MB) is cached in `/tmp/bdo_tools/` for 7 days (`--refresh-db` to re-download). Don't print it.

Output: tab-separated `id`, `name`, `note`. Exit codes: `0` OK · `2` some item NOT FOUND or UNKNOWN ID · `3` network blocked.
