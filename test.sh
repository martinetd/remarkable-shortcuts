#!/bin/bash

error() {
	printf "%s\n" "$@"
	FAILED=$((FAILED+1))
}

run() {
	local -a first=()
	while [[ "${1:-"--"}" !=  "--" ]]; do
		first+=( "$1" )
		shift
	done
	shift
	python3 ./shortcuts.py --no-sleep -e /dev/stdout "${first[@]}" \
		| python3 ./shortcuts.py --no-sleep -e /dev/stdin "$@"
}

run_replay() {
	local file="$1"
	shift

	run --replay -- "$@" < "$file"
}

run_generated() {
	local name="$1"
	shift
	run --replay-action "$name" -- "$@"
}

rgrep() {
	local key="$1"
	shift
	"$@" -vn 2>&1 >/dev/null | grep -q "$key"
}

FAILED=0

run_replay tests/monkey-touch.record \
	|| error "monkey-touch crashed"
rgrep left run_replay tests/double-tap-left.record \
	|| error "left didn't act on left"
rgrep right run_replay tests/double-tap-right.record \
	|| error "right didn't act on right"
rgrep top run_replay tests/double-tap-top.record \
	|| error "top didn't act on top"
rgrep top run_replay tests/double-tap-slow-top-no-event.record \
	&& error "shouldn't trigger top on slow taps"

[[ "$(run_replay tests/double-tap-left.record -o /dev/stdout | wc -c)" = 2520 ]] \
	|| error "left replay does not have correct length"

rgrep left run_generated double_tap_left \
	|| error "left didn't act on synthetic left"
rgrep right run_generated double_tap_right \
	|| error "right didn't act on synthetic right"
rgrep top run_generated double_tap_top \
	|| error "top didn't act on synthetic top"

run_generated double_tap_left --record \
		| rgrep left run --replay --\
	|| error "replay of recording of synthetic left didn't recognize left"

[ "$FAILED" = 0 ]
