#!/usr/bin/env bash
# Builds submission.zip in the shape Gradescope expects:
# unzipping creates a folder containing part_a.py, part_b.py, report.txt, group.txt
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

FOLDER="submission"
FILES=(part_a.py part_b.py report.txt group.txt)

for f in "${FILES[@]}"; do
  if [[ ! -f "$f" ]]; then
    echo "ERROR: missing required file: $f"
    exit 1
  fi
done

if [[ ! -s group.txt ]]; then
  echo "ERROR: group.txt is empty — put entry numbers, one per line."
  exit 1
fi

rm -rf "$FOLDER" submission.zip
mkdir "$FOLDER"
cp "${FILES[@]}" "$FOLDER/"
zip -r submission.zip "$FOLDER" > /dev/null
rm -rf "$FOLDER"

echo "Built submission.zip:"
unzip -l submission.zip
