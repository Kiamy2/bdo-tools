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
```

## Inputs

- **Horse:** a name from `--list` (accents and case optional), or `--horse-file` with your own reading of the in-game simulator (below).
- `--training`: your Training level, in English or French (`Artisan 7`, `Master 20`, `Gourou 57`), or the bonus itself (`21.7`).
- `--learned`: skills the horse already has, besides its innate ones. Skill names in English or French, comma-separated (`"High Jump, Dérapage"`).
- `--level`: the horse's current level (default 1). Leveling always ends at 30, since skills aren't learned past 30.
- `--coupons` (default 30) or `--sweep 0,10,20`: Mount Skill Change Coupons available. `--tickets`: Mount Level Down Tickets (default 0).
- `--wanted`: the skills you want (default: the travel set in the report). `--fodder`: what the `coursier` strategy swaps out (default `Hind Kick, Fore Chop`). `--reserve`: coupons kept for level 30 (default 5).
- `--points`: Skill Change Points the horse already has. `--point-bonus`: how much each point raises the desired skill (default 0.25, see the report).
- `--runs` (default 5000) and `--seed`: simulation size and random seed. Results move by about ±1 point between seeds at 5000 runs.

## Output

The simulation prints one row per strategy (descriptions in `--help` and the report):

```
strategy  coupons  skills at 30   wanted at 30   all wanted   coupons used
coursier  30       18.8/19.3/19.6 12.9/12.9/13.0 90%/94%/97%  27/25/24
```

- Each cell is **a/b/c**: a = no boxes, b = Pearl horse gear **or** Mount Brand Spell Stone (both are +10%), c = both.
- `skills at 30`: learnable skills the horse has at level 30 (innate ones not counted). `wanted at 30`: how many of those are wanted. `all wanted`: chance of ending with every wanted skill. `coupons used`: average.
- `--odds` prints the next level-up's chances like the in-game simulator, with `--gear`/`--brand` for the boxes.
- `--check` compares numbers you read in the in-game simulator with the model (`none` = "no skill"). It exits with 1 on a mismatch, which means the data is outdated or the settings differ (same Training level, boxes and learned skills as in the game?).

## Your own horse (`--horse-file`)

Any horse can be added from one reading of the in-game simulator (Horse info → Growth simulator), taken at horse level 1–30 with no skills toggled and a Training level where "no skill" is above 0%. Write a CSV like [tests/data/sim_mythical_dine_artisan7.csv](../tests/data/sim_mythical_dine_artisan7.csv):

```
# name: My horse
# training: Artisan 7
# boxes: none
# learned: Sprint
none,10.7826
Ruade,15.1844
...
```

`boxes` is `none`, `gear`, `brand` or `both`; `learned` lists the skills shown as innate ("base skill") or toggled. Skill names in English or French.

Exit codes: `0` OK · `1` `--check` mismatch · `2` bad input (unknown horse, skill, strategy or Training level).
