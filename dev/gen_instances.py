#!/usr/bin/env python3
"""Generate nurse-rostering instances for stress testing.

Dev tooling only; never part of the submission.

Parameters are drawn so the cheap necessary conditions in core.Instance hold,
with a `tightness` knob controlling how much slack is left above them. Low
tightness leaves plenty of room; high tightness sits just above the bound,
where the search should actually struggle. Feasibility is NOT guaranteed --
that is what the solver is for -- so treat a persistent failure on a
high-tightness instance as "possibly unsatisfiable" until confirmed.
"""

import argparse
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core import Instance  # noqa: E402


def make_instance(rng, N, D, tightness, leave_rate, surg_rate, T):
    Ns = rng.randint(max(1, N // 6), max(1, (2 * N) // 3))
    Ng = N - Ns

    days = "".join("S" if rng.random() < surg_rate else "G" for _ in range(D))

    # Leaves first: coverage has to fit inside whoever is left.
    leaves = "".join("L" if rng.random() < leave_rate else "W"
                     for _ in range(N * D))

    # Worst-case headcount available on any single day bounds m + a + e.
    per_day_avail = [
        sum(1 for i in range(N) if leaves[i * D + d] == "W") for d in range(D)
    ]
    room = min(per_day_avail)
    if room < 3:
        return None

    # tightness in [0,1] interpolates between a third of the room and all of it.
    budget = max(3, int(room * (0.33 + 0.62 * tightness)))
    m = rng.randint(1, max(1, budget // 2))
    a = rng.randint(1, max(1, budget - m - 1))
    e = max(1, budget - m - a)
    if m + a + e > room:
        return None

    # K must cover the average per-nurse share of the fixed workload, plus slack
    # that shrinks as tightness rises.
    workload = D * (m + a + e)
    fair_share = -(-workload // N)          # ceil
    slack = 1.0 + 0.9 * (1.0 - tightness)
    K = max(2, int(fair_share * slack) + 1)

    return Instance(N=N, D=D, Ns=Ns, Ng=Ng, m=m, a=a, e=e,
                    T=T, days=days, K=K, leaves=leaves)


def make_tight_instance(rng, N, D, leave_rate, T):
    """Build an instance where some day genuinely cannot run on b_d = 1.

    The default generator keeps m + a + e within the thinnest day's headcount,
    which silently guarantees b_d = 1 always fits -- so it never exercises the
    demand-driven branch of min_b(). Here coverage is deliberately pushed past
    the tightest day's availability, forcing b_d above 1 on at least one day.
    """
    # Mostly surgical: B supply is the scarce resource when b_d has to climb.
    Ns = rng.randint(max(2, (2 * N) // 3), N)
    days = "S" * D
    leaves = "".join("L" if rng.random() < leave_rate else "W"
                     for _ in range(N * D))

    per_day = [sum(1 for i in range(N) if leaves[i * D + d] == "W")
               for d in range(D)]
    room = min(per_day)
    if room < 5:
        return None

    # Overshoot the thinnest day by delta, so that day needs b_d >= delta.
    delta = rng.randint(2, 4)
    budget = room + delta
    m = rng.randint(delta, max(delta, budget // 2))
    a = rng.randint(delta, max(delta, budget - m - 1))
    e = budget - m - a
    if e < 1 or m < delta or a < delta:
        return None
    # Morning succession (2m + e <= N) is necessary; do not generate past it.
    if 2 * m + e > N:
        return None

    workload = D * (m + a + e)
    K = max(2, -(-workload // N) + rng.randint(1, 4))

    return Instance(N=N, D=D, Ns=Ns, Ng=N - Ns, m=m, a=a, e=e,
                    T=T, days=days, K=K, leaves=leaves)


def to_csv(inst):
    header = "N,D,N_s,N_g,m,a,e,T,days,K,leaves"
    row = "%d,%d,%d,%d,%d,%d,%d,%g,%s,%d,%s" % (
        inst.N, inst.D, inst.Ns, inst.Ng, inst.m, inst.a, inst.e,
        inst.T, inst.days, inst.K, inst.leaves)
    return header + "\n" + row + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default="my_tests", help="output directory")
    ap.add_argument("--count", type=int, default=40, help="instances per size tier")
    ap.add_argument("--seed", type=int, default=333)
    ap.add_argument("--T", type=float, default=300.0)
    args = ap.parse_args()

    rng = random.Random(args.seed)
    os.makedirs(args.out, exist_ok=True)

    # Sized to bracket the graded range (N <= 50, D <= 30), with small cases
    # kept because degenerate shapes are where edge-case bugs live.
    tiers = [
        ("tiny",   (4, 10),  (2, 6)),
        ("small",  (10, 20), (5, 12)),
        ("medium", (20, 35), (10, 20)),
        ("large",  (35, 50), (20, 30)),
    ]

    written = skipped = 0

    # Tight tier: coverage exceeds the thinnest day, so b_d must exceed 1.
    from core import min_b
    for k in range(args.count):
        inst = None
        for _ in range(200):
            cand = make_tight_instance(
                rng, N=rng.randint(12, 50), D=rng.randint(6, 30),
                leave_rate=rng.choice((0.05, 0.15, 0.3)), T=args.T)
            if cand is None or cand.infeasibility_reason() is not None:
                continue
            # Keep it only if it actually forces b_d > 1 somewhere.
            if any((min_b(cand, d) or 0) > 1 for d in range(cand.D)):
                inst = cand
                break
        if inst is None:
            skipped += 1
            continue
        with open(os.path.join(args.out, "tight_%02d.csv" % k), "w",
                  encoding="utf-8") as f:
            f.write(to_csv(inst))
        written += 1

    for name, (nlo, nhi), (dlo, dhi) in tiers:
        for k in range(args.count):
            tightness = k / max(1, args.count - 1)
            inst = None
            for _ in range(50):
                inst = make_instance(
                    rng,
                    N=rng.randint(nlo, nhi),
                    D=rng.randint(dlo, dhi),
                    tightness=tightness,
                    leave_rate=rng.choice((0.0, 0.05, 0.12, 0.25)),
                    surg_rate=rng.choice((0.0, 0.2, 0.5, 0.85, 1.0)),
                    T=args.T,
                )
                if inst is not None and inst.infeasibility_reason() is None:
                    break
                inst = None
            if inst is None:
                skipped += 1
                continue
            path = os.path.join(args.out, "%s_%02d.csv" % (name, k))
            with open(path, "w", encoding="utf-8") as f:
                f.write(to_csv(inst))
            written += 1

    print("wrote %d instances to %s (%d draws abandoned)"
          % (written, args.out, skipped))


if __name__ == "__main__":
    main()
