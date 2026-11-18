#!/bin/sh
# C39 benchmark driver: one process per run, results appended to c39_bench.jsonl (npz in c39_out/)
mkdir -p c39_out
for case in $CASES; do for J in $JS; do for v in $VARIANTS; do
  python3 -I c39.py $case $C $v $J c39_out/${case}_${C}_${v}_J$J >> c39_bench.jsonl 2>> c39_bench.err || echo "{\"case\": \"$case\", \"C\": $C, \"variant\": \"$v\", \"J\": $J, \"failed\": true}" >> c39_bench.jsonl
done; done; done
