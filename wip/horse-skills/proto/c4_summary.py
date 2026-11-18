"""Summary of c4.py: per case and budget, the rule's plan vs the best plans for safer goals (4000 fresh horses)."""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
NAMES = {0: "All at 30", 1: "V0", 6: "V2", 12: "switch"}
def name(p):
    st, s, c, xa, T = p
    if st == 0: return "All at 30"
    return f"{NAMES[st]}{' T' + str(T) if st == 12 else ''} from {s}, cap {c}"
def p95(v):                      # missing skills for the worst 5%: smallest j with P(missing <= j) >= 95%
    for j in range(5):
        if v[j] >= 0.95: return str(j)
    return ">4"
files = sorted((f for f in os.listdir(os.path.join(HERE, "c4_cases")) if f.endswith(".json")), key=lambda f: int(f[:-5]))
R = [json.load(open(os.path.join(HERE, "c4_cases", f))) for f in files]
print("Cells: full set % | missing <= 1 % | missing <= 2 % | average missing | 95% of horses miss at most  (4000 fresh horses)")
gains = []
for r in R:
    print(f"\n## {r['horse'].split(' (')[0]} | {r['training']}")
    for B, b in r["budgets"].items():
        for k in ("rule", "full", "safe1", "safe2", "mean"):
            v = b[k]["check"]
            print(f"  {B:>2} {k:<5} {100*v[0]:5.1f} {100*v[1]:5.1f} {100*v[2]:5.1f} {v[5]:5.2f}  {p95(v):>2}   {name(b[k]['plan'])}")
        ru, s2, s1 = b["rule"]["check"], b["safe2"]["check"], b["safe1"]["check"]
        gains.append((r["horse"].split(" (")[0], r["training"], int(B), 100*(s1[1]-ru[1]), 100*(s2[2]-ru[2]), 100*(s1[0]-ru[0]), 100*(s2[0]-ru[0]), 100*ru[1], 100*ru[2]))
print("\nSafer plan vs the rule (points; full-set change in brackets):")
print("case | budget | rule: <=1 / <=2 missing | safe1 gain on <=1 (full) | safe2 gain on <=2 (full)")
for g in gains:
    print(f"{g[0]:<10} {g[1]:<10} {g[2]:>2} | {g[7]:5.1f} / {g[8]:5.1f} | {g[3]:+5.1f} ({g[5]:+4.1f}) | {g[4]:+5.1f} ({g[6]:+4.1f})")
