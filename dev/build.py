#!/usr/bin/env python3
"""Emit part_a.py and part_b.py from the shared core plus a per-part driver.

The submitted files must each run standalone, so the core is concatenated in
rather than imported: Gradescope evaluates Part B independently and may not
place part_a.py beside it. Run this after every core.py change.
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

BANNER = '''"""COL333 Assignment 1 -- %s

GENERATED FILE. Edit dev/core.py or dev/driver_%s.py and re-run dev/build.py.
Standard library only; self-contained by design.
"""
'''

ALLOWED_IMPORTS = {"csv", "json", "os", "random", "sys", "time", "collections"}


def build(part):
    core = open(os.path.join(HERE, "core.py"), encoding="utf-8").read()
    driver = open(os.path.join(HERE, "driver_%s.py" % part), encoding="utf-8").read()

    # Drop core's module docstring; the banner replaces it. Locate it by
    # parsing rather than by scanning for a quote sequence -- function
    # docstrings look identical to a naive search.
    body = core
    if core.startswith('"""'):
        body = core[core.index('"""', 3) + 3:].lstrip("\n")

    text = BANNER % ("Part A" if part == "a" else "Part B", part) + body + driver

    out = os.path.join(ROOT, "part_%s.py" % part)
    with open(out, "w", encoding="utf-8") as f:
        f.write(text)
    return out, text


def audit(path, text):
    """Fail loudly rather than ship a file that cannot run standalone."""
    problems = []
    for lineno, line in enumerate(text.splitlines(), 1):
        stripped = line.strip()
        if stripped.startswith(("import ", "from ")) and not line.startswith(" "):
            module = stripped.split()[1].split(".")[0]
            if module not in ALLOWED_IMPORTS:
                problems.append("line %d: disallowed import %r" % (lineno, module))
        if "subprocess" in stripped or "multiprocessing" in stripped:
            problems.append("line %d: forbidden module reference" % lineno)
    if "if __name__ ==" not in text:
        problems.append("no entry point")

    # The text checks above cannot see a mangled concatenation, so actually
    # compile the emitted file.
    try:
        compile(text, path, "exec")
    except SyntaxError as exc:
        problems.append("does not compile: %s (line %s)" % (exc.msg, exc.lineno))
    return problems


def main():
    failed = False
    for part in ("a", "b"):
        driver_path = os.path.join(HERE, "driver_%s.py" % part)
        if not os.path.exists(driver_path):
            print("skip part_%s.py (no dev/driver_%s.py yet)" % (part, part))
            continue
        out, text = build(part)
        problems = audit(out, text)
        status = "OK" if not problems else "PROBLEMS"
        print("%-12s %5d lines  %s" % (os.path.basename(out),
                                       text.count("\n"), status))
        for p in problems:
            print("    " + p)
            failed = True
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
