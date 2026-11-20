# Horse skills: how they're learned, and how to get the ones you want

Report of 2026-11-18. **Outdated draft:** its numbers were computed before the Skill Change Points reset was known (points go back to 0 when a coupon gives the desired skill, seen in-game on 2026-11-19); the tool includes the reset since 2026-11-20 and a new report will replace this one. It explains how a horse picks a skill when it levels up, checks that against the game, and compares ways of using Mount Skill Change Coupons, so you can skip straight to the conclusions.

Everything here can be reproduced with [horse_skills.py](horse_skills.md), a command-line tool in this repo (commands at the end). It also finds the best plan for your own horse, Training level and coupons. The horse data it uses (each skill's weight, explained below) is in [data/horse_skills.json](../data/horse_skills.json).

## Terms used

- **Learn-chance boosts:** the two items that raise a horse's chance of learning a skill, +10% each:
  - the **horse gear set:** any 4 Pearl Shop horse gear pieces worn together, from any set;
  - the **Mount Brand Spell Stone**, applied to the horse.
- **a/b/c:** some results are given as three numbers: **a** = no boost, **b** = one boost (the gear set *or* the brand stone, they're equal), **c** = both boosts.
- **Coupon:** a Mount Skill Change Coupon. It replaces one learned skill with a random unlearned one. You mark one skill as **desired** to make it more likely.
  - Each coupon used gives the horse a **Skill Change Point**, and points make the desired skill more likely still. A coupon that gives the desired skill sets the points back to 0.
  - Innate skills (the ones the horse is born with) can't be swapped.
- **Ticket:** a Mount Level Down Ticket. It undoes a level-up so it can be redone.
- **Travel set:** the skills this report counts as wanted, mainly for getting around (list and reasons in [The travel set](#the-travel-set)). **Full set:** ending at level 30 with every skill of the travel set.
- **Level-30 cleanup:** at level 30, using the coupons left to replace skills outside the travel set, until the travel set is complete or coupons run out.
- **Leveling strategies** (details in [Strategies](#strategies)):
  - **All at 30:** level without coupons, keep them all for the level-30 cleanup.
  - **Coursier:** the classic "coursier method": each time the horse learns Hind Kick or Fore Chop (the two most common skills), swap it right away.
  - **Coursier V2:** the same, but **only swap Hind Kick, never Fore Chop**.
- **Plan:** a strategy plus the level at which you start swapping, and how many coupons you keep for the level-30 cleanup.

## Conclusions

1. **Use Coursier V2: each time the horse learns Hind Kick, swap it; never swap Fore Chop.**
   - It needs far fewer coupons than the classic Coursier or keeping them all for level 30. For a fresh Mythical Diné at Training Artisan 7, a 90% chance of the full set takes 18 coupons, against 22 with the classic Coursier and 31 with All at 30.
   - Why: in the classic Coursier, swapping Fore Chop often draws Hind Kick straight back, and the other way round, so many coupons go round in circles. Keeping Fore Chop learned stops that.
2. **Start swapping at about level 29 − 1.5 × your coupons:** level 22 with 5 coupons, level 14 with 10, level 7 with 15. With about 18–20 coupons, start right away (level 2–5).
   - Across the five horses and Training levels tested, this single rule loses at most 0.6 percentage points of chance against each case's own best plan, up to 18 coupons.
   - From about 25 coupons, the classic Coursier is as good, and slightly better on the T8 example.
3. **At level 30, swap your rarest unwanted skill first, and mark your rarest missing skill as desired.** Common skills such as Hind Kick stay learned until last, so they don't come back in the next coupon draws. Trying every other choice gains nothing measurable.
4. **Training level and boosts save coupons.** For a 90% chance of the full set on a Mythical Diné:
   - Artisan 7: 18 coupons with no boost, 14 with one boost, 11 with both.
   - Guru 20: 4 coupons.
5. **Re-deciding the plan as you level doesn't help with Coursier V2.** Choosing the best plan again at levels 10, 15, 20 and 25, from what the horse actually learned, changed the chance by −0.1 points (±0.7). With the classic Coursier it gained +3.7 points, mostly by limiting its coupon losses. So pick the plan at the start; re-running the tool later only matters if something changes, such as getting more coupons.
6. **How many skills to expect at level 30 without coupons** (Artisan 7, no boost): about 16 of the 20 learnable skills for a Mythical Diné, 17 of 21 for a T9 Doom, and 14 of 19 for the T8 that was checked. With unlimited coupons, a horse can end with nearly all of them.

## How a level-up picks a skill

**In short:** each level-up is a single draw with one outcome: one skill, or nothing. It's not a separate roll for each skill; the game's own numbers rule that out ([How this was checked](#how-this-was-checked)).
- Every skill has a fixed **weight** for each horse type. Common skills like Hind Kick have big weights; rare ones like S: Sideways have tiny ones.
- **The chance of learning anything at all depends on how much weight the unlearned skills still add up to.** A fresh horse learns something on most level-ups. Once the common skills are learned, only small weights are left, and most level-ups teach nothing.
- That's why the Coursier methods work. Swapping Hind Kick away puts its big weight back into the draw, so later level-ups keep teaching something. And each time the horse relearns Hind Kick, that's one more coupon draw, which can't give Hind Kick back and favors the skill you want.
- Your Training level and the boosts raise every skill's chance in the same proportion.
- The horse's own level doesn't matter: a level-up at 25 has the same odds as one at 5, for the same learned skills.

**The formula**, for each skill the horse hasn't learned yet:

    chance of skill i = M × wᵢ / (Σ w of the unlearned skills + W)
    chance of nothing = 1 − (sum of the chances above)

- **wᵢ** is the skill's weight for that horse. Databases such as the [bdolytics horse skills page](https://bdolytics.com/en/training/horse-skills) list it as "learn chance", rounded to 0.01. Skills listed at 100% are innate.
- **W** is the horse's "no skill" weight.
  - For the Mythical Diné and the T9 Doom, W = 100 − (sum of all the horse's weights).
  - For the T8 checked, W is 39.2 instead of the 33.0 that rule gives. So W has to be read from the in-game simulator (next section) for each horse.
- **M = 1 + Training bonus + 0.10 per learn-chance boost.** It's the same for every tier.
  - The Training bonus by level comes from a [community sheet](https://docs.google.com/spreadsheets/d/1erIfp07xnYWG6N0HYPjWiBRCuncOa0x0si_-3XiZHyI), for example Professional 10 = 16.8%, Artisan 7 = 21.7%, Master 10 = 31.4%, Master 20 = 44.1%, Guru 20 and up = 100%.
  - Example: Artisan 7 with both boosts gives M = 1 + 0.217 + 0.2 = 1.417.
- **Cap:** if the skill chances would add up to more than 100%, they're scaled down to exactly 100%, and "nothing" becomes 0%. A fresh Mythical Diné reaches the cap once the Training bonus plus boosts reach 36.4%, for example at Master 14, or at Artisan 7 with both boosts.
- **Sprint** was innate on every horse checked, although bdolytics lists a weight for it.

**Coupons:** the new skill is drawn among the unlearned skills, minus the one removed, using the same weights. The desired skill's weight is multiplied by (1 + 0.25 × Skill Change Points): ×1.25 at 1 point and ×1.5 at 2 points, both read in the game's coupon window. Further points are assumed to keep adding 0.25 each. A coupon that gives the desired skill sets the points back to 0 (seen in-game on 2026-11-19; the numbers in this draft assume no reset, see [Limits](#limits)).

### How this was checked

The game has a **growth simulator** (Horse info → Growth simulator). For any horse, Training level and boosts, it shows the chance of each skill and of "nothing" on the next level-up. You can also toggle skills as learned. The **coupon window** shows the chance of each skill for the next coupon.

The formula was compared with what the game showed on 2026-11-17 and 18:
- **Weights:** taken from bdolytics and stored in `data/horse_skills.json`. For the Mythical Diné, they were refined to 4 decimals from an in-game reading; every refined value is within bdolytics' rounding.
- **W:** fitted to the simulator for each horse checked.
- **Result:** every number below matches, within the rounding of the weights.

| Horse | What was compared | Numbers compared |
|---|---|---|
| Mythical Diné | Simulator at Artisan 7, Professional 10, Master 20, Guru 57; brand stone only; both boosts (cap); one skill toggled as learned | all 20 skills and "nothing" at Artisan 7; 2–8 numbers for each other setting |
| T9 Doom | Simulator at Artisan 7 | all 21 skills and "nothing". Its weights equal bdolytics' Mythical Doom row |
| T8, one coat | Simulator at Artisan 7, Professional 10, gear set | 7 skills and "nothing" for each |
| Mythical Diné | Coupon window at 1 point (desired Instant Accel) and 2 points (desired S: Sideways) | 8 chances each; at 2 points every value within 0.0001 point |

- **One draw, not one roll per skill:** the simulator's chances, "nothing" included, always add up to 100%, and "nothing" drops to exactly 0% at the cap. With a separate roll per skill, the Diné at Artisan 7 would get nothing 39.5% of the time at the chances shown, not 10.8%.

The Mythical Arduanatt and Voltarion in the data file use bdolytics' weights with W = 100 − (sum of weights). That hasn't been checked. Other T8 coats have different weights (bdolytics lists 11 T8 rows), so the T8 results here are only an example.

## Strategies

- **All at 30:** no coupons while leveling, then the level-30 cleanup.
- **Coursier:** each time the horse learns Hind Kick or Fore Chop, swap it. Then the level-30 cleanup.
- **Coursier V2:** each time the horse learns Hind Kick, swap it; keep Fore Chop. Then the level-30 cleanup.
  - V2 swaps the heavier of the two attack skills (Hind Kick on every horse checked; on the T8 both weigh the same). Swapping Fore Chop instead costs 2–6 points of chance on the Diné and the Doom.
  - Also swapping each other unwanted skill once when learned was tested and is worse (−1 to −12 points).
- **The level-30 cleanup,** in every strategy: swap the rarest unwanted skill held, with the rarest missing travel-set skill as the desired one, until the travel set is complete or coupons run out.
  - Swapping the rarest first matters: a swapped-away skill goes back into the draw, so swapping Hind Kick first makes the next coupons likely to land on it again.
  - An exact calculation that tried every possible choice of skill to swap and of desired skill, at every step, found no measurable gain for the full set (at most 0.03 points).
- **Swap once** and **Hard** (swap every unwanted skill once, or until a wanted one comes) never beat the best Coursier plan in earlier searches, at most tying it in easy cases. The tool still offers them.
- **Ideal:** unlimited coupons, used so that the horse always holds the rarest skills. It shows the most skills a horse can reach.

A plan also says **when to start swapping** and **how many coupons to keep** for the cleanup. Coupons are only spent while leveling from the start level on, and never below the number kept. Tickets are used on level-ups that teach nothing.

### The travel set

- **In the set:** Sprint, Instant Accel, S: Instant Accel, Drift, High Jump, Streak Leap, Start Accel, Quick Ride, Charge, Sideways, S: Sideways, Quick Back, Quick Stop.
- **Also in the set:** each Dream horse's own learnable skills: Earth of Protection (Diné), Wings of Freedom (Arduanatt), Dark Sprint (Doom), and Voltarion's Lightning Charge, Instant Accel: Flash, Drift: Flash and Thunderfall.
- **Size per horse:** Sprint is innate, so the set is 13 skills for the Mythical Diné and the T9 Doom, and 12 for the T8.
- **Left out:**
  - Hind Kick, Fore Chop, S: Hind Kick, S: Fore Chop: attacks for mounted combat.
  - Roar: HP/MP regeneration while standing still.
  - Caution: stops the horse from running off ledges. Many riders find it gets in the way.
  - S: Charge: a stronger, repeatable Charge for combat. Doom riders may still want it, since Dark Sprint can follow S: Charge as well as S: Instant Accel.
  - Two-seater (Doom and some T8 horses): carries a passenger.
- **To use another list:** `--wanted`.

## Results

Five cases, from the hardest to the easiest:

| Case | Horse | Training | Boosts |
|---|---|---|---|
| F1 | T8 example | Professional 10 | none |
| F2 | Mythical Diné | Artisan 7 | none |
| F3 | T9 Doom | Artisan 7 | none |
| F5 | Mythical Diné | Artisan 7 | both |
| F6 | Mythical Diné | Guru 20 | none |

Numbers come from the tool's search: every plan (each strategy, every start level from 2 to 29, every number of coupons kept), 1,000 simulated horses each, then the best ones again with 4,000 fresh horses. The level-30 cleanup is computed exactly rather than simulated.

**Coupons needed for a 50% / 90% chance of the full set**, with the best plan of each strategy:

| Case | All at 30 | Coursier | **Coursier V2** |
|---|---|---|---|
| F1 T8, Professional 10 | 16 / over 40 | 14 / **25** | **13** / 28 |
| F2 Diné, Artisan 7 | 14 / 31 | 12 / 22 | **9 / 18** |
| F3 Doom, Artisan 7 | 15 / 30 | 11 / 21 | **6 / 12** |
| F5 Diné, Artisan 7, both boosts | 11 / 24 | 9 / 17 | **5 / 11** |
| F6 Diné, Guru 20 | 6 / 16 | 2 / 9 | **2 / 4** |

**Best plans for the Diné at Artisan 7 (F2).** Several plans are usually tied with the best (within 1 point), so ranges are shown:

| Coupons | Chance of the full set | Tied plans | All at 30 |
|---|---|---|---|
| 5 | 25% | Coursier V2, start at level 22–23 | 11% |
| 10 | 63% | Coursier V2, start at level 10–16 | 32% |
| 15 | 84% | Coursier V2, start at level 2–12 | 54% |
| 20 | 93% | Coursier V2, start at level 2–13 | 71% |
| 25 | 97% | Coursier V2, start at level 2–15 | 83% |
| 30 | 99% | Coursier V2 (start at level 2–17) or Coursier (start at level 2–13) | 90% |

With Coursier V2, the number of coupons kept for level 30 hardly matters: V2 only spends when the horse holds Hind Kick, so its spending stays moderate on its own.

**One rule for everyone.** For each budget, the single plan with the smallest worst-case loss across F1, F2, F3, F5 and F6. The loss is that case's best chance minus this plan's chance, in percentage points. It was then tested on a sixth case it wasn't chosen with: a Mythical Diné at Artisan 7, already level 2 with High Jump, 1 point and 4 tickets.

| Coupons | Plan | Worst loss | Average loss | Loss on the sixth case | All at 30: worst / average loss |
|---|---|---|---|---|---|
| 5 | Coursier V2 from level 22 | 0.4 | 0.0 | 0.1 | 50 / 26 |
| 8 | Coursier V2 from level 17 | 0.5 | 0.2 | 2.2 | 50 / 32 |
| 10 | Coursier V2 from level 14 | 0.6 | 0.2 | 1.3 | 52 / 32 |
| 12 | Coursier V2 from level 11 | 0.3 | 0.1 | 0.4 | 50 / 30 |
| 15 | Coursier V2 from level 7 | 0.1 | 0.0 | 0.1 | 42 / 24 |
| 20 | Coursier V2 from level 5 | 1.4 | 0.3 | 0.1 | 27 / 16 |
| 25 | Coursier from level 16, keep 8 | 2.7 | 1.6 | 1.1 | 16 / 11 |
| 30 | Coursier from level 12, keep 10 | 0.8 | 0.4 | 0.2 | 12 / 7 |

**Skills at level 30 without coupons, and with unlimited coupons** (a/b/c = no boost / one boost / both). "Of N" = number of skills the horse can learn; innate skills aren't counted.

| Training | Diné (of 20): no coupons | Diné: unlimited | Doom (of 21): no coupons | Doom: unlimited | T8 (of 19): no coupons | T8: unlimited |
|---|---|---|---|---|---|---|
| Professional 10 | 15.5/16.0/16.5 | 19.6/19.9/20.0 | 16.9/17.4/17.8 | 20.9/21.0/21.0 | 13.7/14.2/14.7 | 17.2/17.9/18.4 |
| Artisan 7 | 15.8/16.3/16.6 | 19.8/19.9/20.0 | 17.1/17.6/17.9 | 21.0/21.0/21.0 | 13.9/14.4/14.9 | 17.5/18.1/18.5 |
| Master 10 | 16.3/16.6/16.9 | 19.9/20.0/20.0 | 17.6/17.9/18.1 | 21.0/21.0/21.0 | 14.4/14.9/15.3 | 18.1/18.5/18.8 |
| Master 20 | 16.7/17.0/17.2 | 20.0/20.0/20.0 | 18.0/18.2/18.4 | 21.0/21.0/21.0 | 15.0/15.3/15.6 | 18.6/18.8/18.9 |
| Guru 20 | 17.8/17.9/17.9 | 20.0/20.0/20.0 | 18.8/18.9/19.0 | 21.0/21.0/21.0 | 16.4/16.6/16.7 | 19.0/19.0/19.0 |

**Re-deciding the plan during leveling.** Each simulated horse was played twice with the same random numbers: once with the best plan chosen at level 1, once choosing the best plan again at levels 10, 15, 20 and 25 from what it had actually learned. Fresh Mythical Diné, Artisan 7:

| Strategies available | Coupons | Horses | Fixed plan | Re-planned | Gain |
|---|---|---|---|---|---|
| All at 30, Coursier, Swap once, Hard | 15 | 1,200 | 66.2% | 69.8% | +3.7 points (±1.4) |
| All at 30, Coursier, Coursier V2 | 10 | 1,200 | 62.5% | 62.3% | −0.1 points (±0.7) |

## Limits

- **The Skill Change Point bonus beyond 2 points is assumed** to keep growing by +0.25 per point (checked at 1 and 2). The points do reset when a coupon gives the desired skill (seen in-game after this draft); this draft's numbers assume they don't, the tool includes the reset. The bonus matters a lot: without it, the chances of the full set drop sharply.
- **Weights are rounded:** bdolytics rounds to 0.01, which is a few percent for the rarest skills. The Diné's weights were refined from an in-game reading; the Doom's and the T8's weren't.
- **Plans are fixed at level 1.** The tool doesn't follow your horse level by level, but you can run it again from your horse's current state (`--level`, `--learned`, `--points`, `--tickets`).
- **Not modelled:** the Mount Skill Selection Coupon (one guaranteed skill per horse, 3,100 Pearls). It would help most at level 30 on the last rare skill, as long as the horse holds an unwanted skill to replace.
- **Simulation noise:** about ±1 point in the tables; differences under 1 point between plans aren't meaningful. In one re-planning run, a first batch of horses showed −1.7 points by chance; repeated on new horses, it gave −0.1 (scripts on the work branch).
- **The game can change.** To check your horse, run `horse_skills.py` with `--check` and numbers read in the in-game simulator. If they don't match, add your horse from one simulator reading (`--horse-file`, see [the tool's doc](horse_skills.md)).

## Reproduce

The fast engine needs numba (`pip install -r requirements-optional.txt`); without it, the same commands run in plain Python, more slowly.

```
python3 -I horse_skills.py "Mythical Diné" --training "Artisan 7" --optimize 40
python3 -I horse_skills.py "Mythical Diné" --training "Artisan 7" --gear --brand --optimize 40
python3 -I horse_skills.py "Mythical Diné" --training "Guru 20" --optimize 40
python3 -I horse_skills.py "Doom (T9)" --training "Artisan 7" --optimize 40
python3 -I horse_skills.py "T8 example (bdolytics icon horse_71)" --training "Professional 10" --optimize 40
python3 -I horse_skills.py "Mythical Diné" --training "Artisan 7" --runs 4000 --strategy natural,ideal
```

The comparison with the classic Coursier and All at 30, the one-rule table, the cleanup check and the re-planning runs used the analysis scripts in `wip/horse-skills/` on the `horse-skills-wip` branch.

## Sources

- **Skill weights:** [bdolytics horse skills](https://bdolytics.com/en/training/horse-skills), read 2026-11-17 (T8, T9 and T10 tabs). The source and date of each horse are in `data/horse_skills.json`.
- **Training bonus by level:** [community sheet](https://docs.google.com/spreadsheets/d/1erIfp07xnYWG6N0HYPjWiBRCuncOa0x0si_-3XiZHyI). Professional 10 and Artisan 7 were confirmed in-game.
- **Everything else:** the in-game growth simulator and the coupon window, read 2026-11-17 and 18.
