#!/usr/bin/env bash
#
# serve-html.sh — serve a directory of static design files over HTTP so a real
# browser (Claude in Chrome) can load them with relative CSS/JS/asset paths resolving.
# Serving over HTTP (not file://) avoids broken relative URLs and CORS quirks.
#
# The server also carries the comparison harness (viewport.html) at /_h2bt/viewport.html
# and a results sink at /_h2bt/sink/<name>; see references/visual-refinement.md.
#
# With --site-path the server belongs to a run on that Studio site, and its state is kept in
# the site, at <site>/.h2bt/serve.json. A run lasts hours and its orchestrator's context is
# summarised along the way, so nothing about the server has to be remembered: the state file
# says where it is, and --ensure brings it back when it has died.
#
# Start:   serve-html.sh --dir <design-dir> --site-path <site>
# Ensure:  serve-html.sh --ensure --site-path <site> [--dir <design-dir>]
#            -> both print: H2BT_SERVE url=http://127.0.0.1:<port>/ pid=<pid> state=<serve.json> ... reused=<yes|no>
#                           H2BT_HARNESS url=<harness-url> site_copy=<path> sink=<dir>
#            Without --dir, --ensure serves the recorded directory, and after a --stop the
#            run's design directory (design_dir in <site>/.h2bt/run.json).
# Stop:    serve-html.sh --stop --site-path <site>
#            -> also removes the harness copy it placed in the site
# Missing: serve-html.sh --missing --site-path <site>   (or --pidfile <path>)
#            -> the paths the server answered 404 for, from its log: what a mirror lacks
#
# Without a site: serve-html.sh --dir <design-dir>, which prints pidfile=<path>, and
# serve-html.sh --stop --pidfile <path>.
#
# A start that cannot be made ends with H2BT_SERVE_FAIL reason=<why> on standard output.
#
set -euo pipefail

usage() {
	cat <<'EOF'
Usage:
  serve-html.sh --dir <design-dir> --site-path <site> [--port <port>] [--sink-dir <dir>]
  serve-html.sh --ensure --site-path <site> [--dir <design-dir>]
  serve-html.sh --stop --site-path <site>
  serve-html.sh --missing --site-path <site>
  serve-html.sh --dir <design-dir> [--port <port>] [--sink-dir <dir>]
  serve-html.sh --stop --pidfile <path>
  serve-html.sh --missing --pidfile <path>

Starts a background static HTTP server rooted at <design-dir> bound to 127.0.0.1.
It prints two sentinel lines:
  H2BT_SERVE url=<base-url> pid=<pid> state=<serve.json|none> pidfile=<path> reused=<yes|no>
  H2BT_HARNESS url=<harness-url> site_copy=<path|none> sink=<dir>

--site-path  The Studio site being built. The server's state is written to
             <site>/.h2bt/serve.json, and a copy of the comparison harness is placed at
             <site>/_h2bt/viewport.html, where the site serves it, so that the harness can
             read the WordPress page as well as the original. A start for a site whose
             recorded server still answers, on the same directory, reuses it.
--ensure     The recorded server if it still answers, else a new one on the recorded
             directory (or --dir). After a --stop nothing is recorded: the directory is
             then the run's design directory, design_dir in <site>/.h2bt/run.json. Run it
             whenever the server may have died or was stopped: at the start of a session,
             after a long wait, when a page of the original does not load.
--stop       With --site-path: stops the recorded server and removes the harness copy and
             the state file. The harness copy is removed even when no server is recorded.
--missing    Lists the paths the running server answered 404 for, read from its log, with how
             many times each was asked for, and writes them one per line to
             <site>/.h2bt/missing.txt (beside the pid file without a site). Source maps and
             the harness's own paths are left out. Load every page of a mirror once first:
             what is listed is what its scripts load at run time and the mirror lacks, and
             mirror-site.py --assets-from <file> fetches it. Ends with
             H2BT_SERVE_MISSING count=<n> file=<path> log=<path>.
--sink-dir   Where measurements posted to the sink are written (<name>.json). Default:
             <site>/.h2bt/measurements with --site-path, else a directory under $TMPDIR.

A start that cannot be made ends with H2BT_SERVE_FAIL reason=<why> and a non-zero exit.
EOF
}

# A flag that takes a value must be followed by one.
need_value() { [[ $# -ge 2 ]] || { echo "$1 needs a value" >&2; exit 2; }; }

# A start that cannot be made says so on standard output too: a caller that reads only the
# sentinel must not take a usage text, or nothing, for a server.
cannot_serve() { # cannot_serve <reason, no spaces> <message> [<exit code>]
	echo "$2" >&2
	echo "H2BT_SERVE_FAIL reason=$1"
	exit "${3:-1}"
}

dir=""
port=""
stop=0
ensure=0
missing=0
pidfile=""
site_path=""
sink_dir=""

while [[ $# -gt 0 ]]; do
	case "$1" in
		--dir) need_value "$@"; dir="$2"; shift 2 ;;
		--port) need_value "$@"; port="$2"; shift 2 ;;
		--site-path) need_value "$@"; site_path="$2"; shift 2 ;;
		--sink-dir) need_value "$@"; sink_dir="$2"; shift 2 ;;
		--stop) stop=1; shift ;;
		--ensure) ensure=1; shift ;;
		--missing) missing=1; shift ;;
		--pidfile) need_value "$@"; pidfile="$2"; shift 2 ;;
		-h|--help) usage; exit 0 ;;
		*) echo "Unknown argument: $1" >&2; usage >&2; exit 2 ;;
	esac
done

command -v python3 >/dev/null 2>&1 || cannot_serve no-python3 "python3 is required to serve files"

state_get() { # state_get <state file> <key>: a value of the state file, or nothing
	python3 -c 'import json,sys
try:
    print(json.load(open(sys.argv[1])).get(sys.argv[2], ""))
except Exception:
    pass' "$1" "$2"
}

# Whether the server a state file records is still the one on its port. A process id is
# reused and so is a port, so the server is asked for the token it was started with.
recorded_alive() { # recorded_alive <state file>
	local url token
	url="$(state_get "$1" url)"
	token="$(state_get "$1" id)"
	[[ -n "$url" && -n "$token" ]] || return 1
	python3 -c 'import sys,urllib.request
try:
    body = urllib.request.urlopen(sys.argv[1] + "_h2bt/id", timeout=3).read().decode()
except Exception:
    sys.exit(1)
sys.exit(0 if body == sys.argv[2] else 1)' "$url" "$token"
}

# Stops a process only when it is this server: the number in a file outlives its process,
# and after a reboot or a long run it can belong to something else.
stop_server() { # stop_server <pid> [<port>]
	local command
	[[ "${1:-}" =~ ^[0-9]+$ ]] || return 1
	command="$(ps -ww -p "$1" -o command= 2>/dev/null || true)"
	[[ "$command" == *serve.py* ]] || return 1
	[[ -z "${2:-}" || "$command" == *"--port $2 "* ]] || return 1
	kill "$1" 2>/dev/null || true
}

remove_harness_copy() { # remove_harness_copy <path>: a harness copy, and nothing else
	if [[ "$1" == */_h2bt/viewport.html && -f "$1" ]]; then
		rm -f "$1"
		rmdir "$(dirname "$1")" 2>/dev/null || true
		echo "H2BT_HARNESS_REMOVED path=$1"
	fi
}

remove_own_file() { # remove_own_file <path> <suffix>: only a file this script names
	if [[ "$1" == */h2bt-serve-*"$2" ]]; then
		rm -f "$1"
	fi
}

if [[ "$missing" -eq 1 ]]; then
	if [[ -n "$site_path" ]]; then
		[[ -d "$site_path" ]] || { echo "Site path not found: $site_path" >&2; exit 1; }
		site_path="$(cd "$site_path" && pwd)"
		state="$site_path/.h2bt/serve.json"
		[[ -f "$state" ]] || { echo "No server is recorded for this site: start it with --ensure, load the pages, then ask again" >&2; exit 1; }
		log="$(state_get "$state" log)"
		out="$site_path/.h2bt/missing.txt"
	else
		[[ -n "$pidfile" ]] || { echo "--missing needs --site-path or --pidfile" >&2; exit 2; }
		log="${pidfile%.pid}.log"
		out="${pidfile%.pid}.missing.txt"
	fi
	[[ -f "$log" ]] || { echo "The server's log is not there: $log" >&2; exit 1; }
	python3 -I -c 'import collections,re,sys,urllib.parse
counts = collections.Counter()
line_re = re.compile(r"\"(?:GET|HEAD) (\S+) HTTP/[\d.]+\" 404 ")
with open(sys.argv[1], encoding="utf-8", errors="replace") as handle:
    for line in handle:
        match = line_re.search(line)
        if not match:
            continue
        path = urllib.parse.urlsplit(match.group(1)).path
        if path.startswith("/_h2bt") or path.endswith(".map"):
            continue
        counts[path] += 1
with open(sys.argv[2], "w", encoding="utf-8") as handle:
    for path in sorted(counts):
        handle.write(path + "\n")
for path, count in sorted(counts.items()):
    print("  %4d  %s" % (count, path))
print("H2BT_SERVE_MISSING count=%d file=%s log=%s" % (len(counts), sys.argv[2], sys.argv[1]))' "$log" "$out"
	exit 0
fi

if [[ "$stop" -eq 1 ]]; then
	if [[ -n "$site_path" ]]; then
		[[ -d "$site_path" ]] || { echo "Site path not found: $site_path" >&2; exit 1; }
		site_path="$(cd "$site_path" && pwd)"
		state="$site_path/.h2bt/serve.json"
		if [[ -f "$state" ]]; then
			pid="$(state_get "$state" pid)"
			if stop_server "$pid" "$(state_get "$state" port)"; then
				echo "H2BT_SERVE_STOPPED pid=$pid"
			else
				echo "H2BT_SERVE_STOPPED pid=${pid:-unknown} (already gone)"
			fi
			remove_own_file "$(state_get "$state" log)" .log
			remove_own_file "$(state_get "$state" pidfile)" .pid
			remove_own_file "$(state_get "$state" pidfile | sed 's/\.pid$/.state/')" .state
			rm -f "$state"
		else
			echo "H2BT_SERVE_STOPPED (no server is recorded for this site)"
		fi
		# The harness copy never stays in the site, whatever the state file said.
		remove_harness_copy "$site_path/_h2bt/viewport.html"
		exit 0
	fi

	[[ -n "$pidfile" && -f "$pidfile" ]] || { echo "--stop needs --site-path, or a --pidfile that exists" >&2; exit 2; }
	pid="$(cat "$pidfile")"
	# Nothing below runs on a file that is not one of this script's pid files: it would be
	# deleted, and whatever number it held would be signalled.
	[[ "$pid" =~ ^[0-9]+$ ]] || { echo "Not a pid file written by serve-html.sh: $pidfile" >&2; exit 2; }
	if stop_server "$pid"; then
		echo "H2BT_SERVE_STOPPED pid=$pid"
	else
		echo "H2BT_SERVE_STOPPED pid=$pid (already gone)"
	fi
	# Remove the harness copy this server placed in the site. The path was recorded at start;
	# anything that is not a harness copy is left alone.
	statefile="${pidfile%.pid}.state"
	if [[ -f "$statefile" ]]; then
		remove_harness_copy "$(cat "$statefile")"
		rm -f "$statefile"
	fi
	rm -f "$pidfile" "${pidfile%.pid}.log"
	exit 0
fi

[[ "$ensure" -eq 0 || -n "$site_path" ]] || cannot_serve no-site-path "--ensure needs --site-path" 2
[[ -z "$site_path" || -d "$site_path" ]] || cannot_serve site-not-found "Site path not found: $site_path"
[[ -z "$dir" || -d "$dir" ]] || cannot_serve dir-not-found "Directory not found: $dir"
# The port goes into file names and into the listening check below.
[[ -z "$port" || ( "$port" =~ ^[0-9]{1,5}$ && "$port" -ge 1 && "$port" -le 65535 ) ]] || cannot_serve bad-port "--port must be a port number: $port" 2

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
harness="$script_dir/viewport.html"
[[ -r "$harness" && -r "$script_dir/serve.py" ]] || cannot_serve harness-missing "viewport.html or serve.py is missing from $script_dir"

state="none"
if [[ -n "$site_path" ]]; then
	site_path="$(cd "$site_path" && pwd)"
	state="$site_path/.h2bt/serve.json"
	if [[ -f "$state" ]]; then
		recorded_dir="$(state_get "$state" dir)"
		[[ -n "$dir" ]] || dir="$recorded_dir"
		if [[ -d "$dir" && "$(cd "$dir" && pwd)" == "$recorded_dir" ]] && recorded_alive "$state"; then
			# The same server, still answering: nothing to start. The harness copy is put
			# back in case something removed it.
			mkdir -p "$site_path/_h2bt"
			cp "$harness" "$site_path/_h2bt/viewport.html"
			echo "H2BT_SERVE url=$(state_get "$state" url) pid=$(state_get "$state" pid) state=${state} pidfile=$(state_get "$state" pidfile) reused=yes"
			echo "H2BT_HARNESS url=$(state_get "$state" harness) site_copy=$site_path/_h2bt/viewport.html sink=$(state_get "$state" sink)"
			exit 0
		fi
		# A recorded server that is gone, or that serves another directory: clear it first, so
		# that two servers never share one site's harness copy.
		stop_server "$(state_get "$state" pid)" "$(state_get "$state" port)" || true
		remove_own_file "$(state_get "$state" log)" .log
		remove_own_file "$(state_get "$state" pidfile)" .pid
		remove_own_file "$(state_get "$state" pidfile | sed 's/\.pid$/.state/')" .state
		rm -f "$state"
	fi
	# Nothing is recorded after a --stop. The run's own record still says which directory the
	# design is in, so the server comes back without anyone having to remember it.
	if [[ -z "$dir" && -f "$site_path/.h2bt/run.json" ]]; then
		dir="$(state_get "$site_path/.h2bt/run.json" design_dir)"
	fi
fi

[[ -n "$dir" ]] || cannot_serve no-dir "--dir is required: no server is recorded for this site, and its .h2bt/run.json names no design_dir" 2
[[ -d "$dir" ]] || cannot_serve dir-not-found "Directory not found: $dir"
abs_dir="$(cd "$dir" && pwd)"

listening() { python3 -c 'import socket,sys; s=socket.socket(); sys.exit(0 if s.connect_ex(("127.0.0.1",int(sys.argv[1])))==0 else 1)' "$1"; }

if [[ -z "$port" ]]; then
	port="$(python3 -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1",0)); print(s.getsockname()[1]); s.close()')"
elif listening "$port"; then
	# The check after the start cannot tell the new server from one already on the port.
	cannot_serve port-in-use "Port $port is already in use; stop that server or leave --port out"
fi

logfile="${TMPDIR:-/tmp}/h2bt-serve-${port}.log"
pidfile="${TMPDIR:-/tmp}/h2bt-serve-${port}.pid"
statefile="${TMPDIR:-/tmp}/h2bt-serve-${port}.state"

site_copy="none"
if [[ -n "$site_path" ]]; then
	[[ -n "$sink_dir" ]] || sink_dir="$site_path/.h2bt/measurements"
fi
[[ -n "$sink_dir" ]] || sink_dir="${TMPDIR:-/tmp}/h2bt-sink-${port}"
mkdir -p "$sink_dir"
sink_dir="$(cd "$sink_dir" && pwd)"

token="$(python3 -c 'import secrets; print(secrets.token_hex(8))')"
nohup python3 -I "$script_dir/serve.py" --dir "$abs_dir" --port "$port" --harness "$harness" --sink-dir "$sink_dir" --id "$token" >"$logfile" 2>&1 &
pid="$!"
echo "$pid" >"$pidfile"

# Give it a moment and confirm it is actually listening.
for _ in 1 2 3 4 5 6 7 8 9 10; do
	if kill -0 "$pid" 2>/dev/null && listening "$port"; then
		url="http://127.0.0.1:${port}/"
		if [[ -n "$site_path" ]]; then
			# Outside wp-content, so never inside a project repository. Removed by --stop.
			mkdir -p "$site_path/_h2bt" "$site_path/.h2bt"
			cp "$harness" "$site_path/_h2bt/viewport.html"
			site_copy="$site_path/_h2bt/viewport.html"
			printf '%s' "$site_copy" >"$statefile"
			python3 -c 'import json,sys,time
keys = ("url", "harness", "port", "pid", "id", "dir", "sink", "site_copy", "log", "pidfile")
state = dict(zip(keys, sys.argv[2:]))
state["port"], state["pid"] = int(state["port"]), int(state["pid"])
state["started"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
with open(sys.argv[1], "w") as handle:
    json.dump(state, handle, indent=2)
    handle.write("\n")' "$state" "$url" "${url}_h2bt/viewport.html" "$port" "$pid" "$token" "$abs_dir" "$sink_dir" "$site_copy" "$logfile" "$pidfile"
		fi
		echo "H2BT_SERVE url=${url} pid=${pid} state=${state} pidfile=${pidfile} reused=no"
		echo "H2BT_HARNESS url=${url}_h2bt/viewport.html site_copy=${site_copy} sink=${sink_dir}"
		exit 0
	fi
	sleep 0.3
done

kill "$pid" 2>/dev/null || true
rm -f "$pidfile"
cannot_serve start-failed "Server failed to start — see $logfile"
