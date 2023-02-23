#!/bin/sh

error() {
	printf "%s\n" "$@"
	FAILED=$((FAILED+1))
}

run() {
	local file="$1"
	shift

	python3 ./shortcuts.py --no-sleep -e /dev/stdout --replay < "$file" \
		| python3 ./shortcuts.py --no-sleep -e /dev/stdin -n "$@"
}

FAILED=0

run tests/monkey-touch.record || error "monkey-touch crashed"
run tests/double-tap-left.record -v | grep -q left || error "left didn't act on left"
run tests/double-tap-right.record -v | grep -q right || error "right didn't act on right"
run tests/double-tap-top.record -v | grep -q top || error "top didn't act on top"

[ "$FAILED" = 0 ]
