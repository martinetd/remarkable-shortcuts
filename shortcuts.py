#!/opt/bin/python3
# coding=utf-8

"""
stream events from input device, without depending on evdev
"""
from __future__ import print_function
import errno
import fcntl
import json
import os
import select
import struct
import sys
import time

from optparse import OptionParser


parser = OptionParser()
parser.add_option('-v', '--verbose', action='count', default=0)
parser.add_option('-e', '--event', action='store', type='string',
                  default='/dev/input/by-path/platform-30a40000.i2c-event',
                  help='path to event device or index')
parser.add_option('-p', '--pidfile', action='store', type='string',
                  help='pidfile, also kills old instance if existed')
parser.add_option('-D', '--daemonize', action='store_true',
                  help='close files and daemonizes. requires -c')
parser.add_option('-n', '--dry_run', action='store_true',
                  help='Do not actually inject events')
parser.add_option('-g', '--grab', action='store_true',
                  help='Grab input e.g. won\'t be sent to remarkable, useful for record')
parser.add_option('--record', action='store_true',
                  help='record input to stdout (debug)')
parser.add_option('--replay', action='store_true',
                  help='replay stdin (debug)')
parser.add_option('--replay-action', action='store', type='string',
                  help='replay given action (debug)')
parser.add_option('--no-sleep', action='store_true',
                  help='do not sleep during replay (tests)')

(options, args) = parser.parse_args()

if (options.pidfile and options.pidfile.endswith('.pid')
        and options.pidfile.startswith('/run/')
        and '..' not in options.pidfile):
    try:
        with open(options.pidfile, 'r') as pidfile:
            oldpid = pidfile.read().strip()
            with open('/proc/%s/cmdline' % oldpid, 'r') as cmdline:
                if __file__ in cmdline.read():
                    os.kill(int(oldpid), 15)
    except EnvironmentError as err:
        if err.errno == errno.ENOENT:
            pass
        else:
            raise
else:
    options.pidfile = None

if os.path.exists(options.event):
    infile_path = options.event
else:
    infile_path = f"/dev/input/event{options.event}"
outfile = sys.stdout
outproc = None

"""
FORMAT represents the format used by linux kernel input event struct. See
https://github.com/torvalds/linux/blob/v5.5-rc5/include/uapi/linux/input.h#L28
Stands for: long int, long int, unsigned short, unsigned short, unsigned int
"""
FORMAT = 'llHHi'

# input codes for multitouch
ABS_MT_SLOT = 47
ABS_MT_TOUCH_MAJOR = 48
ABS_MT_TOUCH_MINOR = 49
ABS_MT_ORIENTATION = 52
ABS_MT_POSITION_X = 53
ABS_MT_POSITION_Y = 54
ABS_MT_TRACKING_ID = 57
ABS_MT_PRESSURE = 58


EVENT_SIZE = struct.calcsize(FORMAT)
DEBUG = options.verbose
DRY_RUN = options.dry_run
NO_SLEEP = options.no_sleep
RECORD = options.record

# open file in binary mode
in_file = os.open(infile_path, os.O_RDWR)

def grab():
    retries = 10
    while retries > 0:
        try:
            # grab device, this is EVIOCGRAB
            fcntl.ioctl(in_file, 0x40044590, 1)
            break
        except IOError:
            # device busy? XXX kill old and try again?
            # continue for now
            if retries <= 1:
                print("Could not grab, aborting", file=sys.stderr)
                sys.exit(1)
        retries -= 1
        time.sleep(0.2)

def to_sec(sec, usec):
    return sec + usec / 1000000

def frange(start, stop, step):
    """
    inclusive range() for float
    """
    while start <= stop:
        yield start
        start += step

def gen_finger(touch, index):
    if touch.get('type') != 'line':
        raise Exception(f"bad type {touch.get('type', 'unset')}")
    (sx, sy) = touch['start']
    (ex, ey) = touch['end']
    duration = touch['duration']
    interval = touch.get('interval', 0.01)
    start = touch.get('down_time', 0)
    pressure = touch.get('pressure', 70)
    touch_id = touch.get('id', index)
    x = y = -1
    for t in frange(start, start + duration, interval):
        ev = {}
        if t == start:
            ev['id'] = touch_id
            ev['pressure'] = pressure
        nx = int(sx + (ex - sx) * t / duration)
        if x != nx:
            x = nx
            ev['x'] = x
        ny = int(sy + (ey - sy) * t / duration)
        if y != ny:
            y = ny
            ev['y'] = y
        # generate sync even if ev empty to keep touch alive
        yield [t, ev]
    yield [start + duration, {'id': -1}]


def gen_event(descr):
    """
    Generate event for replay.
    descr must be an array of dicts with:
     - type, one string of 'line'
     - down_time, start ts, optional default to 0 or end of previous touch
     - pressure, optional default to 70
     - id, default to 1 or previous touch + 1
     - (XXX add a way to speciify orientation/touch_minor/major if useful)
    for 'line:
     - start: (x,y) tuple
     - end: (x,y) tuple
     - duration: time to go from start to end
     - interval: time between each points, optonal default to 0.02
    Current version only support sequential items in array e.g. on multitouch
    """
    fingers = [gen_finger(touch, index) for index, touch in enumerate(descr)]
    fingers_next = [next(finger) for finger in fingers]
    active = {}
    while fingers:
        ev_time = min(fingers_next, key=lambda event: event[0])[0]
        ev = {}
        i = 0
        while i < len(fingers):
            if fingers_next[i][0] != ev_time:
                i += 1
                continue
            if fingers[i] not in active:
                j = 0
                while j in active.values():
                    j += 1
                active[fingers[i]] = j
            ev[active[fingers[i]]] = fingers_next[i][1]
            try:
                fingers_next[i] = next(fingers[i])
            except StopIteration:
                del active[fingers[i]]
                fingers.pop(i)
                fingers_next.pop(i)
                continue
            i += 1
        if ev:
            yield ['UPDATE', ev_time, ev]



def replay(source):
    """
    Replay events from source (one json per line or list of 'records')
    Record is a triplet:
     - record type
     - timestamp (fractional sec)
     - dict with infos depending on type
    Type is 'UPDATE' or 'RELEASE'
    Update dict:
     - slot_id: {id/x/y/pressure/orientation/touch_minor/touch_major}
    Release dict:
     - slot_id: {}
    """

    def wev(sec, usec, t, c, v):
        if DEBUG == 3:
            print(f"{sec}.{usec:06}: Replay type {t} code {c}, value {v}",
                  file=sys.stderr)
        if not DRY_RUN:
            os.write(in_file, struct.pack(FORMAT, sec, usec, t, c, v))

    def finger(sec, usec, diff):
        if 'id' in diff:
            wev(sec, usec, 3, ABS_MT_TRACKING_ID, diff['id'])
        if 'x' in diff:
            wev(sec, usec, 3, ABS_MT_POSITION_X, diff['x'])
        if 'y' in diff:
            wev(sec, usec, 3, ABS_MT_POSITION_Y, diff['y'])
        if 'pressure' in diff:
            wev(sec, usec, 3, ABS_MT_PRESSURE, diff['pressure'])
        if 'orientation' in diff:
            wev(sec, usec, 3, ABS_MT_ORIENTATION, diff['orientation'])
        if 'touch_minor' in diff:
            wev(sec, usec, 3, ABS_MT_TOUCH_MINOR, diff['touch_minor'])
        if 'touch_major' in diff:
            wev(sec, usec, 3, ABS_MT_TOUCH_MAJOR, diff['touch_major'])

    tstart = time.time()
    tfirst = -1
    cur_slot = 0

    for record in source:
        if isinstance(record, str):
            record = json.loads(record)
        (evtype, sec, detail) = record
        if tfirst == -1:
            tfirst = sec
        if DEBUG == 2:
            print(f"Replay {record}", file=sys.stderr)

        delay = sec - tfirst + tstart - time.time()
        if delay > 0 and not NO_SLEEP:
            time.sleep(delay)

        tv_sec = int(sec)
        tv_usec = int((sec - tv_sec) * 1000000)
        last_slot = cur_slot
        if evtype == 'RELEASE':
            if last_slot in detail:
                wev(tv_sec, tv_usec, 3, ABS_MT_TRACKING_ID, -1)
            for slot in detail.keys():
                if slot == last_slot:
                    continue
                wev(tv_sec, tv_usec, 3, ABS_MT_SLOT, int(slot))
                cur_slot = slot
                wev(tv_sec, tv_usec, 3, ABS_MT_TRACKING_ID, -1)
            wev(tv_sec, tv_usec, 0, 0, 0)
        elif evtype == 'UPDATE':
            if last_slot in detail:
                finger(tv_sec, tv_usec, detail[last_slot])
            for slot in detail.keys():
                if slot == last_slot:
                    continue
                wev(tv_sec, tv_usec, 3, ABS_MT_SLOT, int(slot))
                cur_slot = slot
                finger(tv_sec, tv_usec, detail[slot])
            wev(tv_sec, tv_usec, 0, 0, 0)
        else:
            print(f'invalid event type {evtype}', file=sys.stderr)
            return


if options.grab:
    grab()

if options.daemonize:
    if not options.command:
        print("Cannot daemonize if no command!", file=sys.stderr)
        sys.exit(1)
    devnull = open('/dev/null', 'w+')
    #sys.stdout = devnull
    #sys.stderr = devnull
    sys.stdin.close()
    if os.fork() != 0:
        sys.exit(0)
    if os.fork() != 0:
        sys.exit(0)

if options.pidfile:
    with open(options.pidfile, 'w') as pidfile:
        pidfile.write("%d\n" % os.getpid())


def point(finger, sec):
    point = dict(sec=sec)
    if finger.x != -1:
        point['x'] = finger.x
    if finger.y != -1:
        point['y'] = finger.y
    if finger.pressure != -1:
        point['pressure'] = finger.pressure
    if finger.orientation != -1:
        point['orientation'] = finger.orientation
    if finger.touch_minor != -1:
        point['touch_minor'] = finger.touch_minor
    if finger.touch_major != -1:
        point['touch_major'] = finger.touch_major
    return point


class Finger():
    x = -1
    y = -1
    pressure = -1
    orientation = -1
    touch_minor = -1
    touch_major = -1
    # valid after release
    up_sec = -1
    down_duration = -1

    def __init__(self, tracking_id, sec, usec):
        self.id = tracking_id
        self.down_sec = to_sec(sec, usec)
        self.trace = []

    def update(self, code, value):
        if code == ABS_MT_POSITION_X:
            self.x = value
        elif code == ABS_MT_POSITION_Y:
            self.y = value
        elif code == ABS_MT_PRESSURE:
            self.pressure = value
        elif code == ABS_MT_ORIENTATION:
            self.orientation = value
        elif code == ABS_MT_TOUCH_MINOR:
            self.touch_minor = value
        elif code == ABS_MT_TOUCH_MAJOR:
            self.touch_major = value
        else:
            return False
        return True

    def commit(self, sec):
        self.trace.append(point(self, sec))

    # return touch duration in msec
    def release(self, sec):
        self.up_sec = sec
        self.down_duration = (self.up_sec - self.down_sec)


def detect_double_tap(tracking, feature):
    if not tracking.prev:
        return None
    prev = tracking.prev
    cur = tracking.cur

    # total time with prev and current touch < 1s
    if cur.up_sec - prev.down_sec > 1:
        return None
    # prev and current touch < 0.5s
    if prev.down_duration > 0.5 or cur.down_duration > 0.5:
        return None
    # prev and current touch area is small enough
    # for simplicity we only consider the last position
    if abs(prev.x - cur.x) > 50 or abs(prev.y - cur.y) > 50:
        return None

    # check for min/max edges... Only check last position again.
    if cur.x < feature.get('x_min', 0):
        return None
    if cur.y < feature.get('y_min', 0):
        return None
    if cur.x > feature.get('x_max', 1500):
        return None
    if cur.y > feature.get('y_max', 1900):
        return None

    # okay!
    return gen_event(feature['action'])

DETECT = {
    'double_tap': detect_double_tap,
}

class Tracking():
    prev = None
    cur = None

    def update(self, finger):
        self.cur = finger
        i = 0
        while i < len(FEATURES):
            feature = FEATURES[i]
            detect = DETECT.get(feature['type'])
            if not detect:
                print(f"Invalid feature type {feature['type']}, skipping",
                      file=sys.stderr)
                FEATURES.pop(i)
                continue
            action = detect(self, feature)
            if action:
                if DEBUG >= 1:
                    print(f"Detected {feature.get('name')}")
                return action
            i += 1

        self.prev = finger
        return None


class State():
    fingers = {}
    slot_id = 0
    finger = None
    last_side = None
    actions = []
    # batch per sync event
    updated = {}
    released = {}

    def update(self, tv_sec, tv_usec, code, value):
        if code == ABS_MT_SLOT:
            self.slot_id = value
            self.finger = self.fingers.get(value)
            if self.finger:
                self.updated[value] = self.finger
            return
        if code == ABS_MT_TRACKING_ID and value >= 0:
            self.finger = Finger(value, tv_sec, tv_usec)
            self.fingers[self.slot_id] = self.finger
            self.updated[self.slot_id] = self.finger
            return

        if code == 0:
            sec = to_sec(tv_sec, tv_usec)
            if RECORD:
                if self.released:
                    print(json.dumps(["RELEASE",
                                      sec,
                                      {slot_id: {} for slot_id in self.released.keys()}]))
                recorded = {}
                for slot, finger in self.updated.items():
                    diff = {}
                    prev = finger.trace[-1] if finger.trace else {}
                    if not prev:
                        diff['id'] = finger.id
                    if finger.x != prev.get('x', -1):
                        diff['x'] = finger.x
                    if finger.y != prev.get('y', -1):
                        diff['y'] = finger.y
                    if finger.pressure != prev.get('pressure', -1):
                        diff['pressure'] = finger.pressure
                    if finger.orientation != prev.get('orientation', -1):
                        diff['orientation'] = finger.orientation
                    if finger.touch_minor != prev.get('touch_minor', -1):
                        diff['touch_minor'] = finger.touch_minor
                    if finger.touch_major != prev.get('touch_major', -1):
                        diff['touch_major'] = finger.touch_major
                    recorded[slot]=diff
                if recorded:
                    print(json.dumps(["UPDATE", sec, recorded]))
            for (slot_id, finger) in self.released.items():
                finger.release(sec)
                if DEBUG == 2:
                    print(f"{tv_sec}.{tv_usec:06}: {finger.id} up {finger.x},{finger.y} after {finger.down_duration}. Pressure {finger.pressure} Orientation {finger.orientation}",
                          file=sys.stderr)
                # trigger events on release for now
                if not RECORD:
                    action = tracking.update(finger)
                    if action:
                        state.actions.append(action)
            for finger in self.updated.values():
                finger.commit(sec)
                if DEBUG == 2:
                    print(f"{tv_sec}.{tv_usec:06}: {finger.id} pressed {finger.x},{finger.y}. Pressure {finger.pressure} Orientation {finger.orientation}",
                          file=sys.stderr)
            self.released = {}
            self.updated = {}
            return

        if self.finger is None:
            print(f"{tv_sec}.{tv_usec:06}: Unhandled touch event without id code {code}, value {value}",
                  file=sys.stderr)
            return

        if self.finger.update(code, value):
            self.updated[self.slot_id] = self.finger
        elif code == ABS_MT_TRACKING_ID:
            self.released[self.slot_id] = self.finger
            self.finger = None
            del self.fingers[self.slot_id]
        else:
            if DEBUG == 1:
                print(f"{tv_sec}.{tv_usec:06}: Unhandled touch event code {code}, value {value}",
                      file=sys.stderr)


ACTIONS = {
    'swipe_to_right':  [
        dict(type='line',
             start=(300, 700),
             end=(1000, 700),
             duration=0.5),
    ],
    'swipe_to_left': [
        dict(type='line',
             start=(1000, 700),
             end=(300, 700),
             duration=0.5),
    ],
    'swipe_down_from_top': [
        dict(type='line',
             start=(700, 1819),
             end=(700, 1200),
             duration=0.5),
    ],
    # for test
    'double_swipe_down_from_top': [
        dict(type='line',
             start=(700, 1819),
             end=(700, 1200),
             duration=0.5),
        dict(type='line',
             start=(750, 1819),
             end=(750, 1200),
             duration=0.5),
    ],
    'double_tap_left': [
        dict(type='line',
             start=(300, 300),
             end=(300, 300),
             duration=0.2),
        dict(type='line',
             down_time=0.4,
             start=(300, 300),
             end=(300, 300),
             duration=0.2),
    ],
    'double_tap_right': [
        dict(type='line',
             start=(1000, 300),
             end=(1000, 300),
             duration=0.2),
        dict(type='line',
             down_time=0.4,
             start=(1000, 300),
             end=(1000, 300),
             duration=0.2),
    ],
    'double_tap_top': [
        dict(type='line',
             start=(600, 1300),
             end=(600, 1300),
             duration=0.2),
        dict(type='line',
             down_time=0.4,
             start=(600, 1300),
             end=(600, 1300),
             duration=0.2),
    ],
}

FEATURES = [
    {
        'name': 'left double-tap',
        'type': 'double_tap',
        'x_max': 500,
        'y_max': 1000,
        'action': ACTIONS['swipe_to_right'],
    },
    {
        'name': 'right double-tap',
        'type': 'double_tap',
        'x_min': 700,
        'y_max': 1000,
        'action': ACTIONS['swipe_to_left'],
    },
    {
        'name': 'top double-tap',
        'type': 'double_tap',
        'y_min': 1200,
        'action': ACTIONS['swipe_down_from_top'],
    },
]

if options.replay:
    replay(sys.stdin)
    sys.exit(0)

if options.replay_action:
    if options.replay_action not in ACTIONS:
        print(f"action {options.replay_action} not found",
              file=sys.stderr)
        sys.exit(1)
    replay(gen_event(ACTIONS[options.replay_action]))
    sys.exit(0)

tracking = Tracking()
state = State()

def parse(tv_sec, tv_usec, evtype, code, value):
    if DEBUG == 3:
        print(f"{tv_sec}.{tv_usec:06}: Event type {evtype} code {code}, value {value}",
              file=sys.stderr)

    if evtype == 0 and code == 0 and value == 0:
        pass
    elif evtype != 3:
        print(f"{tv_sec}.{tv_usec:06}: Unhandled key type {evtype} code {code}, value {value}",
              file=sys.stderr)
        return

    state.update(tv_sec, tv_usec, code, value)


def handle_input():
    timeout = None
    # NO_SLEEP actually waits a bit for pipe input
    if state.actions or NO_SLEEP:
        timeout = 0.05
    (ready, _, errors) = select.select([in_file], [], [in_file], timeout)
    if errors:
        print("input file in error state!", file=sys.stderr)
        return False
    if in_file in ready:
        event = os.read(in_file, EVENT_SIZE)
        if len(event) != EVENT_SIZE:
            print(f"input file had something to read, but no event or bad length {len(event)}",
                  file=sys.stderr)
            return False
        parse(*struct.unpack(FORMAT, event))
    elif state.actions:
        replay(state.actions.pop(0))
    elif NO_SLEEP:
        return False
    return True


# wait for input to start
if NO_SLEEP:
    select.select([in_file], [], [])

while handle_input():
    pass

while state.actions:
    replay(state.actions.pop(0))

# unreachable...
os.close(in_file)
