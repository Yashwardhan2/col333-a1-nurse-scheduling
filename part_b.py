"""COL333 Assignment 1 -- Part B

Nurse rostering solved as a constraint satisfaction problem. Standard library
only; this file is self-contained and takes an input CSV and an output JSON
path as its two arguments.
"""
import csv
import json
import os
import random
import sys
import time

# ---- encoding ----

# Shifts are small ints so rosters can live in flat lists and hot loops can
# compare with `==` instead of hashing strings.
R, M, A, E, B = 0, 1, 2, 3, 4
SHIFT_CHARS = ("R", "M", "A", "E", "B")

# A nurse's contribution to (mornings, afternoons, evenings) per shift.
MORNING_SHIFTS = (M, B)
AFTERNOON_SHIFTS = (A, B)

# H8 weight:
SHIFT_UNITS = (0, 1, 1, 1, 2)


# ---- input ----

def parse_input(input_csv):
    """Read the single instance row. Column names follow the starter code."""
    with open(input_csv, "r", newline="", encoding="utf-8") as f:
        row = next(csv.DictReader(f))
    return Instance(
        N=int(row["N"]),
        D=int(row["D"]),
        Ns=int(row["N_s"]),
        Ng=int(row["N_g"]),
        m=int(row["m"]),
        a=int(row["a"]),
        e=int(row["e"]),
        T=float(row["T"]),
        days=row["days"],
        K=int(row["K"]),
        leaves=row["leaves"],
    )


class Instance:
    """Instance data plus the precomputation every search layer shares."""

    __slots__ = (
        "N", "D", "Ns", "Ng", "m", "a", "e", "T", "days", "K", "leaves",
        "surgical_day", "on_leave", "avail", "avail_surg",
        "b_lo", "b_hi", "b_req", "b_suffix",
        "max_work_days", "capacity", "total_units",
    )

    def __init__(self, N, D, Ns, Ng, m, a, e, T, days, K, leaves):
        self.N, self.D, self.Ns, self.Ng = N, D, Ns, Ng
        self.m, self.a, self.e = m, a, e
        self.T, self.days, self.K = T, days, K
        self.leaves = leaves

        self.surgical_day = [c == "S" for c in days]

        # on_leave is flat and parallel to a roster, so H9 checks are O(1).
        self.on_leave = [leaves[idx] == "L" for idx in range(N * D)]

        # Per-day headcount available to work at all.
        self.avail = [0] * D
        self.avail_surg = [0] * D
        for i in range(N):
            base = i * D
            surgical = i < Ns
            for d in range(D):
                if not self.on_leave[base + d]:
                    self.avail[d] += 1
                    if surgical:
                        self.avail_surg[d] += 1

        # b_d = number of B shifts on day d.
        self.b_lo = [0] * D
        self.b_hi = [0] * D
        for d in range(D):
            if self.surgical_day[d]:
                self.b_lo[d] = 1
                self.b_hi[d] = min(m, a, self.avail_surg[d])

        # Minimum B shifts each day needs, and the suffix sums, so day filling
        # can tell how much of the surgical nurses' K budget is already spoken
        self.b_req = [max(self.b_lo[d], m + a + e - self.avail[d])
                      if self.surgical_day[d] else 0 for d in range(D)]
        self.b_suffix = [0] * (D + 1)
        for d in range(D - 1, -1, -1):
            self.b_suffix[d] = self.b_suffix[d + 1] + self.b_req[d]

        self.max_work_days = [self._max_work_days(i) for i in range(N)]
        # Upper bound on a nurse's H8 units:
        self.capacity = [min(K, 2 * self.max_work_days[i]) for i in range(N)]

        # Invariant:
        self.total_units = D * (m + a + e)

    def _max_work_days(self, i):
        """Most days nurse i could work, honouring their leaves and H5."""
        D = self.D
        base = i * D
        NEG = -1
        # dp[run] = best working-day count with a run of `run` working days
        # ending at the current day.
        dp = [NEG] * 6
        dp[0] = 0
        for d in range(D):
            nxt = [NEG] * 6
            forced_rest = self.on_leave[base + d]
            for run in range(6):
                val = dp[run]
                if val < 0:
                    continue
                if val > nxt[0]:
                    nxt[0] = val          # rest today
                if not forced_rest and run < 5:
                    if val + 1 > nxt[run + 1]:
                        nxt[run + 1] = val + 1   # work today
            dp = nxt
        return max(dp)

    def _max_alternating_days(self, i, lo=0, hi=None):
        """Most days in [lo, hi) nurse i could take B: off leave, never two in.
        """
        if hi is None:
            hi = self.D
        base = i * self.D
        count = 0
        prev = -2
        for d in range(lo, hi):
            if not self.on_leave[base + d] and d != prev + 1:
                count += 1
                prev = d
        return count

    # ------------------------------------------------------- feasibility --

    def infeasibility_reason(self):
        """Return a reason string if the instance is provably unsatisfiable."""
        N, D, m, a, e = self.N, self.D, self.m, self.a, self.e

        if self.Ns + self.Ng != N:
            return "N_s + N_g != N"
        if len(self.days) != D:
            return "len(days) != D"
        if len(self.leaves) != N * D:
            return "len(leaves) != N*D"

        for d in range(D):
            if self.surgical_day[d]:
                # H7 needs a B, which needs a free surgical nurse and room in
                # both the morning and afternoon quotas.
                if self.b_hi[d] < 1:
                    return "day %d is surgical but no B is possible" % d
                workers = m + a + e - self.b_hi[d]
            else:
                workers = m + a + e
            # Every covered slot needs a distinct nurse (H1), except that a B
            # nurse covers a morning and an afternoon at once.
            if workers > self.avail[d]:
                return ("day %d needs %d distinct nurses but only %d are off leave"
                        % (d, workers, self.avail[d]))

        # Morning succession.
        if D >= 2:
            pools = [set(i for i in range(N) if not self.on_leave[i * D + d])
                     for d in range(D)]
            for d in range(1, D):
                escapable = len(pools[d - 1] - pools[d])
                legal = len(pools[d]) - max(0, (m + e) - escapable)
                if legal < m:
                    return ("day %d can offer at most %d nurses with a legal "
                            "morning but needs %d" % (d, legal, m))

        # B capacity, checked over sliding windows rather than globally.
        b_req = self.b_req
        if any(b_req):
            per_nurse_cap = self.K // 2
            for width in range(2, min(D, 8) + 1):
                for lo in range(0, D - width + 1):
                    need = sum(b_req[lo:lo + width])
                    if not need:
                        continue
                    supply = sum(
                        min(per_nurse_cap, self._max_alternating_days(i, lo,
                                                                     lo + width))
                        for i in range(self.Ns))
                    if need > supply:
                        return ("days %d-%d need %d B shifts but the surgical "
                                "nurses can supply at most %d there"
                                % (lo, lo + width - 1, need, supply))
            # Whole horizon too, which the bounded widths above do not cover.
            need = sum(b_req)
            supply = sum(min(per_nurse_cap, self._max_alternating_days(i, 0, D))
                         for i in range(self.Ns))
            if need > supply:
                return ("surgical days need %d B shifts but the surgical nurses "
                        "can supply at most %d" % (need, supply))

        # Nurse-days over sliding windows.
        free_prefix = []
        for i in range(N):
            base = i * D
            acc = [0] * (D + 1)
            for d in range(D):
                acc[d + 1] = acc[d] + (0 if self.on_leave[base + d] else 1)
            free_prefix.append(acc)

        for width in range(6, min(D, 12) + 1):
            cap = width - width // 6
            for lo in range(0, D - width + 1):
                hi = lo + width
                demand = sum(m + a + e - self.b_hi[d] for d in range(lo, hi))
                if demand <= 0:
                    continue
                supply = 0
                for i in range(N):
                    acc = free_prefix[i]
                    supply += min(cap, acc[hi] - acc[lo])
                    if supply >= demand:
                        break
                if supply < demand:
                    return ("days %d-%d need %d nurse-days but H5 and leave "
                            "allow at most %d there"
                            % (lo, hi - 1, demand, supply))

        # H8 in aggregate:
        if self.total_units > sum(self.capacity):
            return ("workload %d exceeds total nurse capacity %d"
                    % (self.total_units, sum(self.capacity)))

        # H5 in aggregate:
        days_needed = sum(m + a + e - self.b_hi[d] for d in range(D))
        if days_needed > sum(self.max_work_days):
            return ("roster needs %d nurse-days but only %d are workable"
                    % (days_needed, sum(self.max_work_days)))

        return None

    # ------------------------------------------------------------ part B --

    def cost_lower_bound(self, deadline=None):
        """Greatest lower bound we can prove on the Part B cost."""
        m, a, e = self.m, self.a, self.e
        spread = (m - a) ** 2 + (a - e) ** 2 + (e - m) ** 2
        raw = self.D * self.D * spread
        column = -(-raw // self.N)              # ceil
        column += column % 2                    # the cost is always even
        residue = 0 if self.total_units % 3 == 0 else 2
        bound = max(column, residue)

        # When the relaxation is small enough to solve exactly it dominates
        # both analytic forms, because it accounts for H8.
        exact = _relaxed_column_optimum(self.N, self.D * m, self.D * a,
                                        self.D * e, self.K, deadline=deadline)
        if exact is not None and exact > bound:
            bound = exact
        return bound


def _relaxed_column_optimum(N, X, Y, Z, K, budget_states=120000,
                            max_seconds=1.5, deadline=None):
    """Exact minimum cost over per-nurse column totals."""
    if (X + 1) * (Y + 1) * (Z + 1) > budget_states:
        return None
    if (K + 1) * (K + 2) * (K + 3) // 6 > 2000:
        return None
    stop_at = time.monotonic() + max_seconds
    if deadline is not None and deadline < stop_at:
        stop_at = deadline
    total = X + Y + Z
    if total == 0:
        return 0
    # More nurses than units is pointless:
    max_nurses = min(N, total)

    profiles = []
    for dx in range(min(K, X) + 1):
        for dy in range(min(K - dx, Y) + 1):
            for dz in range(min(K - dx - dy, Z) + 1):
                if dx or dy or dz:
                    profiles.append((dx, dy, dz,
                                     (dx - dy) ** 2 + (dy - dz) ** 2 + (dz - dx) ** 2))
    if not profiles:
        return None

    INF = float("inf")
    cur = {(0, 0, 0): 0}
    best = INF
    target = (X, Y, Z)
    for _ in range(max_nurses):
        if time.monotonic() > stop_at:
            return None
        nxt = {}
        # The clock has to be read inside this loop, not just once per nurse:
        seen = 0
        for (x, y, z), c in cur.items():
            seen += 1
            if not seen & 255 and time.monotonic() > stop_at:
                return None
            for dx, dy, dz, pc in profiles:
                nx, ny, nz = x + dx, y + dy, z + dz
                if nx > X or ny > Y or nz > Z:
                    continue
                key = (nx, ny, nz)
                nc = c + pc
                if nxt.get(key, INF) > nc:
                    nxt[key] = nc
        if not nxt:
            break
        cur = nxt
        hit = cur.get(target)
        if hit is not None and hit < best:
            best = hit
    return None if best is INF else best


# ---- output ----

def roster_to_dict(inst, roster):
    D = inst.D
    out = {}
    for i in range(inst.N):
        base = i * D
        for d in range(D):
            out["N%d_%d" % (i, d)] = SHIFT_CHARS[roster[base + d]]
    return out


def write_solution(path, obj):
    """Write JSON so an external kill can never leave a truncated file."""
    directory = os.path.dirname(os.path.abspath(path)) or "."
    tmp = os.path.join(directory, "." + os.path.basename(path) + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


# ---- objective ----

def shift_totals(inst, roster):
    """Per nurse (mornings, afternoons, evenings), with B counting in both."""
    D = inst.D
    totals = []
    for i in range(inst.N):
        base = i * D
        mo = af = ev = 0
        for d in range(D):
            s = roster[base + d]
            if s == M:
                mo += 1
            elif s == A:
                af += 1
            elif s == E:
                ev += 1
            elif s == B:
                mo += 1
                af += 1
        totals.append((mo, af, ev))
    return totals


def objective(inst, roster):
    """Part B cost, matching verifier.calculate_objective exactly."""
    total = 0
    for mo, af, ev in shift_totals(inst, roster):
        t = mo + af + ev
        total += 3 * (mo * mo + af * af + ev * ev) - t * t
    return total


# ---- verifier ----

def violations(inst, roster):
    """Names of every hard constraint the roster breaks."""
    N, D = inst.N, inst.D
    bad = []

    # H1:
    for i in range(N):
        base = i * D
        for d in range(D):
            s = roster[base + d]
            if not 0 <= s <= 4 or (s == B and i >= inst.Ns):
                bad.append("H1")
                break
        else:
            continue
        break

    for i in range(N):
        base = i * D
        for d in range(D - 1):
            cur, nxt = roster[base + d], roster[base + d + 1]
            if cur in MORNING_SHIFTS and nxt in MORNING_SHIFTS:
                bad.append("H2")
                break
        else:
            continue
        break

    for i in range(N):
        base = i * D
        for d in range(D - 1):
            if roster[base + d] == E and roster[base + d + 1] in MORNING_SHIFTS:
                bad.append("H3")
                break
        else:
            continue
        break

    # H4:
    for d in range(D):
        cm = ca = ce = cb = 0
        for i in range(N):
            s = roster[i * D + d]
            if s == M:
                cm += 1
            elif s == A:
                ca += 1
            elif s == E:
                ce += 1
            elif s == B:
                cb += 1
        if cb and not inst.surgical_day[d]:
            bad.append("H4")
            break
        if cm + cb != inst.m or ca + cb != inst.a or ce != inst.e:
            bad.append("H4")
            break

    # H5:
    for i in range(N):
        base = i * D
        for start in range(D - 5):
            if all(roster[base + d] != R for d in range(start, start + 6)):
                bad.append("H5")
                break
        else:
            continue
        break

    for i in range(N):
        base = i * D
        for d in range(D - 1):
            if roster[base + d] == B and roster[base + d + 1] not in (R, E):
                bad.append("H6")
                break
        else:
            continue
        break

    for d in range(D):
        if inst.surgical_day[d] and not any(
                roster[i * D + d] == B for i in range(inst.Ns)):
            bad.append("H7")
            break

    for i in range(N):
        base = i * D
        if sum(SHIFT_UNITS[roster[base + d]] for d in range(D)) > inst.K:
            bad.append("H8")
            break

    for idx in range(N * D):
        if inst.on_leave[idx] and roster[idx] != R:
            bad.append("H9")
            break

    return bad


def is_valid(inst, roster):
    return not violations(inst, roster)


# ---- day filling ----

# Which of yesterday's shifts block a morning (M or B) today:
_BLOCKED_BEFORE_MORNING = (M, B, E)


def min_b(inst, d):
    """Fewest B shifts day d can run with, or None if the day is impossible."""
    if not inst.surgical_day[d]:
        return 0
    b = max(inst.b_lo[d], inst.m + inst.a + inst.e - inst.avail[d])
    return b if b <= inst.b_hi[d] else None


def fill_day(inst, d, b, units, last, run, cnt, rng, cost_aware=False):
    """Pick who works day d, using exactly b surgical (B) shifts."""
    N, D, K, Ns = inst.N, inst.D, inst.K, inst.Ns
    m, a, e = inst.m, inst.a, inst.e

    if b < inst.b_lo[d] or b > inst.b_hi[d] or m - b < 0 or a - b < 0:
        return None

    need = {}
    if b:
        need[B] = b
    if m - b:
        need[M] = m - b
    if a - b:
        need[A] = a - b
    if e:
        need[E] = e

    # Off leave (H9), still inside budget (H8), not at five straight days (H5).
    free = [i for i in range(N)
            if not inst.on_leave[i * D + d] and units[i] < K and run[i] < 5]

    # Only surgical nurses can take B, every B costs two units of K, and the
    # remaining surgical days have a fixed B demand.
    reserve_surgical = False
    if Ns and inst.b_suffix[d]:
        surgical_capacity = sum((K - units[i]) // 2 for i in range(Ns))
        reserve_surgical = surgical_capacity - inst.b_suffix[d] <= 1

    used = [False] * N
    chosen = {}
    while need:
        best_shift = best_slack = best_cands = None
        for shift, want in need.items():
            if shift == B:
                cands = [i for i in free
                         if not used[i] and i < Ns
                         and last[i] not in _BLOCKED_BEFORE_MORNING
                         and units[i] + 2 <= K]
            elif shift == M:
                cands = [i for i in free
                         if not used[i]
                         and last[i] not in _BLOCKED_BEFORE_MORNING]
            elif shift == A:
                cands = [i for i in free if not used[i] and last[i] != B]
            else:                                   # E has no predecessor rule
                cands = [i for i in free if not used[i]]

            slack = len(cands) - want
            if slack < 0:
                return None
            if best_slack is None or slack < best_slack:
                best_shift, best_slack, best_cands = shift, slack, cands

        # LCV.
        held_back = (reserve_surgical and best_shift != B)

        if best_shift == A:
            blocks = None
        else:
            nxt = d + 1
            if nxt < D:
                blocks = [0 if inst.on_leave[i * D + nxt] else 1
                          for i in range(N)]
            else:
                blocks = None

        if cost_aware:
            # Part B:
            col = None if best_shift == B else (
                2 if best_shift == E else (1 if best_shift == A else 0))

            def key(i, col=col, blocks=blocks, held=held_back):
                spent = cnt[i][0] + cnt[i][1] if col is None else cnt[i][col]
                return (1 if held and i < Ns else 0,
                        0 if blocks is None else blocks[i],
                        spent, units[i], run[i], rng.random())
            best_cands.sort(key=key)
        else:
            def key(i, blocks=blocks, held=held_back):
                return (1 if held and i < Ns else 0,
                        0 if blocks is None else blocks[i],
                        units[i], run[i], rng.random())
            best_cands.sort(key=key)

        want = need.pop(best_shift)
        for i in best_cands[:want]:
            used[i] = True
            chosen[i] = best_shift
    return chosen


def advance(inst, chosen, units, last, run, cnt):
    """Per-nurse state after one day. Returns fresh lists, leaving inputs alone.
    """
    N = inst.N
    nunits, nrun = units[:], run[:]
    nlast = [R] * N
    ncnt = [c[:] for c in cnt]
    for i in range(N):
        shift = chosen.get(i, R)
        nlast[i] = shift
        if shift == R:
            nrun[i] = 0                      # a rest clears the H5 run
        else:
            nrun[i] += 1
            nunits[i] += SHIFT_UNITS[shift]
            if shift == M:
                ncnt[i][0] += 1
            elif shift == A:
                ncnt[i][1] += 1
            elif shift == E:
                ncnt[i][2] += 1
            else:
                ncnt[i][0] += 1
                ncnt[i][1] += 1
    return nunits, nlast, nrun, ncnt


def forward_ok(inst, d, units, last, run):
    """Forward check: can day d still be staffed from the current state?."""
    if d >= inst.D:
        return True
    N, D, K, Ns = inst.N, inst.D, inst.K, inst.Ns
    b = min_b(inst, d)
    if b is None:
        return False

    workers = mornings = surgical_mornings = 0
    for i in range(N):
        if inst.on_leave[i * D + d] or units[i] >= K or run[i] >= 5:
            continue
        workers += 1
        if last[i] not in _BLOCKED_BEFORE_MORNING:
            mornings += 1
            if i < Ns and units[i] + 2 <= K:
                surgical_mornings += 1

    if workers < inst.m + inst.a + inst.e - inst.b_hi[d]:
        return False
    if mornings < inst.m:
        return False
    return surgical_mornings >= b


# ---- tier 1: construction ----

def construct(inst, rng, cost_aware=False, b_policy="min"):
    """Greedy pass over the days. Returns a roster, or None on a dead end."""
    N, D = inst.N, inst.D
    roster = [R] * (N * D)
    units, last, run = [0] * N, [R] * N, [0] * N
    cnt = [[0, 0, 0] for _ in range(N)]

    for d in range(D):
        b = min_b(inst, d)
        if b is None:
            return None
        chosen = None
        if b_policy == "max" and inst.b_hi[d] > b:
            chosen = fill_day(inst, d, inst.b_hi[d], units, last, run, cnt,
                              rng, cost_aware)
        if chosen is None:
            chosen = fill_day(inst, d, b, units, last, run, cnt, rng, cost_aware)
        if chosen is None:
            return None
        for i, shift in chosen.items():
            roster[i * D + d] = shift
        units, last, run, cnt = advance(inst, chosen, units, last, run, cnt)

    return roster


# ------------------------------------------------- tier 2: backtracking CSP --

def solve_tier2(inst, deadline, rng, variants=3, node_budget=None,
                cost_aware=False):
    """Day-level backtracking for instances where restarts alone dead-end."""
    N, D = inst.N, inst.D
    roster = [R] * (N * D)
    state = {"nodes": 0, "stop": False}

    def descend(d, units, last, run, cnt):
        if state["stop"]:
            return False
        if d == D:
            return True

        state["nodes"] += 1
        if not state["nodes"] & 31:
            if time.monotonic() > deadline:
                state["stop"] = True
                return False
        if node_budget is not None and state["nodes"] > node_budget:
            state["stop"] = True
            return False

        low = min_b(inst, d)
        if low is None:
            return False
        b_values = range(low, inst.b_hi[d] + 1) if inst.surgical_day[d] else (0,)

        for b in b_values:
            for _ in range(variants):
                if state["stop"]:
                    return False
                chosen = fill_day(inst, d, b, units, last, run, cnt, rng,
                                  cost_aware)
                if chosen is None:
                    continue            # randomised: another draw may staff it
                nunits, nlast, nrun, ncnt = advance(
                    inst, chosen, units, last, run, cnt)
                if not forward_ok(inst, d + 1, nunits, nlast, nrun):
                    continue
                for i, shift in chosen.items():
                    roster[i * D + d] = shift
                if descend(d + 1, nunits, nlast, nrun, ncnt):
                    return True
                for i in chosen:                     # undo before the next try
                    roster[i * D + d] = R
        return False

    start = ([0] * N, [R] * N, [0] * N, [[0, 0, 0] for _ in range(N)])
    found = descend(0, *start)
    return roster if found else None


def solve_part_a(inst, deadline, rng=None):
    """Find any valid roster. Returns (roster or None, attempts)."""
    if rng is None:
        rng = random.Random(0xC01333)
    if inst.infeasibility_reason() is not None:
        return None, 0

    now = time.monotonic()
    # Tier 1 resolves in milliseconds when it resolves at all, so its slice
    # must be a small constant rather than a fraction of the budget:
    tier1_until = min(deadline, now + min(3.0, 0.5 * (deadline - now)))

    attempts = 0
    while time.monotonic() < tier1_until:
        attempts += 1
        roster = construct(inst, rng)
        if roster is not None and is_valid(inst, roster):
            return roster, attempts

    budget_nodes = 2000
    while time.monotonic() < deadline:
        attempts += 1
        roster = solve_tier2(inst, deadline, rng, node_budget=budget_nodes)
        if roster is not None and is_valid(inst, roster):
            return roster, attempts
        # Exhausting the budget means this subtree was a bad bet, not that the
        # instance is hopeless -- restart wider with a fresh set of tie-breaks.
        budget_nodes *= 4

    return None, attempts


# --------------------------------------------------- part B: local search --

def swap_ok(inst, roster, units, d, i, j):
    """Can nurses i and j exchange their day-d shifts?."""
    D = inst.D
    u = roster[i * D + d]
    v = roster[j * D + d]
    if u == v:
        return False
    if (v == B and i >= inst.Ns) or (u == B and j >= inst.Ns):
        return False                                            # H1
    if (inst.on_leave[i * D + d] and v != R) or \
       (inst.on_leave[j * D + d] and u != R):
        return False                                            # H9
    wu, wv = SHIFT_UNITS[u], SHIFT_UNITS[v]
    if units[i] - wu + wv > inst.K or units[j] - wv + wu > inst.K:
        return False                                            # H8

    for nurse, shift in ((i, v), (j, u)):
        base = nurse * D
        prev = roster[base + d - 1] if d > 0 else R
        nxt = roster[base + d + 1] if d < D - 1 else R
        if shift in MORNING_SHIFTS and prev in (M, B, E):
            return False                                        # H2, H3
        if nxt in MORNING_SHIFTS and shift in (M, B, E):
            return False                                        # H2, H3
        if prev == B and shift not in (R, E):
            return False                                        # H6
        if shift == B and nxt not in (R, E):
            return False                                        # H6

    # H5 can only break when one side rests and the other does not:
    if (u == R) != (v == R):
        for nurse, shift in ((i, v), (j, u)):
            if shift == R:
                continue                                # resting only splits runs
            base = nurse * D
            before = 0
            for step in range(1, 6):
                if d - step < 0 or roster[base + d - step] == R:
                    break
                before += 1
            after = 0
            for step in range(1, 6):
                if d + step >= D or roster[base + d + step] == R:
                    break
                after += 1
            if before + 1 + after > 5:
                return False
    return True


def _nurse_cost(mornings, afternoons, evenings):
    """Per-nurse cost via the squared-differences identity (see §2.3)."""
    return ((mornings - afternoons) ** 2 + (afternoons - evenings) ** 2
            + (evenings - mornings) ** 2)


def _shift_delta(counts, shift, sign):
    if shift == M:
        counts[0] += sign
    elif shift == A:
        counts[1] += sign
    elif shift == E:
        counts[2] += sign
    elif shift == B:
        counts[0] += sign
        counts[1] += sign


def optimize(inst, roster, deadline, rng, bound=None, on_improve=None):
    """Hill-climb the soft cost over the same-day swap neighbourhood."""
    D, N = inst.D, inst.N
    if bound is None:
        bound = inst.cost_lower_bound()

    counts = [list(t) for t in shift_totals(inst, roster)]
    units = [sum(SHIFT_UNITS[roster[i * D + d]] for d in range(D))
             for i in range(N)]
    cost = objective(inst, roster)

    # Sampling only from nurses who actually hold a shift avoids the rest/rest
    # draws, which are the large majority when few nurses work each day.
    workers = [[i for i in range(N) if roster[i * D + d] != R] for d in range(D)]

    best_cost, best_roster = cost, roster[:]
    if on_improve is not None:
        on_improve(best_roster, best_cost)

    checks = 0
    while cost > bound:
        checks += 1
        if not checks & 255 and time.monotonic() > deadline:
            break

        d = rng.randrange(D)
        pool = workers[d]
        if not pool:
            continue
        i = pool[rng.randrange(len(pool))]
        j = rng.randrange(N)
        if i == j:
            continue
        u = roster[i * D + d]
        v = roster[j * D + d]
        if u == v:
            continue

        ci, cj = counts[i], counts[j]
        before = _nurse_cost(*ci) + _nurse_cost(*cj)
        _shift_delta(ci, u, -1)
        _shift_delta(ci, v, 1)
        _shift_delta(cj, v, -1)
        _shift_delta(cj, u, 1)
        delta = _nurse_cost(*ci) + _nurse_cost(*cj) - before

        if delta <= 0 and swap_ok(inst, roster, units, d, i, j):
            roster[i * D + d] = v
            roster[j * D + d] = u
            units[i] += SHIFT_UNITS[v] - SHIFT_UNITS[u]
            units[j] += SHIFT_UNITS[u] - SHIFT_UNITS[v]
            if (u == R) != (v == R):
                if v == R:
                    pool.remove(i)
                    pool.append(j)
                else:
                    pool.remove(j)
                    pool.append(i)
            cost += delta
            if cost < best_cost:
                best_cost, best_roster = cost, roster[:]
                if on_improve is not None:
                    on_improve(best_roster, best_cost)
        else:
            _shift_delta(ci, v, -1)
            _shift_delta(ci, u, 1)
            _shift_delta(cj, u, -1)
            _shift_delta(cj, v, 1)

    return best_roster, best_cost


def solve_part_b(inst, deadline, rng=None, on_improve=None):
    """Find a low-cost valid roster. Returns (roster or None, cost)."""
    if rng is None:
        rng = random.Random(0xC01333)
    if inst.infeasibility_reason() is not None:
        return None, 0

    # The relaxation DP is worth a lot -- it is what makes the early exit fire
    # -- but it must never eat the budget it is meant to save. Cap it at a
    # fifth of what is left, so a slow bound degrades to the analytic form
    # instead of starving the search or overrunning T.
    now = time.monotonic()
    bound = inst.cost_lower_bound(deadline=now + 0.2 * (deadline - now))

    best_roster = best_cost = None

    # A few construction attempts, keeping the cheapest.
    candidates = []
    for policy in ("min", "max"):
        attempts_left = 4
        best_here = None
        gen_deadline = min(deadline,
                           time.monotonic() + 0.02 * (deadline - time.monotonic()))
        while attempts_left > 0 and time.monotonic() < gen_deadline:
            attempts_left -= 1
            roster = construct(inst, rng, cost_aware=True, b_policy=policy)
            if roster is None or not is_valid(inst, roster):
                continue
            cost = objective(inst, roster)
            if best_here is None or cost < best_here[1]:
                best_here = (roster[:], cost)
        if best_here is not None:
            candidates.append(best_here)

    if candidates:
        candidates.sort(key=lambda pair: pair[1])
        best_roster, best_cost = candidates[0]
        if on_improve is not None:
            on_improve(best_roster, best_cost)
        if best_cost <= bound:
            return best_roster, best_cost

    if best_roster is None:
        roster, _ = solve_part_a(inst, deadline, rng)
        if roster is None:
            return None, 0
        best_roster, best_cost = roster, objective(inst, roster)
        if on_improve is not None:
            on_improve(best_roster, best_cost)

    # The cheaper starting roster does not reliably stay cheaper after local
    # search, so climb from each distinct candidate and keep the winner.
    if best_cost > bound and candidates:
        share = (deadline - time.monotonic()) / len(candidates)
        for roster, _ in candidates:
            sub = min(deadline, time.monotonic() + share)
            found, cost = optimize(inst, roster, sub, rng, bound=bound)
            if cost < best_cost:
                best_roster, best_cost = found, cost
                if on_improve is not None:
                    on_improve(best_roster, best_cost)
            if best_cost <= bound:
                break
    elif best_cost > bound:
        best_roster, best_cost = optimize(inst, best_roster, deadline, rng,
                                          bound=bound, on_improve=on_improve)
    return best_roster, best_cost

# ------------------------------------------------------------ entry point --

if __name__ == "__main__":
    instance = parse_input(sys.argv[1])
    output_path = sys.argv[2]

    # Part B is scored on cost first, so unlike Part A it spends the budget --
    # but every improvement is written as it is found, so an unexpected kill
    # still leaves the best roster so far on disk rather than nothing.
    budget = max(1.0, 0.9 * instance.T)
    deadline = time.monotonic() + budget

    written = [None]

    def publish(roster, cost):
        if written[0] is None or cost < written[0]:
            written[0] = cost
            write_solution(output_path, roster_to_dict(instance, roster))

    roster, _ = solve_part_b(instance, deadline, on_improve=publish)

    if roster is None:
        write_solution(output_path, {})
