#!/usr/bin/env python3
"""Run a solver over a folder of instances, timing and verifying each one.

Dev tooling only. Uses subprocess to get honest wall-clock numbers and to make
sure the solver really does run standalone -- the submitted files must not use
subprocess themselves.
"""

import argparse
import json
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core import Instance, parse_input, violations, objective, SHIFT_CHARS  # noqa: E402

CHAR_TO_SHIFT = {c: i for i, c in enumerate(SHIFT_CHARS)}


def load_roster(inst, path):
    with open(path, encoding="utf-8") as f:
        obj = json.load(f)
    if obj == {}:
        return None
    roster = [0] * (inst.N * inst.D)
    for i in range(inst.N):
        for d in range(inst.D):
            roster[i * inst.D + d] = CHAR_TO_SHIFT[obj["N%d_%d" % (i, d)]]
    return roster


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("solver")
    ap.add_argument("testdir")
    ap.add_argument("--outdir", default="outputs")
    ap.add_argument("--timeout", type=float, default=None,
                    help="override the instance's own T, in seconds")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    os.makedirs(args.outdir, exist_ok=True)
    files = sorted(f for f in os.listdir(args.testdir) if f.endswith(".csv"))

    ok = bad = empty = crashed = timed_out = 0
    total_time = 0.0
    total_cost = 0
    total_bound = 0
    rows = []

    for name in files:
        csv_path = os.path.join(args.testdir, name)
        out_path = os.path.join(args.outdir, name[:-4] + ".json")
        inst = parse_input(csv_path)
        limit = args.timeout if args.timeout is not None else inst.T

        if os.path.exists(out_path):
            os.remove(out_path)

        start = time.perf_counter()
        try:
            proc = subprocess.run(
                [sys.executable, args.solver, csv_path, out_path],
                stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                timeout=limit)
            elapsed = time.perf_counter() - start
            rc, err = proc.returncode, proc.stderr.decode()[-400:]
        except subprocess.TimeoutExpired:
            elapsed = time.perf_counter() - start
            rc, err = None, ""

        total_time += elapsed
        bound = inst.cost_lower_bound()

        if rc is None:
            status, cost = "TIMEOUT", None
            timed_out += 1
        elif rc != 0:
            status, cost = "CRASH rc=%s %s" % (rc, err.strip()[:120]), None
            crashed += 1
        elif not os.path.exists(out_path):
            status, cost = "NO OUTPUT", None
            crashed += 1
        else:
            try:
                roster = load_roster(inst, out_path)
            except Exception as exc:
                roster, status, cost = None, "UNREADABLE %s" % exc, None
                crashed += 1
            else:
                if roster is None:
                    status, cost = "EMPTY {}", None
                    empty += 1
                else:
                    broken = violations(inst, roster)
                    if broken:
                        status, cost = "INVALID " + ",".join(broken), None
                        bad += 1
                    else:
                        cost = objective(inst, roster)
                        status = "VALID"
                        ok += 1
                        total_cost += cost
                        total_bound += bound

        rows.append((name, inst.N, inst.D, elapsed, limit, status, cost, bound))
        if not args.quiet:
            gap = ""
            if cost is not None:
                gap = "  cost=%d bound=%d%s" % (
                    cost, bound, "  OPTIMAL" if cost == bound else "")
            print("%-18s N=%-3d D=%-3d %7.3fs/%-6.0fs  %s%s"
                  % (name, inst.N, inst.D, elapsed, limit, status, gap))

    print("\n%d files: %d valid, %d invalid, %d empty, %d crashed, %d timed out"
          % (len(files), ok, bad, empty, crashed, timed_out))
    print("total wall clock %.2fs" % total_time)
    if ok:
        print("cost on valid instances: %d (sum of lower bounds %d)"
              % (total_cost, total_bound))
    return 0 if bad == 0 and crashed == 0 and timed_out == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
