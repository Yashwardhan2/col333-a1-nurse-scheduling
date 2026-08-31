# COL333 — Assignment 1: Nurse Scheduling with Constraints

Private working repo for Assignment 1 (Introduction to AI). Nurse rostering solved as a
Constraint Satisfaction Problem.

> **Private repo.** Course policy compares submissions against internet sources and past
> submissions. Do not make this public.

## Problem summary

Build a roster for `N` nurses over `D` days. Each day is surgical (`S`) or general (`G`).
Each nurse gets one of `{M, A, E, R, B}` per day — morning, afternoon, evening, rest, or
surgery (B = morning + afternoon, surgical nurses only).

**Part A** — find any roster satisfying hard constraints H1–H9:

| ID | Constraint |
|----|------------|
| H1 | Exactly one label per nurse per day; `B` only for surgical nurses (indices `0 .. Ns-1`) |
| H2 | No two consecutive morning shifts |
| H3 | No morning shift immediately after an evening shift |
| H4 | Exactly `m` / `a` / `e` nurses in morning / afternoon / evening each day (`B` counts toward both `m` and `a`) |
| H5 | No more than 5 consecutive working days (every 6-day window has a rest) |
| H6 | After a `B` day, no `M` or `A` the next day |
| H7 | Every surgical day has ≥ 1 nurse on `B` |
| H8 | At most `K` shifts per nurse overall (`B` costs 2) |
| H9 | Leave days must be `R` |

**Part B** — same hard constraints, but minimise the soft cost

```
C = 9 * sum_i (1/3) * [ (C_iM - mu_i)^2 + (C_iA - mu_i)^2 + (C_iE - mu_i)^2 ]
mu_i = (C_iM + C_iA + C_iE) / 3
```

Lower is better; `C = 0` when every nurse's shifts are evenly split. `C` is always an integer.

## Repo layout

```
.
├── part_a.py              # my solution — Part A   (submitted)
├── part_b.py              # my solution — Part B   (submitted)
├── report.txt             # ≤2 pages, 11pt Arial   (submitted)
├── group.txt              # entry numbers, one per line (submitted)
├── verifier.py            # starter code — DO NOT MODIFY
├── visualizer.py          # starter code — DO NOT MODIFY
├── sample_test_cases/     # test1.csv, test2.csv, test3.csv
├── my_tests/              # extra instances I generate for stress testing
├── outputs/               # generated rosters (gitignored)
├── scripts/
│   ├── make_submission.sh # builds submission.zip in the required shape
│   └── run_all.sh         # run + verify against every csv in a folder
├── .gitignore
└── README.md
```

## Environment

```bash
conda create -n ai_a1 python=3.10
conda activate ai_a1
```

Standard library only. No extra packages, no threading, no multiprocessing, no subprocesses.
Evaluation: single CPU, 64 GB RAM, 20 min cap for `N ≤ 50, D ≤ 30`.

## Input / output

```bash
python part_a.py <input_csv_path> <output_json_path>
python part_b.py <input_csv_path> <output_json_path>
```

Input CSV: header row + one value row with 11 columns —
`N,D,N_s,N_g,m,a,e,T,days,K,leaves`

Output: exactly one JSON object with all `N × D` keys of the form `"Ni_j"` mapping to
`"M" | "A" | "E" | "R" | "B"`. If no valid roster exists, write `{}`.

## Verify and visualise

```bash
python verifier.py sample_test_cases/test1.csv outputs/test1.json
python visualizer.py sample_test_cases/test1.csv outputs/test1.json 15
```

The verifier prints `VALID <objective>` or `INVALID` (plus some debug noise). The objective it
prints is exactly the Part B cost `C`, computed as
`sum_i [ 3*(C_iM^2 + C_iA^2 + C_iE^2) - (C_iM + C_iA + C_iE)^2 ]`.

## Quick loop

```bash
mkdir -p outputs
python part_a.py sample_test_cases/test1.csv outputs/test1.json && \
python verifier.py sample_test_cases/test1.csv outputs/test1.json
```

Or everything at once:

```bash
bash scripts/run_all.sh part_a.py sample_test_cases
```

## Build the submission

```bash
bash scripts/make_submission.sh
```

Produces `submission.zip` which unzips into a folder containing `part_a.py`, `part_b.py`,
`report.txt`, `group.txt`. Upload to Gradescope; do not rename the zip. If working in a pair,
set the partner via **Group Members** after uploading.

## Notes / log

- Due **5:00 pm, Thu 3 Sep 2026**. Late accepted 2 days, −10% per day.
- Weightage ≈ 8 ± 2% overall. Part A ≈ 80%, Part B ≈ 20%.
- Doubts go on the A1 thread on Piazza, not email/Teams.

## Spec details taken from verifier.py

Where the handout is ambiguous, the verifier is the ground truth:

- `B` counts as a morning shift for **H2**, so `B` cannot be followed by `M` or `B`.
- **H4** rejects any `B` on a general (`G`) day — `B` is legal only on `S` days.
- **H6** allows only `R` or `E` on the day after a `B`.
- **H8** counts `B` as 2 towards `K` (it adds to both the morning and afternoon totals).
- **H5** only kicks in when `D >= 6`; the loop is over windows `[start, start+5]`.
- Coverage is exact, not a minimum: `#M + #B == m`, `#A + #B == a`, `#E == e`.

## Sample instances

| file | N | D | Ns | m,a,e | K | days |
|------|---|---|----|-------|---|------|
| test1.csv | 18 | 9 | 9 | 1,3,3 | 6 | SSSGGSGSG |
| test2.csv | 39 | 4 | 19 | 3,1,4 | 4 | GGSS |
| test3.csv | 23 | 6 | 6 | 1,1,1 | 2 | SGGGGG |

`len(leaves) == N*D` in all three. Real evaluation goes up to `N <= 50`, `D <= 30`.

### Approach log

Keep short dated entries here so `report.txt` is easy to write at the end.

- `YYYY-MM-DD` — ...
- 2026-08-31 — env: conda ai_a1, Python 3.10.21. Verifier prints [H2..H9] list once an output JSON exists.
