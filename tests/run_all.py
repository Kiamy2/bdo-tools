#!/usr/bin/env python3
"""Regression tests for every tool (live API calls). Run before every push:

    python3 -I tests/run_all.py

Prints one line per check and 'ALL OK' at the end; exit code 1 if anything failed.
Expect ~10-60 s (Arsha retries can make it slower).
"""
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
failures = 0


def run(*args):
    p = subprocess.run([sys.executable, "-I", *args], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", timeout=600)
    return p.returncode, p.stdout + p.stderr


def check(name, cond, out=""):
    global failures
    print(("ok   " if cond else "FAIL ") + name)
    if not cond:
        failures += 1
        print("     output:", out[:800].replace("\n", "\n     "))


# --- prices.py ---------------------------------------------------------------
code, out = run("prices.py", "Vell's Heart", "4998", "Silver Ingot", "Gold Bar 1,000G",
                "Advice of Valks (+300) Box", "Vells Hart", "Urugon's Shoes", "999999999", "--sid", "0", "--tax")
check("prices: exit code 2 (deliberate bad inputs)", code == 2, out)
check("prices: Vell's Heart priced with basis", re.search(r"^45332\tVell's Heart\t[\d,]+\t[\d,]+\t(last sale|\d+-day avg)", out, re.M), out)
check("prices: shard priced", re.search(r"^4998\tSharp Black Crystal Shard\t[\d,]+", out, re.M), out)
check("prices: Silver Ingot same-name note + row", "SAME NAME, 2 IDs - hid untradeable" in out and re.search(r"^4252\tSilver Ingot\t[\d,]+", out, re.M), out)
check("prices: gold bar fixed, untaxed", "5\tGold Bar 1,000G\t10,000,000\t10,000,000\tfixed NPC value" in out, out)
check("prices: Valks box NOT ON MARKET", re.search(r"^860139\t.*NOT ON MARKET", out, re.M), out)
check("prices: typo suggests Vell's Heart", "NOT FOUND" in out and "Vell's Heart (id 45332)" in out, out)
check("prices: Urugon's Shoes one priced row", re.search(r"^11103\tUrugon's Shoes\t[\d,]+", out, re.M), out)
check("prices: unknown id", re.search(r"^999999999\t.*UNKNOWN ID", out, re.M), out)

code, out = run("prices.py", "--avg", "30", "4998")
check("prices --avg 30", code == 0 and re.search(r"30-day avg to \d{4}-\d\d-\d\d", out), out)
code, out = run("prices.py", "--latest", "4998", "--details")
check("prices --latest --details", code == 0 and "last sale" in out and "\tmax\t" in out, out)

# --- items.py ----------------------------------------------------------------
code, out = run("items.py", "Vell's Heart", "4998", "Vells Hart")
check("items: resolve + typo", code == 2 and "45332\tVell's Heart" in out and "4998\tSharp Black Crystal Shard" in out and "NOT FOUND" in out, out)
code, out = run("items.py", "--search", "Dehkia's Artifact")
check("items --search", code == 0 and "748022\tDehkia's Artifact - All Evasion" in out, out)

# --- languages and loose matching (both tools share bdo/items.py) -------------
code, out = run("items.py", "--lang", "fr", "Coeur de Vell", "eclat de cristal noir tranchant", "Lingot d'or 1000G")
check("items --lang fr: oe, accents, spaces", code == 0 and "45332\tCœur de Vell" in out
      and "4998\tÉclat de cristal noir tranchant" in out and "5\tLingot d'or 1 000 G" in out, out)
code, out = run("items.py", "Vells Heart", "Hashashin BD9 Armor N")
check("items: compact match; loose match on different names refused", "45332\tVell's Heart" in out and code == 2 and re.search(r"Hashashin BD9 Armor N\tNOT FOUND.*BD9\+ Armor N", out), out)
code, out = run("items.py", "--lang", "en,fr", "Vell's Heart", "Pierre de Caphras")
check("items --lang en,fr: both columns, either language", code == 0 and out.startswith("id\tname_en\tname_fr\tnote")
      and "45332\tVell's Heart\tCœur de Vell" in out and "721003\tCaphras Stone\tPierre de Caphras" in out, out)
code, out = run("items.py", "--lang", "en,fr", "--search", "coeur de vell")
check("items --search in French", code == 0 and "45332\tVell's Heart\tCœur de Vell" in out, out)
code, out = run("items.py", "--lang", "xx", "4998")
check("items: unknown language", code == 2 and "UNKNOWN LANGUAGE" in out, out)
code, out = run("prices.py", "--lang", "fr", "Coeur de Vell", "4998")
check("prices --lang fr", code == 0 and re.search(r"^45332\tCœur de Vell\t[\d,]+", out, re.M)
      and re.search(r"^4998\tÉclat de cristal noir tranchant\t[\d,]+", out, re.M), out)
code, out = run("prices.py", "--lang", "en,fr", "Pierre de Caphras")
check("prices --lang en,fr", code == 0 and re.search(r"^721003\tCaphras Stone\tPierre de Caphras\t[\d,]+", out, re.M), out)
code, out = run("prices.py", "--lang", "xx", "4998")
check("prices: unknown language", code == 2 and "UNKNOWN LANGUAGE" in out, out)

# --- horse_skills.py (offline) -------------------------------------------------
# In-game growth simulator readings (2026-11-17): the model must reproduce them.
D = "Mythical Diné"
for args, obs in [
    (["--training", "Artisan 7"], ["Ruade=15.1844", "none=10.7826", "Accél. Fulgurante=1.4554"]),
    (["--training", "Professionnel 10"], ["Ruade=14.5731", "none=14.3746"]),
    (["--training", "Artisan 7", "--brand"], ["Ruade=16.4321", "none=3.4516"]),
    (["--training", "Artisan 7", "--gear", "--brand"], ["Ruade=17.0196", "none=0"]),       # cap
    (["--training", "Gourou 57"], ["Ruade=17.0194", "none=0"]),
    (["--training", "Artisan 7", "--learned", "Saut haut"], ["Ruade=15.6382", "none=11.7532"]),
]:
    code, out = run("horse_skills.py", D, *args, "--check", *obs)
    check(f"horse_skills --check {' '.join(args)}", code == 0 and "MISMATCH" not in out, out)
code, out = run("horse_skills.py", "T8 example (bdolytics icon horse_71)", "--training", "Professional 10", "--check",
                "none=27.3544", "Ruade=10.5304", "Accél. Fulgurante=1.6668")
check("horse_skills --check T8", code == 0 and "MISMATCH" not in out, out)
code, out = run("horse_skills.py", "Doom (T9)", "--training", "Artisan 7", "--check", "none=2.8289", "Deux places=3.7851", "Galop funeste=2.7253")
check("horse_skills --check T9 Doom", code == 0 and "MISMATCH" not in out, out)
code, out = run("horse_skills.py", D, "--training", "Artisan 7", "--check", "Ruade=16")
check("horse_skills --check mismatch exits 1", code == 1 and "MISMATCH" in out, out)
code, out = run("horse_skills.py", "--horse-file", "tests/data/sim_mythical_dine_artisan7.csv", "--training", "Professional 10",
                "--check", "Ruade=14.5731", "none=14.3746")
check("horse_skills --horse-file (simulator reading)", code == 0 and "MISMATCH" not in out, out)
code, out = run("horse_skills.py", D, "--training", "Artisan 7", "--runs", "300", "--coupons", "20")
rows = {l.split("\t")[0]: l.split("\t") for l in out.splitlines() if not l.startswith("#")}
ok = code == 0 and set(rows) >= {"natural", "at30", "coursier", "hard", "ideal"}
if ok:
    first = lambda r, i: float(r[i].split("/")[0].rstrip("%"))
    ok = first(rows["ideal"], 2) >= first(rows["coursier"], 2) >= first(rows["natural"], 2)
check("horse_skills simulation table", ok, out)
code, out = run("horse_skills.py", D, "--training", "Artisan 7", "--runs", "200", "--target", "50",
               "--strategy", "at30,coursier")
m = re.search(r"^coursier\t(\d+)/(\d+)/(\d+)$", out, re.M)
check("horse_skills --target (coupons needed)", code == 0 and m and all(10 <= int(x) <= 30 for x in m.groups())
      and re.search(r"^at30\t\d+/\d+/\d+$", out, re.M), out)
code, out = run("horse_skills.py", D, "--training", "Artisan 7", "--target", "0")
check("horse_skills: bad --target exits 2", code == 2 and "--target" in out, out)
code, out = run("horse_skills.py", "T8 example (bdolytics icon horse_71)", "--training", "Guru 20", "--optimize", "3")
m = re.findall(r"^(\d+)\t([\d.]+)%\t", out, re.M)
check("horse_skills --optimize", code == 0 and [b for b, _ in m] == ["0", "1", "2", "3"]
      and float(m[3][1]) >= float(m[0][1]) and "coupons for a 50%" in out, out)
code, out = run("horse_skills.py", D, "--training", "Artisan 7", "--odds", "--lang", "fr")
check("horse_skills --odds --lang fr", code == 0 and "Ruade\t15.18" in out and "none\t10.7" in out, out)
code, out = run("horse_skills.py", D, "--training", "Expert 3")
check("horse_skills: bad Training level exits 2", code == 2 and "unknown Training level" in out, out)
code, out = run("horse_skills.py", "Pegasus", "--training", "Artisan 7")
check("horse_skills: unknown horse exits 2", code == 2 and "unknown horse" in out, out)

print("ALL OK" if not failures else f"{failures} CHECK(S) FAILED")
sys.exit(1 if failures else 0)
