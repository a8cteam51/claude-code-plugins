#!/usr/bin/env bash
#
# serve-html.sh — serve a directory of static design files over HTTP so a real
# browser (Claude in Chrome) can load them with relative CSS/JS/asset paths resolving.
# Serving over HTTP (not file://) avoids broken relative URLs and CORS quirks.
#
# The server also carries the comparison harness (viewport.html) at /_h2bt/viewport.html
# and a results sink at /_h2bt/sink/<name>; see references/visual-refinement.md.
#
# Start:  serve-html.sh --dir <design-dir> [--site-path <site>] [--sink-dir <dir>]
#           -> prints: H2BT_SERVE url=http://127.0.0.1:<port>/ pid=<pid> pidfile=<path>
#                      H2BT_HARNESS url=<harness-url> site_copy=<path|none> sink=<dir>
# Stop:   serve-html.sh --stop --pidfile <path>
#           -> also removes the harness copy it placed in the site
#
set -euo pipefail

usage() {
	cat <<'EOF'
Usage:
  serve-html.sh --dir <design-dir> [--port <port>] [--site-path <site>] [--sink-dir <dir>]
  serve-html.sh --stop --pidfile <path>

Starts a background static HTTP server rooted at <design-dir> bound to 127.0.0.1.
On start it prints two sentinel lines:
  H2BT_SERVE url=<base-url> pid=<pid> pidfile=<path>
  H2BT_HARNESS url=<harness-url> site_copy=<path|none> sink=<dir>
Capture the url for the browser and the pidfile to stop it later.

--site-path  The Studio site being built. A copy of the comparison harness is placed at
             <site>/_h2bt/viewport.html, where the site serves it, so that the harness can
             read the WordPress page as well as the original. --stop removes it again.
--sink-dir   Where measurements posted to the sink are written (<name>.json). Default:
             <site>/.h2bt/measurements with --site-path, else a directory under $TMPDIR.
EOF
}

# A flag that takes a value must be followed by one.
need_value() { [[ $# -ge 2 ]] || { echo "$1 needs a value" >&2; exit 2; }; }

dir=""
port=""
stop=0
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
		--pidfile) need_value "$@"; pidfile="$2"; shift 2 ;;
		-h|--help) usage; exit 0 ;;
		*) echo "Unknown argument: $1" >&2; usage >&2; exit 2 ;;
	esac
done

if [[ "$stop" -eq 1 ]]; then
	[[ -n "$pidfile" && -f "$pidfile" ]] || { echo "Missing or invalid --pidfile" >&2; exit 2; }
	pid="$(cat "$pidfile")"
	# Nothing below runs on a file that is not one of this script's pid files: it would be
	# deleted, and whatever number it held would be signalled.
	[[ "$pid" =~ ^[0-9]+$ ]] || { echo "Not a pid file written by serve-html.sh: $pidfile" >&2; exit 2; }
	# A pid outlives its process: after a reboot or a long run the number can belong to
	# something else. Only a process that is this server is stopped.
	if ps -p "$pid" -o command= 2>/dev/null | grep -q 'serve\.py'; then
		kill "$pid" 2>/dev/null || true
		echo "H2BT_SERVE_STOPPED pid=$pid"
	else
		echo "H2BT_SERVE_STOPPED pid=$pid (already gone)"
	fi
	# Remove the harness copy this server placed in the site. The path was recorded at start;
	# anything that is not a harness copy is left alone.
	statefile="${pidfile%.pid}.state"
	if [[ -f "$statefile" ]]; then
		site_copy="$(cat "$statefile")"
		if [[ "$site_copy" == */_h2bt/viewport.html && -f "$site_copy" ]]; then
			rm -f "$site_copy"
			rmdir "$(dirname "$site_copy")" 2>/dev/null || true
			echo "H2BT_HARNESS_REMOVED path=$site_copy"
		fi
		rm -f "$statefile"
	fi
	rm -f "$pidfile" "${pidfile%.pid}.log"
	exit 0
fi

[[ -n "$dir" ]] || { echo "--dir is required" >&2; usage >&2; exit 2; }
# The port goes into file names and into the listening check below.
[[ -z "$port" || ( "$port" =~ ^[0-9]{1,5}$ && "$port" -ge 1 && "$port" -le 65535 ) ]] || { echo "--port must be a port number: $port" >&2; exit 2; }
[[ -d "$dir" ]] || { echo "Directory not found: $dir" >&2; exit 1; }
[[ -z "$site_path" || -d "$site_path" ]] || { echo "Site path not found: $site_path" >&2; exit 1; }
command -v python3 >/dev/null 2>&1 || { echo "python3 is required to serve files" >&2; exit 1; }

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
harness="$script_dir/viewport.html"
[[ -r "$harness" && -r "$script_dir/serve.py" ]] || { echo "viewport.html or serve.py is missing from $script_dir" >&2; exit 1; }

abs_dir="$(cd "$dir" && pwd)"

listening() { python3 -c 'import socket,sys; s=socket.socket(); sys.exit(0 if s.connect_ex(("127.0.0.1",int(sys.argv[1])))==0 else 1)' "$1"; }

if [[ -z "$port" ]]; then
	port="$(python3 -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1",0)); print(s.getsockname()[1]); s.close()')"
elif listening "$port"; then
	# The check after the start cannot tell the new server from one already on the port.
	echo "Port $port is already in use; stop that server or leave --port out" >&2
	exit 1
fi

logfile="${TMPDIR:-/tmp}/h2bt-serve-${port}.log"
pidfile="${TMPDIR:-/tmp}/h2bt-serve-${port}.pid"
statefile="${TMPDIR:-/tmp}/h2bt-serve-${port}.state"

site_copy="none"
if [[ -n "$site_path" ]]; then
	site_path="$(cd "$site_path" && pwd)"
	[[ -n "$sink_dir" ]] || sink_dir="$site_path/.h2bt/measurements"
fi
[[ -n "$sink_dir" ]] || sink_dir="${TMPDIR:-/tmp}/h2bt-sink-${port}"
mkdir -p "$sink_dir"
sink_dir="$(cd "$sink_dir" && pwd)"

nohup python3 -I "$script_dir/serve.py" --dir "$abs_dir" --port "$port" --harness "$harness" --sink-dir "$sink_dir" >"$logfile" 2>&1 &
pid="$!"
echo "$pid" >"$pidfile"

# Give it a moment and confirm it is actually listening.
for _ in 1 2 3 4 5 6 7 8 9 10; do
	if kill -0 "$pid" 2>/dev/null && listening "$port"; then
		if [[ -n "$site_path" ]]; then
			# Outside wp-content, so never inside a project repository. Removed by --stop.
			mkdir -p "$site_path/_h2bt"
			cp "$harness" "$site_path/_h2bt/viewport.html"
			site_copy="$site_path/_h2bt/viewport.html"
			printf '%s' "$site_copy" >"$statefile"
		fi
		echo "H2BT_SERVE url=http://127.0.0.1:${port}/ pid=${pid} pidfile=${pidfile}"
		echo "H2BT_HARNESS url=http://127.0.0.1:${port}/_h2bt/viewport.html site_copy=${site_copy} sink=${sink_dir}"
		exit 0
	fi
	sleep 0.3
done

echo "Server failed to start — see $logfile" >&2
kill "$pid" 2>/dev/null || true
rm -f "$pidfile"
exit 1
