# Changelog

## 2026-11-13
- Docs reorganised for public use: `docs/prices.md`, `docs/items.md`, `docs/data-sources.md`, `CONTRIBUTING.md`, `AGENTS.md`.
- `prices.py` (v2.1) and `items.py` moved onto a shared library (`bdo/`), with tests in `tests/run_all.py`.
- Price rule: last sale if under 24 h old, else 7-day average, else base price (flagged). Options `--latest`, `--avg`, `--fallback-days`, `--tax`/`--no-vp`, `--details`, `--sid`, `--region`, `--json`.

## 2026-11-12
- First version of the price script (base and last-sold prices, name lookup, retries).
