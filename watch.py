#!/usr/bin/python
# coding=utf-8

"""
stream events from input device, without depending on evdev
"""
from __future__ import print_function
import struct
import sys
import os
import time
import json
import fcntl
import errno
import select
import signal

from optparse import OptionParser
import subprocess

parser = OptionParser()
parser.add_option('-v', '--verbose', action='count')
parser.add_option('-e', '--event', action='store', type='string', default='0',
                  help='event number e.g. 3 for /dev/input/event3 (default 0)')
parser.add_option('-p', '--pidfile', action='store', type='string',
                  help='pidfile, also kills old instance if existed')
parser.add_option('-D', '--daemonize', action='store_true',
                  help='close files and daemonizes. requires -c')
parser.add_option('-n', '--dry_run', action='store_true',
                  help='Do not actually inject events')
parser.add_option('--record', action='store_true',
                  help='record input to stdout (debug)')
parser.add_option('--replay', action='store_true',
                  help='replay stdin (debug)')

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

infile_path = "/dev/input/event%s" % options.event
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

# record + sed -e '1i[' -e '$a]' -e 's/$/,/' -e 's/^/    /'
# long lines slow down ALE too much...
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
    [1, -924799, 3, 53, 466],
    [1, -924799, 3, 58, 115],
    [1, -924799, 3, 52, 4],
    [1, -924799, 0, 0, 0],
    [1, -912650, 3, 53, 486],
    [1, -912650, 3, 58, 112],
    [1, -912650, 0, 0, 0],
    [1, -900813, 3, 53, 511],
    [1, -900813, 3, 58, 117],
    [1, -900813, 3, 52, 3],
    [1, -900813, 0, 0, 0],
    [1, -888977, 3, 53, 543],
    [1, -888977, 3, 58, 118],
    [1, -888977, 3, 49, 8],
    [1, -888977, 3, 52, 2],
    [1, -888977, 0, 0, 0],
    [1, -877336, 3, 53, 582],
    [1, -877336, 3, 58, 113],
    [1, -877336, 0, 0, 0],
    [1, -865154, 3, 53, 623],
    [1, -865154, 3, 58, 112],
    [1, -865154, 3, 49, 17],
    [1, -865154, 3, 52, 4],
    [1, -865154, 0, 0, 0],
    [1, -853423, 3, 53, 671],
    [1, -853423, 3, 58, 119],
    [1, -853423, 0, 0, 0],
    [1, -841385, 3, 53, 719],
    [1, -841385, 3, 58, 120],
    [1, -841385, 0, 0, 0],
    [1, -829848, 3, 53, 768],
    [1, -829848, 3, 58, 116],
    [1, -829848, 3, 52, 3],
    [1, -829848, 0, 0, 0],
    [1, -817860, 3, 53, 817],
    [1, -817860, 3, 54, 706],
    [1, -817860, 3, 58, 112],
    [1, -817860, 3, 52, 4],
    [1, -817860, 0, 0, 0],
    [1, -805893, 3, 53, 864],
    [1, -805893, 3, 54, 708],
    [1, -805893, 3, 58, 113],
    [1, -805893, 0, 0, 0],
    [1, -794085, 3, 53, 905],
    [1, -794085, 3, 54, 709],
    [1, -794085, 3, 52, 3],
    [1, -794085, 0, 0, 0],
    [1, -782264, 3, 53, 945],
    [1, -782264, 3, 54, 711],
    [1, -782264, 3, 58, 115],
    [1, -782264, 3, 49, 8],
    [1, -782264, 3, 52, 2],
    [1, -782264, 0, 0, 0],
    [1, -770518, 3, 53, 980],
    [1, -770518, 3, 54, 712],
    [1, -770518, 3, 49, 17],
    [1, -770518, 3, 52, 3],
    [1, -770518, 0, 0, 0],
    [1, -758644, 3, 53, 1015],
    [1, -758644, 3, 54, 713],
    [1, -758644, 3, 58, 109],
    [1, -758644, 3, 52, 4],
    [1, -758644, 0, 0, 0],
    [1, -746717, 3, 53, 1049],
    [1, -746717, 3, 54, 714],
    [1, -746717, 3, 58, 112],
    [1, -746717, 3, 52, 3],
    [1, -746717, 0, 0, 0],
    [1, -734703, 3, 53, 1082],
    [1, -734703, 3, 58, 114],
    [1, -734703, 0, 0, 0],
    [1, -722869, 3, 53, 1108],
    [1, -722869, 3, 54, 715],
    [1, -722869, 3, 58, 117],
    [1, -722869, 0, 0, 0],
    [1, -710909, 3, 53, 1132],
    [1, -710909, 3, 58, 111],
    [1, -710909, 3, 52, 4],
    [1, -710909, 0, 0, 0],
    [1, -699289, 3, 53, 1154],
    [1, -699289, 3, 58, 110],
    [1, -699289, 3, 52, 3],
    [1, -699289, 0, 0, 0],
    [1, -687300, 3, 53, 1173],
    [1, -687300, 3, 54, 713],
    [1, -687300, 3, 58, 91],
    [1, -687300, 3, 49, 8],
    [1, -687300, 3, 52, 2],
    [1, -687300, 0, 0, 0],
    [1, -651935, 3, 57, -1],
    [1, -651935, 0, 0, 0],
]


# open file in binary mode
in_file = os.open(infile_path, os.O_RDWR)

def lock():
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
    first_sec = -1
    first_usec = -1
    while True:
        event = os.read(in_file, EVENT_SIZE)
        (tv_sec, tv_usec, evtype, code, value) = struct.unpack(FORMAT, event)
        if first_sec < 0:
            first_sec = tv_sec
            first_usec = tv_usec
        sys.stdout.write(json.dumps(
            (tv_sec - first_sec, tv_usec - first_usec, evtype, code, value)))
        sys.stdout.write('\n')
        sys.stdout.flush()

def replay(source):
    if DRY_RUN:
        return
    # XXX output is mangled and does not work if we write immediately
    # figure why sleep helps
    time.sleep(0.05)
    tstart = time.time()
    for line in source:
        (sec, usec, evtype, code, value) = json.loads(line) if isinstance(line, str) else line
        delay = sec + usec / 1000000 - time.time() + tstart
        if delay > 0:
            time.sleep(delay)
        os.write(in_file, struct.pack(FORMAT, sec, usec, evtype, code, value))


if options.record:
    lock()
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
    x = -1
    y = -1
    pressure = -1
    orientation = -1

    def __init__(self, tracking_id, sec, usec):
        self.id = tracking_id
        self.down_usec = to_usec(sec, usec)

    # return touch duration in msec
    def release(self, sec, usec):
        self.up_usec = to_usec(sec, usec)
        return (self.up_usec - self.down_usec) / 1000

def which_side(finger):
    # only bottom half-ish
    if finger.y > 1000:
        return None
    if finger.x < 500:
        return Side.LEFT
    elif finger.x > 700:
        # some blank in the middle too
        return Side.RIGHT
    return None

class Side():
    LEFT = 0
    RIGHT = 1

    def __init__(self, finger):
        self.side = which_side(finger)
        self.usec = finger.up_usec

    def double_tap(self, finger):
        if self.side is None:
            return False
        if finger.down_usec - self.usec > 500000:
            return False
        return self.side == which_side(finger)


class State():
    fingers = {}
    slot_id = 0
    finger = None
    last_side = None

    def update(self, tv_sec, tv_usec, code, value):
        if code == ABS_MT_SLOT:
            self.slot_id = value
            return
        if code == ABS_MT_TRACKING_ID and value >= 0:
            self.finger = Finger(value, tv_sec, tv_usec)
            self.fingers[self.slot_id] = self.finger

        if self.finger is None:
            if code != 0:
                print(f"{tv_sec}.{tv_usec:06}: Unhandled touch event without id code {code}, value {value}",
                      file=sys.stderr)
            return

        if code == ABS_MT_POSITION_X:
            self.finger.x = value
        elif code == ABS_MT_POSITION_Y:
            self.finger.y = value
        elif code == ABS_MT_PRESSURE:
            self.finger.pressure = value
        elif code == ABS_MT_ORIENTATION:
            self.finger.orientation = value
        elif code == ABS_MT_TRACKING_ID and value < 0:
            down_time = self.finger.release(tv_sec, tv_usec)
            if DEBUG == 2:
                print(f"{tv_sec}.{tv_usec:06}: {self.finger.id} up {self.finger.x},{self.finger.y} after {down_time}. Pressure {self.finger.pressure} Orientation {self.finger.orientation}",
                      file=sys.stderr)
            if down_time < 300:
                if self.last_side is not None and self.last_side.double_tap(self.finger):
                    if self.last_side.side == Side.LEFT:
                        if DEBUG >= 1:
                            print("Running left action")
                        replay(EMUL_PREV)
                    else:
                        if DEBUG >= 1:
                            print("Running right action")
                        replay(EMUL_NEXT)
                    self.last_side = None
                else:
                    self.last_side = Side(self.finger)
            self.finger = None
            del self.fingers[self.slot_id]
        elif code == 0:
            if DEBUG == 2:
                print(f"{tv_sec}.{tv_usec:06}: {self.finger.id} pressed {self.finger.x},{self.finger.y}. Pressure {self.finger.pressure} Orientation {self.finger.orientation}",
                      file=sys.stderr)
        elif code not in [ABS_MT_TRACKING_ID, ABS_MT_SLOT, ABS_MT_TOUCH_MAJOR, ABS_MT_TOUCH_MINOR]:
            if DEBUG == 1:
                print(f"{tv_sec}.{tv_usec:06}: Unhandled touch event code {code}, value {value}",
                      file=sys.stderr)


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


while True:
    event = os.read(in_file, EVENT_SIZE)
    parse(*struct.unpack(FORMAT, event))

in_file.close()
