#!/usr/bin/env bash
set -e

# Run from the project root
cd "$(dirname "$0")"

# Use python3 if available (Mac/Linux), otherwise python (Windows Git Bash)
if command -v python3 >/dev/null 2>&1; then
  PY=python3
else
  PY=python
fi

echo "Step 1/3: Building the database..."
$PY src/build_db.py

echo "Step 2/3: Computing quality rubric scores..."
$PY src/compute_scores.py

echo "Step 3/3: Running downstream fix analysis..."
$PY src/explore.py "$@"

echo "Pipeline finished successfully."