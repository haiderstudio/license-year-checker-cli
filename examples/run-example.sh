#!/bin/sh
# Run the checker over each example file and show the result.
# The flagged examples fail on purpose, so each run is allowed to fail.
cd "$(dirname "$0")/.."
for f in examples/LICENSE-clean examples/LICENSE-flagged examples/LICENSE-missing examples/LICENSE-edge; do
  echo "== $f =="
  python3 src/license_year_checker.py "$f" || true
  echo
done
echo "== examples/ : the whole folder =="
python3 src/license_year_checker.py examples/ || true
