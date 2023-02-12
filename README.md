# remarkable shortcuts mapper

Read touch events and act on it.

Current v0 watches for double taps in bottom half, left/right and emulates a swipe left or right,
and top to emulate swipe down.

## Installation

Installation happens through ssh.

This version requires python3 installed (e.g. [toltec](https://toltec-dev.org/)), so install/enable that if not done yet.

Then just copy shortcuts.py to /home/root/shortcuts.py, shortcuts.service in /etc/systemd/system, then turn it on and forget it:
```
systemctl daemon-reload && systemctl enable --now shortcuts
```


## TODO

- record/replay points instead of raw events (makes it more compact and easier to handle even if less precise, intermediate states between SYN (0) do not matter)
- make actions configurable? emulation result is easy, but feature detection might be hard to configure...
- could imagine toddling with finger instead of pen by sending in events on event1 ?
