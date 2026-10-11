#!/usr/bin/env bash
#
# dev-mode.sh — turn WP_DEVELOPMENT_MODE on for a build, and put back what was there.
#
# WordPress caches a theme's file list and its theme.json. With WP_DEVELOPMENT_MODE set to
# "theme" it does not, so a new or deleted template shows at once. A build needs that; the
# site should not keep it afterwards, and it should not lose a value it had before.
#
#   dev-mode.sh on --site-path <site>        records the value the site had, once, then sets "theme"
#   dev-mode.sh restore --site-path <site>   puts the recorded value back, or removes the constant
#
# The value is recorded in <site>/.h2bt/dev-mode.prior the first time `on` runs, and never
# overwritten: a run that is resumed calls `on` again and must not record "theme" as the
# value to restore.
#
# Last line: H2BT_DEV_MODE on prior=<value|absent>, H2BT_DEV_MODE restored value=<value|absent>,
# H2BT_DEV_MODE restored value=nothing-recorded, or H2BT_DEV_MODE_FAIL reason=... (exit 1).
#
set -euo pipefail

usage() {
	cat <<'EOF'
Usage:
  dev-mode.sh on --site-path <site>
  dev-mode.sh restore --site-path <site>

on       Records the site's current WP_DEVELOPMENT_MODE (once) and sets it to "theme".
restore  Puts the recorded value back, or removes the constant if the site had none.
EOF
}

# A flag that takes a value must be followed by one.
need_value() { [[ $# -ge 2 ]] || { echo "$1 needs a value" >&2; exit 2; }; }

action="${1:-}"
[[ $# -gt 0 ]] && shift
site_path=""
while [[ $# -gt 0 ]]; do
	case "$1" in
		--site-path) need_value "$@"; site_path="$2"; shift 2 ;;
		-h|--help) usage; exit 0 ;;
		*) echo "Unknown argument: $1" >&2; usage >&2; exit 2 ;;
	esac
done

case "$action" in
	on|restore) ;;
	-h|--help) usage; exit 0 ;;
	*) usage >&2; exit 2 ;;
esac
[[ -n "$site_path" && -d "$site_path" ]] || { echo "--site-path must name the Studio site directory" >&2; exit 2; }
command -v studio >/dev/null 2>&1 || { echo "studio CLI not found" >&2; echo "H2BT_DEV_MODE_FAIL reason=no-studio"; exit 1; }

site_path="$(cd "$site_path" && pwd)"
prior_file="$site_path/.h2bt/dev-mode.prior"
name="WP_DEVELOPMENT_MODE"

wp() { ( cd "$site_path" && studio wp "$@" --path="$site_path" ); }

has_constant() { wp config has "$name" >/dev/null 2>&1; }

# The constant's value. Studio can print notices around it, so the value is the last line.
current_value() { wp config get "$name" 2>/dev/null | tr -d '\r' | tail -1; }

fail() { # fail <reason, no spaces> <message>
	echo "$2" >&2
	echo "H2BT_DEV_MODE_FAIL reason=$1"
	exit 1
}

if [[ "$action" == "on" ]]; then
	mkdir -p "$site_path/.h2bt"
	if [[ ! -f "$prior_file" ]]; then
		if has_constant; then
			printf 'value=%s\n' "$(current_value)" >"$prior_file"
		else
			printf 'absent\n' >"$prior_file"
		fi
	fi
	wp config set "$name" theme >/dev/null 2>&1 || fail set-failed "Could not set $name in wp-config.php"
	[[ "$(current_value)" == "theme" ]] || fail not-set "$name is not \"theme\" after setting it"
	prior="$(cat "$prior_file")"
	echo "H2BT_DEV_MODE on prior=${prior#value=}"
	exit 0
fi

if [[ ! -f "$prior_file" ]]; then
	echo "H2BT_DEV_MODE restored value=nothing-recorded"
	exit 0
fi
prior="$(cat "$prior_file")"
if [[ "$prior" == "absent" ]]; then
	if has_constant; then
		wp config delete "$name" >/dev/null 2>&1 || fail delete-failed "Could not remove $name from wp-config.php"
	fi
	has_constant && fail still-set "$name is still in wp-config.php after removing it"
	rm -f "$prior_file"
	echo "H2BT_DEV_MODE restored value=absent"
	exit 0
fi
value="${prior#value=}"
wp config set "$name" "$value" >/dev/null 2>&1 || fail set-failed "Could not set $name back to \"$value\""
[[ "$(current_value)" == "$value" ]] || fail not-restored "$name is not \"$value\" after restoring it"
rm -f "$prior_file"
echo "H2BT_DEV_MODE restored value=$value"
