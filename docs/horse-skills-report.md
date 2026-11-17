# Horse skills: how they're learned, and how to get the ones you want

Report of 2026-11-17. It explains how a horse picks a skill when it levels up, checks that against the game, and simulates the usual ways of leveling a horse, so you can skip straight to the conclusions.

Everything here can be reproduced with [horse_skills.py](horse_skills.md), a command-line tool in this repo (commands at the end). The tool can also run the same simulations for your own horse and Training level. The horse data it uses (each skill's weight, explained below) is in [data/horse_skills.json](../data/horse_skills.json).

## Terms used

- **Learn-chance boosts:** the two items that raise a horse's chance of learning a skill. Each adds +10%:
  - the **horse gear set:** any 4 Pearl Shop horse gear pieces worn together, from any set;
  - the **Mount Brand Spell Stone**, applied to the horse.
- **a/b/c:** most results are given as three numbers: **a** = no boost, **b** = one boost (the gear set *or* the brand stone, they're equal), **c** = both boosts.
- **Coupon:** a Mount Skill Change Coupon. It replaces a learned skill with a random unlearned one, and you can mark one skill as **desired** to make it more likely.
  - Each coupon used gives the horse a **Skill Change Point**, and points make the desired skill more likely still.
  - Innate skills (the ones the horse is born with) can't be swapped.
- **Ticket:** a Mount Level Down Ticket. It undoes a level-up so it can be redone.
- **Travel set:** the skills this report counts as wanted, mainly for getting around (full list and reasons in [The travel set](#the-travel-set)). **Full set:** ending at level 30 with every skill of the travel set.
- **Leveling strategies** compared (details in [Strategies](#strategies)):
  - **Natural:** level 1 to 30 without coupons.
  - **All at 30:** level naturally, then at level 30 swap every skill outside the travel set until a travel-set skill comes out, while coupons last. That last step is called the **level-30 cleanup**.
  - **Coursier:** the classic "coursier method": each time the horse learns Hind Kick or Fore Chop, swap it right away, but keep 5 coupons (the **reserve**) for the level-30 cleanup.
  - **Hard:** swap every unwanted skill as soon as it's learned, and keep swapping until a travel-set skill comes out (same reserve).

## Conclusions

1. **Use the coursier method, keeping 5 coupons for level 30.**
   - With 10 coupons or fewer, it's about as good as keeping them all for level 30, within a few percentage points either way.
   - From 15–20 coupons, it's much better. For example, a Mythical Diné at Training Artisan 7 with 30 coupons ends with the full set 90% of the time, against 62% with All at 30.
2. **Don't use the Hard strategy.** It's the worst of the coupon strategies at every Training level. Most swaps land on common skills, so the coupons run out halfway through leveling.
3. **Each learn-chance boost adds about half a skill** at Training Professional–Artisan, a third of a skill at Master 20, and almost nothing at Guru 20.
   - With coupons, a boost raises the chance of the full set by a few percentage points.
   - Compared with simply having more coupons (Mythical Diné, Artisan 7, Coursier): with 20 coupons, one boost helps about as much as 1–2 extra coupons; with 30 coupons, as much as about 6 extra. At 30 coupons, though, both only add a few points, since you're already near 90%.
4. **Training level matters more than the boosts:** going from Professional 10 to Guru 20 adds about 2 skills by level 30. Tickets help too: 4 tickets add about 0.7 skill.
5. **How many skills to expect at level 30 without coupons** (Artisan 7, no boost): about 16 of the 20 learnable skills for a Mythical Diné, 17 of 21 for a T9 Doom, and 14 of 19 for the T8 that was checked.

## How a level-up picks a skill

**In short:** each level-up is a single draw with one outcome: one skill, or nothing. It's not a separate roll for each skill; the game's own numbers rule that out ([How this was checked](#how-this-was-checked)).
- Every skill has a fixed **weight** for each horse type. Common skills like Hind Kick have big weights; rare ones like S: Sideways have tiny ones.
- **The chance of learning anything at all depends on how much weight the unlearned skills still add up to.** A fresh horse learns something on most level-ups. Once the common skills are learned, only small weights are left, and most level-ups teach nothing.
- That's why the Coursier method works. Swapping Hind Kick away puts its big weight back into the draw, so later level-ups keep teaching something. And each time the horse relearns Hind Kick, that's one more coupon draw, which can't give Hind Kick back and favors the skill you want.
- Your Training level and the boosts raise every skill's chance in the same proportion.
- The horse's own level doesn't matter: a level-up at 25 has the same odds as one at 5, for the same learned skills.

**The formula**, for each skill the horse hasn't learned yet:

    chance of skill i = M × wᵢ / (Σ w of the unlearned skills + W)
    chance of nothing = 1 − (sum of the chances above)

- **wᵢ** is the skill's weight for that horse. Databases such as the [bdolytics horse skills page](https://bdolytics.com/en/training/horse-skills) list it as "learn chance". Skills listed at 100% are innate.
- **W** is the horse's "no skill" weight.
  - For the Mythical Diné and the T9 Doom, W = 100 − (sum of all the horse's weights).
  - For the T8 checked, W is 39.2 instead of the 33.0 that rule gives. So W has to be read from the in-game simulator (next section) for each horse.
- **M = 1 + Training bonus + 0.10 per learn-chance boost.** It's the same for every tier.
  - The Training bonus by level comes from a [community sheet](https://docs.google.com/spreadsheets/d/1erIfp07xnYWG6N0HYPjWiBRCuncOa0x0si_-3XiZHyI), for example Professional 10 = 16.8%, Artisan 7 = 21.7%, Master 10 = 31.4%, Master 20 = 44.1%, Guru 20 and up = 100%.
  - Example: Artisan 7 with both boosts gives M = 1 + 0.217 + 0.2 = 1.417.
- **Cap:** if the skill chances would add up to more than 100%, they're scaled down to exactly 100%, and "nothing" becomes 0%.
  - A fresh Mythical Diné reaches the cap once the Training bonus plus boosts reach 36.4%, for example at Master 14, or at Artisan 7 with both boosts.
  - The cap is why boosts matter less at high Training levels: early level-ups already can't fail.
- **Sprint** was innate on every horse checked, although bdolytics lists a weight for it.

**Coupons:** the new skill is drawn among the unlearned skills, minus the one removed, using the same weights. The desired skill's weight is multiplied by (1 + 0.25 × Skill Change Points).
- The ×1.25 at 1 point was read in the game's coupon window.
- Two things are **assumptions**, and they have a large effect (see [Limits](#limits)): that the bonus grows by +0.25 for each further point, and that points only reset when a horse is awakened into a Mythical.

### How this was checked

The game has a **growth simulator** (Horse info → Growth simulator). For any horse, Training level and boosts, it shows the chance of each skill and of "nothing" on the next level-up. You can also toggle skills as learned.

The formula was compared with what the simulator shows on 2026-11-17:
- **Weights:** taken from bdolytics and stored in `data/horse_skills.json`.
- **W:** fitted to the simulator for each horse checked.
- **Result:** every number below matches, within the rounding of bdolytics' weights (0.01).
- **One draw, not one roll per skill:** the simulator's chances, "nothing" included, always add up to 100%, and "nothing" drops to exactly 0% at the cap. With a separate roll per skill, the Diné at Artisan 7 would get nothing 39.5% of the time at the chances shown, not 10.8%. Even tuned to give 10.8%, separate rolls would put Hind Kick at 16.2% instead of the 15.2% shown.

| Horse | Simulator settings compared | Numbers compared |
|---|---|---|
| Mythical Diné | Artisan 7, Professional 10, Master 20, Guru 57; brand stone only; both boosts (cap); one skill toggled as learned | all 20 skills and "nothing" at Artisan 7; 2–8 numbers for each other setting |
| T9 Doom | Artisan 7 | all 21 skills and "nothing". Its weights equal bdolytics' Mythical Doom row (bdolytics' T9 Doom row shows every skill at 100%) |
| T8, one coat | Artisan 7, Professional 10, gear set | 7 skills and "nothing" for each |
| Mythical Diné, coupon window | 1 Skill Change Point, desired skill Instant Accel | the 8 draw chances shown |

The Mythical Arduanatt and Voltarion in the data file use bdolytics' weights with W = 100 − (sum of weights). That hasn't been checked. Other T8 coats have different weights (bdolytics lists 11 T8 rows), so the T8 results here are only an example.

## Strategies

- **Natural:** no coupons.
- **All at 30:** level naturally. Then the level-30 cleanup: swap each skill outside the travel set, and keep swapping the same slot until a travel-set skill comes out, while coupons last.
- **Coursier:**
  - Each time the horse learns Hind Kick or Fore Chop (the two most common skills), swap it right away, as long as more than 5 coupons are left. Then do the level-30 cleanup with what's left.
  - Why it works: swapping a common skill puts a big weight back into the draw, which keeps later level-ups productive. The horse also often relearns it, which gives another swap.
- **Hard:** swap every skill outside the travel set as soon as it's learned, and keep swapping until a travel-set skill comes out, keeping the same 5-coupon reserve. Then the level-30 cleanup.
- **Ideal:** an upper bound, not a real strategy: unlimited coupons, used so that the horse always holds the rarest skills.

In every strategy, the coupon's desired skill is the rarest travel-set skill the horse is still missing. Tickets are used on level-ups that teach nothing. The results below use no tickets unless stated.

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

Simulated from level 1 to 30, 4,000 runs per number, random seed 1. Remember that **a/b/c** = no boost / one boost / both boosts.

**Skills at level 30 with natural leveling** (no coupons, no tickets). "Of N" = number of skills the horse can learn; innate skills aren't counted.

| Training | Mythical Diné (of 20) | T9 Doom (of 21) | T8 example (of 19) |
|---|---|---|---|
| Professional 10 | 15.6/16.1/16.5 | 16.9/17.4/17.8 | 13.7/14.2/14.7 |
| Artisan 7 | 15.8/16.3/16.7 | 17.1/17.6/17.9 | 13.9/14.4/14.9 |
| Master 10 | 16.3/16.6/16.9 | 17.6/17.9/18.1 | 14.4/14.9/15.3 |
| Master 20 | 16.7/17.0/17.2 | 18.0/18.2/18.4 | 15.0/15.3/15.6 |
| Guru 20 | 17.8/17.9/18.0 | 18.8/18.9/19.0 | 16.4/16.6/16.7 |

**Chance of ending with the full set**, by strategy and number of coupons.

Mythical Diné (travel set: 13 skills):

| Training | All at 30, 10 coupons | Coursier, 10 coupons | All at 30, 30 coupons | Coursier, 30 coupons | Hard, 30 coupons |
|---|---|---|---|---|---|
| Professional 10 | 10%/13%/18% | 9%/13%/16% | 58%/66%/72% | 85%/93%/96% | 48%/53%/59% |
| Artisan 7 | 11%/16%/19% | 12%/16%/20% | 62%/70%/73% | 90%/94%/97% | 52%/58%/62% |
| Master 10 | 16%/19%/25% | 15%/19%/24% | 68%/73%/77% | 95%/97%/98% | 57%/61%/66% |
| Master 20 | 20%/26%/29% | 22%/25%/28% | 75%/77%/80% | 98%/98%/99% | 62%/65%/69% |
| Guru 20 | 42%/44%/49% | 38%/42%/45% | 87%/89%/89% | 100%/100%/100% | 74%/77%/78% |

T9 Doom (travel set: 13 skills):

| Training | All at 30, 10 coupons | Coursier, 10 coupons | All at 30, 30 coupons | Coursier, 30 coupons | Hard, 30 coupons |
|---|---|---|---|---|---|
| Professional 10 | 8%/12%/15% | 7%/10%/14% | 48%/54%/60% | 88%/93%/95% | 33%/41%/45% |
| Artisan 7 | 9%/14%/17% | 9%/12%/16% | 52%/57%/62% | 91%/94%/95% | 37%/44%/48% |
| Master 10 | 14%/17%/20% | 12%/17%/20% | 59%/61%/66% | 94%/95%/96% | 45%/49%/50% |
| Master 20 | 17%/22%/26% | 18%/20%/22% | 63%/68%/69% | 95%/97%/98% | 47%/52%/54% |
| Guru 20 | 37%/40%/42% | 35%/36%/37% | 78%/78%/80% | 99%/100%/100% | 63%/65%/67% |

T8 example (travel set: 12 skills):

| Training | All at 30, 10 coupons | Coursier, 10 coupons | All at 30, 30 coupons | Coursier, 30 coupons | Hard, 30 coupons |
|---|---|---|---|---|---|
| Professional 10 | 13%/17%/22% | 12%/17%/22% | 72%/78%/83% | 86%/91%/94% | 65%/70%/73% |
| Artisan 7 | 15%/19%/24% | 14%/20%/25% | 75%/81%/85% | 89%/91%/95% | 69%/73%/76% |
| Master 10 | 19%/23%/30% | 19%/25%/29% | 81%/84%/88% | 93%/95%/97% | 72%/76%/80% |
| Master 20 | 26%/31%/35% | 27%/31%/36% | 86%/88%/90% | 96%/97%/98% | 76%/81%/83% |
| Guru 20 | 51%/54%/57% | 50%/53%/54% | 94%/95%/96% | 100%/100%/100% | 89%/89%/90% |

**How many coupons do you need?** Mythical Diné, Artisan 7, chance of the full set:

| Coupons | 5 | 10 | 15 | 20 | 25 | 30 | 40 |
|---|---|---|---|---|---|---|---|
| All at 30 | 4%/7%/10% | 11%/16%/19% | 22%/27%/33% | 34%/43%/48% | 49%/56%/62% | 62%/70%/73% | 82%/85%/89% |
| Coursier | 4%/7%/10% | 12%/16%/20% | 28%/35%/39% | 56%/62%/70% | 79%/86%/89% | 90%/94%/97% | 97%/99%/100% |

With only 5 coupons, Coursier is the same as All at 30, because all 5 are kept in reserve.

## Limits

- **The coupon's desired-skill bonus is the biggest unknown** (see [Coupons](#how-a-level-up-picks-a-skill)).
  - If marking a skill as desired did nothing at all, the Mythical Diné at Artisan 7 with 30 coupons and no boost would drop from 90% to 63% (Coursier), from 62% to 19% (All at 30), and from 52% to 14% (Hard).
  - The ranking of the strategies stays the same.
- **Tickets:** with 4 Mount Level Down Tickets, natural leveling ends with 0.7 more skills (16.5 instead of 15.8), and Coursier with 30 coupons reaches the full set 96% of the time instead of 90% (Mythical Diné, Artisan 7, no boost).
- **Rounding:** bdolytics rounds weights to 0.01, so the tool's chances can be off by up to about 0.005 points per skill, and "nothing" by up to about 0.05.
- **The game can change.** To check your horse, run `horse_skills.py` with `--check` and numbers read in the in-game simulator. If they don't match, add your horse from one simulator reading (`--horse-file`, see [the tool's doc](horse_skills.md)).
- **Simulation noise:** about ±1–2 percentage points.

## Reproduce

```
python3 -I horse_skills.py "Mythical Diné" --training "Artisan 7" --runs 4000 --sweep 10,30
python3 -I horse_skills.py "Mythical Diné" --training "Artisan 7" --runs 4000 --strategy natural,ideal
python3 -I horse_skills.py "Mythical Diné" --training "Artisan 7" --runs 4000 --sweep 5,10,15,20,25,30,40 --strategy at30,coursier
python3 -I horse_skills.py "Mythical Diné" --training "Artisan 7" --runs 4000 --point-bonus 0
python3 -I horse_skills.py "Mythical Diné" --training "Artisan 7" --runs 4000 --tickets 4
```

Use `"Doom (T9)"` or `"T8 example (bdolytics icon horse_71)"` for the other horses, and other `--training` values for the other rows. With the default seed, these commands give exactly the numbers in the tables.

## Sources

- **Skill weights:** [bdolytics horse skills](https://bdolytics.com/en/training/horse-skills), read 2026-11-17 (T8, T9 and T10 tabs). The source and date of each horse are in `data/horse_skills.json`.
- **Training bonus by level:** [community sheet](https://docs.google.com/spreadsheets/d/1erIfp07xnYWG6N0HYPjWiBRCuncOa0x0si_-3XiZHyI). Professional 10 and Artisan 7 were confirmed in-game.
- **Everything else:** the in-game growth simulator and the coupon window, read 2026-11-17.
