# horse_skills.py: horse skill odds and leveling strategies

Offline (no network). It answers "what are my odds on the next level-up?" and "how many skills will my horse end up with, and should I use the gear, the brand stone or my coupons this way or that way?". The model, the data and the conclusions are in [horse-skills-report.md](horse-skills-report.md).

For AI assistants guiding a player step by step through a horse's leveling: [horse_skills_guide.md](horse_skills_guide.md).

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

- **Horse:** a name from `--list` (accents and case optional), or `--horse-file` with your own reading of the in-game simulator (below). T8s by type number: `T8 Type 1` to `T8 Type 22` for the default horses read so far (Sprint as the only innate skill; types sharing the same weights are aliases); a horse with other innate skills: `--innate` (below) or its own reading.
- `--training`: your Training level, in English or French (`Artisan 7`, `Master 20`, `Gourou 57`), or the bonus itself (`21.7`).
- `--learned`: skills the horse already has, besides its innate ones. Skill names in English or French, comma-separated (`"High Jump, Dérapage"`).
- `--level`: the horse's current level (default 1). Leveling always ends at 30, since skills aren't learned past 30.
- `--coupons` (default 30) or `--sweep 0,10,20`: Mount Skill Change Coupons available. `--tickets`: Mount Level Down Tickets (default 0).
- `--wanted`: the skills you want: your own comma-separated list, or a named set. `courser` = what a T8 needs (with level 30) for courser training into a Dream Horse (T9): Charge, Drift, Sprint, Instant Accel, Sideways, S: Instant Accel, S: Sideways. `travel` = an example of a finished set for a T10 (the list in the report). Default: `courser` for a T8, `travel` otherwise; the output says which set it used. `--fodder`: what the `coursier` strategies swap out, in that order (default `Fore Chop, Hind Kick`; `coursier_v2` cycles only the heaviest of them, Hind Kick on ties). `--reserve`: coupons kept for level 30 (default 5). `--swap-from`: level from which the strategies start swapping while leveling (default 1). `--switch-at`: the learned-skill count at which `coursier_switch` changes from `coursier` to `coursier_v2` swaps (default 12).
- `--points`: Skill Change Points the horse already has. `--point-bonus`: how much each point raises the desired skill (default 0.25, see the report). Each Change Coupon adds 1 point, except one that gives the desired skill: then the points go back to 0 (seen in-game).
- `--runs` (default 5000) and `--seed`: simulation size and random seed. Results move by about ±1 point between seeds at 5000 runs.

## Strategies

`--strategy` takes a comma-separated subset (default all):

- `natural`: no coupons. `at30`: all coupons kept for level 30.
Plans name these strategies **S1** and **S2** (called V0 and V2 before 2026-11-23):

- `coursier` (S1): once per level, after the level-up: swap Fore Chop if held, then Hind Kick if held; never more than this one pass per level. Swapping one often draws the other back, so coupons churn. Fore Chop first is slightly better than Hind Kick first when Hind Kick is the heavier (up to about 1 point; none on the T8, where they weigh the same), and swapping again until neither is held is worse (see the report).
- `coursier_v2` (S2): once per level, after the level-up: swap Hind Kick (the heavier of the two) if held; never Fore Chop. No loop: best with few coupons (see the report).
- `coursier_switch`: `coursier` (S1) swaps until the horse has `--switch-at` learned skills, then `coursier_v2` (S2) swaps until level 30. The count starts at `--swap-from` (no swaps before); a horse that already has enough skills there goes straight to S2. **Learned skills don't include innate ones:** in-game, the skill list also shows them (7 on a Mythical Diné or Arduanatt, 4 on a T9 Doom, 1 on a T8), so add those when you count. S1 first builds up skills, S2 then stops the Hind Kick ↔ Fore Chop loop: best with many coupons.
- `once`, `hard`: swap every unwanted skill once / until a wanted one comes. Rarely worth it.
- `ideal`: unlimited coupons, always holding the rarest skills (the most skills a horse can reach).

Every strategy except `natural` and `ideal` ends with the **level-30 cleanup**: swap the rarest unwanted skill held, with the rarest missing wanted skill as the desired one, until every wanted skill is held or coupons run out. Swapping the rarest first keeps the common skills (Hind Kick...) held, so they don't come back in the next coupon draws. Trying every other choice of desired skill gains nothing measurable for the full set (checked with the points reset); other choices of skill to swap gained nothing either (checked before the reset).

## Output

The simulation prints one row per strategy (descriptions in `--help` and the report):

```
strategy  coupons  skills at 30   wanted at 30   all wanted    coupons used  <=1 missing    worst 5%
coursier  30       18.8/19.3/19.6 12.9/13.0/13.0 93%/96%/98%   23/23/23      99%/100%/100%  1/0/0
```
(Mythical Diné, Artisan 7, 30 coupons.)

- Each cell is **a/b/c**: a = no learn-chance boost, b = Pearl horse gear set **or** Mount Brand Spell Stone (both are +10%), c = both.
- `skills at 30`: learnable skills the horse has at level 30 (innate ones not counted). `wanted at 30`: how many of those are wanted. `all wanted`: chance of ending with every wanted skill. `coupons used`: average. `<=1 missing`: chance of missing at most one wanted skill. `worst 5%`: how many wanted skills the worst 5% of runs miss (the bad cases).
- `--odds` prints the next level-up's chances like the in-game simulator, with `--gear`/`--brand` for the learn-chance boosts.
- `--target 50,90`: instead of a budget, the coupons needed to end with every wanted skill in 50% / 90% of runs, per strategy (fixed `--reserve` / `--swap-from`).
- `--check` compares numbers you read in the in-game simulator with the model (`none` = "no skill"). It exits with 1 on a mismatch, which means the data is outdated or the settings differ (same Training level, boosts and learned skills as in the game?).

## Best plan per budget (`--optimize N`)

> **Being rechecked:** the Skill Change Points reset (see `--points`) is in the model since 2026-11-20, so every chance the tool prints includes it. The general rule, the cleanup's desired-skill choice and "the plan best for the full set is also the safest" have been redone with it; one finding quoted here comes from a study done before it and is being redone: the Selection Coupon targeting gain (below).

`--optimize 30` searches, for every budget from 0 to 30 coupons, the best plan: the strategy, the level to start swapping, how many coupons to keep for level 30, and for `coursier_switch` the learned-skill count to switch at (9 to 16). It prints the plans tied with the best (within 1 point) for two goals, the full set and the most wanted skills on average, then the coupons needed for a 50 / 80 / 90 / 95% chance of the full set. Works from a horse's current state (`--level`, `--learned`, `--points`, `--tickets`).

```
coupons  full set: chance  tied plans                              most wanted: avg  tied plans  at30: chance, avg
10       21.5%             coursier_v2: from lvl 10-21, keep 0-7 | coursier_switch: ...  10.59  ...  16.8%, 10.48
20       61.2%             from lvl 3-12, S1 until 10-11 learned skills, then S2, keep 1-12   ...
```
(T8 example, Skilled 1, `--optimize 20 --wanted travel`.)

After the table, a **suggested plan per budget**: one concrete plan for the full set, such as `10  from lvl 14, S2 until lvl 30, keep 1  21.2%  rule (best 21.4%)` (T8 example, Skilled 1, travel set). It's the general rule's plan (the same for everyone, see below) when that plan is within 1 point of the best one found for your horse and no plan at least as likely to give the full set uses 0.2 or more fewer coupons on average; otherwise it's the best plan found, and the line says how much the rule would lose (or that a cheaper plan is at least as good). The rule was fitted on default horses only: it isn't used for a special horse (`--innate`), a `--horse-file` horse, or a horse with more learned skills than levels gained (a default horse learns at most one skill per level-up: the tool warns, since it suggests innate skills typed as learned, or a typo). `--always-best` suggests the best plan found for every budget instead (the best of many near-tied plans is partly luck, which is why the rule is preferred by default).

The suggested plans are **rechecked with 20,000 fresh horses** (4,000 with the plain-Python engine): for each budget the plans tied in the table above, the rule's plan and at30. Fresh horses matter: the best of many plans looks a bit lucky on the horses it was picked on (0.5-1.1 points too high on the T8 Type 6 below). Among the rechecked plans within 0.3 points of the best full-set chance, "the best" is the one most likely to miss at most 1 wanted skill, and among those also within 0.3 points of that, the one using the fewest coupons on average (e.g. on the T8 Type 6 below with the gear, 2 coupons: from lvl 24, 51.1% and 95.9% missing at most 1, rather than from lvl 25, 50.7% and 94.4%). The `--coupons-used`, `with Selection Coupon` and `keeping tickets` numbers use the same fresh horses.

S1 = `coursier` swaps, S2 = `coursier_v2` swaps. Plans are printed in their effective form for your horse: a `coursier_switch` threshold your horse has already reached prints as plain S2 (e.g. "S1 until 9 learned skills, then S2" for a horse with 15 is "S2"), and a start level already passed prints as your next level. Each line also shows the bad cases: the chances of missing at most 1 and at most 2 wanted skills, and how many the worst 5% of horses miss. `used` is the average number of coupons used with that budget (a horse that doesn't get the full set counts every coupon it used; every column is over all horses, stuck ones included as played under `--when-stuck`), and `per full set` is `used` divided by the full-set chance: a plan that saves coupons by failing more often shows a higher value. The plan that's best for the full set is also the safest here: in tests over many horses, Training levels and budgets, no plan within 1 point of it had noticeably fewer bad cases.

The **general rule** (N = coupons) depends a little on the target set:
- N = 1: no swaps while leveling; use the coupon at level 30.
- N = 2-24: do S2 until level 30, keeping 1 coupon, from level max(10, 31 - 1.75 x N), rounded (halves up). With the courser set and 2-6 coupons, start earlier: from level 30 - 2 x N (26, 24, 22, 20, 18).
- N = 25 or more: from level 10, do S1 until 12 learned skills, then S2 until level 30, spending at most 24 coupons while leveling.

It was checked with fresh horses over 148 courser situations (the default T8 types, 6 Training levels, 3 boosts, and horses partway through leveling) and 60 travel situations (Mythical Diné, Doom and Arduanatt), up to 40 coupons. Against each situation's own best plan it loses 1.8-3.5 points at 2-8 coupons and at most 1.7 above for the courser set; 1.9-3.9 at 2-7 coupons and at most 2.5 above for the travel set. For a T8 or T9 aiming at the travel set it can be further off (the switch to S2 is better there at 20-24 coupons); `--optimize` then suggests its best plan instead.

**Mount Skill Selection Coupon** (`--selection-coupon planned` or `fallback`): one per horse, it changes one of the horse's current skills into the skill you pick. It's best used at the very end, on the last missing skill, and it needs an unwanted skill to change (a horse with fewer learned skills than wanted ones can't use it). It adds a lot in hard cases: on the T8 example at Skilled 1 with 20 coupons and the travel set, 61% becomes about 91%.
- `planned`: you'll use it for sure. Every Change Coupon, while leveling and at level 30, then aims at the **second** rarest missing skill (the desired skill), keeping the rarest for the Selection Coupon. The plan search and every chance include it. This targeting is only a bit better (up to about 0.6 points) **if you do use the coupon**; if you might keep it, don't use it while leveling.
- `fallback`: a safety net. The plans stay the ones without it, and the suggested plans get a `with Selection Coupon` column: your chance if, at level 30, you decide to use it (from then on, Change Coupons aim at the second rarest missing skill). Decide at 30, depending on how leveling went.

**Coupons used by a plan** (`--coupons-used`, or `--coupons-used 0,2,3` for some budgets only; 0 = no swaps while leveling): for the suggested plans, the chance of the full set with **at most B coupons in total**, for every B, when you follow the plan as planned while leveling and the level-30 cleanup goes on until the full set (up to 20 coupons in total, or the `--optimize` maximum + 10). It answers "if I follow the 3-coupon plan, what's my chance of being done with only 2?" and "the 2-coupon plan, then a 3rd coupon at level 30?". At a plan's own budget the value is its `full set` chance in the table above (the same horses); below it, only the horses whose leveling spent fewer coupons can count. Then, per plan, the coupons used on average, and the coupons that give the full set to half, 90% and 99% of horses. On the T8 Type 6 of the first live test (level 19, 15 learned skills, Artisan 9, gear):
```
at most B coupons  plan for 2 coupons  plan for 3 coupons
2                  51.1%               34.2%
3                  62.9%               91.7%
4                  71.7%               93.9%
plan                average  median  90%  99%  full set with 20
plan for 2 coupons  3.66     2       7    13   100.0%
plan for 3 coupons  2.93     3       3    9    100.0%
```

**Your own plans** (`--plan`, repeatable): compare a plan of yours with the suggested ones, in the three-criteria comparison (marked `(yours)`, always listed) and in `--coupons-used`. The syntax: the strategy `s1`, `s2` or `s1-s2`, then `L` + the level to start swapping, `C` + the coupons spent at most while leveling, and for `s1-s2` `T` + the learned skills at which S1 switches to S2, separated by `:` (any order, any case); or `at30`. Examples: `--plan s2:L20:C2` (from level 20, S2, spending at most 2 coupons while leveling), `--plan s1-s2:L10:C24:T12`, `--plan at30`. The comparison shows every plan's code in brackets, e.g. `[s2:L20:C2]`, ready to reuse.

**Plans compared on three criteria** (printed by default; `--no-frontier` to skip it): the suggested plans aim at the best chance with a fixed budget; this compares plans for every goal at once, with up to N coupons in total (N = the `--optimize` maximum; if you can get more coupons later, rerun with a larger N). Each plan is followed as planned while leveling, then the level-30 cleanup goes on until the full set or the N coupons are spent. The three criteria:
- **full set within N**;
- **stuck**: horses reaching level 30 with fewer learned skills than wanted ones (see "Stuck horses" below): what they cost is the horse, not coupons. The other failures (**unfinished**) would get there with more coupons. Shown as `0%` only when it can't happen (the horse already has enough learned skills); when none of the simulated horses got stuck, as `<0.02%`;
- **coupons avg**: coupons used on average, over all horses (a horse that is unfinished counts N; a stuck horse what it spent before it stopped, under the default `--when-stuck stop`).

**Every column is over all horses, unless its name ends with `| not stuck` or `| successes`**: two more averages, for information only, come after the others: `coupons avg | not stuck` and `coupons avg | successes` (the horses that get the full set; lower for plans whose successes are the easy horses: don't compare plans on it alone).

Plus the median coupons and the chance of the full set with at most 1, 2, 3, 5 and 10 coupons in total. Listed: the plans no other plan beats on all three within noise (`--frontier-tol`, default `0.3,0.03,0.3`: points of full-set chance, coupons, points of stuck horses), found among the plans of the search's first stage (1,000 horses each) and rechecked with fresh horses (`--recheck-runs`, default 20,000 with the fast engine); at most `--frontier-rows` (default 8). `*` marks the best value of each column (within the tolerance), `pick` the best plan for each criterion, and `--prefer chance|coupons|safe` sets the order (default chance). When one plan is the best on every criterion, the tool says so. A smaller tolerance lists more plans, some differing only by noise; more horses make the differences more precise (the noise of a chance near 50% is about 0.35 points at 20,000 horses, 0.25 at 40,000). The first stage can miss a plan within a few tenths of a point of a listed one.

Examples: on the T8 Type 6 above (level 19, 15 learned skills, Artisan 9, gear, 5 coupons) one plan is the best on every criterion (`from lvl 20, S2 until lvl 30, spend <= 2 while leveling`: 95.5%, stuck 0%, 2.79 coupons). On the T8 example at Skilled 1 with the travel set and 20 coupons there's a trade-off: `from lvl 10, S1 until 12 learned skills, then S2, spend <= 14` gives 60.2% with 4.0% stuck and 15.59 coupons on average (the best chance and the fewest stuck); no swaps while leveling uses the fewest coupons, 13.08 on average, but gives only 48.7%, with 16.1% stuck (its stuck horses spend nothing). On a T8 born with 5 of the 7 courser skills, no swaps while leveling is the best on every criterion (0.83 coupons on average). Adds about 10 s to `--optimize 20` from level 1 (the recheck), about 1 s from a horse partway through leveling.

The tool also says when **every skill left to learn is wanted**: any swap then gives a wanted skill, and what matters is which skill you give up (level-ups may teach it back). The header shows the learned skills with the count the game shows (`learned: 15 + 1 innate (Sprint) = 16 in game`); innate skills given in `--learned` are ignored, with a note.

**Stuck horses** (`--when-stuck stop|continue`, every strategy, every table): a horse is stuck when it reaches level 30 with fewer learned skills than wanted ones. No Change Coupon can then complete the set (a coupon never changes the number of skills) and neither can a Selection Coupon (it needs an unwanted skill to change). A failed horse is either stuck or unfinished (it ran out of coupons).
- `stop` (default): no more coupons on a horse once it is certainly stuck. While leveling, that's as soon as its learned skills plus the level-ups left are fewer than the wanted skills (a level-up teaches at most one skill, a Level Down Ticket only redoes an empty one): the plan's swaps stop there. At level 30, a stuck horse doesn't start the cleanup. Every number then describes that way of playing: the full-set chance is the same as with `continue` (a stuck horse fails either way), the coupons used are lower (a stuck horse spends nothing more), and "missing at most 1 / 2" and "worst 5%" count what the stuck horses held when they stopped.
- `continue`: the tool's behavior before 2026-11-23: the plan's swaps go on, and at level 30 a stuck horse still swaps its unwanted skills (rarest first) until none is left or the coupons run out. For a player who would still improve a stuck horse: it ends with more wanted skills, never the full set, and every number includes those coupons.
- The header says which rule a run uses. On the T8 example at Skilled 1 (travel set, 20 coupons), no swaps while leveling: 16.9% of horses stuck; coupons used on average 12.97 with `stop`, 15.60 with `continue`; "missing at most 1" 74.9% vs 80.6%.

**Percentages** never claim more than the simulation shows: a share that would round to 100.0% or 0.0% prints as `>99.9%` / `<0.1%`, and one that every (or none) of the simulated horses reached prints as `>99.98%` / `<0.02%` with 20,000 horses (the usual 95% bound, 3 / horses). Only the comparison's `stuck` column prints `0%`, where the rules make it impossible.

**Noise:** the table of tied plans and the search use 1,000 and 4,000 horses, and every plan is played on the same horses, so those chances can be off by a point or so, every plan in the same direction (the best ones a bit high: they were picked on those horses). The suggested plans, `--coupons-used` and the three-criteria comparison are rechecked on 20,000 fresh horses (with the fast engine; `--recheck-runs`): about 0.3-0.4 points of noise on a chance near 50%, and differences between plans are more precise than that.

Last, a table of the **average learned skills when reaching each level** (innate ones not counted), one column per suggested plan (plans within 0.2 skills of each other share a column). Rerunning the tool partway through leveling, compare your horse with it: below average means leveling is going worse than usual.

**Level Down Tickets** (`--tickets N`): they're used on every level-up that teaches nothing, from your current level on. With tickets, the suggested plans get a `keeping tickets` column: the same plan's chance if you don't use them. Rerun the tool partway through leveling (`--level`, `--learned`, `--points`, `--tickets`) to see whether your remaining tickets are worth spending on this horse.

- **Fast engine** (`--engine numba`, the default when numba is installed: `pip install -r requirements-optional.txt`): tries every plan (`at30`, and `coursier` / `coursier_v2` with every start level and spending cap; `coursier_switch` with every start level and threshold, on a grid of spending caps refined around the best) and computes the level-30 cleanup exactly instead of simulating it. About 20 seconds and 0.5 GB of memory for 20 coupons, 45 seconds and 1.2 GB for 40 (measured on the T8 example, 2 cores). `--low-memory` keeps the level-30 values as 16-bit numbers: about 0.4 GB less at 40 coupons, same speed, chances within 0.001 points (a plan right at the edge of a tied range can move in or out of it).
- **Plain Python** (`--engine python`, or when numba isn't installed): a grid of plans refined around the best ones (`coursier_switch` thresholds 9, 11, 13, 15, then their neighbors), simulated. Several minutes and noisier, same model.

## Your own horse (`--horse-file`)

Any horse can be added from one reading of the in-game simulator (Horse info → Growth simulator), taken at horse level 1–30 with no skills toggled and a Training level where "no skill" is above 0%. Write a CSV like [tests/data/sim_mythical_dine_artisan7.csv](../tests/data/sim_mythical_dine_artisan7.csv):

```
# name: My horse
# training: Artisan 7
# boosts: none
# tier: 10
# type: 6
# innate: Sprint
none,10.7826
Ruade,15.1844
...
```

`tier` (e.g. `8` or `T8`) sets the default target set (courser for a T8) and is shown; `type` (the in-game type) is shown; `innate` lists the skills shown as innate ("base skill"). `boosts` is `none`, `gear`, `brand` or `both` (`boxes` is also accepted). The older `learned` header lists the skills shown as innate or toggled at the reading (both headers take them out of the draw). Skill names in English or French.

**Special horses** (extra innate skills, e.g. a T8 born with Instant Accel): `--innate "Instant Accel"` on a known horse takes those skills out of its draw and counts them as innate, keeping its 'no skill' weight. That matches most special T8s read so far (the T8 Type 11 reading is `T8 Type 5 --innate "Instant Accel"` to 0.0002 points), but not all: a special Type 4 born with S: Sideways also had Two-seater and another 'no skill' weight. So check it once with a simulator reading at level 1, no boosts: `--innate ... --check none=17.15 Ruade=13.1 ...` (exit 1 on a mismatch: then use `--horse-file`).

Exit codes: `0` OK · `1` `--check` mismatch · `2` bad input (unknown horse, skill, strategy or Training level).
