#!/usr/bin/env bash
# Usage: bash scripts/run_all.sh part_a.py sample_test_cases
# Runs the given solver on every .csv in the folder, then verifies each output
# and prints wall-clock time per instance.
set -uo pipefail

SOLVER="${1:-part_a.py}"
TESTDIR="${2:-sample_test_cases}"

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
mkdir -p outputs

# starter code ships this as verify.py in the tree but verifier.py in the docs
VERIFIER="verify.py"
[[ -f "$VERIFIER" ]] || VERIFIER="verifier.py"

for csv in "$TESTDIR"/*.csv; do
  name="$(basename "${csv%.csv}")"
  out="outputs/${name}.json"

  start=$(date +%s.%N)
  python "$SOLVER" "$csv" "$out"
  rc=$?
  end=$(date +%s.%N)

  printf '%-14s  %6.2fs  ' "$name" "$(echo "$end - $start" | bc)"
  if [[ $rc -ne 0 ]]; then
    echo "CRASHED (exit $rc)"
    continue
  fi
  python "$VERIFIER" "$csv" "$out"
done
