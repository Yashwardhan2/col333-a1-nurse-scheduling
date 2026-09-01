# COL333 Assignment 1 — Nurse Scheduling: Progress & Design Document

**Status:** Complete and submittable. Part A hardened; Part B optimal on all three
samples; `report.txt` written; `submission.zip` verified end to end.
**Deadline:** 17:00, Thu 3 Sep 2026. **Weighting:** Part A ≈ 80%, Part B ≈ 20%.

This document is a self-contained record of the work so far, written so that a
reviewer with no prior context can critique the modelling, the algorithms, and
the empirical claims. Sections 3, 6 and 10 are where review is most useful.

---

## 1. Problem statement (as pinned against the grader)

Build a roster for `N` nurses over `D` days. Day `d` is surgical (`S`) or
general (`G`). Each nurse gets exactly one label per day from
`{M, A, E, R, B}` — morning, afternoon, evening, rest, surgery.
`B` = morning + afternoon combined, surgical nurses only (indices `0 … Ns-1`).

**Hard constraints (Part A):**

| ID | Constraint |
|----|------------|
| H1 | Exactly one label per nurse per day; `B` only for surgical nurses |
| H2 | No two consecutive morning shifts (`B` counts as a morning) |
| H3 | No morning shift immediately after an evening shift |
| H4 | Exactly `m`/`a`/`e` nurses on morning/afternoon/evening each day; `B` counts toward both `m` and `a` |
| H5 | No more than 5 consecutive working days (every 6-day window has a rest) |
| H6 | The day after a `B` must be `R` or `E` |
| H7 | Every surgical day has ≥ 1 nurse on `B` |
| H8 | At most `K` shifts per nurse overall; **`B` costs 2** |
| H9 | Leave days must be `R` |

**Soft cost (Part B), to minimise:**

```
C = Σ_i [ 3·(C_iM² + C_iA² + C_iE²) − (C_iM + C_iA + C_iE)² ]
```

### 1.1 Where the handout and the grader disagree

`verifier.py` is what grades us, so it wins. Confirmed on Piazza:

- **No `B` on general days.** The handout never says this; the verifier rejects
  it outright. Confirmed twice by the TAs.
- **H6 is stricter than stated.** The handout says "no `M` or `A` after `B`";
  the verifier permits only `R` or `E`, so `B → B` is also banned.
- **H2 treats `B` as a morning** on both sides, so `M→B`, `B→M`, `B→B` all fail.
- **H8 counts `B` as 2**, since it lands in both the morning and afternoon
  totals. The TAs confirmed this and explained the H1/H8 tension: `B` is *one
  shift type* for H1 but *two shifts* for H8.
- **H5 is vacuous for `D ≤ 5`** — the verifier loops `range(D-5)`.
- **H4 is exact, not a minimum:** `#M+#B == m`, `#A+#B == a`, `#E == e`.
- The shipped verifier originally had an H7 bug (`!= "R"` instead of `== "B"`),
  fixed in the 24 Aug starter update. Our copy is the fixed one.

### 1.2 Scoring and time budget (from Piazza, materially affects design)

- **`T` (a CSV column) is the enforced per-instance limit.** "If your algorithm
  does not terminate within T, it will be terminated." Tiers are roughly 5 min
  (easy) / 10 min (medium) / 20 min (hard).
- **Part A is scored on *actual runtime*, not budget used** — validity is a
  gate, then time. So Part A must return the instant a roster verifies.
- **Part B is scored on cost first**, with runtime only as a tie-break among
  equal-cost solutions.
- Infeasible instances are graded separately; the verifier only sees feasible
  ones, so `{}` printing `INVALID` is expected.
- **Only algorithms taught in class and extensions of them.** z3 and other
  constraint solvers are explicitly banned. Standard library only; no threads,
  no multiprocessing, no subprocesses.
- **`part_b.py` must run standalone** — it may not assume `part_a.py` ran or
  that a Part A `solution.json` exists. Copying Part A code into it is fine.

---

## 2. Structural analysis

Three facts drive every design decision below.

### 2.1 It is a row/column matrix CSP

H2, H3, H5, H6, H8, H9 live entirely **inside one nurse's row**.
H4 and H7 live entirely **inside one day's column**. Nothing else couples them.

**Consequence:** swapping two nurses' shifts on the *same day* provably cannot
disturb H4 or H7. It perturbs only two rows at days `d−1, d, d+1` plus their
`K` totals. This is a cheap, column-safe move operator — the backbone of Part
B's planned local search.

### 2.2 Column constraints collapse to one integer per day

Let `b_d` = number of `B` shifts on day `d`. Then the day needs exactly
`m−b_d` on `M`, `a−b_d` on `A`, `e` on `E`, `b_d` on `B`, rest resting. So:

- `b_d = 0` on G days; `1 ≤ b_d ≤ min(m, a, avail_surg[d])` on S days;
- the day consumes exactly `m + a + e − b_d` **distinct nurses**.

Once `b_d` is fixed, H4/H7 are just "pick disjoint sets of these sizes".

### 2.3 Two independent lower bounds on the Part B cost

**Column imbalance (the strong one).** The per-nurse cost has a much cleaner
form than it first appears. Writing a nurse's totals as `(x, y, z)`:

```
3(x² + y² + z²) − (x + y + z)²  ≡  (x − y)² + (y − z)² + (z − x)²
```

(verified exhaustively). So a zero-cost nurse has `x = y = z`. Summing over all
nurses would force `D·m = D·a = D·e` — **cost 0 is possible only when
`m = a = e`.** In general, Cauchy–Schwarz on each column gives

```
C  ≥  D²·[(m−a)² + (a−e)² + (e−m)²] / N          rounded up to an even number
```

(even because, with `u = x−y`, `v = y−z`, the per-nurse cost is `2(u²+uv+v²)`).
Brute-force validated against exhaustive optima on small cases: zero violations.

**Residue (the weak one).** Total workload is invariant:
`Σ_i (C_iM + C_iA + C_iE) = D·(m + a + e)`, independent of every `b_d`. Given a
nurse's total `t`, the floor is `0` if `t ≡ 0 (mod 3)` and `2` otherwise, so at
most one nurse need be off a multiple of three — giving `0` or `2`.

**Exact relaxation (the one that actually binds).** Keep only H4's column sums
and H8's budget: every valid roster gives each nurse a triple `(x,y,z)` with
`x+y+z ≤ K`, the three columns summing to `(Dm, Da, De)`. Minimising over all
such assignments is a genuine relaxation, so its optimum bounds the real one —
and unlike the analytic forms it **sees `K`**. Solved by DP, guarded by a state
budget *and* a wall-clock cap (the profile count grows as `K³`, so state count
alone badly under-predicts the work); too large an instance falls back.

The bound used is the **maximum** of all three.

| instance | residue | column | **exact** | achieved |
|---|---|---|---|---|
| test1 | 0 | 36 | **36** | 36 — optimal |
| test2 | 2 | 6 | **24** | 24 — optimal |
| test3 | 0 | 0 | **18** | 18 — optimal |

`test3` shows why `K` matters: with `K = 2` no nurse can ever hold `(1,1,1)` —
three units exceeds the budget — so every working nurse costs ≥ 2, and 18 units
at ≤ 2 each needs ≥ 9 nurses. **18 is unbeatable**; the analytic bound of 0 was
chasing a phantom.

> **Correction to an earlier version of this document.** It reported the
> residue bound alone, claiming `0` for test1. That is valid but badly loose —
> the column bound is strictly stronger on **48 of 60** generated instances.
> The practical cost of the error would have been real: Part B's early exit
> would have chased an unreachable `0` on test1 and burned the whole budget,
> losing precisely the runtime tie-break the exit exists to win.

> **A second tempting wrong turn.** "Distribute work evenly across nurses" is
> *not* the right objective either. Cost depends on `t_i mod 3`, not on how
> equal the `t_i` are. For `N=4, S=16`: totals `(4,4,4,4)` cost **8**, while
> `(6,6,3,1)` or `(3,3,3,7)` cost **2**. Equalising is 4× worse.

### 2.4 The `B → E` pairing is free

`B` contributes `(M+1, A+1, E+0)`, so a nurse with `b` B-shifts and `b`
E-shifts sits at exactly `(b, b, b)` — total `3b`, **cost 0**. H6 permits `E`
right after `B`, so `B→E` is both legal and cost-optimal.

Transition choreography (verified numerically):

| pattern | (M,A,E) | t | cost | floor | |
|---|---|---|---|---|---|
| `B,E,R,B,E,R` | (2,2,2) | 6 | **0** | 0 | optimal |
| `B,E,A,B,E,A` | (2,4,2) | 8 | **8** | 2 | **not** optimal |

`E→B` is banned by H3, so the cycle needs a spacer — but it must be `R`, not
`A`: `B` already supplies the afternoon, so a bare `A` double-counts that
column.

---

## 3. Infeasibility theory

Four sound necessary conditions. **Sound** here means: they only ever fire on
instances that genuinely admit no roster. All four were verified against every
instance the solver independently solves — **zero false positives in 59**.

This matters for two reasons: correctly emitting `{}` fast, and — more
importantly — not mistaking an unsatisfiable instance for a weak search. Every
instance our search initially failed on turned out to be unsatisfiable.

### 3.1 Per-day headcount
Day `d` needs `m + a + e − b_d` distinct nurses off leave. Using `b_hi[d]`
minimises that, so `m + a + e − b_hi[d] > avail[d]` is fatal.

### 3.2 Morning succession (sharpened per day)

On day `d−1`, exactly `m` nurses hold `M`/`B` and exactly `e` hold `E` (H4).
Those `m + e` nurses are distinct and all available on `d−1`. A nurse taking a
morning on day `d` must avoid both sets (H2, H3). The blocked set is drawn from
day `d−1`'s pool, so at most `|avail(d−1) \ avail(d)|` of it can dodge day `d`;
everything beyond that must overlap:

```
morning_legal(d)  ≤  |avail(d)| − max(0, (m + e) − |avail(d−1) \ avail(d)|)
```

Infeasible if this drops below `m`.

The leave-free form is just `2m + e ≤ N`. **The per-day form is strictly
stronger, and it is the stronger form that catches real instances** — one test
case passed `2m+e ≤ N` globally but failed at day 15.

### 3.3 B capacity over sliding windows

H2 stops a nurse taking `B` on consecutive days, so within any window of `L`
consecutive days one nurse covers at most `⌈L/2⌉` B shifts; each also costs 2
units of `K`. For every window (widths 2…8, plus the whole horizon):

```
Σ_{d in window} b_min(d)  ≤  Σ_{surgical i} min( K//2 , max_alternating_days(i, window) )
```

**A whole-horizon count is not enough.** A single surgical nurse facing two
*adjacent* surgical days is stuck no matter how large `K` is — a real generated
instance (`Ns=1`, S days at 1, 2, 5, 8) passed the global test and failed the
window test at days 1–2.

### 3.4 Nurse-days over sliding windows (H5 locally)

H5 caps a nurse at `W − W//6` working days inside any window of `W`
consecutive days. So for every window (widths 6…12):

```
Σ_{d in window} (m+a+e−b_hi[d])  ≤  Σ_i min( W − W//6 , non-leave days of i in window )
```

A locally dense stretch starves even when whole-horizon totals are comfortable.
Confirmed on a synthetic case: 6 nurses, 6 general days, `m+a+e = 6`. Every
nurse must rest once in the window, so supply is 30 nurse-days against a demand
of 36 — invisible to any global count.

### 3.5 Aggregate workload and nurse-days
`D(m+a+e) ≤ Σ_i min(K, 2·max_work_days_i)`, and
`Σ_d (m+a+e−b_hi[d]) ≤ Σ_i max_work_days_i`, where `max_work_days_i` is an
exact DP over H5 and that nurse's leaves.

---

## 4. Design decisions

| # | Decision | Choice | Rationale |
|---|---|---|---|
| 1 | Part A engine | Layered: constructive tier 1 → day-level backtracking tier 2 | Part A is scored on raw runtime. Cell-level MRV over `N×D` (up to 1500 vars) must *propagate its way to* the exact-count structure we derive in closed form. |
| 2 | Code sharing | Shared core, concatenated into each part by a build step | `part_b.py` must run standalone; `import part_a` risks `ModuleNotFoundError` if the grader isolates the file — 20% of marks against saving one shell command. Verified by running the emitted file from an unrelated directory. |
| 3 | Deadline | `0.9·T`, atomic writes | Temp file in the *same directory* (`os.replace` is only atomic within a filesystem), `flush()` + `fsync()` before the swap, so a kill never leaves a truncated or empty file. |
| 4 | Part B | Cost-aware construction + swap local search, early exit at the mod-3 bound | Not yet built. |
| 5 | `b_d` selection | Demand-driven: `clamp(max(1, m+a+e−avail[d]), b_lo, b_hi)`, with `b_d` as a tier-2 backtracking dimension | `B` is expensive: 2 units of `K`, and H6 forces `R`/`E` the next day. Take as few as H7 allows unless the day is short-staffed. |

**On decision 5:** `b_d` cannot change the workload at all (§2.3) — it only
changes how many *distinct nurse-days* a day consumes. Note also that `b_hi`
must use `avail_surg[d]` (surgical nurses off leave **that day**), not `Ns`;
using `Ns` proposes `b` values that cannot exist. Constructed example: 5
surgical nurses with 4 on leave gives `avail_surg = 1`, so `b_hi = 1`, while
the `Ns` form would claim 3 and search two impossible branches.

**Completeness caveat:** backtracking over `b_d` alone does **not** make the
search complete — tier 2 samples `variants` fillings per `b` rather than
enumerating every partition of nurses into slots. So a `None` result means
*"not found"*, never *"proved unsatisfiable"*. Only `infeasibility_reason()`
proves the latter.

---

## 5. Repository layout

```
part_a.py           749 lines  GENERATED — submitted
part_b.py            26 lines  starter stub, not yet written
report.txt           22 lines  template, not yet written
group.txt                      entry number
verifier.py         221 lines  starter code, unmodified
visualizer.py       145 lines  starter code, unmodified
sample_test_cases/             test1/2/3.csv
my_tests/                      60 generated instances (gitignored, seed 333)
dev/                           NOT submitted
  core.py           732 lines  shared solver core
  driver_a.py        18 lines  Part A entry point
  build.py           86 lines  emits part_a.py / part_b.py, audits + compiles
  gen_instances.py  181 lines  instance generator
  bench.py          127 lines  timed run + verify + cost-vs-bound
  selftest.py       161 lines  cross-checks core against verifier.py
```

**Build:** `python3 dev/build.py` concatenates `core.py` + `driver_<part>.py`
into each submitted file. The audit rejects non-stdlib imports, any mention of
`subprocess`/`multiprocessing`, a missing entry point, and — crucially —
anything that fails to `compile()`.

---

## 6. Algorithms

### 6.1 Shared day-filling (`fill_day`)

Given day `d` and a chosen `b`, pick who works. Returns `{nurse: shift}` or
`None`.

**Eligibility.** A nurse may work at all if off leave (H9), `units < K` (H8),
and `run < 5` (H5). Per shift:

| shift | additional requirement |
|---|---|
| `B` | surgical, `last ∉ {M,B,E}`, `units + 2 ≤ K` |
| `M` | `last ∉ {M,B,E}` |
| `A` | `last ≠ B` |
| `E` | none — `E` has no predecessor restriction |

**Variable ordering — MRV over shift *types*, not cells.** Compute
`slack = |eligible| − needed` for each unfilled type, fill the tightest first,
recompute after each (assigning one type shrinks the others' pools). Negative
slack fails the day immediately. `B` typically goes first, `E` last.

**Value ordering — LCV by levelling.** Sort candidates by:

1. **`blocks_tomorrow`** — for `M`, `B`, `E` only. These are exactly the shifts
   that bar a morning tomorrow (H2/H3), and tomorrow always needs `m` nurses
   with a legal morning. So spend them **first on nurses who cannot work
   tomorrow anyway** (on leave `d+1`) — blocking those costs nothing.
2. **shift-type count** (Part B mode only) — whoever is shortest on this type;
   `B` reads the morning + afternoon columns together.
3. **`units` spent** — lowest first, keeping `K` budgets level so nobody
   exhausts early and shrinks a later day's pool.
4. **`run`** — shortest first, deferring forced rests.
5. **random jitter** — what makes a restart explore somewhere new.

### 6.2 Tier 1 — constructive (`construct`)

One greedy pass over days using `min_b(d)`. Randomised tie-breaks make
restarting a search strategy in its own right. Resolves most instances on the
**first pass with no backtracking at all**.

### 6.3 Tier 2 — day-level backtracking (`solve_tier2`)

Depth `D`, not `N×D`: one decision per day. Each node branches over `b_d` and
over a few randomised fillings, with **forward checking** on day `d+1`:

```
workers ≥ m + a + e − b_hi[d+1]      -- headcount
mornings ≥ m                          -- M and B together always need m legal mornings
surgical_mornings ≥ b_min(d+1)        -- H7 supply
```

Mornings are the binding resource, so this catches most dead ends one level
early. Restarts with a growing node budget (2000 × 4ⁿ) rather than one
unbounded descent, since a single DFS can sink its whole budget into one bad
subtree.

### 6.4 Layering (`solve_part_a`)

1. `infeasibility_reason()` → emit `{}` immediately.
2. Tier 1 restarts for `min(3s, 50% of budget)`.
3. Tier 2 with growing node budgets until the deadline.

The tier-1 slice must be a **small constant**, not a fraction — see §7.

---

## 7. Bugs found (and how)

All three were found by *building instances designed to break the solver*, not
by inspection. Two would have cost marks silently.

1. **Deadline overrun — would have scored zero.** Returning `False` on timeout
   was indistinguishable from "this branch failed", so every ancestor tried its
   remaining variants and unwinding an exponential tree was itself exponential.
   A **5-second** deadline ran **~100 seconds**. In a graded run that is an
   overrun of `T` and a zero on that instance. Fixed with an explicit `stop`
   flag that collapses the stack at once.

2. **Tier 1 hogging the budget.** It was given 25% of the budget; on a 300s
   instance that is 67 seconds of hopeless restarts before real search starts.
   Tier 1 resolves in milliseconds when it resolves at all.

3. **LCV blind to tomorrow.** See §6.1 item 1. Before this, day 0's greedy
   choice routinely poisoned day 1 beyond any `b` value's rescue.

Also: `build.py`'s audit originally only grepped text and happily emitted a
file with an `IndentationError`. It now `compile()`s the output.

---

## 8. Testing

- **`selftest.py`** validates the internal verifier *against* `verifier.py`
  rather than trusting it: all 3 handout worked examples, 360 random rosters,
  and **176 single-cell mutations of known-valid rosters** (random rosters are
  almost all invalid and only exercise rejection; mutations sit on the boundary
  where a false *accept* would hide). Plus objective agreement.
- **`gen_instances.py`** produces 60 instances across five tiers up to
  `N=50, D=30`, with a tightness knob. A **tight mode** deliberately pushes
  coverage past the thinnest day's headcount so `b_d` is forced above 1 — the
  default mode structurally cannot produce that case (it enforces
  `m+a+e ≤ min(avail)`, which silently guarantees `b_d = 1` always fits).

---

## 9. Current results

| | |
|---|---|
| Sample instances, official verifier | **3/3 VALID**, ~0.04s each |
| Generated set (60 instances) | **59 valid, 1 correctly empty**, 0 invalid, 0 timeouts |
| Full sweep wall clock | **49s** (was 602s with 10 timeouts before the fixes) |
| Slowest single solve | 16.6s (`tight_02`) — marginal against an 18s budget, comfortable at the graded `T` |
| Part A cost vs bound | 76876 vs **51918** — Part A ignores the objective entirely |

**Caveat on this evidence.** Every instance here is one we generated. 59/60
says the solver is sound and fast on *our* distribution; it is not evidence
about the graders'. The TAs said they would release test cases with expected
times — those are the real signal.

---

## 9a. Part B

**Construction.** The Part A engine with `cost_aware` value ordering, biasing
each slot toward whichever of M/A/E that nurse currently has least of, so local
search starts near-balanced instead of climbing out of a hole.

**Neighbourhood.** Same-day swaps. Exchanging two nurses' day-`d` shifts leaves
the day's multiset untouched, so H4 and H7 hold *automatically*; only rows
`d−1, d, d+1` need checking. Cost moves by an **O(1) delta** over the two
nurses touched, via the squared-differences identity.

**Acceptance.** Hill climbing with neutral moves accepted. Simulated annealing
was implemented and compared head-to-head on every instance with a real gap —
it **tied on all of them**, so the temperature machinery is not carried.

**Early exit.** Stop the instant cost reaches the bound. This is what the exact
relaxation buys: all three samples reach a *proven* optimum and stop —
**test1 36 in 1.4s, test2 24 in 0.15s, test3 18 in 0.07s against a 90s
budget** — winning the runtime tie-break rather than spending the budget.

**Durability.** Every improvement is written atomically, so a kill leaves the
best roster so far rather than nothing.

**Across 48 generated instances at 1.2s each:** total cost 44986 against a
total bound of 44108 — **2.0% above provable optimum**, 12 proved optimal, zero
invalid. The graded `T` is 300s+, so this is a floor on what it will do.

**Not built:** the B-split/merge move that changes `b_d`. Same-day swaps
preserve `b_d`, so the search is confined to the constructed `b` vector. `b_d`
is pinned to 1 on all three samples (`min(m,a)=1`), so it is a no-op there;
it has scope on 30 of 63 instances. Deferred as the lowest-value item.

## 9b. Changes after external review (round 2)

An external reviewer read the whole codebase. One finding was real; the fix it
proposed was not. Everything below was measured before being adopted.

### The bug: only one roster was ever constructed

`solve_part_b` had a `while` loop ending in an unconditional `break` — an `if`
in disguise. Confirmed and fixed.

### The proposed fix does not work, and the data says why

The reviewer's remedy was multi-start: spend 10% of the budget on repeated
cost-aware constructions and hill-climb from the cheapest. Given identical total
budgets across nine instances:

| strategy | total gap over bound |
|---|---|
| single start (what we had) | 298 |
| multi-start (proposed) | **298** |
| restart on stagnation | **298** |
| iterated, fixed time slices | **worse** |

Identical on every instance. The diagnostic explains it: twenty cost-aware
constructions of `large_01` span initial costs **1592–1664**, yet every hill
climb from them lands on exactly **1452**. Same on `large_00` (568–594 → all
498). Convergence *speed* was checked separately — also no difference.

**Hill climbing reaches the same attractor from any start, so the neighbourhood
— not the starting point — is what limits quality.** This is the second
independent signal pointing there; simulated annealing tying with hill climbing
was the first.

The dead loop was still replaced, with a *bounded* multi-start (8 attempts,
capped at 2% of the budget) — kept as insurance for instances unlike those
tested, and commented as such, not because it was shown to help.

### Corrections to the reviewer's report draft

Its structure was sound and its vocabulary right, but four claims did not match
the implementation:

| draft | actual |
|---|---|
| "four sound infeasibility conditions" | **six** |
| tier 2 "branches on daily shift permutations" | branches on `b_d` and randomised day fillings |
| "Late Acceptance / flat Hill Climbing" | plain hill climbing with neutral moves |
| "DP over valid column permutations" | DP over per-nurse column triples |

Also rejected: its diagnosis that `large_01`'s gap comes from tier 1 locking
into a tight H5 corner. Every start converges to 1452, so it is not a
bad-start artifact.

### Submission verification

`submission.zip` unzipped in isolation, with nothing else present:

| | test1 | test2 | test3 |
|---|---|---|---|
| Part A | VALID 168 | VALID 58 | VALID 38 |
| Part B | **VALID 36** | **VALID 24** | **VALID 18** |

Part B at the proven optimum on all three. Imports are `csv`, `json`, `os`,
`random`, `sys`, `time` only; zero occurrences of `subprocess`, `threading` or
`multiprocessing`. `report.txt` is 984 words, ≈1.9 pages at 11pt.

## 9c. External checker validation (AbhinavPJ/COL333-A1-CHECKER)

1034 instances across four suites, with reference solutions and the assignment's
own verifier. Run on the submitted files.

**Part A: 1034/1034 correct.** The checker reports 1032/1034; both reported
failures are errors in its reference solutions, not ours:

| case | checker's reference | ours | official starter verifier |
|---|---|---|---|
| `suite_003/test8` | `{}` (infeasible) | 54-key roster | **VALID 42** |
| `suite_004/test1` | `{}` (infeasible) | 1500-key roster | **VALID 664** |

`suite_003/test8` is feasible by counting: workload `6·3 = 18` units against
capacity `9 · K=2 = 18`, exactly tight. The checker's own verifier accepts both
rosters — that is where its printed objective comes from — and it marks them
FAIL only because `compare()` sees an empty reference.

Of the 1000 instances in suite_001, **300 have empty references and we agree on
every one**, each resolved in about 0.1s by the infeasibility conditions in §3
rather than by exhausting the budget.

**Part B: 158 of a 260-case sample** before the run was cut short: 151 MATCHED,
2 MORE_OPTIMAL, 5 SUBOPTIMAL, 0 FAIL.

### Two solver fixes this found

**B-budget starvation.** One instance had 2 surgical nurses covering 15 surgical
days, each B costing 2 units against K=16 — 16 units of capacity for 15 B
shifts. The LCV rule prefers the least-spent nurse for every shift, so it gave
ordinary work to surgical nurses early and burned the budget B duty needed;
greedy died on day 28 of 30 in 397 of 400 trials. `fill_day` now holds surgical
nurses back from non-B shifts when the remaining B demand nearly exhausts their
budget. That case went from a 9.04s timeout to a pass in 0.045s.

**The B-per-day policy is a cost decision, not only a feasibility one.** Four of
the five suboptimal Part B cases had `D` of 1 or 2. On a one-day horizon every
working nurse costs exactly 2 — even `B` gives `(1,1,0)` — so cost is
`2(m+a+e−b)` and *maximising* `b` is the whole objective. `min_b` is right for
Part A and backwards for Part B here, so `construct` gained a `b_policy` and
Part B builds under both, climbs from each, and keeps the winner. Three of those
cases then matched the reference exactly, one went 6 → 0, one 20 → 16.

This is the item deferred in §10 and the one an external reviewer advised
dropping outright ("the ROI isn't worth the risk"). Choosing the policy at
construction time captures most of the benefit without the mid-search
constraint risk that warning was about.

## 9d. Round 4 — auditing an all-clear review

An external reviewer audited the post-checker submission and returned an
unqualified pass: *"There are no vulnerabilities here. Do not touch a single
line of this code."* That verdict was itself treated as a claim to test. It was
wrong, and the bug it missed could have scored zero on an instance.

### The bug: the relaxation DP's time cap did not hold

`_relaxed_column_optimum` checked its 1.5s cap once per **nurse iteration**, but
a single pass over a large state set takes seconds by itself. On
`suite_001/test635` the bound took **4.86s against a 1.5s cap** — a 3× overrun.

Why that is severe rather than merely wasteful: the bound is computed *inside*
Part B's budget, and suite_001 carries `T` values as low as **3s** (budget
2.7s). A slow bound on a small-`T` instance overruns `T` outright, so the
process is killed and the instance scores zero — not "spends its budget badly".

Fixed twice over: the clock is now read every 256 states, holding the cap to
about 3%; and Part B caps the bound at a fifth of its remaining budget, so a
slow relaxation degrades to the analytic form rather than starving the search.

| | before | after |
|---|---|---|
| `test635` bound | 4.86s | **1.55s** |
| `test635` end-to-end at `T=3` | at risk of overrunning | **2.75–2.77s**, valid (3s limit) |
| bounds returned | — | unchanged (76, 0, 56) |

### Duplicate candidates — real, but not a regression

On **17 of 27** instances, including all three samples, the `"min"` and `"max"`
b-policies produce an *identical* b-vector, so Part B optimises two equivalent
candidates on half the budget each. Measured across eight instances: **no cost
difference**, because hill climbing converges well inside half the budget —
the same convergence behaviour four earlier experiments found. So this is
wasted work, not lost quality. Recorded rather than fixed, because the fix
would trade a known-neutral inefficiency for fresh risk days before a deadline.

### Degenerate inputs

Twelve constructed edge cases — zero demand, `D=1`, `N=1`, `K=0`, no surgical
nurses, all-leave, `D=5`, huge `K`, evening-only, morning-only-on-S. All run
cleanly with no crashes. **Every empty output is a proved infeasibility with a
correct stated reason**, never a give-up. Zero demand on all-general days
correctly yields a valid all-rest roster (`VALID 0`), while zero demand with any
surgical day is correctly rejected — H7 needs a `B` that `m = a = 0` cannot
supply.

### What the review got right, and what it overstated

**Right, and confirmed:** the `held_back` LCV key is structurally incapable of
creating false infeasibilities (it is a preference over a sorted list, so every
candidate stays reachable). The `D = 1` optimality argument is sound. The time
partition strands nothing — measured at 5.46s used of a 5.4s budget.

**Overstated:** it called `(K − units[i]) // 2` the *exact* B capacity of the
surgical pool. It is not — it ignores H2's alternation and ignores whether those
nurses are on leave, so it over-estimates and the trigger fires *less* often
than ideal. Harmless, but the reasoning behind the endorsement was wrong.

**Missed:** both the DP guard bug and the duplicate candidates, the latter in
code it specifically praised as "flawless".

The transferable lesson: a review that finds nothing is not evidence that
nothing is wrong. This one audited what the code *says* it does. The bug was in
whether a guard actually *held* under load, which only measurement reveals.

## 10. Remaining work

**Done since the last revision:** `report.txt` written (984 words, ~1.9 pages),
`submission.zip` built and verified end to end.

**The one real remaining gap.** Same-day swaps preserve `b_d`, so Part B's local
search is confined to the `b` vector its construction happened to pick. Given
the measurements above — start doesn't matter, annealing doesn't help, restarts
don't help — a move that *changes* `b_d` is now the only change with a plausible
path to lower cost. The B-split/merge move (turn `M`+`A`+`R` into `R`+`R`+`B`
and back, preserving `#M+#B`, `#A+#B` and `#E`) needs two guards the reviewer
omitted: merge only on an S day, split only while `b_d > b_lo`. It is a no-op on
all three samples, where `b_d` is pinned to 1, and has scope on 30 of 63
instances.

## 11. Questions a reviewer could usefully attack

**Resolved since the last revision** (kept so a reviewer does not re-derive them):

- *Q1 morning-bound tightness* — accepted as sound but not strictly tight; the
  dynamic form lives in `forward_ok`. No change.
- *Q2 incompleteness* — accepted; bounded randomised restarts are the right
  trade against heavy-tailed runtimes when the grader cuts at `T`.
- *Q3 missing condition* — yes: sliding-window nurse-days (§3.4). Implemented.
- *Q4 mod-3 achievability* — superseded. The residue bound was the wrong tool;
  the exact column relaxation (§2.3) answers it directly and proves all three
  samples optimal.
- *Q5 swap connectivity* — confirmed: same-day swaps preserve `b_d`, so the
  search is confined to the constructed `b` vector. The B-split/merge move is
  the fix; deferred because it is a no-op on all three samples.

**Still open:**

1. **The exact relaxation only runs on small instances.** It is guarded by a
   state budget and a 1.5s cap, and falls back to the analytic bound above
   that — so on large instances we cannot tell an optimal roster from a merely
   good one, and the early exit never fires. Is there a bound that is both
   tight and cheap at `N=50, D=30`? An LP relaxation over profiles would do it,
   but no LP solver is available (standard library only, no scipy).
2. **How much does the B-split/merge move actually buy?** It has scope on 30 of
   63 instances but is a no-op on all three samples. Is there an argument for
   how far a fixed `b` vector can be from optimal, to decide whether this is
   worth the implementation risk this close to the deadline?
3. **Is same-day swapping with neutral moves the right neighbourhood at all?**
   SA tied with hill climbing everywhere tested, which suggests the landscape
   is not rugged but rather that the neighbourhood is *narrow*. Would a
   3-cycle rotation (i→j→k→i on one day) reach places pairwise swaps cannot?
4. **We are 2.0% above the provable bound in aggregate at 1.2s per instance.**
   Where is that residue — a few instances far off, or a uniform small gap?
   (Current data: `large_01` alone accounts for a gap of 198 of ~878 total.)
5. **Is our tier-1/tier-2 split still right for Part B?** Part B calls the
   cost-aware constructor once and then optimises. Would repeated cost-aware
   restarts, keeping the best starting roster, beat spending all the time in
   local search from a single start?
