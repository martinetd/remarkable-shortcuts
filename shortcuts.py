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
EVENT_SIZE = struct.calcsize(FORMAT)
DEBUG = options.verbose
DRY_RUN = options.dry_run
NO_SLEEP = options.no_sleep

# record + sed -e '1i[' -e '$a]' -e 's/$/,/' -e 's/^/    /'
# long lines slow down ALE too much...
EMUL_PREV = [
    [0, 0, 3, 47, 0],
    [0, 0, 3, 57, 1279],
    [0, 0, 3, 53, 417],
    [0, 0, 3, 54, 704],
    [0, 0, 3, 58, 103],
    [0, 0, 0, 0, 0],
    [0, 21576, 3, 53, 420],
    [0, 21576, 3, 58, 109],
    [0, 21576, 0, 0, 0],
    [0, 29799, 3, 53, 424],
    [0, 29799, 3, 58, 106],
    [0, 29799, 3, 49, 17],
    [0, 29799, 3, 52, 4],
    [0, 29799, 0, 0, 0],
    [0, 39680, 3, 53, 430],
    [0, 39680, 3, 58, 108],
    [0, 39680, 0, 0, 0],
    [0, 51543, 3, 53, 438],
    [0, 51543, 3, 58, 116],
    [0, 51543, 0, 0, 0],
    [0, 63654, 3, 53, 450],
    [0, 63654, 3, 58, 114],
    [0, 63654, 3, 52, 3],
    [0, 63654, 0, 0, 0],
    [0, 75201, 3, 53, 466],
    [0, 75201, 3, 58, 115],
    [0, 75201, 3, 52, 4],
    [0, 75201, 0, 0, 0],
    [0, 87350, 3, 53, 486],
    [0, 87350, 3, 58, 112],
    [0, 87350, 0, 0, 0],
    [0, 99187, 3, 53, 511],
    [0, 99187, 3, 58, 117],
    [0, 99187, 3, 52, 3],
    [0, 99187, 0, 0, 0],
    [0, 111023, 3, 53, 543],
    [0, 111023, 3, 58, 118],
    [0, 111023, 3, 49, 8],
    [0, 111023, 3, 52, 2],
    [0, 111023, 0, 0, 0],
    [0, 122664, 3, 53, 582],
    [0, 122664, 3, 58, 113],
    [0, 122664, 0, 0, 0],
    [0, 134846, 3, 53, 623],
    [0, 134846, 3, 58, 112],
    [0, 134846, 3, 49, 17],
    [0, 134846, 3, 52, 4],
    [0, 134846, 0, 0, 0],
    [0, 146577, 3, 53, 671],
    [0, 146577, 3, 58, 119],
    [0, 146577, 0, 0, 0],
    [0, 158615, 3, 53, 719],
    [0, 158615, 3, 58, 120],
    [0, 158615, 0, 0, 0],
    [0, 170152, 3, 53, 768],
    [0, 170152, 3, 58, 116],
    [0, 170152, 3, 52, 3],
    [0, 170152, 0, 0, 0],
    [0, 182140, 3, 53, 817],
    [0, 182140, 3, 54, 706],
    [0, 182140, 3, 58, 112],
    [0, 182140, 3, 52, 4],
    [0, 182140, 0, 0, 0],
    [0, 194107, 3, 53, 864],
    [0, 194107, 3, 54, 708],
    [0, 194107, 3, 58, 113],
    [0, 194107, 0, 0, 0],
    [0, 205915, 3, 53, 905],
    [0, 205915, 3, 54, 709],
    [0, 205915, 3, 52, 3],
    [0, 205915, 0, 0, 0],
    [0, 217736, 3, 53, 945],
    [0, 217736, 3, 54, 711],
    [0, 217736, 3, 58, 115],
    [0, 217736, 3, 49, 8],
    [0, 217736, 3, 52, 2],
    [0, 217736, 0, 0, 0],
    [0, 229482, 3, 53, 980],
    [0, 229482, 3, 54, 712],
    [0, 229482, 3, 49, 17],
    [0, 229482, 3, 52, 3],
    [0, 229482, 0, 0, 0],
    [0, 241356, 3, 53, 1015],
    [0, 241356, 3, 54, 713],
    [0, 241356, 3, 58, 109],
    [0, 241356, 3, 52, 4],
    [0, 241356, 0, 0, 0],
    [0, 253283, 3, 53, 1049],
    [0, 253283, 3, 54, 714],
    [0, 253283, 3, 58, 112],
    [0, 253283, 3, 52, 3],
    [0, 253283, 0, 0, 0],
    [0, 265297, 3, 53, 1082],
    [0, 265297, 3, 58, 114],
    [0, 265297, 0, 0, 0],
    [0, 277131, 3, 53, 1108],
    [0, 277131, 3, 54, 715],
    [0, 277131, 3, 58, 117],
    [0, 277131, 0, 0, 0],
    [0, 289091, 3, 53, 1132],
    [0, 289091, 3, 58, 111],
    [0, 289091, 3, 52, 4],
    [0, 289091, 0, 0, 0],
    [0, 300711, 3, 53, 1154],
    [0, 300711, 3, 58, 110],
    [0, 300711, 3, 52, 3],
    [0, 300711, 0, 0, 0],
    [0, 312700, 3, 53, 1173],
    [0, 312700, 3, 54, 713],
    [0, 312700, 3, 58, 91],
    [0, 312700, 3, 49, 8],
    [0, 312700, 3, 52, 2],
    [0, 312700, 0, 0, 0],
    [0, 348065, 3, 57, -1],
    [0, 348065, 0, 0, 0],
]

EMUL_NEXT = [
    [0, 0, 3, 57, 1273],
    [0, 0, 3, 53, 1008],
    [0, 0, 3, 54, 792],
    [0, 0, 3, 58, 114],
    [0, 0, 3, 48, 17],
    [0, 0, 3, 49, 17],
    [0, 0, 3, 52, 3],
    [0, 0, 0, 0, 0],
    [0, 8254, 3, 53, 1003],
    [0, 8254, 3, 58, 117],
    [0, 8254, 0, 0, 0],
    [0, 17036, 3, 53, 991],
    [0, 17036, 3, 58, 108],
    [0, 17036, 0, 0, 0],
    [0, 27041, 3, 53, 974],
    [0, 27041, 3, 54, 793],
    [0, 27041, 0, 0, 0],
    [0, 38558, 3, 53, 950],
    [0, 38558, 3, 49, 8],
    [0, 38558, 3, 52, 2],
    [0, 38558, 0, 0, 0],
    [0, 50972, 3, 53, 915],
    [0, 50972, 3, 54, 794],
    [0, 50972, 3, 58, 101],
    [0, 50972, 0, 0, 0],
    [0, 62781, 3, 53, 856],
    [0, 62781, 3, 54, 795],
    [0, 62781, 3, 58, 103],
    [0, 62781, 3, 49, 17],
    [0, 62781, 3, 52, 3],
    [0, 62781, 0, 0, 0],
    [0, 74709, 3, 53, 797],
    [0, 74709, 3, 54, 796],
    [0, 74709, 3, 58, 107],
    [0, 74709, 0, 0, 0],
    [0, 86467, 3, 53, 729],
    [0, 86467, 3, 54, 797],
    [0, 86467, 3, 58, 108],
    [0, 86467, 3, 49, 8],
    [0, 86467, 3, 52, 2],
    [0, 86467, 0, 0, 0],
    [0, 98329, 3, 53, 663],
    [0, 98329, 3, 58, 104],
    [0, 98329, 0, 0, 0],
    [0, 110353, 3, 53, 604],
    [0, 110353, 3, 58, 102],
    [0, 110353, 3, 49, 17],
    [0, 110353, 3, 52, 3],
    [0, 110353, 0, 0, 0],
    [0, 122313, 3, 53, 546],
    [0, 122313, 3, 58, 96],
    [0, 122313, 0, 0, 0],
    [0, 134096, 3, 53, 497],
    [0, 134096, 3, 54, 796],
    [0, 134096, 3, 58, 84],
    [0, 134096, 3, 48, 8],
    [0, 134096, 3, 52, 2],
    [0, 134096, 0, 0, 0],
    [0, 146026, 3, 53, 446],
    [0, 146026, 3, 54, 793],
    [0, 146026, 3, 58, 66],
    [0, 146026, 0, 0, 0],
    [0, 181453, 3, 57, -1],
    [0, 181453, 0, 0, 0],
]

EMUL_HOME = [
    [0, 0, 3, 57, 1549],
    [0, 0, 3, 53, 751],
    [0, 0, 3, 54, 1854],
    [0, 0, 3, 58, 85],
    [0, 0, 0, 0, 0],
    [0, 26802, 3, 54, 1851],
    [0, 26802, 3, 58, 101],
    [0, 26802, 3, 48, 17],
    [0, 26802, 3, 52, 4],
    [0, 26802, 0, 0, 0],
    [0, 39007, 3, 54, 1848],
    [0, 39007, 3, 58, 109],
    [0, 39007, 0, 0, 0],
    [0, 50914, 3, 54, 1843],
    [0, 50914, 3, 58, 114],
    [0, 50914, 0, 0, 0],
    [0, 62655, 3, 54, 1837],
    [0, 62655, 3, 58, 119],
    [0, 62655, 0, 0, 0],
    [0, 74468, 3, 54, 1827],
    [0, 74468, 3, 58, 115],
    [0, 74468, 3, 48, 8],
    [0, 74468, 3, 52, 2],
    [0, 74468, 0, 0, 0],
    [0, 86460, 3, 54, 1815],
    [0, 86460, 3, 58, 116],
    [0, 86460, 3, 48, 17],
    [0, 86460, 3, 52, 4],
    [0, 86460, 0, 0, 0],
    [0, 97872, 3, 53, 750],
    [0, 97872, 3, 54, 1803],
    [0, 97872, 3, 58, 119],
    [0, 97872, 0, 0, 0],
    [0, 110148, 3, 53, 749],
    [0, 110148, 3, 54, 1788],
    [0, 110148, 3, 58, 116],
    [0, 110148, 3, 48, 8],
    [0, 110148, 3, 52, 2],
    [0, 110148, 0, 0, 0],
    [0, 122073, 3, 53, 748],
    [0, 122073, 3, 54, 1772],
    [0, 122073, 3, 58, 117],
    [0, 122073, 3, 48, 17],
    [0, 122073, 3, 52, 4],
    [0, 122073, 0, 0, 0],
    [0, 133821, 3, 54, 1754],
    [0, 133821, 3, 58, 111],
    [0, 133821, 3, 48, 8],
    [0, 133821, 3, 52, 2],
    [0, 133821, 0, 0, 0],
    [0, 145812, 3, 54, 1733],
    [0, 145812, 3, 58, 113],
    [0, 145812, 3, 48, 17],
    [0, 145812, 3, 52, 4],
    [0, 145812, 0, 0, 0],
    [0, 157627, 3, 54, 1710],
    [0, 157627, 3, 58, 106],
    [0, 157627, 3, 48, 8],
    [0, 157627, 3, 52, 2],
    [0, 157627, 0, 0, 0],
    [0, 168700, 3, 54, 1685],
    [0, 168700, 3, 48, 17],
    [0, 168700, 3, 52, 3],
    [0, 168700, 0, 0, 0],
    [0, 181279, 3, 54, 1657],
    [0, 181279, 3, 58, 108],
    [0, 181279, 3, 52, 4],
    [0, 181279, 0, 0, 0],
    [0, 192762, 3, 53, 750],
    [0, 192762, 3, 54, 1618],
    [0, 192762, 3, 58, 102],
    [0, 192762, 3, 48, 8],
    [0, 192762, 3, 52, 2],
    [0, 192762, 0, 0, 0],
    [0, 205104, 3, 53, 752],
    [0, 205104, 3, 54, 1577],
    [0, 205104, 3, 58, 95],
    [0, 205104, 0, 0, 0],
    [0, 217004, 3, 54, 1536],
    [0, 217004, 3, 58, 89],
    [0, 217004, 0, 0, 0],
    [0, 228905, 3, 54, 1494],
    [0, 228905, 3, 58, 85],
    [0, 228905, 0, 0, 0],
    [0, 240753, 3, 54, 1446],
    [0, 240753, 3, 58, 87],
    [0, 240753, 0, 0, 0],
    [0, 252590, 3, 53, 749],
    [0, 252590, 3, 54, 1404],
    [0, 252590, 3, 58, 89],
    [0, 252590, 3, 48, 17],
    [0, 252590, 3, 52, 3],
    [0, 252590, 0, 0, 0],
    [0, 264456, 3, 53, 747],
    [0, 264456, 3, 54, 1362],
    [0, 264456, 0, 0, 0],
    [0, 276332, 3, 53, 744],
    [0, 276332, 3, 54, 1321],
    [0, 276332, 3, 58, 84],
    [0, 276332, 3, 48, 8],
    [0, 276332, 3, 52, 2],
    [0, 276332, 0, 0, 0],
    [0, 288200, 3, 53, 742],
    [0, 288200, 3, 54, 1288],
    [0, 288200, 3, 58, 86],
    [0, 288200, 0, 0, 0],
    [0, 300169, 3, 53, 740],
    [0, 300169, 3, 54, 1260],
    [0, 300169, 3, 58, 87],
    [0, 300169, 3, 48, 17],
    [0, 300169, 3, 52, 3],
    [0, 300169, 0, 0, 0],
    [0, 311976, 3, 54, 1233],
    [0, 311976, 3, 58, 89],
    [0, 311976, 3, 48, 8],
    [0, 311976, 3, 52, 2],
    [0, 311976, 0, 0, 0],
    [0, 323721, 3, 54, 1208],
    [0, 323721, 3, 58, 85],
    [0, 323721, 0, 0, 0],
    [0, 335654, 3, 54, 1184],
    [0, 335654, 3, 58, 86],
    [0, 335654, 3, 48, 17],
    [0, 335654, 3, 52, 4],
    [0, 335654, 0, 0, 0],
    [0, 347556, 3, 54, 1161],
    [0, 347556, 3, 58, 76],
    [0, 347556, 3, 48, 8],
    [0, 347556, 3, 52, 2],
    [0, 347556, 0, 0, 0],
    [0, 359393, 3, 54, 1140],
    [0, 359393, 3, 58, 65],
    [0, 359393, 0, 0, 0],
    [0, 394798, 3, 57, -1],
    [0, 394798, 0, 0, 0],
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

def to_usec(sec, usec):
    return sec * 1000000 + usec

def record():
    print("Recording...", file=sys.stderr)
    first_sec = -1
    first_usec = -1
    while True:
        ev = os.read(in_file, EVENT_SIZE)
        (tv_sec, tv_usec, evtype, code, value) = struct.unpack(FORMAT, ev)
        if first_sec < 0:
            first_sec = tv_sec
            first_usec = tv_usec
        if tv_usec < first_usec:
            tv_usec += 1000000
            tv_sec -= 1
        sys.stdout.write(json.dumps(
            (tv_sec - first_sec, tv_usec - first_usec, evtype, code, value)))
        sys.stdout.write('\n')
        sys.stdout.flush()

def replay(source):
    if DRY_RUN:
        return
    tstart = time.time()
    for item in source:
        if isinstance(item, str):
            (sec, usec, evtype, code, value) = json.loads(item)
        else:
            (sec, usec, evtype, code, value) = item
        delay = sec + usec / 1000000 - time.time() + tstart
        if delay > 0 and not NO_SLEEP:
            time.sleep(delay)
        os.write(in_file, struct.pack(FORMAT, sec, usec, evtype, code, value))


if options.grab:
    grab()

if options.record:
    record()
    # never returns, but just in case..
    sys.exit(1)

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

class Finger():
    start_x = -1
    start_y = -1
    x = -1
    y = -1
    pressure = -1
    orientation = -1

    def __init__(self, tracking_id, sec, usec):
        self.id = tracking_id
        self.down_usec = to_usec(sec, usec)

    def update(self, code, value):
        if code == ABS_MT_POSITION_X:
            if self.start_x < 0:
                self.start_x = value
            self.x = value
        elif code == ABS_MT_POSITION_Y:
            if self.start_y < 0:
                self.start_y = value
            self.y = value
        elif code == ABS_MT_PRESSURE:
            self.pressure = value
        elif code == ABS_MT_ORIENTATION:
            self.orientation = value
        elif code in [ABS_MT_TOUCH_MAJOR, ABS_MT_TOUCH_MINOR]:
            # large surface contact?
            pass
        else:
            return False
        return True


    # return touch duration in msec
    def release(self, sec, usec):
        self.up_usec = to_usec(sec, usec)
        self.down_time = (self.up_usec - self.down_usec) / 1000

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
        self.usec = finger.up_usec

    def double_tap(self, finger):
        if self.side is None:
            return None
        if finger.down_usec - self.usec > 500000:
            return None
        if self.side != which_side(finger):
            return None
        return ACTIONS[self.side]


class Tracking():
    last_side = None

    def update(self, finger):
        if finger.down_time < 300:
            if self.last_side is not None:
                action = self.last_side.double_tap(finger)
                if action:
                    if DEBUG >= 1:
                        print(f"Running {action['name']}")
                    state.actions.append(action['action'])
                    self.last_side = None
                else:
                    self.last_side = Side(finger)
            else:
                self.last_side = Side(finger)


class State():
    fingers = {}
    slot_id = 0
    finger = None
    last_side = None
    actions = []

    def update(self, tv_sec, tv_usec, code, value):
        if code == ABS_MT_SLOT:
            self.slot_id = value
            self.finger = self.fingers.get(value)
            return
        if code == ABS_MT_TRACKING_ID and value >= 0:
            self.finger = Finger(value, tv_sec, tv_usec)
            self.fingers[self.slot_id] = self.finger
            return

        if self.finger is None:
            if code != 0:
                print(f"{tv_sec}.{tv_usec:06}: Unhandled touch event without id code {code}, value {value}",
                      file=sys.stderr)
            return

        if self.finger.update(code, value):
            pass
        elif code == ABS_MT_TRACKING_ID:
            # value < 0
            down_time = self.finger.release(tv_sec, tv_usec)
            if DEBUG == 2:
                print(f"{tv_sec}.{tv_usec:06}: {self.finger.id} up {self.finger.x},{self.finger.y} after {down_time}. Pressure {self.finger.pressure} Orientation {self.finger.orientation}",
                      file=sys.stderr)
            action = tracking.update(self.finger)
            self.finger = None
            del self.fingers[self.slot_id]
        elif code == 0:
            if DEBUG == 2:
                print(f"{tv_sec}.{tv_usec:06}: {self.finger.id} pressed {self.finger.x},{self.finger.y}. Pressure {self.finger.pressure} Orientation {self.finger.orientation}",
                      file=sys.stderr)
        else:
            if DEBUG == 1:
                print(f"{tv_sec}.{tv_usec:06}: Unhandled touch event code {code}, value {value}",
                      file=sys.stderr)

tracking = Tracking()
state = State()

# input codes for multitouch
ABS_MT_SLOT = 47
ABS_MT_TOUCH_MAJOR = 48
ABS_MT_TOUCH_MINOR = 49
ABS_MT_ORIENTATION = 52
ABS_MT_POSITION_X = 53
ABS_MT_POSITION_Y = 54
ABS_MT_TRACKING_ID = 57
ABS_MT_PRESSURE = 58



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
