# Work in progress: horse skills analysis (remove before merging)

Scratch scripts and outputs behind the horse skills report, saved here so they aren't lost.
Not part of the tools; to be deleted (or turned into proper docs) before this branch is merged.

- `step3/`: `--optimize 40` for six scenarios (s0-s5; in chat relabelled F1-F6 from least to most favourable:
  F1 = s4 T8 Pro 10, F2 = s0 Diné Art 7, F3 = s3 Doom Art 7, F4 = s5 user's Diné, F5 = s1 Diné Art 7 both boosts,
  F6 = s2 Diné Guru 20), and the runner.
- `c13/`: one "safest" Coursier plan per budget across F1, F2, F3, F5, F6 (grid.py simulates every plan,
  analyze.py picks the plan with the smallest worst-case loss and rechecks it with fresh runs).
- `*_grid.py`, `reserve_sweep.py`: earlier reserve / start-level sweeps. The ones run before the cleanup-order
  fix (reserve_sweep, the first reserve_grid) gave wrong numbers.
