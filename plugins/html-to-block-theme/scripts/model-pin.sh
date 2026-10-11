#!/usr/bin/env bash
#
# model-pin.sh — check or move the one model and effort this plugin is pinned to.
#
# The evals check the guides against one model at one effort, so the plugin runs on that
# pair: both subagents name it in their frontmatter, the skill's preconditions require the
# model of the session, and the evals run on it. This script keeps those places in step.
#
#   model-pin.sh --check                              exit 0 when every place agrees
#   model-pin.sh --set <model-id> [--effort <level>]  move every place to another model
#   model-pin.sh --effort <level>                     change the effort alone
#
# Output: H2BT_MODEL_PIN model=<id> effort=<level> places=<n> ok, or one
# H2BT_MODEL_PIN_MISMATCH line per place that disagrees and a non-zero exit. The pins are
# read from the section-builder agent. The changelog and the evals' reports are history and
# are not touched.
#
set -euo pipefail

usage() {
	cat <<'EOF'
Usage:
  model-pin.sh --check
  model-pin.sh --set <model-id> [--effort <level>]
  model-pin.sh --effort <level>

--check exits 0 when the subagents, the skill's precondition, the evals and the README all
name the same model and effort. --set and --effort move them all. Run the evals on a new
model or effort before relying on it.
EOF
}

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# file|extended regex, with MODEL and EFFORT standing for the pins. Each must match.
places=(
	'agents/blueprint-analyzer.md|^model: MODEL$'
	'agents/blueprint-analyzer.md|^effort: EFFORT$'
	'agents/section-builder.md|^model: MODEL$'
	'agents/section-builder.md|^effort: EFFORT$'
	'skills/html-to-block-theme/SKILL.md|/model MODEL`'
	'evals/eval.config.json|"model": "MODEL"'
	'evals/eval.config.json|"effort": "EFFORT"'
	'README.md|`MODEL` at `EFFORT` effort'
)

pinned() {
	sed -n "s/^$1: //p" "$root/agents/section-builder.md" | head -n 1
}

check() {
	local model="$1" effort="$2" failed=0 place file pattern
	for place in "${places[@]}"; do
		file="${place%%|*}"
		pattern="${place#*|}"
		pattern="${pattern//MODEL/${model//./\\.}}"
		pattern="${pattern//EFFORT/$effort}"
		if ! grep -Eq -- "$pattern" "$root/$file" 2>/dev/null; then
			echo "H2BT_MODEL_PIN_MISMATCH file=$file expected=\"${pattern}\""
			failed=1
		fi
	done
	if [[ "$failed" -ne 0 ]]; then
		return 1
	fi
	echo "H2BT_MODEL_PIN model=$model effort=$effort places=${#places[@]} ok"
}

mode=""
new_model=""
new_effort=""

while [[ $# -gt 0 ]]; do
	case "$1" in
		--check) mode="check"; shift ;;
		--set) mode="set"; new_model="${2:-}"; shift 2 ;;
		--effort) [[ -n "$mode" ]] || mode="set"; new_effort="${2:-}"; shift 2 ;;
		-h|--help) usage; exit 0 ;;
		*) echo "Unknown argument: $1" >&2; usage >&2; exit 2 ;;
	esac
done

old_model="$(pinned model)"
old_effort="$(pinned effort)"
if [[ -z "$old_model" || "$old_model" == "inherit" || -z "$old_effort" ]]; then
	echo "No pinned model and effort in agents/section-builder.md." >&2
	exit 1
fi

case "$mode" in
	check)
		check "$old_model" "$old_effort"
		;;
	set)
		new_model="${new_model:-$old_model}"
		new_effort="${new_effort:-$old_effort}"
		if [[ ! "$new_model" =~ ^[A-Za-z0-9][A-Za-z0-9._-]*$ ]]; then
			echo "Not a model id: '$new_model'" >&2
			exit 2
		fi
		if [[ ! "$new_effort" =~ ^(low|medium|high|xhigh|max)$ ]]; then
			echo "Not an effort level: '$new_effort'" >&2
			exit 2
		fi
		for place in "${places[@]}"; do
			python3 - "$root/${place%%|*}" "${place#*|}" "$old_model" "$new_model" "$old_effort" "$new_effort" <<'PY'
import pathlib
import re
import sys

path, shape, old_model, new_model, old_effort, new_effort = sys.argv[1:7]
path = pathlib.Path( path )


def fill( model, effort, escape ):
	# The place's own shape, as a pattern for the old pins or as text for the new ones.
	anchored = shape.startswith( '^' ) and shape.endswith( '$' )
	parts = re.split( r'(MODEL|EFFORT)', shape.strip( '^$' ) )
	text = ''.join( ( model if part == 'MODEL' else effort if part == 'EFFORT' else part ) if not escape else ( re.escape( model ) if part == 'MODEL' else re.escape( effort ) if part == 'EFFORT' else re.escape( part ) ) for part in parts )
	return ( '^' + text + '$', re.MULTILINE ) if anchored and escape else ( text, 0 )


pattern, flags = fill( old_model, old_effort, True )
replacement, _ = fill( new_model, new_effort, False )
path.write_text( re.sub( pattern, lambda _match: replacement, path.read_text(), flags=flags ) )
PY
		done
		check "$new_model" "$new_effort"
		echo "Run the evals on $new_model at $new_effort before relying on it: evals/README.md."
		;;
	*)
		usage >&2
		exit 2
		;;
esac
