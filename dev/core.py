"""Shared solver core for COL333 A1 (nurse rostering).

This module is concatenated verbatim into part_a.py and part_b.py by dev/build.py,
so it must stay standard-library only and must not define a __main__ block.
"""

import csv
import json
import os
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
