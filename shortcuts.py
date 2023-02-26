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

# record + sed -e '1i[' -e '$a]' -e 's/$/,/' -e 's/^/    /'
# long lines slow down ALE too much...
EMUL_PREV = [
    ["UPDATE", 1677409911.819618, {"0": {"id": 4163, "x": 376, "y": 681, "pressure": 65}}],
    ["UPDATE", 1677409911.837785, {"0": {"x": 381, "pressure": 66, "orientation": 2, "touch_minor": 17}}],
    ["UPDATE", 1677409911.849842, {"0": {"x": 387, "pressure": 68}}],
    ["UPDATE", 1677409911.861585, {"0": {"x": 394, "y": 682, "orientation": 1, "touch_minor": 8}}],
    ["UPDATE", 1677409911.873545, {"0": {"x": 405, "y": 683, "pressure": 67, "orientation": 2, "touch_minor": 17}}],
    ["UPDATE", 1677409911.885474, {"0": {"x": 418, "pressure": 68}}],
    ["UPDATE", 1677409911.897283, {"0": {"x": 434, "y": 684}}],
    ["UPDATE", 1677409911.909113, {"0": {"x": 451}}],
    ["UPDATE", 1677409911.920781, {"0": {"x": 472}}],
    ["UPDATE", 1677409911.932689, {"0": {"x": 494}}],
    ["UPDATE", 1677409911.944771, {"0": {"x": 518, "pressure": 65}}],
    ["UPDATE", 1677409911.956673, {"0": {"x": 543, "pressure": 66, "orientation": 1, "touch_minor": 8}}],
    ["UPDATE", 1677409911.968514, {"0": {"x": 570, "y": 683, "pressure": 63, "orientation": 2, "touch_minor": 17}}],
    ["UPDATE", 1677409911.980156, {"0": {"x": 597, "pressure": 66, "orientation": 1, "touch_minor": 8}}],
    ["UPDATE", 1677409911.992123, {"0": {"x": 623, "pressure": 63, "orientation": 2, "touch_minor": 17}}],
    ["UPDATE", 1677409912.004157, {"0": {"x": 650, "pressure": 66, "orientation": 1, "touch_minor": 8}}],
    ["UPDATE", 1677409912.015997, {"0": {"x": 676, "pressure": 65, "orientation": 2, "touch_minor": 17}}],
    ["UPDATE", 1677409912.027751, {"0": {"x": 701, "pressure": 68, "orientation": 1, "touch_minor": 8}}],
    ["UPDATE", 1677409912.039872, {"0": {"x": 724, "y": 685, "orientation": 2, "touch_minor": 17}}],
    ["UPDATE", 1677409912.051323, {"0": {"x": 745, "y": 686}}],
    ["UPDATE", 1677409912.063419, {"0": {"x": 766, "y": 687, "pressure": 69, "orientation": 1, "touch_minor": 8}}],
    ["UPDATE", 1677409912.075354, {"0": {"x": 785, "y": 688, "orientation": 3, "touch_minor": 17, "touch_major": 17}}],
    ["UPDATE", 1677409912.087194, {"0": {"x": 803, "y": 689, "pressure": 67, "orientation": 2, "touch_major": 8}}],
    ["UPDATE", 1677409912.098912, {"0": {"x": 819, "pressure": 69, "orientation": 1, "touch_minor": 8}}],
    ["UPDATE", 1677409912.110909, {"0": {"x": 836, "pressure": 68}}],
    ["UPDATE", 1677409912.122926, {"0": {"x": 852, "pressure": 65, "orientation": 2, "touch_minor": 17}}],
    ["UPDATE", 1677409912.13467, {"0": {"x": 866, "pressure": 67}}],
    ["UPDATE", 1677409912.14642, {"0": {"x": 881, "orientation": 1, "touch_minor": 8}}],
    ["UPDATE", 1677409912.158387, {"0": {"x": 896, "y": 688, "pressure": 66, "orientation": 2, "touch_minor": 17}}],
    ["UPDATE", 1677409912.170146, {"0": {"x": 909, "y": 687, "pressure": 63}}],
    ["UPDATE", 1677409912.182156, {"0": {"x": 920, "y": 686}}],
    ["UPDATE", 1677409912.193937, {"0": {"x": 929, "y": 685, "pressure": 62}}],
    ["UPDATE", 1677409912.205868, {"0": {"x": 937, "y": 684, "pressure": 65}}],
    ["UPDATE", 1677409912.217682, {"0": {"x": 944}}],
    ["UPDATE", 1677409912.229519, {"0": {"x": 951, "orientation": 1, "touch_minor": 8}}],
    ["UPDATE", 1677409912.241419, {"0": {"x": 960, "pressure": 64}}],
    ["UPDATE", 1677409912.253326, {"0": {"x": 969, "pressure": 60, "orientation": 2, "touch_minor": 17}}],
    ["UPDATE", 1677409912.264746, {"0": {"x": 978, "pressure": 47}}],
    ["RELEASE", 1677409912.300545, {"0": {}}],
]

EMUL_NEXT = [
    ["UPDATE", 1677409903.224997, {"0": {"id": 4162, "x": 983, "y": 711, "pressure": 70}}],
    ["UPDATE", 1677409903.242273, {"0": {"x": 979}}],
    ["UPDATE", 1677409903.251933, {"0": {"x": 975, "pressure": 69, "orientation": 3, "touch_minor": 17}}],
    ["UPDATE", 1677409903.263995, {"0": {"x": 970, "orientation": 4}}],
    ["UPDATE", 1677409903.276106, {"0": {"x": 962, "pressure": 71, "orientation": 2, "touch_minor": 8}}],
    ["UPDATE", 1677409903.28781, {"0": {"x": 952, "y": 712}}],
    ["UPDATE", 1677409903.299889, {"0": {"x": 940, "pressure": 69, "orientation": 4, "touch_minor": 17}}],
    ["UPDATE", 1677409903.311293, {"0": {"x": 925, "y": 714, "pressure": 72, "orientation": 2, "touch_minor": 8}}],
    ["UPDATE", 1677409903.323343, {"0": {"x": 906, "y": 715, "pressure": 69, "touch_minor": 17, "touch_major": 8}}],
    ["UPDATE", 1677409903.335187, {"0": {"x": 885, "y": 716, "orientation": 1, "touch_minor": 8}}],
    ["UPDATE", 1677409903.347141, {"0": {"x": 861, "y": 717, "pressure": 65, "orientation": 2, "touch_minor": 17}}],
    ["UPDATE", 1677409903.359011, {"0": {"x": 834, "y": 718, "pressure": 69}}],
    ["UPDATE", 1677409903.370587, {"0": {"x": 806, "y": 719, "pressure": 72, "orientation": 1, "touch_minor": 8}}],
    ["UPDATE", 1677409903.382607, {"0": {"x": 773, "pressure": 71, "orientation": 2, "touch_minor": 17}}],
    ["UPDATE", 1677409903.394664, {"0": {"x": 739, "y": 720, "pressure": 69}}],
    ["UPDATE", 1677409903.406199, {"0": {"x": 706, "y": 721, "pressure": 73, "orientation": 1, "touch_minor": 8}}],
    ["UPDATE", 1677409903.418435, {"0": {"x": 679, "pressure": 71, "orientation": 2, "touch_minor": 17}}],
    ["UPDATE", 1677409903.429947, {"0": {"x": 646, "y": 722}}],
    ["UPDATE", 1677409903.442041, {"0": {"x": 618, "y": 723, "pressure": 73}}],
    ["UPDATE", 1677409903.453851, {"0": {"x": 586, "pressure": 71}}],
    ["UPDATE", 1677409903.465755, {"0": {"x": 559, "pressure": 74, "orientation": 1, "touch_minor": 8}}],
    ["UPDATE", 1677409903.477416, {"0": {"x": 531, "pressure": 72, "orientation": 2, "touch_minor": 17}}],
    ["UPDATE", 1677409903.48958, {"0": {"x": 505, "touch_minor": 8, "touch_major": 17}}],
    ["UPDATE", 1677409903.50141, {"0": {"x": 481, "pressure": 73, "touch_minor": 17, "touch_major": 8}}],
    ["UPDATE", 1677409903.513212, {"0": {"x": 459, "y": 722, "pressure": 72, "orientation": 3, "touch_major": 17}}],
    ["UPDATE", 1677409903.525244, {"0": {"x": 440, "y": 721, "pressure": 74}}],
    ["UPDATE", 1677409903.536996, {"0": {"x": 422, "y": 720, "orientation": 2, "touch_minor": 8}}],
    ["UPDATE", 1677409903.548895, {"0": {"x": 406, "pressure": 75, "orientation": 3, "touch_minor": 17}}],
    ["UPDATE", 1677409903.560983, {"0": {"x": 393, "y": 719, "pressure": 73}}],
    ["UPDATE", 1677409903.572516, {"0": {"x": 382, "pressure": 72}}],
    ["UPDATE", 1677409903.584474, {"0": {"x": 372}}],
    ["UPDATE", 1677409903.596273, {"0": {"x": 364, "y": 718, "pressure": 73}}],
    ["UPDATE", 1677409903.608237, {"0": {"x": 357, "pressure": 71}}],
    ["UPDATE", 1677409903.62013, {"0": {"x": 352, "pressure": 70}}],
    ["UPDATE", 1677409903.631989, {"0": {"x": 347, "pressure": 68, "orientation": 2, "touch_minor": 8}}],
    ["UPDATE", 1677409903.643834, {"0": {"x": 342, "pressure": 61, "orientation": 1, "touch_major": 8}}],
    ["UPDATE", 1677409903.655656, {"0": {"x": 338, "pressure": 34}}],
    ["RELEASE", 1677409903.691095, {"0": {}}],
]

EMUL_HOME = [
    ["UPDATE", 1677409920.129119, {"0": {"id": 4164, "x": 723, "y": 1819, "pressure": 59, "touch_minor": 8, "touch_major": 17}}],
    ["UPDATE", 1677409920.183101, {"0": {"y": 1815, "pressure": 75, "orientation": 1, "touch_major": 8}}],
    ["UPDATE", 1677409920.195142, {"0": {"y": 1811, "pressure": 78}}],
    ["UPDATE", 1677409920.20685, {"0": {"y": 1804, "pressure": 81, "orientation": 2, "touch_major": 17}}],
    ["UPDATE", 1677409920.218978, {"0": {"y": 1798, "pressure": 85}}],
    ["UPDATE", 1677409920.230574, {"0": {"y": 1789, "pressure": 86}}],
    ["UPDATE", 1677409920.242537, {"0": {"y": 1778, "pressure": 82, "orientation": 3, "touch_minor": 17}}],
    ["UPDATE", 1677409920.254558, {"0": {"y": 1766, "pressure": 86, "orientation": 2, "touch_minor": 8}}],
    ["UPDATE", 1677409920.2663, {"0": {"x": 722, "y": 1750, "pressure": 83, "orientation": 3, "touch_minor": 17}}],
    ["UPDATE", 1677409920.278071, {"0": {"y": 1733, "pressure": 82, "orientation": 2, "touch_minor": 8}}],
    ["UPDATE", 1677409920.29015, {"0": {"y": 1713, "pressure": 81, "touch_minor": 17, "touch_major": 8}}],
    ["UPDATE", 1677409920.302009, {"0": {"y": 1691, "pressure": 84, "touch_minor": 8, "touch_major": 17}}],
    ["UPDATE", 1677409920.313853, {"0": {"y": 1667, "pressure": 79, "orientation": 1, "touch_major": 8}}],
    ["UPDATE", 1677409920.325652, {"0": {"y": 1641, "pressure": 82, "orientation": 2, "touch_major": 17}}],
    ["UPDATE", 1677409920.337564, {"0": {"y": 1613, "pressure": 79}}],
    ["UPDATE", 1677409920.349259, {"0": {"y": 1582, "pressure": 78, "touch_minor": 17, "touch_major": 8}}],
    ["UPDATE", 1677409920.361308, {"0": {"y": 1554, "pressure": 81, "touch_minor": 8, "touch_major": 17}}],
    ["UPDATE", 1677409920.373417, {"0": {"x": 721, "y": 1520, "pressure": 74, "touch_minor": 17, "touch_major": 8}}],
    ["UPDATE", 1677409920.384894, {"0": {"x": 719, "y": 1493, "pressure": 77, "orientation": 3, "touch_major": 17}}],
    ["UPDATE", 1677409920.396938, {"0": {"x": 716, "y": 1460, "pressure": 75}}],
    ["UPDATE", 1677409920.408622, {"0": {"x": 714, "y": 1433, "pressure": 73, "orientation": 2, "touch_major": 8}}],
    ["UPDATE", 1677409920.42083, {"0": {"x": 711, "y": 1406, "pressure": 71, "orientation": 4, "touch_major": 17}}],
    ["UPDATE", 1677409920.432711, {"0": {"x": 708, "y": 1382, "pressure": 75}}],
    ["UPDATE", 1677409920.444453, {"0": {"x": 706, "y": 1359, "pressure": 72, "orientation": 2, "touch_major": 8}}],
    ["UPDATE", 1677409920.456292, {"0": {"x": 705, "y": 1338, "pressure": 76, "orientation": 3, "touch_major": 17}}],
    ["UPDATE", 1677409920.468007, {"0": {"x": 703, "y": 1320, "pressure": 78, "orientation": 4}}],
    ["UPDATE", 1677409920.480112, {"0": {"x": 702, "y": 1304, "orientation": 3}}],
    ["UPDATE", 1677409920.491885, {"0": {"x": 701, "y": 1290, "pressure": 76, "orientation": 2, "touch_major": 8}}],
    ["UPDATE", 1677409920.503725, {"0": {"y": 1277, "pressure": 75}}],
    ["UPDATE", 1677409920.515752, {"0": {"x": 700, "y": 1264, "pressure": 77, "orientation": 3, "touch_major": 17}}],
    ["UPDATE", 1677409920.527558, {"0": {"y": 1253, "pressure": 80, "orientation": 4}}],
    ["UPDATE", 1677409920.539394, {"0": {"y": 1244, "pressure": 78}}],
    ["UPDATE", 1677409920.551226, {"0": {"x": 699, "y": 1235, "pressure": 76, "orientation": 3}}],
    ["UPDATE", 1677409920.562986, {"0": {"x": 697, "y": 1225, "pressure": 72, "orientation": 2, "touch_major": 8}}],
    ["UPDATE", 1677409920.574881, {"0": {"x": 695, "y": 1216, "pressure": 70}}],
    ["UPDATE", 1677409920.586609, {"0": {"x": 691, "y": 1207, "pressure": 59, "orientation": 1, "touch_minor": 8}}],
    ["RELEASE", 1677409920.622096, {"0": {}}],
]

LEFT = 1
RIGHT = 2
TOP = 3

ACTIONS = {
    LEFT:  {'name': 'left',  'action': EMUL_PREV},
    RIGHT: {'name': 'right', 'action': EMUL_NEXT},
    TOP:   {'name': 'top',   'action': EMUL_HOME},
}

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
    if DRY_RUN:
        return

    def wev(sec, usec, t, c, v):
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
    slot = 0

    for record in source:
        if isinstance(record, str):
            record = json.loads(record)
        (evtype, sec, detail) = record
        if tfirst == -1:
            tfirst = sec

        delay = sec - tfirst + tstart - time.time()
        if delay > 0 and not NO_SLEEP:
            time.sleep(delay)

        tv_sec = int(sec)
        tv_usec = int((sec - tv_sec) * 1000000)
        last_slot = slot
        if evtype == 'RELEASE':
            if slot in detail:
                wev(tv_sec, tv_usec, 3, ABS_MT_TRACKING_ID, -1)
            for slot in detail.keys():
                if slot == last_slot:
                    continue
                wev(tv_sec, tv_usec, 3, ABS_MT_SLOT, int(slot))
                wev(tv_sec, tv_usec, 3, ABS_MT_TRACKING_ID, -1)
            wev(tv_sec, tv_usec, 0, 0, 0)
        elif evtype == 'UPDATE':
            if slot in detail:
                finger(tv_sec, tv_usec, detail[slot])
            for slot in detail.keys():
                if slot == last_slot:
                    continue
                wev(tv_sec, tv_usec, 3, ABS_MT_SLOT, int(slot))
                finger(tv_sec, tv_usec, detail[slot])
            wev(tv_sec, tv_usec, 0, 0, 0)
        else:
            print(f'invalid event type {evtype}', file=sys.stderr)
            return


if options.grab:
    grab()

if options.replay:
    replay(sys.stdin)
    sys.exit(0)

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

def which_side(finger):
    # only bottom half-ish
    if finger.y > 1200:
        return TOP
    if finger.y > 1000:
        return None
    if finger.x < 500:
        return LEFT
    if finger.x > 700:
        # some blank in the middle too
        return RIGHT
    return None


class Side():
    LEFT = 0
    RIGHT = 1
    TOP = 2

    def __init__(self, finger):
        self.side = which_side(finger)
        self.usec = finger.up_sec

    def double_tap(self, finger):
        if self.side is None:
            return None
        if finger.down_sec - self.usec > 500000:
            return None
        if self.side != which_side(finger):
            return None
        return ACTIONS[self.side]


class Tracking():
    last_side = None
    last_ts = -1

    def update(self, finger):
        if finger.down_duration < 0.3:
            if self.last_side is not None and finger.up_sec - self.last_ts < 3:
                action = self.last_side.double_tap(finger)
                if action:
                    if DEBUG >= 1:
                        print(f"Running {action['name']}")
                    state.actions.append(action['action'])
                    self.last_side = None
                else:
                    self.last_side = Side(finger)
                    self.last_ts = finger.up_sec
            else:
                self.last_side = Side(finger)
                self.last_ts = finger.up_sec


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
            else:
                for (slot_id, finger) in self.released.items():
                    finger.release(sec)
                    if DEBUG == 2:
                        print(f"{tv_sec}.{tv_usec:06}: {finger.id} up {finger.x},{finger.y} after {finger.down_duration}. Pressure {finger.pressure} Orientation {finger.orientation}",
                              file=sys.stderr)
                    # trigger events on release for now
                    tracking.update(finger)
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
    # NO_SLEEP actually needs to wait a bit for the very first input...
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


while handle_input():
    pass

while state.actions:
    replay(state.actions.pop(0))

# unreachable...
os.close(in_file)
