#!/usr/bin/env bash
# Install, remove or check one of the migration mu-plugins on a site.
#
#   mu_plugin.sh install <pressable|wpcom> <site> <path/to/t51-migration-*.php>
#   mu_plugin.sh remove  <pressable|wpcom> <site> <t51-migration-*.php>
#   mu_plugin.sh status  <pressable|wpcom> <site> <t51-migration-*.php>
#
# install and remove CHANGE THE SITE. For the freeze plugin, set
# T51_FREEZE_MODE=drain|frozen when installing (default: frozen).
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
action="${1:-}"; host="${2:-}"; site="${3:-}"; file="${4:-}"
[[ -n "$action" && -n "$host" && -n "$site" && -n "$file" ]] || { sed -n '2,9p' "$0" >&2; exit 64; }
name="$(basename "$file")"

case "$action" in
	install)
		[[ -r "$file" ]] || { echo "cannot read $file" >&2; exit 66; }
		php -l "$file" >/dev/null || { echo "$file has a PHP syntax error; not installing" >&2; exit 65; }
		content=$(base64 < "$file" | tr -d '\n')
		mode="${T51_FREEZE_MODE:-frozen}"
		export T51_ARGS="{\"action\":\"install\",\"name\":\"$name\",\"content_b64\":\"$content\",\"replace\":{\"__T51_FREEZE_MODE__\":\"$mode\"}}"
		;;
	remove|status)
		export T51_ARGS="{\"action\":\"$action\",\"name\":\"$name\"}"
		;;
	*) echo "action must be install, remove or status" >&2; exit 64 ;;
esac
"$here/wp_eval.sh" "$host" "$site" "$here/mu_plugin.php"
