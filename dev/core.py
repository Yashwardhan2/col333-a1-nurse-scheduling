"""Shared solver core for COL333 A1 (nurse rostering).

This module is concatenated verbatim into part_a.py and part_b.py by dev/build.py,
so it must stay standard-library only and must not define a __main__ block.
"""

import csv
import json
import os
import random
import sys
import time

# ---------------------------------------------------------------- encoding --

# Shifts are small ints so rosters can live in flat lists and hot loops can
# compare with `==` instead of hashing strings.
R, M, A, E, B = 0, 1, 2, 3, 4
SHIFT_CHARS = ("R", "M", "A", "E", "B")

# A nurse's contribution to (mornings, afternoons, evenings) per shift.
MORNING_SHIFTS = (M, B)
AFTERNOON_SHIFTS = (A, B)

# H8 weight: B occupies both a morning and an afternoon slot.
SHIFT_UNITS = (0, 1, 1, 1, 2)


# ------------------------------------------------------------------- input --

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
    """Instance data plus the precomputation every search layer shares.

    Rosters are flat lists of length N*D indexed by `i * D + d`.
    """

    __slots__ = (
        "N", "D", "Ns", "Ng", "m", "a", "e", "T", "days", "K", "leaves",
        "surgical_day", "on_leave", "avail", "avail_surg",
        "b_lo", "b_hi", "max_work_days", "capacity", "total_units",
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

        # b_d = number of B shifts on day d. H4 forbids B on G days; H7 forces
        # at least one on S days. A B nurse fills one morning and one afternoon
        # slot, so b_d cannot exceed m or a.
        self.b_lo = [0] * D
        self.b_hi = [0] * D
        for d in range(D):
            if self.surgical_day[d]:
                self.b_lo[d] = 1
                self.b_hi[d] = min(m, a, self.avail_surg[d])

        self.max_work_days = [self._max_work_days(i) for i in range(N)]
        # Upper bound on a nurse's H8 units: every working day yields at most 2
        # (a B day). Deliberately loose so infeasibility claims stay sound.
        self.capacity = [min(K, 2 * self.max_work_days[i]) for i in range(N)]

        # Invariant: sum over nurses of (C_M + C_A + C_E) is fixed, because each
        # day hands out exactly m + a + e slot-units regardless of how many B's
        # are used. This is what pins down the Part B lower bound.
        self.total_units = D * (m + a + e)

    def _max_work_days(self, i):
        """Most days nurse i could work, honouring their leaves and H5."""
        D = self.D
        base = i * D
        NEG = -1
        # dp[run] = best working-day count with a run of `run` working days
        # ending at the current day. H5 caps a run at 5.
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
        """Most days in [lo, hi) nurse i could take B: off leave, never two in
        a row. Greedy earliest-first is optimal for an interval like this."""
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
        """Return a reason string if the instance is provably unsatisfiable.

        Sound but not complete: it only ever reports conditions that genuinely
        rule out every roster, so a None result means "not obviously broken",
        never "definitely solvable".
        """
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

        # Morning succession. Yesterday's m morning workers are blocked by H2
        # and its e evening workers by H3, so today's m mornings must come from
        # nurses outside that set of exactly m + e. The blocked set is drawn
        # from yesterday's available pool, so the most of it that can dodge
        # today's pool is |avail(d-1) \ avail(d)| -- everything beyond that must
        # overlap and eats into today's morning-legal supply.
        #
        # The leave-free form of this is just 2m + e <= N; accounting for who is
        # actually on leave each day makes it strictly sharper, and it is that
        # sharper form which catches real instances.
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
        # H2 stops a nurse taking B on consecutive days, so inside any window of
        # L consecutive days one nurse can cover at most ceil(L/2) of its B
        # shifts -- and every B costs 2 units of K on top. A whole-horizon count
        # misses the local squeeze: a single surgical nurse facing two adjacent
        # surgical days has ample budget overall yet cannot cover both.
        b_req = [max(self.b_lo[d], m + a + e - self.avail[d])
                 if self.surgical_day[d] else 0 for d in range(D)]
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

        # H8 in aggregate: the fixed workload must fit inside the nurses' budgets.
        if self.total_units > sum(self.capacity):
            return ("workload %d exceeds total nurse capacity %d"
                    % (self.total_units, sum(self.capacity)))

        # H5 in aggregate: count nurse-days rather than slot-units. Using b_hi
        # minimises the days required, keeping the test sound.
        days_needed = sum(m + a + e - self.b_hi[d] for d in range(D))
        if days_needed > sum(self.max_work_days):
            return ("roster needs %d nurse-days but only %d are workable"
                    % (days_needed, sum(self.max_work_days)))

        return None

    # ------------------------------------------------------------ part B --

    def cost_lower_bound(self):
        """Least achievable Part B cost, ignoring the hard constraints.

        Per nurse the cost floor is decided purely by the parity of their total
        units t: 0 when t % 3 == 0, else 2 (verified by brute force in
        dev/verify_bound.py). Since sum(t_i) = total_units is invariant, at most
        one nurse need be off a multiple of three.
        """
        return 0 if self.total_units % 3 == 0 else 2


# ------------------------------------------------------------------ output --

def roster_to_dict(inst, roster):
    D = inst.D
    out = {}
    for i in range(inst.N):
        base = i * D
        for d in range(D):
            out["N%d_%d" % (i, d)] = SHIFT_CHARS[roster[base + d]]
    return out


def write_solution(path, obj):
    """Write JSON so an external kill can never leave a truncated file.

    The temp file shares a directory with the target (os.replace is only atomic
    within one filesystem) and is fsynced before the swap, so the replacement is
    never an empty file.
    """
    directory = os.path.dirname(os.path.abspath(path)) or "."
    tmp = os.path.join(directory, "." + os.path.basename(path) + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


# --------------------------------------------------------------- objective --

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


# ---------------------------------------------------------------- verifier --

def violations(inst, roster):
    """Names of every hard constraint the roster breaks.

    Mirrors verifier.py exactly, including the places where the shipped
    verifier is stricter than the handout: B is rejected on G days (H4), and
    only R or E may follow a B (H6).
    """
    N, D = inst.N, inst.D
    bad = []

    # H1: legal label, and B reserved for surgical nurses.
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

    # H4: exact daily cover, with B counting toward both m and a.
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

    # H5: only meaningful once there is a full six-day window.
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


# ------------------------------------------------------------ day filling --

# Which of yesterday's shifts block a morning (M or B) today:
#   H2  no morning straight after a morning
#   H3  no morning straight after an evening
#   H6  only R or E may follow a B
_BLOCKED_BEFORE_MORNING = (M, B, E)


def min_b(inst, d):
    """Fewest B shifts day d can run with, or None if the day is impossible.

    Decision 5, option C: as few B shifts as H7 allows, raised only when the day
    cannot otherwise field m + a + e - b distinct nurses.
    """
    if not inst.surgical_day[d]:
        return 0
    b = max(inst.b_lo[d], inst.m + inst.a + inst.e - inst.avail[d])
    return b if b <= inst.b_hi[d] else None


def fill_day(inst, d, b, units, last, run, cnt, rng, cost_aware=False):
    """Pick who works day d, using exactly b surgical (B) shifts.

    Returns {nurse: shift} covering everyone who works, or None if the day
    cannot be staffed. Shift types are filled in MRV order -- least slack first,
    recomputed after each type, since assigning one type shrinks the others'
    pools. Nurses come from an LCV rule that keeps later days viable.
    """
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

        # LCV. Lowest spend first keeps K budgets level so nobody exhausts early
        # and shrinks a later day's pool; shortest run first defers forced rests;
        # the jitter is what makes a restart explore somewhere new.
        #
        # M, B and E are the shifts that block a morning tomorrow (H2/H3), and
        # tomorrow always needs exactly m nurses with a legal morning. So spend
        # them first on nurses who cannot work tomorrow anyway -- blocking those
        # costs nothing, while blocking an available nurse eats into a quota
        # that is usually the binding one.
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
            # Part B: prefer whoever is shortest on this shift type. A B shift
            # adds a morning and an afternoon at once, so it reads both columns.
            col = None if best_shift == B else (
                2 if best_shift == E else (1 if best_shift == A else 0))

            def key(i, col=col, blocks=blocks):
                spent = cnt[i][0] + cnt[i][1] if col is None else cnt[i][col]
                return (0 if blocks is None else blocks[i],
                        spent, units[i], run[i], rng.random())
            best_cands.sort(key=key)
        else:
            def key(i, blocks=blocks):
                return (0 if blocks is None else blocks[i],
                        units[i], run[i], rng.random())
            best_cands.sort(key=key)

        want = need.pop(best_shift)
        for i in best_cands[:want]:
            used[i] = True
            chosen[i] = best_shift
    return chosen


def advance(inst, chosen, units, last, run, cnt):
    """Per-nurse state after one day. Returns fresh lists, leaving inputs alone
    so a backtracking caller can reuse the parent's state."""
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
    """Forward check: can day d still be staffed from the current state?

    Mornings are the binding resource -- M and B together always need exactly m
    nurses whose previous shift permits a morning -- so this catches most dead
    ends one day before the search walks into them.
    """
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


# ---------------------------------------------------- tier 1: construction --

def construct(inst, rng, cost_aware=False):
    """Greedy pass over the days. Returns a roster, or None on a dead end.

    Randomised tie-breaks make restarting a search strategy in its own right:
    each restart re-rolls the choices that led into the dead end.
    """
    N, D = inst.N, inst.D
    roster = [R] * (N * D)
    units, last, run = [0] * N, [R] * N, [0] * N
    cnt = [[0, 0, 0] for _ in range(N)]

    for d in range(D):
        b = min_b(inst, d)
        if b is None:
            return None
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
    """Day-level backtracking for instances where restarts alone dead-end.

    Depth is D, not N*D: one decision per day. Each node branches over b_d
    (Decision 5, option D) and over a few randomised fillings of that day, with
    forward checking on the next day pruning most dead ends a level early.

    Aborting matters as much as searching here. A plain `return False` on the
    deadline is indistinguishable from "this branch failed", so every ancestor
    would dutifully try its remaining variants and unwinding would itself take
    exponential time -- overrunning T and scoring zero. The `stop` flag makes
    the abort unambiguous and collapses the stack immediately.

    Not complete -- it samples `variants` fillings per b rather than enumerating
    every partition of nurses into slots -- so a None result means "not found",
    never "proved unsatisfiable". Only infeasibility_reason() proves that.
    """
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
    """Find any valid roster. Returns (roster or None, attempts).

    Tier 1 first: it settles most instances in milliseconds, and Part A is
    graded on actual runtime, so the cheap path has to come first. Tier 2 takes
    over the remaining budget for whatever survives.
    """
    if rng is None:
        rng = random.Random(0xC01333)
    if inst.infeasibility_reason() is not None:
        return None, 0

    now = time.monotonic()
    # Tier 1 resolves in milliseconds when it resolves at all, so its slice must
    # be a small constant rather than a fraction of the budget: on a 300s
    # instance a 25% share burned a minute of hopeless restarts before the real
    # search got a look in.
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
