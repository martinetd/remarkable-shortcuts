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
 * Done, make something to generate perfect trajectories next
 * Pretty sure replay isn't correct for multislot
- make actions configurable?
 * keep action separate is a huge plus, having it smaller (see previous point) would help but not hard requirement
 * feature detection:
   - detect double-tap not by checking twice for quadrant, but by checking proximity to first click then we can check directly in config
     (bonus: more than double-tap? that's more work, maybe in v3)
   - gestures: first approximation checks just down and up coordinates? won't allow e.g. circles but that wouldn't be easy to do anyway.
   - could also use pressure e.g. only trigger heavy tap? would be easy.
   - eventually: check how to use major/minor and orientation, apparently large surface of contact? maybe for v3.
- add an enable/disable shortcut... this is bad for virtual keyboard
- could imagine toddling with finger instead of pen by sending in events on event1 ?
