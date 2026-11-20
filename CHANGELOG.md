# Changelog

## 2026-11-21
- Skill Change Points now go back to 0 when a Change Coupon gives the desired skill (seen in-game twice; before, the model let them grow by 1 per coupon). Both engines, while leveling and in the level-30 cleanup; `simulate_plan`'s `points_reset` option is gone (always on). Chances drop in hard cases, e.g. the T8 example at Skilled 1, best plan with 20 coupons: 61% instead of 71%.
- `bdo/horses_fast.py`: the exact level-30 cleanup is swept by wanted skills held, then points (the reset breaks the old order by points); `cleanup_values` lost its `bound` argument. `--optimize` on the T8 example: about 20 s / 0.5 GB at 20 coupons, 45 s / 1.2 GB at 40 (`--low-memory`: 0.8 GB).

## 2026-11-19
- `data/horse_skills.json`: T9 Doom and T8 example weights refined to 4 decimals from in-game simulator readings at Artisan 8 (`tests/data/sim_doom_t9_artisan8.csv`, `sim_t8_choky_artisan8.csv`); all within bdolytics' 0.01 rounding. They reproduce the earlier independent readings (Doom at Artisan 7, T8 at Professional 10) to 0.0001 points.

## 2026-11-18
- `--optimize` ends with the average learned skills per level for the suggested plans (`Evaluator.learned_by_level`, `bdo.horses.learned_by_level`).
- `--optimize --selection-coupon planned|fallback`: a Mount Skill Selection Coupon used at the very end on the last missing skill (needs an unwanted skill to change). `planned`: every Change Coupon aims at the second rarest missing skill, keeping the rarest for it, and the plan search includes it; `fallback`: plans as without it, plus the chance if you decide at level 30 to use it. With `--tickets`, the suggested plans also show the chance if you keep the tickets. `simulate_plan(coupon=...)`, `Evaluator.plans(coupon=...)`.
- Bad cases shown: the strategies table has `<=1 missing` and `worst 5%` columns; the `--optimize` suggested plans show the chances of missing at most 1 / 2 wanted skills and what the worst 5% of horses miss (exact in the fast engine: `Evaluator.plans(tails=True)`; `simulate_plan` returns `tails`).
- `--optimize`: a suggested plan per budget after the table: the general rule's plan (`bdo/horses.py` `rule_plan`, fitted over 72 situations) when it's within 1 point of the best plan found, else the best. Plans are written as "from lvl 10, V0 until 11 learned skills, then V2, keep 5".
- `bdo/horses_fast.py`: the exact level-30 cleanup is now computed per batch of plans, sweeping the reachable states by Skill Change Points (two levels in memory; only points + coupons left <= starting points + largest budget). Same results; `--optimize` on the T8 example: 13 s / 0.5 GB instead of 30 s / 1.0 GB at 20 coupons, 26 s / 0.7 GB instead of 90 s / 2.9 GB at 40. New `--low-memory` (16-bit values). `Evaluator.plans()` evaluates a batch; the persistent `Table` is gone.
- `horse_skills.py`: new strategy `coursier_switch`: `coursier` swaps until the horse has `--switch-at` learned skills (default 12; innate ones don't count), then `coursier_v2` swaps. Building skills first, then stopping the loop, beats both with many coupons. `--optimize` searches its threshold (9-16); plans are now (strategy, start level, spending cap, threshold) in `bdo/horses.py` and `bdo/horses_fast.py`, and tied plans read "from lvl 7-11, V0 until 10-13 learned skills, then V2, keep 0-10".
- `horse_skills.py`: new strategy `coursier_v2`: swap only Hind Kick (the heavier fodder skill) and keep Fore Chop. Plain `coursier` loses many coupons to a Hind Kick <-> Fore Chop loop; `coursier_v2` needs far fewer coupons for the same chance in most cases (see the report).
- Level-30 cleanup rule changed to "swap the rarest unwanted skill held" (was: keep re-swapping the same slot). Slightly better, and as good as the best possible cleanup for the full set. Simulated numbers move by about +1 point.
- `--optimize N`: best plan per budget (strategy, start level, coupons kept), with tied ranges and coupons needed for 50/80/90/95%. `--target`: coupons needed per strategy. `--swap-from`: level to start swapping.
- New optional fast engine `bdo/horses_fast.py` (numba, `requirements-optional.txt`): every plan tried, level-30 cleanup computed exactly. `--engine auto|python|numba`; without numba everything still works in plain Python.
- `data/horse_skills.json`: Mythical Diné weights refined to 4 decimals from an in-game simulator reading (bdolytics rounds to 0.01); checked against a coupon-window reading at 2 Skill Change Points.

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
