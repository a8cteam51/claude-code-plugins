#!/usr/bin/env bash
#
# serve-html.sh — serve a directory of static design files over HTTP so a real
# browser (Playwright) can load them with relative CSS/JS/asset paths resolving.
# Serving over HTTP (not file://) avoids broken relative URLs and CORS quirks.
#
# Start:  serve-html.sh --dir <design-dir>
#           -> prints: H2BT_SERVE url=http://127.0.0.1:<port>/ pid=<pid> pidfile=<path>
# Stop:   serve-html.sh --stop --pidfile <path>
#
set -euo pipefail

usage() {
	cat <<'EOF'
Usage:
  serve-html.sh --dir <design-dir> [--port <port>]
  serve-html.sh --stop --pidfile <path>

Starts a background static HTTP server rooted at <design-dir> bound to 127.0.0.1.
On start it prints a single sentinel line:
  H2BT_SERVE url=<base-url> pid=<pid> pidfile=<path>
Capture the url for the browser and the pidfile to stop it later.
EOF
}

dir=""
port=""
stop=0
pidfile=""

while [[ $# -gt 0 ]]; do
	case "$1" in
		--dir) dir="${2:-}"; shift 2 ;;
		--port) port="${2:-}"; shift 2 ;;
		--stop) stop=1; shift ;;
		--pidfile) pidfile="${2:-}"; shift 2 ;;
		-h|--help) usage; exit 0 ;;
		*) echo "Unknown argument: $1" >&2; usage >&2; exit 2 ;;
	esac
done

if [[ "$stop" -eq 1 ]]; then
	[[ -n "$pidfile" && -f "$pidfile" ]] || { echo "Missing or invalid --pidfile" >&2; exit 2; }
	pid="$(cat "$pidfile")"
	if kill "$pid" 2>/dev/null; then
		echo "H2BT_SERVE_STOPPED pid=$pid"
	else
		echo "H2BT_SERVE_STOPPED pid=$pid (already gone)"
	fi
	rm -f "$pidfile"
	exit 0
fi

[[ -n "$dir" ]] || { echo "--dir is required" >&2; usage >&2; exit 2; }
[[ -d "$dir" ]] || { echo "Directory not found: $dir" >&2; exit 1; }
command -v python3 >/dev/null 2>&1 || { echo "python3 is required to serve files" >&2; exit 1; }

abs_dir="$(cd "$dir" && pwd)"

if [[ -z "$port" ]]; then
	port="$(python3 -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1",0)); print(s.getsockname()[1]); s.close()')"
fi

logfile="${TMPDIR:-/tmp}/h2bt-serve-${port}.log"
pidfile="${TMPDIR:-/tmp}/h2bt-serve-${port}.pid"

nohup python3 -m http.server "$port" --bind 127.0.0.1 --directory "$abs_dir" >"$logfile" 2>&1 &
pid="$!"
echo "$pid" >"$pidfile"

# Give it a moment and confirm it is actually listening.
for _ in 1 2 3 4 5 6 7 8 9 10; do
	if kill -0 "$pid" 2>/dev/null && python3 -c "import socket,sys; s=socket.socket(); sys.exit(0 if s.connect_ex(('127.0.0.1',$port))==0 else 1)"; then
		echo "H2BT_SERVE url=http://127.0.0.1:${port}/ pid=${pid} pidfile=${pidfile}"
		exit 0
	fi
	sleep 0.3
done

echo "Server failed to start — see $logfile" >&2
kill "$pid" 2>/dev/null || true
rm -f "$pidfile"
exit 1
