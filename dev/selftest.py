#!/usr/bin/env python3
"""Sanity checks for core.py. Dev tooling only.

The important one is agreement: core.violations() must accept exactly the
rosters that the shipped verifier.py accepts, since that file is what grades us.
"""

import io
import os
import random
import sys
from contextlib import redirect_stdout

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

import verifier  # noqa: E402  (starter code, unmodified)
from core import (Instance, parse_input, violations, is_valid, objective,  # noqa: E402
                  roster_to_dict, SHIFT_CHARS)

CHAR_TO_SHIFT = {c: i for i, c in enumerate(SHIFT_CHARS)}
failures = []


def check(label, condition, detail=""):
    if condition:
        print("  pass  %s" % label)
    else:
        print("  FAIL  %s  %s" % (label, detail))
        failures.append(label)


def as_verifier_instance(inst):
    return {"N": inst.N, "D": inst.D, "N_s": inst.Ns, "N_g": inst.Ng,
            "m": inst.m, "a": inst.a, "e": inst.e, "T": inst.T,
            "days": inst.days, "K": inst.K, "leaves": inst.leaves}


def official_says_valid(inst, roster):
    solution = roster_to_dict(inst, roster)
    with redirect_stdout(io.StringIO()):
        return verifier.verify_solution(as_verifier_instance(inst), solution)


def roster_from_rows(rows):
    return [CHAR_TO_SHIFT[c] for row in rows for c in row]


print("1. handout worked examples")

# Example 1: N=4 D=3 m=a=e=1 Ns=1 K=3 days=SGG
ex1 = Instance(N=4, D=3, Ns=1, Ng=3, m=1, a=1, e=1, T=100,
               days="SGG", K=3, leaves="WWWWWLWWWWWW")
r1 = roster_from_rows(["BRM", "EAR", "RMA", "REE"])
check("example 1 valid", is_valid(ex1, r1), violations(ex1, r1))
check("example 1 agrees with verifier.py", official_says_valid(ex1, r1))

# Example 2: N=4 D=2 m=a=e=1 Ns=1 K=2 days=SG
ex2 = Instance(N=4, D=2, Ns=1, Ng=3, m=1, a=1, e=1, T=100,
               days="SG", K=2, leaves="W" * 8)
r2 = roster_from_rows(["BR", "EA", "RM", "RE"])
check("example 2 valid", is_valid(ex2, r2), violations(ex2, r2))
check("example 2 agrees with verifier.py", official_says_valid(ex2, r2))

# Example 3: handout prints days='SGGGGGG' but states D=6, so it is a typo.
ex3 = Instance(N=4, D=6, Ns=1, Ng=3, m=1, a=1, e=1, T=100,
               days="SGGGGG", K=5, leaves="W" * 24)
r3 = roster_from_rows(["BRRRRE", "EEEEER", "RMAMAM", "RAMAMA"])
check("example 3 valid", is_valid(ex3, r3), violations(ex3, r3))
check("example 3 agrees with verifier.py", official_says_valid(ex3, r3))

print("\n2. targeted constraint violations are caught")
cases = [
    ("H1 B for a general nurse", ex2, ["BR", "EA", "BM", "RE"], "H1"),
    ("H2 back-to-back mornings", ex3, ["BRRRRE", "EEEEER", "RMMMAM", "RAMAMA"], "H2"),
    ("H4 B on a general day",    ex2, ["RB", "EA", "RM", "RE"], "H4"),
    ("H9 working while on leave", ex1, ["BRM", "EAA", "RMA", "REE"], "H9"),
]
for label, inst, rows, expected in cases:
    roster = roster_from_rows(rows)
    got = violations(inst, roster)
    check(label, expected in got, "expected %s, got %s" % (expected, got))

print("\n3. random rosters: core.violations vs verifier.py")
rng = random.Random(7)
mismatches = 0
trials = 0
for path in sorted(os.listdir(os.path.join(ROOT, "sample_test_cases"))):
    if not path.endswith(".csv"):
        continue
    inst = parse_input(os.path.join(ROOT, "sample_test_cases", path))
    for _ in range(120):
        # Mostly-random rosters, occasionally nudged toward legality so the
        # comparison sees accepting cases and not only rejections.
        roster = [rng.choice((0, 0, 1, 2, 3, 4)) for _ in range(inst.N * inst.D)]
        for i in range(inst.Ns, inst.N):
            for d in range(inst.D):
                if roster[i * inst.D + d] == 4:
                    roster[i * inst.D + d] = 0
        mine = is_valid(inst, roster)
        theirs = official_says_valid(inst, roster)
        trials += 1
        if mine != theirs:
            mismatches += 1
            if mismatches <= 3:
                print("     mismatch on %s: mine=%s theirs=%s (%s)"
                      % (path, mine, theirs, violations(inst, roster)))
check("%d random rosters agree" % trials, mismatches == 0,
      "%d mismatches" % mismatches)

# Random rosters are nearly all invalid, so they mostly exercise rejection.
# Single-cell mutations of a known-valid roster sit right on the boundary,
# which is where a false accept would actually hide.
mut_mismatch = 0
mut_trials = 0
for inst, base in ((ex1, r1), (ex2, r2), (ex3, r3)):
    for idx in range(inst.N * inst.D):
        for value in range(5):
            if value == base[idx]:
                continue
            roster = list(base)
            roster[idx] = value
            mut_trials += 1
            if is_valid(inst, roster) != official_says_valid(inst, roster):
                mut_mismatch += 1
                if mut_mismatch <= 3:
                    print("     mutation mismatch idx=%d -> %s"
                          % (idx, SHIFT_CHARS[value]))
check("%d single-cell mutations agree" % mut_trials, mut_mismatch == 0,
      "%d mismatches" % mut_mismatch)

print("\n4. objective matches verifier.calculate_objective")
diffs = 0
for path in sorted(os.listdir(os.path.join(ROOT, "sample_test_cases"))):
    if not path.endswith(".csv"):
        continue
    inst = parse_input(os.path.join(ROOT, "sample_test_cases", path))
    for _ in range(40):
        roster = [rng.choice((0, 1, 2, 3, 4)) for _ in range(inst.N * inst.D)]
        theirs = verifier.calculate_objective(
            as_verifier_instance(inst), roster_to_dict(inst, roster))
        if objective(inst, roster) != theirs:
            diffs += 1
check("objective agrees", diffs == 0, "%d differences" % diffs)

print("\n5. derived quantities on the sample instances")
for path in sorted(os.listdir(os.path.join(ROOT, "sample_test_cases"))):
    if not path.endswith(".csv"):
        continue
    inst = parse_input(os.path.join(ROOT, "sample_test_cases", path))
    print("  %-11s N=%-3d D=%-3d Ns=%-3d m,a,e=%d,%d,%d K=%-2d "
          "workload=%-4d bound=%d  b_hi=%s  infeasible=%s"
          % (path, inst.N, inst.D, inst.Ns, inst.m, inst.a, inst.e, inst.K,
             inst.total_units, inst.cost_lower_bound(),
             "".join(str(x) for x in inst.b_hi), inst.infeasibility_reason()))

print("\n%s" % ("ALL CHECKS PASSED" if not failures
                else "FAILURES: %s" % ", ".join(failures)))
sys.exit(1 if failures else 0)
