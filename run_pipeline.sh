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

"$PY" run_pipeline.py "$@"
