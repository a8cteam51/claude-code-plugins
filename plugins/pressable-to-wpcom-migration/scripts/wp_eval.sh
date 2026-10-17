#!/usr/bin/env bash
# Run a PHP file on a Pressable or WordPress.com site through `wp eval`, using
# the team51 CLI, and print the JSON the script emits between its markers.
#
#   wp_eval.sh <pressable|wpcom> <site domain or ID> <script.php> [--raw]
#
# Set T51_ARGS to a JSON object to pass arguments; the script reads them from
# the $t51_args array.
#
# The PHP is sent base64-encoded so nothing in it needs shell escaping. The
# scripts in this directory are read-only; this wrapper does not make them so.
set -euo pipefail

host="${1:-}"; site="${2:-}"; script="${3:-}"; raw="${4:-}"
if [[ -z "$host" || -z "$site" || -z "$script" ]]; then
	echo "usage: wp_eval.sh <pressable|wpcom> <site> <script.php> [--raw]" >&2
	exit 64
fi
[[ -r "$script" ]] || { echo "cannot read $script" >&2; exit 66; }
command -v team51 >/dev/null || { echo "team51 CLI not found on PATH" >&2; exit 69; }

# Drop the opening tag: eval() takes bare PHP.
args_b64=$(printf '%s' "${T51_ARGS:-{\}}" | base64 | tr -d '\n')
# The transport can insert line breaks into long output, so results travel as
# base64 in short lines and are reassembled here.
prelude='$t51_args = json_decode(base64_decode("'"$args_b64"'"), true); function t51_emit($data) { echo "\n##T51_RESULT_BEGIN##\n" . chunk_split(base64_encode(wp_json_encode($data)), 76, "\n") . "##T51_RESULT_END##\n"; }'
payload=$( { printf '%s\n' "$prelude"; sed '1{/^<?php/d;}' "$script"; } | base64 | tr -d '\n')
cmd="eval \"eval(base64_decode(\\\"${payload}\\\"));\""

# 1Password authorises per shell and the grant can lapse; prompt for it up front.
if command -v op >/dev/null; then
	op vault list --account a8cteam51.1password.com >/dev/null 2>&1 || true
fi

case "$host" in
	pressable) output=$(team51 pressable:run-site-wp-cli-command "$cmd" "$site" -n --no-ansi </dev/null 2>&1) || status=$? ;;
	wpcom)     output=$(team51 wpcom:run-site-wp-cli-command "$site" "$cmd" -n --no-ansi </dev/null 2>&1) || status=$? ;;
	*) echo "host must be pressable or wpcom" >&2; exit 64 ;;
esac

if [[ "$raw" == "--raw" ]]; then
	printf '%s\n' "$output"
	exit "${status:-0}"
fi

encoded=$(printf '%s\n' "$output" | awk '/##T51_RESULT_BEGIN##/{f=1;next} /##T51_RESULT_END##/{f=0} f' | tr -d ' \t\r\n')
if [[ -z "$encoded" ]]; then
	echo "No result markers in the output. Last lines from the CLI:" >&2
	printf '%s\n' "$output" | tail -n 25 >&2
	exit "${status:-1}"
fi
printf '%s' "$encoded" | base64 -d
echo
