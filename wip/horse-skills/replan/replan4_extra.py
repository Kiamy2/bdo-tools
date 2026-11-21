"""replan4.py with extra cases, added here so replan4.py (and the code hash in its result files) stays unchanged.
The case's horse, Training and coupons are in each file's settings header. Usage: as replan4.py."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import replan4 as R

R.CASES.update({
    "dine_m10": {"horse": "Mythical Diné", "training": "Master 10", "coupons": 10},
})
sys.argv[0] = R.__file__
if __name__ == "__main__":
    R.main()
