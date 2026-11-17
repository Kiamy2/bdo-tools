# Changelog

## 2026-11-17
- New `horse_skills.py` (offline): horse skill odds per level-up and a leveling-strategy simulator (natural, coupons at 30, coursier, hard, ideal), with the gear set / brand stone as a/b/c columns, coupon budgets, Mount Level Down Tickets, a horse's current level and learned skills. `--check` compares in-game simulator readings with the model; `--horse-file` adds any horse from one reading.
- New `bdo/horses.py` (model and simulation) and `data/horse_skills.json` (weights for Mythical Diné, Arduanatt and Doom, Doom T9, Voltarion and one T8 coat, with source and date).
- New report `docs/horse-skills-report.md`: the learning formula (checked in-game), strategy comparison and conclusions.

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
