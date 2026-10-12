#!/usr/bin/env bash
#
# model-pin.sh — check or move the model this plugin is pinned to, and each subagent's effort.
#
# The evals check the guides against one model, so the plugin runs on it: both subagents name
# it in their frontmatter, the skill's preconditions require it of the session, and the evals
# run on it. Each subagent has its own effort: the builder's, which the evals also run at, and
# the analyzer's. This script keeps those places in step.
#
#   model-pin.sh --check                       exit 0 when every place agrees
#   model-pin.sh --set <model-id> [--effort <level>] [--analyzer-effort <level>]
#                                              move every place to another model
#   model-pin.sh --effort <level>              change the builder's effort alone
#   model-pin.sh --analyzer-effort <level>     change the analyzer's effort alone
#
# Output: H2BT_MODEL_PIN model=<id> effort=<level> analyzer_effort=<level> places=<n> ok, or
# one H2BT_MODEL_PIN_MISMATCH line per place that disagrees and a non-zero exit. The model and
# the builder's effort are read from the section-builder agent, the analyzer's effort from the
# blueprint-analyzer agent. The changelog and the evals' reports are history and are not
# touched.
#
set -euo pipefail

usage() {
	cat <<'EOF'
Usage:
  model-pin.sh --check
  model-pin.sh --set <model-id> [--effort <level>] [--analyzer-effort <level>]
  model-pin.sh --effort <level>
  model-pin.sh --analyzer-effort <level>

--check exits 0 when the subagents, the skill's precondition, the evals and the README all
name the same model, the builder's effort and the analyzer's effort. --set, --effort and
--analyzer-effort move them. Run the evals on a new model or effort before relying on it.
EOF
}

# A flag that takes a value must be followed by one.
need_value() { [[ $# -ge 2 ]] || { echo "$1 needs a value" >&2; exit 2; }; }

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# file|extended regex, with MODEL, EFFORT (the builder's) and ANALYZER (the analyzer's effort)
# standing for the pins. Each must match.
places=(
	'agents/blueprint-analyzer.md|^model: MODEL$'
	'agents/blueprint-analyzer.md|^effort: ANALYZER$'
	'agents/section-builder.md|^model: MODEL$'
	'agents/section-builder.md|^effort: EFFORT$'
	'skills/html-to-block-theme/SKILL.md|one model, `MODEL`,'
	'skills/html-to-block-theme/SKILL.md|/model MODEL`'
	'skills/html-to-block-theme/SKILL.md|builder runs at `EFFORT` effort'
	'evals/eval.config.json|"model": "MODEL"'
	'evals/eval.config.json|"effort": "EFFORT"'
	'README.md|runs on `MODEL`,'
	'README.md|builder at `EFFORT` effort and the analyzer at `ANALYZER`'
)

pinned() { # pinned <field> <agent>
	sed -n "s/^$1: //p" "$root/agents/$2.md" | head -n 1
}

check() {
	local model="$1" effort="$2" analyzer="$3" failed=0 place file pattern
	for place in "${places[@]}"; do
		file="${place%%|*}"
		pattern="${place#*|}"
		pattern="${pattern//MODEL/${model//./\\.}}"
		pattern="${pattern//EFFORT/$effort}"
		pattern="${pattern//ANALYZER/$analyzer}"
		if ! grep -Eq -- "$pattern" "$root/$file" 2>/dev/null; then
			echo "H2BT_MODEL_PIN_MISMATCH file=$file expected=\"${pattern}\""
			failed=1
		fi
	done
	if [[ "$failed" -ne 0 ]]; then
		return 1
	fi
	echo "H2BT_MODEL_PIN model=$model effort=$effort analyzer_effort=$analyzer places=${#places[@]} ok"
}

mode=""
new_model=""
new_effort=""
new_analyzer=""

set_mode() { # set_mode <check|set>: --check does not combine with a change
	if [[ -n "$mode" && "$mode" != "$1" ]]; then
		echo "--check does not combine with --set, --effort or --analyzer-effort" >&2
		exit 2
	fi
	mode="$1"
}

while [[ $# -gt 0 ]]; do
	case "$1" in
		--check) set_mode check; shift ;;
		--set) need_value "$@"; set_mode set; new_model="$2"; shift 2 ;;
		--effort) need_value "$@"; set_mode set; new_effort="$2"; shift 2 ;;
		--analyzer-effort) need_value "$@"; set_mode set; new_analyzer="$2"; shift 2 ;;
		-h|--help) usage; exit 0 ;;
		*) echo "Unknown argument: $1" >&2; usage >&2; exit 2 ;;
	esac
done

old_model="$(pinned model section-builder)"
old_effort="$(pinned effort section-builder)"
old_analyzer="$(pinned effort blueprint-analyzer)"
if [[ -z "$old_model" || "$old_model" == "inherit" || -z "$old_effort" || -z "$old_analyzer" ]]; then
	echo "No pinned model and effort in agents/section-builder.md, or no effort in agents/blueprint-analyzer.md." >&2
	exit 1
fi

case "$mode" in
	check)
		check "$old_model" "$old_effort" "$old_analyzer"
		;;
	set)
		new_model="${new_model:-$old_model}"
		new_effort="${new_effort:-$old_effort}"
		new_analyzer="${new_analyzer:-$old_analyzer}"
		if [[ ! "$new_model" =~ ^[A-Za-z0-9][A-Za-z0-9._-]*$ ]]; then
			echo "Not a model id: '$new_model'" >&2
			exit 2
		fi
		for level in "$new_effort" "$new_analyzer"; do
			if [[ ! "$level" =~ ^(low|medium|high|xhigh|max)$ ]]; then
				echo "Not an effort level: '$level'" >&2
				exit 2
			fi
		done
		for place in "${places[@]}"; do
			python3 - "$root/${place%%|*}" "${place#*|}" "$old_model" "$new_model" "$old_effort" "$new_effort" "$old_analyzer" "$new_analyzer" <<'PY'
import pathlib
import re
import sys

path, shape, old_model, new_model, old_effort, new_effort, old_analyzer, new_analyzer = sys.argv[1:9]
path = pathlib.Path( path )


def fill( values, escape ):
	# The place's own shape, as a pattern for the old pins or as text for the new ones.
	anchored = shape.startswith( '^' ) and shape.endswith( '$' )
	parts = re.split( r'(MODEL|EFFORT|ANALYZER)', shape.strip( '^$' ) )
	text = ''.join( ( re.escape( values.get( part, part ) ) if escape else values.get( part, part ) ) for part in parts )
	return ( '^' + text + '$', re.MULTILINE ) if anchored and escape else ( text, 0 )


pattern, flags = fill( { 'MODEL': old_model, 'EFFORT': old_effort, 'ANALYZER': old_analyzer }, True )
replacement, _ = fill( { 'MODEL': new_model, 'EFFORT': new_effort, 'ANALYZER': new_analyzer }, False )
path.write_text( re.sub( pattern, lambda _match: replacement, path.read_text(), flags=flags ) )
PY
		done
		check "$new_model" "$new_effort" "$new_analyzer"
		echo "Run the evals on $new_model at $new_effort before relying on it: evals/README.md."
		;;
	*)
		usage >&2
		exit 2
		;;
esac
