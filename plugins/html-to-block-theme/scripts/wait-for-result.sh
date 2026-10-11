#!/usr/bin/env bash
#
# wait-for-result.sh — a clock for a builder that may never report.
#
# The orchestrator waits for a builder's completion notice, and nothing bounds that wait: a
# builder stuck on one browser call never reports, and the run stands still until someone
# looks. Started in the background when a builder is dispatched, this script ends either
# when the builder's result file appears or when the time is up. Its ending brings the
# orchestrator back, which can then tell a builder that is working from one that is stuck.
#
#   wait-for-result.sh --site-path <site> --name <name> [--minutes <n>] [--watch <dir>]...
#
# The result file is <site>/.h2bt/results/<name>.json. Only one written after this script
# started counts: a file left by an earlier attempt at the same view is not this builder's
# result. --watch names directories whose
# newest change tells whether anything is still being written; <site>/.h2bt is always
# watched. A builder goes quiet for long stretches while it refines in the browser, so a
# quiet half hour is not a stuck builder by itself: read the age against --minutes.
#
# Last line, exit 0:  H2BT_RESULT name=<name> status=<status> file=<path>
# Last line, exit 1:  H2BT_RESULT_TIMEOUT name=<name> minutes=<n> quiet_minutes=<m> newest=<file>
#
set -euo pipefail

usage() {
	cat <<'EOF'
Usage:
  wait-for-result.sh --site-path <site> --name <name> [--minutes <n>] [--watch <dir>]...

Waits for <site>/.h2bt/results/<name>.json. Run it in the background when a builder is
dispatched. It ends when the file is there (exit 0) or after --minutes (default 90, exit 1),
and then says how long ago anything under <site>/.h2bt or a --watch directory last changed.
EOF
}

# A flag that takes a value must be followed by one.
need_value() { [[ $# -ge 2 ]] || { echo "$1 needs a value" >&2; exit 2; }; }

site_path=""
name=""
minutes=90
watch=()
while [[ $# -gt 0 ]]; do
	case "$1" in
		--site-path) need_value "$@"; site_path="$2"; shift 2 ;;
		--name) need_value "$@"; name="$2"; shift 2 ;;
		--minutes) need_value "$@"; minutes="$2"; shift 2 ;;
		--watch) need_value "$@"; watch+=("$2"); shift 2 ;;
		-h|--help) usage; exit 0 ;;
		*) echo "Unknown argument: $1" >&2; usage >&2; exit 2 ;;
	esac
done

[[ -n "$site_path" && -d "$site_path" ]] || { echo "--site-path must name the Studio site directory" >&2; exit 2; }
[[ "$name" =~ ^[A-Za-z0-9][A-Za-z0-9._-]*$ ]] || { echo "--name must be a result name (letters, digits, dots, hyphens): $name" >&2; exit 2; }
[[ "$minutes" =~ ^[0-9]+$ && "$minutes" -ge 1 ]] || { echo "--minutes must be a whole number of minutes: $minutes" >&2; exit 2; }

site_path="$(cd "$site_path" && pwd)"
result="$site_path/.h2bt/results/$name.json"

started="$(date +%s)"

# The status of a result file that is complete JSON and was written since this script
# started, or nothing: while it is being written, or when it is an earlier attempt's.
status_of() {
	python3 -c 'import json,os,sys
try:
    if os.path.getmtime(sys.argv[1]) < float(sys.argv[2]) - 1:
        sys.exit(0)
    print(json.load(open(sys.argv[1])).get("status", "unknown"))
except Exception:
    pass' "$1" "$started"
}

# How often to look, in seconds. Only tests set it.
interval="${H2BT_WAIT_INTERVAL:-20}"
deadline=$(( started + minutes * 60 ))
while :; do
	if [[ -f "$result" ]]; then
		status="$(status_of "$result")"
		if [[ -n "$status" ]]; then
			echo "H2BT_RESULT name=$name status=$status file=$result"
			exit 0
		fi
	fi
	[[ "$(date +%s)" -lt "$deadline" ]] || break
	sleep "$interval"
done

# Time is up: say how quiet things have been, and where the last change was.
python3 -c 'import os,sys,time
newest, where = 0.0, "-"
for root in sys.argv[3:]:
    for folder, folders, files in os.walk(root):
        folders[:] = [f for f in folders if f not in ("node_modules", ".git", "vendor")]
        for file in files:
            path = os.path.join(folder, file)
            try:
                changed = os.path.getmtime(path)
            except OSError:
                continue
            if changed > newest:
                newest, where = changed, path
quiet = int((time.time() - newest) / 60) if newest else -1
print("H2BT_RESULT_TIMEOUT name=%s minutes=%s quiet_minutes=%s newest=%s" % (sys.argv[1], sys.argv[2], quiet, where))' "$name" "$minutes" "$site_path/.h2bt" "${watch[@]+"${watch[@]}"}"
exit 1
