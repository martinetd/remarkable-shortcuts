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
		| python3 ./shortcuts.py --no-sleep -e /dev/stdin -n "$@"
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

FAILED=0

run_replay tests/monkey-touch.record \
	|| error "monkey-touch crashed"
run_replay tests/double-tap-left.record -v | grep -q left \
	|| error "left didn't act on left"
run_replay tests/double-tap-right.record -v | grep -q right \
	|| error "right didn't act on right"
run_replay tests/double-tap-top.record -v | grep -q top \
	|| error "top didn't act on top"
run_replay tests/double-tap-slow-top-no-event.record -v | grep -q top \
	&& error "shouldn't trigger top on slow taps"

run_generated double_tap_left -v | grep -q left \
	|| error "left didn't act on synthetic left"
run_generated double_tap_right -v | grep -q right \
	|| error "right didn't act on synthetic right"
run_generated double_tap_top -v | grep -q top \
	|| error "top didn't act on synthetic top"

[ "$FAILED" = 0 ]
