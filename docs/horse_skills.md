# horse_skills.py: horse skill odds and leveling strategies

Offline (no network). It answers "what are my odds on the next level-up?" and "how many skills will my horse end up with, and should I use the gear, the brand stone or my coupons this way or that way?". The model, the data and the conclusions are in [horse-skills-report.md](horse-skills-report.md).

```
python3 -I horse_skills.py --list                                                   # horses in the data file
python3 -I horse_skills.py "Mythical Diné" --training "Artisan 7"                   # all strategies, 30 coupons
python3 -I horse_skills.py "Mythical Diné" --training "Artisan 7" --coupons 10 --tickets 4
python3 -I horse_skills.py "Mythical Diné" --training "Artisan 7" --level 2 --learned "High Jump"
python3 -I horse_skills.py "Mythical Diné" --training "Artisan 7" --sweep 0,10,20,40 --strategy at30,coursier
python3 -I horse_skills.py "Mythical Diné" --training "Artisan 7" --odds --gear --lang fr   # next level-up's odds
python3 -I horse_skills.py "Mythical Diné" --training "Artisan 7" --check "Ruade=15.1844" "none=10.7826"
python3 -I horse_skills.py "Mythical Diné" --training "Artisan 7" --optimize 30            # best plan per budget
python3 -I horse_skills.py "Mythical Diné" --training "Artisan 7" --target 50,90 --strategy coursier_v2
```

## Inputs

- **Horse:** a name from `--list` (accents and case optional), or `--horse-file` with your own reading of the in-game simulator (below).
- `--training`: your Training level, in English or French (`Artisan 7`, `Master 20`, `Gourou 57`), or the bonus itself (`21.7`).
- `--learned`: skills the horse already has, besides its innate ones. Skill names in English or French, comma-separated (`"High Jump, Dérapage"`).
- `--level`: the horse's current level (default 1). Leveling always ends at 30, since skills aren't learned past 30.
- `--coupons` (default 30) or `--sweep 0,10,20`: Mount Skill Change Coupons available. `--tickets`: Mount Level Down Tickets (default 0).
- `--wanted`: the skills you want (default: the travel set in the report). `--fodder`: what the `coursier` strategies swap out (default `Hind Kick, Fore Chop`; `coursier_v2` cycles only the heaviest of them). `--reserve`: coupons kept for level 30 (default 5). `--swap-from`: level from which the strategies start swapping while leveling (default 1). `--switch-at`: the learned-skill count at which `coursier_switch` changes from `coursier` to `coursier_v2` swaps (default 12).
- `--points`: Skill Change Points the horse already has. `--point-bonus`: how much each point raises the desired skill (default 0.25, see the report).
- `--runs` (default 5000) and `--seed`: simulation size and random seed. Results move by about ±1 point between seeds at 5000 runs.

## Strategies

`--strategy` takes a comma-separated subset (default all):

- `natural`: no coupons. `at30`: all coupons kept for level 30.
- `coursier`: swap Hind Kick and Fore Chop each time they're learned. Swapping one often draws the other back, so coupons churn.
- `coursier_v2` (V2): swap only Hind Kick (the heavier of the two) each time it's learned, and keep Fore Chop. No loop: best with few coupons (see the report).
- `coursier_switch`: `coursier` (V0) swaps until the horse has `--switch-at` learned skills, then `coursier_v2` (V2) swaps until level 30. The count starts at `--swap-from` (no swaps before); a horse that already has enough skills there goes straight to V2. **Learned skills don't include innate ones:** in-game, the skill list also shows them (7 on a Mythical Diné or Arduanatt, 4 on a T9 Doom, 1 on a T8), so add those when you count. V0 first builds up skills, V2 then stops the Hind Kick ↔ Fore Chop loop: best with many coupons.
- `once`, `hard`: swap every unwanted skill once / until a wanted one comes. Rarely worth it.
- `ideal`: unlimited coupons, always holding the rarest skills (the most skills a horse can reach).

Every strategy except `natural` and `ideal` ends with the **level-30 cleanup**: swap the rarest unwanted skill held, with the rarest missing wanted skill as the desired one, until every wanted skill is held or coupons run out. Swapping the rarest first keeps the common skills (Hind Kick...) held, so they don't come back in the next coupon draws. Trying every other choice of skill to swap and of desired skill gains nothing measurable for the full set.

## Output

The simulation prints one row per strategy (descriptions in `--help` and the report):

```
strategy  coupons  skills at 30   wanted at 30   all wanted    coupons used  <=1 missing    worst 5%
coursier  30       18.8/19.3/19.6 13.0/13.0/13.0 97%/99%/100%  23/23/23      99%/100%/100%  0/0/0
```
(Mythical Diné, Artisan 7, 30 coupons.)

- Each cell is **a/b/c**: a = no learn-chance boost, b = Pearl horse gear set **or** Mount Brand Spell Stone (both are +10%), c = both.
- `skills at 30`: learnable skills the horse has at level 30 (innate ones not counted). `wanted at 30`: how many of those are wanted. `all wanted`: chance of ending with every wanted skill. `coupons used`: average. `<=1 missing`: chance of missing at most one wanted skill. `worst 5%`: how many wanted skills the worst 5% of runs miss (the bad cases).
- `--odds` prints the next level-up's chances like the in-game simulator, with `--gear`/`--brand` for the learn-chance boosts.
- `--target 50,90`: instead of a budget, the coupons needed to end with every wanted skill in 50% / 90% of runs, per strategy (fixed `--reserve` / `--swap-from`).
- `--check` compares numbers you read in the in-game simulator with the model (`none` = "no skill"). It exits with 1 on a mismatch, which means the data is outdated or the settings differ (same Training level, boosts and learned skills as in the game?).

## Best plan per budget (`--optimize N`)

`--optimize 30` searches, for every budget from 0 to 30 coupons, the best plan: the strategy, the level to start swapping, how many coupons to keep for level 30, and for `coursier_switch` the learned-skill count to switch at (9 to 16). It prints the plans tied with the best (within 1 point) for two goals, the full set and the most wanted skills on average, then the coupons needed for a 50 / 80 / 90 / 95% chance of the full set. Works from a horse's current state (`--level`, `--learned`, `--points`, `--tickets`).

```
coupons  full set: chance  tied plans                              most wanted: avg  tied plans  at30: chance, avg
10       62.6%             coursier_v2: from lvl 10-16, keep 0-3  12.46             ...         32.3%, 11.94
20       71.2%             coursier_switch: from lvl 7-11, V0 until 10-13 learned skills, then V2, keep 0-10   ...
```

After the table, a **suggested plan per budget**: one concrete plan for the full set, such as `20  from lvl 10, V0 until 11 learned skills, then V2, keep 5  70.7%  rule (best 71.2%)`. It's the general rule's plan (the same for everyone, chosen to lose the least over many horses and Training levels) when that plan is within 1 point of the best one found for your horse; otherwise it's the best plan found, and the line says how much the rule would lose. V0 = `coursier` swaps, V2 = `coursier_v2` swaps. Each line also shows the bad cases: the chances of missing at most 1 and at most 2 wanted skills, and how many the worst 5% of horses miss. The plan that's best for the full set is also the safest here: in tests over many horses, Training levels and budgets, no plan within 1 point of it had noticeably fewer bad cases.

**Mount Skill Selection Coupon** (`--selection-coupon planned` or `fallback`): one per horse, it changes one of the horse's current skills into the skill you pick. It's best used at the very end, on the last missing skill, and it needs an unwanted skill to change (a horse with fewer learned skills than wanted ones can't use it). It adds a lot in hard cases: on the T8 example at Skilled 1 with 20 coupons, 70% becomes about 93%.
- `planned`: you'll use it for sure. Every Change Coupon, while leveling and at level 30, then aims at the **second** rarest missing skill (the desired skill), keeping the rarest for the Selection Coupon. The plan search and every chance include it. This targeting is only a bit better (up to about 0.6 points) **if you do use the coupon**; if you might keep it, don't use it while leveling.
- `fallback`: a safety net. The plans stay the ones without it, and the suggested plans get a `with Selection Coupon` column: your chance if, at level 30, you decide to use it (from then on, Change Coupons aim at the second rarest missing skill). Decide at 30, depending on how leveling went.

Last, a table of the **average learned skills when reaching each level** (innate ones not counted), one column per suggested plan (plans within 0.2 skills of each other share a column). Rerunning the tool partway through leveling, compare your horse with it: below average means leveling is going worse than usual.

**Level Down Tickets** (`--tickets N`): they're used on every level-up that teaches nothing, from your current level on. With tickets, the suggested plans get a `keeping tickets` column: the same plan's chance if you don't use them. Rerun the tool partway through leveling (`--level`, `--learned`, `--points`, `--tickets`) to see whether your remaining tickets are worth spending on this horse.

- **Fast engine** (`--engine numba`, the default when numba is installed: `pip install -r requirements-optional.txt`): tries every plan (`at30`, and `coursier` / `coursier_v2` with every start level and spending cap; `coursier_switch` with every start level and threshold, on a grid of spending caps refined around the best) and computes the level-30 cleanup exactly instead of simulating it. About 15 seconds and 0.5 GB of memory for 20 coupons, 30 seconds and 0.7 GB for 40 (measured on the T8 example, 2 cores). `--low-memory` keeps the level-30 values as 16-bit numbers: about 0.1 GB less at 40 coupons, same speed, chances within 0.001 points (a plan right at the edge of a tied range can move in or out of it).
- **Plain Python** (`--engine python`, or when numba isn't installed): a grid of plans refined around the best ones (`coursier_switch` thresholds 9, 11, 13, 15, then their neighbors), simulated. Several minutes and noisier, same model.

## Your own horse (`--horse-file`)

Any horse can be added from one reading of the in-game simulator (Horse info → Growth simulator), taken at horse level 1–30 with no skills toggled and a Training level where "no skill" is above 0%. Write a CSV like [tests/data/sim_mythical_dine_artisan7.csv](../tests/data/sim_mythical_dine_artisan7.csv):

```
# name: My horse
# training: Artisan 7
# boosts: none
# learned: Sprint
none,10.7826
Ruade,15.1844
...
```

`boosts` is `none`, `gear`, `brand` or `both` (`boxes` is also accepted); `learned` lists the skills shown as innate ("base skill") or toggled. Skill names in English or French.

Exit codes: `0` OK · `1` `--check` mismatch · `2` bad input (unknown horse, skill, strategy or Training level).
