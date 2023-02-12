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

# open file in binary mode
in_file = open(infile_path, "rb")

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
    pass

class State():
    # track only one finger
    x = 0
    y = 0
    tracking_id = 0
    pressure = 0
    down_usec = 0

    def touch(self, sec, usec):
        self.down_usec = sec * 1000000 + usec

    # return touch duration in msec
    def release(self, sec, usec):
        up_usec = sec * 1000000 + usec
        return (up_usec - self.down_usec) / 1000


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
    if DEBUG == 2:
        print("Event: type %i, code %i, value %i at %d.%06d" %
              (evtype, code,
               value, tv_sec, tv_usec),
              file=sys.stderr)

    if evtype == 0 and code == 0 and value == 0:
        pass
    elif evtype != 3:
        print("Unhandled key: type %i, code %i, value %i at %d.%06d" %
              (evtype, code, value, tv_sec, tv_usec),
              file=sys.stderr)
        return

    # codes:
    # 48 ABS_MT_TOUCH_MAJOR
    # 49 ABS_MT_TOUCH_MINOR
    # 53 ABS_MT_POSITION_X
    # 
    # 53 x, 54 y
    # 57 touchdown id or -1 (release)
    # 58 ?? pressure
    # 49 ??
    # 52: finger# ?
    # code 0 value 0: ???
    if code == ABS_MT_POSITION_X:
        state.x = value
    elif code == ABS_MT_POSITION_Y:
        state.y = value
    elif code == ABS_MT_PRESSURE:
        state.pressure = value
    elif code == ABS_MT_TRACKING_ID and value > 0:
        state.tracking_id = value
        state.touch(tv_sec, tv_usec)
    elif code == ABS_MT_TRACKING_ID:
        down_time = state.release(tv_sec, tv_usec)
        print(f"{tv_sec}.{tv_usec:06}: {state.tracking_id} up {state.x},{state.y} after {down_time}. Pressure {state.pressure}")
    elif code == 0:
        print(f"{tv_sec}.{tv_usec:06}: {state.tracking_id} down {state.x},{state.y}. Pressure {state.pressure}")
    elif code not in [48, 49, 52, 58]:
        print(f"{tv_sec}.{tv_usec:06}: code {code}, value {value}",
              file=sys.stderr)
        sys.stdout.flush()

    sys.stdout.flush()


while True:
    (ready, _, _) = select.select([in_file], [], [])
    if in_file in ready:
        event = in_file.read(EVENT_SIZE)
        parse(*struct.unpack(FORMAT, event))

in_file.close()
