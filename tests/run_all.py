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
    p = subprocess.run([sys.executable, "-I", *args], cwd=ROOT, capture_output=True, text=True, timeout=600)
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

print("ALL OK" if not failures else f"{failures} CHECK(S) FAILED")
sys.exit(1 if failures else 0)
