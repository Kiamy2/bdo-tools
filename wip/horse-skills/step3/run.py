import subprocess, sys
from concurrent.futures import ThreadPoolExecutor
O = "/home/claude/scratch/step3"
S = {
    "s1_dine_a7_both": ["Mythical Diné", "--training", "Artisan 7", "--gear", "--brand"],
    "s2_dine_guru20": ["Mythical Diné", "--training", "Guru 20"],
    "s3_doom_a7": ["Doom (T9)", "--training", "Artisan 7"],
    "s4_t8_pro10": ["T8 example (bdolytics icon horse_71)", "--training", "Professional 10"],
    "s5_user_dine": ["Mythical Diné", "--training", "Artisan 7", "--level", "2", "--learned", "High Jump",
                     "--points", "1", "--tickets", "4"],
}
def run(name):
    with open(f"{O}/{name}.txt", "w") as out, open(f"{O}/{name}.err", "w") as err:
        r = subprocess.run(["python3", "-I", "horse_skills.py", *S[name], "--optimize", "40"],
                           cwd="/home/claude/bdo-tools", stdout=out, stderr=err)
    print(name, "exit", r.returncode, flush=True)
with ThreadPoolExecutor(2) as ex:
    list(ex.map(run, S))
