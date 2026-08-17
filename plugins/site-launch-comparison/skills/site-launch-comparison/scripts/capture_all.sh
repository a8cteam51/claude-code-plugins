#!/usr/bin/env bash
# Run capture.py repeatedly until everything is captured.
#
# capture.py deliberately stops before its time budget expires so it never gets
# killed mid-screenshot. That means someone has to call it again — this does the
# calling. Use it wherever your shell has no hard timeout; in an agent shell that
# does cap calls, invoke capture.py directly once per call instead.
#
# Usage: bash scripts/capture_all.sh <config.json> [max_rounds]

set -uo pipefail

CONFIG="${1:?usage: capture_all.sh <config.json> [max_rounds]}"
MAX="${2:-40}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

[ -f /tmp/browser-env.sh ] && source /tmp/browser-env.sh

for i in $(seq 1 "$MAX"); do
  echo "--- round $i ---"
  OUT="$(BUDGET="${BUDGET:-90}" python3 "$HERE/capture.py" "$CONFIG" 2>&1)"
  rc=$?
  echo "$OUT" | grep -vE "^Skipping host"

  # A traceback (missing playwright, unreadable config, hand-edited config with a
  # bad key) matches neither pattern below, so without this the same failing
  # command reruns $MAX times and scrolls the real error off screen.
  if [ "$rc" -ne 0 ]; then
    echo "capture.py exited with status $rc — stopping rather than retrying a hard failure."
    exit 1
  fi

  if echo "$OUT" | grep -q "^REMAINING 0"; then
    echo "All captures complete after $i round(s)."
    exit 0
  fi
  # No progress and nothing left to retry means we're stuck, not slow.
  if echo "$OUT" | grep -q "gave up" && ! echo "$OUT" | grep -q "^OK"; then
    echo "No progress this round. Stopping so the failures can be looked at."
    exit 1
  fi
done

echo "Hit the $MAX round limit with captures still outstanding."
exit 1
