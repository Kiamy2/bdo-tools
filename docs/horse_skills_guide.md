# Guiding a player with horse_skills.py (for AI assistants)

How an AI assistant (a chat bot or an agent with a shell) can help a player level one horse, step by step, with [`horse_skills.py`](horse_skills.md). Read the tool's doc first; this page is about using it in a conversation. A step-by-step mode of the tool doesn't exist yet: you apply the rules below and use the tool to plan.

## 1. Setup

Run these as two separate commands (some assistants' safety checks refused a combined command with `&&`, `-q` or `-r`):
```
git clone --depth 1 https://github.com/Kiamy2/bdo-tools
```
```
pip install --break-system-packages numba==0.68.1 llvmlite==0.50.0 numpy==2.5.3
```
- The pip line is optional: it installs the fast engine of `--optimize` (about 15 s the first time, compilation included, then about 1 s from a horse's current state; 20-30 s for 20 coupons from level 1). Without it everything works, slower and noisier.
- Run from the repo root (`cd bdo-tools`) with `python3 -I horse_skills.py ...`; give `--optimize` calls a timeout of about 5 minutes.

## 2. Ask the player once (all of it)

- **Horse:** a name from `--list` (T8s as `T8 Type N`, the type shown in game). A T8 type that isn't listed, or a special horse with extra innate skills: ask for an in-game growth simulator screenshot at level 1, no boosts (the top of the list: 'no skill' and Hind Kick chances). A special horse is often a known one with extra innate skills: try `--innate "..." --check none=... Ruade=...` (see the tool doc); on a mismatch, build a `--horse-file` from the reading.
- **Training level** (e.g. Artisan 7) and **boosts** (Pearl horse gear: `--gear`; Mount Brand Spell Stone: `--brand`).
- **Current level, learned skills** (French names work), and the **Skill Change Points** shown in the coupon window.
- **The skill count shown in game**, as a check: in-game count = learned skills + innate skills (a default T8 shows 16 for 15 learned + the innate Sprint). Never put innate skills in `--learned` (the tool ignores them, with a note).
- **Mount Skill Change Coupons** available and how many they're willing to spend; **Level Down Tickets** (only for this horse, or worth keeping for another?); a **Mount Skill Selection Coupon** (none / sure to use it = `planned` / a safety net = `fallback`).
- **Target set:** `courser` (a T8 for courser training into a Dream Horse: Charge, Drift, Sprint, Instant Accel, Sideways, S: Instant Accel, S: Sideways, + level 30), `travel` (an example set for a finished T10), or their own list. The tool's default: courser for a T8, travel otherwise. Say which one you use.
- **Goal:** the highest chance with the coupons given, a target chance with as few coupons as possible, or the fewest coupons on average. They lead to different plans: ask.

## 3. The plan

```
python3 -I horse_skills.py "T8 Type 2" --training "Artisan 7" [--gear] [--brand] --level 10 \
  --learned "Ruade,Saut haut" --points 3 --tickets 2 --optimize 20 [--wanted courser|travel|LIST] \
  [--selection-coupon planned|fallback] [--coupons-used] --lang fr
```
- Read the header: the horse (an alias shows the type the player gave), the target set, the learned skills with the in-game count, and the note **'every skill left to learn is wanted: any swap is a sure hit'** when it applies (see §5).
- The **suggested plan per budget** block: one plan per number of coupons, the general rule's plan or the best one found for this horse (`--always-best`: always the best). Columns: full-set chance, missing at most 1 / 2, worst 5%, `used` (coupons used on average with that budget), `per full set` (used / full-set chance), and with tickets or a fallback Selection Coupon their columns.
- Plans are printed in their effective form for this horse. State the chosen plan in an explicit form: "from level N, after each level-up do V2 (or V0) once; spend at most C coupons while leveling (in total); at level 30, the cleanup", and say what each action is (§4).
- **`--coupons-used`**: for the suggested plans, the chance of the full set with **at most B coupons in total**, for each B (the plan followed as planned, the level-30 cleanup going on past its budget), and the average / median / 90% / 99% coupons used. It answers "if I follow the 3-coupon plan, what's my chance of being done with only 2?". It covers only the suggested plans; for another plan, use the engine directly: `bdo.horses_fast.Evaluator(horse, M, max_budget=20, start_level=L, learned=[...], points=P, wanted=W).plans([plan], 4000, seed, at_most=True, used=True)`, with plan = (strategy, start level, spending cap, switch threshold) as in `bdo/horses.py`.
- The ranking is by the full-set chance at each budget. For **"fewest coupons on average"**, compare `used` and `--coupons-used` across plans, and include `no swaps while leveling, every coupon at level 30`: when most wanted skills are already held or innate, it can beat every swapping plan (seen on a T8 born with 5 of the 7 courser skills).
- The general rules (by target set): 1 coupon: all at level 30; 2-24: V2 from level max(10, 31 - 1.75 x N), keep 1 (courser set with 2-6 coupons: from level 30 - 2 x N); 25+: from level 10, V0 until 12 learned skills, then V2, spending at most 24 while leveling.

## 4. Each level-up (the loop)

The player reports the level-up's result: a skill, or nothing.
1. **Check the report.** The skill must not be held already, and the in-game count must be learned + innate (+1 if a skill came). If something is impossible, ask: the skill name only shows in a popup for about 3 seconds, so mix-ups happen. Before the level-up, `--odds` (with the state before it) lists the possible results with their chances, so the player only has to confirm one name.
2. **Nothing learned and tickets left:** the tool's plans use a ticket on every level-up that teaches nothing. With only one skill left to learn, keep the last ticket for the last level-up (29 -> 30): same chance, and it may be saved. If the tickets are worth keeping for another horse: earlier research found that using them only while the horse is behind the average horse (the `--optimize` table of average learned skills per level) gets more out of each ticket used (being rechecked, see §6).
3. **Swaps for this level** (only from the plan's start level, and while the plan's spending cap isn't reached), **one pass per level, never more:**
   - V0 (`coursier`): swap Fore Chop (Cabrade) if held, then Hind Kick (Ruade) if held, even one the first swap just gave back; then stop until the next level-up. Not "until neither is held" (tested: worse).
   - V2 (`coursier_v2`): swap Hind Kick (Ruade) if held; **never Fore Chop**.
   - "V0 until T learned skills, then V2": V0 while the horse has fewer than T learned skills (innate ones don't count), then V2 for good.
   - **Desired skill** in the coupon window: the rarest missing wanted skill (lowest weight). The order, with French names:
     ```
     python3 -I -c "import sys; sys.path.insert(0,'.'); from bdo import horses as H; d=H.load_data(); fr=d['skills_fr']; h=H.get_horse(d,'T8 Type 2'); w=[s for s in H.COURSER_SET if s in h.weights]; [print(s, '/', fr.get(s), h.weights[s]) for s in sorted(w, key=lambda s: h.weights[s])]"
     ```
     With a Selection Coupon `planned`: the second rarest missing one, keeping the rarest for the Selection Coupon.
4. **Skill Change Points:** +1 per coupon, back to 0 when the coupon gives the desired skill. Use the value shown in game as a check.
5. **Re-plan** after this level's swaps (the tool's `--level L` means the swaps of level L are done), every few levels or when something unusual happens. Re-planning from the real state was measured to be as good as keeping the plan, so small differences are fine; don't swing between plans for a few tenths of a point.

## 5. Level 30

- **Cleanup:** swap the rarest unwanted skill held, with the rarest missing wanted skill as the desired one, until every wanted skill is held or the coupons run out.
- **Selection Coupon:** at the very end, on the last missing wanted skill. It needs an unwanted skill to change.
- **When any swap is a sure hit** (the horse can only learn wanted skills, plus the skill swapped out), the real choice is which skill to give up, because level-ups may teach it back. Holding a heavy fodder skill (Fore Chop) is what makes such swaps likely hits earlier on.

## 6. Being reliable

- **Separate what the tool measured from reasoning.** Say which numbers come from the tool and which statements are your own reasoning. Don't state as fact what you haven't measured: run the tool (or the engine) first, or say it's a guess. If the data is clear but the reason isn't, say "I'm not sure why, but the data is clear"; when you do explain, list every effect first. Example: swapping out Hind Kick puts its weight back in the draw: each level-up then gives the wanted skills a smaller share, but it teaches something more often, so the horse ends with more skills and better coupon draws at 30. Naming only one effect gets the answer wrong.
- **Say what a table covers:** which plans, start levels and budgets were checked, and which were not.
- **Noise:** the tool's numbers come from 4,000 simulated horses, and every plan is played on the same horses, so a whole table can be a point or so off, every plan in the same direction. Differences between plans are more precise than the chances themselves. Don't present differences of half a point as real; when it matters, rerun with more horses through the engine (e.g. 40,000).
- **Label every budget** in a table, and say that an average under a budget counts failed horses at the full budget.
- **Say plainly when a decision makes no difference** (e.g. two options both near 0% failure: choose by coupons).
- **Rules, stated explicitly:** "once per level", "never Fore Chop in V2", "learned skills don't count innate ones", "the spending cap counts every coupon used while leveling". A player once looped 6 swaps at one level because V0 wasn't stated as once per level.
- **Being rechecked:** the advice on tickets (which level-ups to use them on) and on the Selection Coupon's targeting comes from studies done before the Skill Change Points reset was modelled; the tool's own numbers include the reset.
