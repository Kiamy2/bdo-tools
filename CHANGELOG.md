# Changelog

## 2026-11-16
- `--lang` in `items.py` and `prices.py` now takes several languages (`--lang en,fr`): names are matched in any of them and printed one column per language. Useful to translate item names, or to work in French end to end.
- Looser name matching in both tools: if there's no exact (case-insensitive) match, accents, `œ`/`oe`, typographic apostrophes and extra spaces are ignored, then all spaces and punctuation. A loose match that hits different names is refused with the candidates listed.
- Better suggestions for unmatched names: names containing every word in any order, across all `--lang` languages.
- An unknown `--lang` now stops at once with `UNKNOWN LANGUAGE` (exit 2). Before, `prices.py` reported every item as UNKNOWN ID. Arsha HTTP 400 errors are no longer retried.
- `prices.py` always fetches market data with `lang=en`; displayed names come from the item lists.
- Output is always UTF-8 (avoids crashes on Windows pipes with non-Latin names).

## 2026-11-13
- Licensed under MIT.
- Docs reorganised for public use: `docs/prices.md`, `docs/items.md`, `docs/data-sources.md`, `CONTRIBUTING.md`, `AGENTS.md`.
- `prices.py` (v2.1) and `items.py` moved onto a shared library (`bdo/`), with tests in `tests/run_all.py`.
- Price rule: last sale if under 24 h old, else 7-day average, else base price (flagged). Options `--latest`, `--avg`, `--fallback-days`, `--tax`/`--no-vp`, `--details`, `--sid`, `--region`, `--json`.

## 2026-11-12
- First version of the price script (base and last-sold prices, name lookup, retries).
