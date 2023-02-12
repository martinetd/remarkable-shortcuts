# remarkable shortcuts mapper

Read touch events and act on it.

Current v0 watches for double taps in bottom half, left/right and emulates a swipe left or right


## Installation

This version requires python3 installed (toltec), so install/enable that.

Then just copy shortcuts.py wherever, optionally shortcuts.service in /etc/systemd/system, enable service and forget it


## TODO

- record/replay points instead of raw events (makes it more compact and easier to handle even if less precise, intermediate states between SYN (0) do not matter)
- make actions configurable?
- could imagine toddling with finger instead of pen by sending in events on event1 ?
