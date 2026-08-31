"""COL333 Assignment 1 -- Part A

GENERATED FILE. Edit dev/core.py or dev/driver_a.py and re-run dev/build.py.
Standard library only; self-contained by design.
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

    def _max_alternating_days(self, i):
        """Most days nurse i could take B: non-leave and never two in a row."""
        base = i * self.D
        count = 0
        prev = -2
        for d in range(self.D):
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

        # Morning succession. On any day after the first, everyone who worked a
        # morning yesterday is blocked by H2 and everyone who worked an evening
        # is blocked by H3. Those are m + e distinct nurses, so at most
        # N - m - e can start a morning today.
        if D >= 2 and 2 * m + e > N:
            return ("2m + e = %d exceeds N = %d, so no day after the first can "
                    "staff %d mornings" % (2 * m + e, N, m))

        # B capacity. Each surgical day needs at least b_lo B shifts, every B
        # costs 2 units of K, and H2 stops one nurse taking B on consecutive
        # days -- so B supply is far scarcer than raw headcount suggests.
        b_needed = sum(max(self.b_lo[d], m + a + e - self.avail[d])
                       for d in range(D) if self.surgical_day[d])
        if b_needed:
            b_supply = sum(min(self.K // 2, self._max_alternating_days(i))
                           for i in range(self.Ns))
            if b_needed > b_supply:
                return ("surgical days need %d B shifts but the surgical nurses "
                        "can supply at most %d" % (b_needed, b_supply))

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


# ------------------------------------------------------- tier 1: construct --

# Which previous-day shifts block today's shift.
#   H2  no morning (M or B) straight after a morning (M or B)
#   H3  no morning straight after an evening
#   H6  only R or E may follow a B
_BLOCKED_BEFORE_MORNING = (M, B, E)


def construct(inst, rng, cost_aware=False):
    """Build a roster one day at a time. Returns a roster, or None on dead end.

    Each day is 'choose disjoint nurse sets of sizes b, m-b, a-b, e'. Within a
    day the shift types are filled in MRV order -- tightest slack first -- and
    each type's nurses are picked by an LCV-flavoured rule that spreads load, so
    budgets and rest runs stay usable on later days.

    Randomised tie-breaks make this worth restarting: the caller re-runs it with
    a fresh rng until it succeeds or the deadline passes.
    """
    N, D, K, Ns = inst.N, inst.D, inst.K, inst.Ns
    m, a, e = inst.m, inst.a, inst.e

    roster = [R] * (N * D)
    units = [0] * N          # H8 spend so far (B costs 2)
    last = [R] * N           # yesterday's shift, for H2/H3/H6
    run = [0] * N            # consecutive working days ending yesterday, for H5
    cnt = [[0, 0, 0] for _ in range(N)]   # per nurse: mornings, afternoons, evenings

    for d in range(D):
        surgical = inst.surgical_day[d]
        offset = d

        # Decision 5, option C: as few B shifts as H7 allows, unless the day is
        # too short-staffed to field m + a + e - b distinct nurses.
        if surgical:
            b = max(inst.b_lo[d], m + a + e - inst.avail[d])
            if b > inst.b_hi[d]:
                return None
        else:
            b = 0

        need = {}
        if b:
            need[B] = b
        if m - b:
            need[M] = m - b
        if a - b:
            need[A] = a - b
        if e:
            need[E] = e
        if m - b < 0 or a - b < 0:
            return None

        # Nurses who may work at all today: off leave, under budget, and not
        # already at five consecutive working days.
        free = [i for i in range(N)
                if not inst.on_leave[i * D + offset]
                and units[i] < K and run[i] < 5]

        used = [False] * N
        while need:
            # MRV over shift types: fill whichever has the least slack.
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
                else:                                    # E is unrestricted
                    cands = [i for i in free if not used[i]]

                slack = len(cands) - want
                if slack < 0:
                    return None
                if best_slack is None or slack < best_slack:
                    best_shift, best_slack, best_cands = shift, slack, cands

            # LCV: spend the nurses who constrain the future least. Lowest spend
            # first keeps budgets level (so nobody hits K early and shrinks a
            # later day's pool), shortest run first defers forced rests.
            if cost_aware:
                # Part B: also favour whoever is shortest on this shift type.
                # A B shift adds a morning and an afternoon at once.
                col = 2 if best_shift == E else (1 if best_shift == A else 0)
                if best_shift == B:
                    best_cands.sort(key=lambda i: (cnt[i][0] + cnt[i][1],
                                                   units[i], run[i], rng.random()))
                else:
                    best_cands.sort(key=lambda i: (cnt[i][col], units[i],
                                                   run[i], rng.random()))
            else:
                best_cands.sort(key=lambda i: (units[i], run[i], rng.random()))

            want = need.pop(best_shift)
            for i in best_cands[:want]:
                used[i] = True
                roster[i * D + offset] = best_shift

        # Roll the per-nurse state forward. Everyone unassigned rests, which
        # clears their run.
        for i in range(N):
            shift = roster[i * D + offset]
            last[i] = shift
            if shift == R:
                run[i] = 0
            else:
                run[i] += 1
                units[i] += SHIFT_UNITS[shift]
                if shift == M:
                    cnt[i][0] += 1
                elif shift == A:
                    cnt[i][1] += 1
                elif shift == E:
                    cnt[i][2] += 1
                else:
                    cnt[i][0] += 1
                    cnt[i][1] += 1

    return roster


def solve_part_a(inst, deadline, rng=None):
    """Find any valid roster. Returns (roster or None, attempts used).

    Tier 1 is randomised, so restarting it is itself a search strategy: each
    restart re-rolls the tie-breaks that led into the dead end. Part A is graded
    on wall-clock time, so this returns the first roster that verifies.
    """
    if rng is None:
        rng = random.Random(0xC01333)

    if inst.infeasibility_reason() is not None:
        return None, 0

    attempts = 0
    while time.monotonic() < deadline:
        attempts += 1
        roster = construct(inst, rng)
        if roster is not None and is_valid(inst, roster):
            return roster, attempts
    return None, attempts

# ------------------------------------------------------------ entry point --

if __name__ == "__main__":
    instance = parse_input(sys.argv[1])
    output_path = sys.argv[2]

    # T is enforced per instance, so leave a margin for interpreter start-up
    # and the final write. Part A is scored on actual runtime, not on budget
    # used, so this is only a ceiling -- solve_part_a returns the moment a
    # roster verifies.
    budget = max(1.0, 0.9 * instance.T)
    roster, _ = solve_part_a(instance, deadline=time.monotonic() + budget)

    if roster is None:
        write_solution(output_path, {})
    else:
        write_solution(output_path, roster_to_dict(instance, roster))
