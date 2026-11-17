# Horse skills: how they're learned, and how to get the ones you want

Report of 2026-11-17. It explains how a horse picks a skill when it levels up, checks that against the game, and simulates the usual leveling strategies, so you can skip straight to the conclusions. Numbers are reproducible with [horse_skills.py](horse_skills.md) (commands at the end).

## Conclusions

1. **Use the coursier method, but keep about 5 coupons for level 30.** Swap Hind Kick and Fore Chop each time they're learned, then spend what's left at level 30 on unwanted skills. With 10 coupons or fewer it's about as good as keeping them all for level 30 (within a few points either way). From about 15–20 coupons it's much better: 90% vs 62% chance of the full travel set with 30 coupons (Mythical Diné, Artisan 7).
2. **Don't "go hard"** (re-swapping every unwanted skill until a wanted one comes out). It's the worst coupon strategy at every Training level: most draws land on common skills, so coupons run out mid-leveling.
3. **The horse gear set and the Mount Brand Spell Stone are each worth about half a skill at Professional–Artisan**, a third at Master 20, and almost nothing at Guru 20. With coupons, each one adds a few points of chance of the full set. In coupons, each box is worth roughly 1 to 6 coupons at Artisan 7, depending on how many you have. Compare that with what they cost you.
4. **Training level matters more than either box:** Professional 10 → Guru 20 adds about 2 skills from natural leveling. Mount Level Down Tickets add about 0.7 skill for 4 tickets.
5. **How many skills to expect at level 30 without coupons:** about 16 of 20 learnable for a Mythical Diné, 17 of 21 for a Doom (T9), 14 of 19 for the T8 checked (Artisan 7, no boxes).

## How a level-up picks a skill

Each level-up teaches **exactly one skill or nothing**. For every skill the horse hasn't learned yet:

    chance of skill i = M × wᵢ / (Σ w of unlearned skills + W)
    chance of nothing = 1 − Σ chances above

- **wᵢ** is the skill's weight for that horse: the "learn chance" databases list, e.g. the [bdolytics horse skills page](https://bdolytics.com/en/training/horse-skills). Skills listed at 100% are innate.
- **W** is the horse's "no skill" weight. For the Mythical Diné and the Doom checked, W = 100 − Σ of all its weights. For the T8 checked it's 39.2 instead of 33.0, so it has to be read from the in-game simulator for each horse.
- **M = 1 + Training bonus + 0.10 for the horse gear (4 Pearl pieces, any set) + 0.10 for the Mount Brand Spell Stone.** It's the same for every tier. The Training bonus comes from a [community sheet](https://docs.google.com/spreadsheets/d/1erIfp07xnYWG6N0HYPjWiBRCuncOa0x0si_-3XiZHyI): for example Professional 10 = 16.8%, Artisan 7 = 21.7%, Master 10 = 31.4%, Master 20 = 44.1%, Guru 20+ = 100%.
- **Cap:** if the skill chances would add up to more than 100%, they're scaled down to exactly 100%, and "nothing" drops to 0%. A fresh Mythical Diné reaches the cap at a total bonus of 36.4%: Master 14, or Artisan 7 with both boxes.
- **The horse's level doesn't change the odds.** Learning a skill removes its weight from the sum, so every remaining skill becomes slightly more likely, and so does "nothing".
- **Sprint** was innate on every horse checked, although bdolytics lists a weight for it.

**Mount Skill Change Coupon:** the new skill is drawn among the unlearned skills, minus the one removed, with the same weights. The skill you mark as desired gets its weight × (1 + 0.25 × Skill Change Points). The ×1.25 at 1 point was read in-game. That it grows by +0.25 per point, and is never reset except by awakening, is an **assumption**, with a large effect (see Limits).

### What was checked in-game

All with the in-game growth simulator (Horse info → Growth simulator), 2026-11-17. The model reproduces every value within the rounding of the data.

| Horse | Settings | Values |
|---|---|---|
| Mythical Diné | Artisan 7; Professional 10; Master 20; Guru 57; brand stone only; both boxes (cap); one skill learned | all 20 skills + "nothing" at Artisan 7, 2–8 values for each other setting |
| Doom (T9) | Artisan 7 | all 21 skills + "nothing" (same weights as bdolytics' Mythical Doom) |
| T8 (one coat) | Artisan 7; Professional 10; gear box | 7 skills + "nothing" each |
| Mythical Diné, coupon | 1 Skill Change Point, desired Instant Accel | 8 draw chances |

The Mythical Arduanatt and Voltarion use bdolytics' weights with W = 100 − Σ, which hasn't been checked. Other T8 coats have different weights (bdolytics lists 11 T8 rows).

## Strategies compared

- **natural:** no coupons.
- **at30:** level naturally, then at level 30 swap every unwanted skill until a wanted one comes out, while coupons last.
- **coursier:** each time the horse learns Hind Kick or Fore Chop (the most common skills), swap it, keeping a reserve of 5 coupons. Then the at30 cleanup with what's left. Swapping a common skill puts a big weight back in the pool, which keeps later level-ups productive, and the horse often relearns it, which gives another swap.
- **hard:** swap every unwanted skill as soon as it's learned, re-swapping until a wanted one comes out (same reserve), then the cleanup.
- **ideal:** an upper bound with unlimited coupons, where the horse always holds the rarest skills.

**Travel set** (the "wanted" skills): Sprint, Instant Accel, S: Instant Accel, Drift, High Jump, Streak Leap, Start Accel, Quick Ride, Charge, Sideways, S: Sideways, Quick Back, Quick Stop, plus each Dream horse's learnable exclusive (Earth of Protection, Wings of Freedom, Dark Sprint, Voltarion's). Sprint is innate, so the set is 13 skills for the Mythical Diné and the Doom, and 12 for the T8.
- **Left out:** S: Charge, which is mostly combat. Doom riders may still want it, since Dark Sprint can follow S: Charge as well as S: Instant Accel.
- **Change it** with `--wanted`.

## Results

Simulated from level 1 to 30, 4000 runs per cell, seed 1. Each cell is **a/b/c**: a = no boxes, b = gear **or** brand stone, c = both.

**Skills at 30, natural leveling (no coupons, no tickets).** "Of N" = learnable skills, innate ones not counted.

| Training | Mythical Diné (of 20) | Doom T9 (of 21) | T8 example (of 19) |
|---|---|---|---|
| Professional 10 | 15.6/16.1/16.5 | 16.9/17.4/17.8 | 13.7/14.2/14.7 |
| Artisan 7 | 15.8/16.3/16.7 | 17.1/17.6/17.9 | 13.9/14.4/14.9 |
| Master 10 | 16.3/16.6/16.9 | 17.6/17.9/18.1 | 14.4/14.9/15.3 |
| Master 20 | 16.7/17.0/17.2 | 18.0/18.2/18.4 | 15.0/15.3/15.6 |
| Guru 20 | 17.8/17.9/18.0 | 18.8/18.9/19.0 | 16.4/16.6/16.7 |

**Chance of ending with the full travel set**, by strategy and number of coupons ("at30, 10" = at30 strategy with 10 coupons).

Mythical Diné (13 wanted):

| Training | at30, 10 | coursier, 10 | at30, 30 | coursier, 30 | hard, 30 |
|---|---|---|---|---|---|
| Professional 10 | 10%/13%/18% | 9%/13%/16% | 58%/66%/72% | 85%/93%/96% | 48%/53%/59% |
| Artisan 7 | 11%/16%/19% | 12%/16%/20% | 62%/70%/73% | 90%/94%/97% | 52%/58%/62% |
| Master 10 | 16%/19%/25% | 15%/19%/24% | 68%/73%/77% | 95%/97%/98% | 57%/61%/66% |
| Master 20 | 20%/26%/29% | 22%/25%/28% | 75%/77%/80% | 98%/98%/99% | 62%/65%/69% |
| Guru 20 | 42%/44%/49% | 38%/42%/45% | 87%/89%/89% | 100%/100%/100% | 74%/77%/78% |

Doom T9 (13 wanted):

| Training | at30, 10 | coursier, 10 | at30, 30 | coursier, 30 | hard, 30 |
|---|---|---|---|---|---|
| Professional 10 | 8%/12%/15% | 7%/10%/14% | 48%/54%/60% | 88%/93%/95% | 33%/41%/45% |
| Artisan 7 | 9%/14%/17% | 9%/12%/16% | 52%/57%/62% | 91%/94%/95% | 37%/44%/48% |
| Master 10 | 14%/17%/20% | 12%/17%/20% | 59%/61%/66% | 94%/95%/96% | 45%/49%/50% |
| Master 20 | 17%/22%/26% | 18%/20%/22% | 63%/68%/69% | 95%/97%/98% | 47%/52%/54% |
| Guru 20 | 37%/40%/42% | 35%/36%/37% | 78%/78%/80% | 99%/100%/100% | 63%/65%/67% |

T8 example (12 wanted):

| Training | at30, 10 | coursier, 10 | at30, 30 | coursier, 30 | hard, 30 |
|---|---|---|---|---|---|
| Professional 10 | 13%/17%/22% | 12%/17%/22% | 72%/78%/83% | 86%/91%/94% | 65%/70%/73% |
| Artisan 7 | 15%/19%/24% | 14%/20%/25% | 75%/81%/85% | 89%/91%/95% | 69%/73%/76% |
| Master 10 | 19%/23%/30% | 19%/25%/29% | 81%/84%/88% | 93%/95%/97% | 72%/76%/80% |
| Master 20 | 26%/31%/35% | 27%/31%/36% | 86%/88%/90% | 96%/97%/98% | 76%/81%/83% |
| Guru 20 | 51%/54%/57% | 50%/53%/54% | 94%/95%/96% | 100%/100%/100% | 89%/89%/90% |

**How many coupons?** Mythical Diné, Artisan 7, chance of the full set:

| Coupons | 5 | 10 | 15 | 20 | 25 | 30 | 40 |
|---|---|---|---|---|---|---|---|
| at30 | 4%/7%/10% | 11%/16%/19% | 22%/27%/33% | 34%/43%/48% | 49%/56%/62% | 62%/70%/73% | 82%/85%/89% |
| coursier | 4%/7%/10% | 12%/16%/20% | 28%/35%/39% | 56%/62%/70% | 79%/86%/89% | 90%/94%/97% | 97%/99%/100% |

With 5 coupons, coursier equals at30, because all 5 are kept in reserve.

## Limits

- **The coupon's desired-skill bonus is the biggest unknown.** With no bonus at all (coupons fully random), the Mythical Diné at Artisan 7 with 30 coupons drops from 90% to 63% (coursier), 62% to 19% (at30) and 52% to 14% (hard). The ranking of the strategies doesn't change.
- **Mount Level Down Tickets:** with 4 tickets, used on level-ups that teach nothing, natural leveling gives +0.7 skill (16.5 vs 15.8) and coursier with 30 coupons gives 96% instead of 90%.
- **Weights are rounded to 0.01 by bdolytics,** so chances are off by up to about 0.005 points per skill, and "nothing" by up to about 0.05.
- **The game can change.** Check your horse with `--check`, using numbers from the in-game simulator. If they don't match, add your horse from a simulator reading (`--horse-file`).
- **Simulation noise:** about ±1–2 points on the percentages.

## Reproduce

```
python3 -I horse_skills.py "Mythical Diné" --training "Artisan 7" --runs 4000 --sweep 10,30
python3 -I horse_skills.py "Mythical Diné" --training "Artisan 7" --runs 4000 --strategy natural,ideal
python3 -I horse_skills.py "Mythical Diné" --training "Artisan 7" --runs 4000 --sweep 5,10,15,20,25,30,40 --strategy at30,coursier
python3 -I horse_skills.py "Mythical Diné" --training "Artisan 7" --runs 4000 --point-bonus 0
python3 -I horse_skills.py "Mythical Diné" --training "Artisan 7" --runs 4000 --tickets 4
```

Use the same commands with `"Doom (T9)"` or `"T8 example (bdolytics icon horse_71)"`, and other `--training` values. The tables above were run with seed 1 in one batch, so a single command can differ from them by simulation noise.

## Sources

- Skill weights: [bdolytics horse skills](https://bdolytics.com/en/training/horse-skills), read 2026-11-17 (T8, T9 and T10 tabs). The source and date of each horse are in `data/horse_skills.json`.
- Training bonus by level: [community sheet](https://docs.google.com/spreadsheets/d/1erIfp07xnYWG6N0HYPjWiBRCuncOa0x0si_-3XiZHyI). Professional 10 and Artisan 7 were confirmed in-game.
- Everything else: the in-game growth simulator and the coupon window, read 2026-11-17.
