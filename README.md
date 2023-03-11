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

- [x] Improve recording (raw events -> more summarized tracing)
  - [x] Check/fix generation of multitouch
  - [ ] Improve generation for more complex curves if required
- [x] make actions configurable (currently hard-coded in .py file, but it's a pure dict = as good as done if someone ever needs to change it)
- [ ] more feature detection
  - [x] detect double-tap not by checking twice for quadrant, but by checking proximity to first click then we can check directly in config
  - [ ] gestures: first approximation checks just down and up coordinates? won't allow e.g. circles but that wouldn't be easy to do anyway.
  - [ ] could also use pressure e.g. only trigger heavy tap (easy)
  - [ ] eventually: check how to use major/minor and orientation, apparently large surface of contact? maybe for later...
- [ ] add an enable/disable shortcut... When using keyboard close-by touches are incorrectly considered double-taps.
- [ ] could imagine doodling with finger instead of pen by forwarding events to event1 ? (second alt mode, easier than taking pen)
