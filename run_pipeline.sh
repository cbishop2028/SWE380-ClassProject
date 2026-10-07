#!/usr/bin/env bash
set -e

# Run from the project root, no matter where the script is called from
cd "$(dirname "$0")"

# Use python3 if available (Mac/Linux), otherwise python (Windows Git Bash)
if command -v python3 >/dev/null 2>&1; then
  PY=python3
else
  PY=python
fi

echo "Step 1/2: building the database..."
$PY src/build_db.py

echo "Step 2/2: running the analysis..."
$PY src/explore.py "$@"

echo "Pipeline finished."
