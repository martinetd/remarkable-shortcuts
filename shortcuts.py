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
    ["UPDATE", 1677239624.38075, {"0": {"id": 3675, "x": 797, "y": 758, "pressure": 68, "orientation": 4, "touch_minor": 17, "touch_major": 17}}],
    ["UPDATE", 1677239624.389091, {"0": {"id": 3675, "x": 795, "y": 758, "pressure": 69, "orientation": 2, "touch_minor": 8, "touch_major": 17}}],
    ["UPDATE", 1677239624.397917, {"0": {"id": 3675, "x": 789, "y": 759, "pressure": 70, "orientation": 2, "touch_minor": 8, "touch_major": 17}}],
    ["UPDATE", 1677239624.407299, {"0": {"id": 3675, "x": 780, "y": 761, "pressure": 70, "orientation": 3, "touch_minor": 17, "touch_major": 17}}],
    ["UPDATE", 1677239624.419612, {"0": {"id": 3675, "x": 771, "y": 763, "pressure": 71, "orientation": 2, "touch_minor": 17, "touch_major": 8}}],
    ["UPDATE", 1677239624.431601, {"0": {"id": 3675, "x": 757, "y": 766, "pressure": 70, "orientation": 2, "touch_minor": 17, "touch_major": 8}}],
    ["UPDATE", 1677239624.443478, {"0": {"id": 3675, "x": 741, "y": 769, "pressure": 71, "orientation": 2, "touch_minor": 17, "touch_major": 8}}],
    ["UPDATE", 1677239624.455402, {"0": {"id": 3675, "x": 721, "y": 773, "pressure": 71, "orientation": 2, "touch_minor": 17, "touch_major": 8}}],
    ["UPDATE", 1677239624.467275, {"0": {"id": 3675, "x": 697, "y": 776, "pressure": 73, "orientation": 1, "touch_minor": 8, "touch_major": 8}}],
    ["UPDATE", 1677239624.479207, {"0": {"id": 3675, "x": 669, "y": 779, "pressure": 73, "orientation": 2, "touch_minor": 17, "touch_major": 8}}],
    ["UPDATE", 1677239624.490972, {"0": {"id": 3675, "x": 629, "y": 783, "pressure": 73, "orientation": 2, "touch_minor": 17, "touch_major": 8}}],
    ["UPDATE", 1677239624.502855, {"0": {"id": 3675, "x": 588, "y": 786, "pressure": 73, "orientation": 2, "touch_minor": 17, "touch_major": 8}}],
    ["UPDATE", 1677239624.514815, {"0": {"id": 3675, "x": 548, "y": 788, "pressure": 75, "orientation": 2, "touch_minor": 17, "touch_major": 8}}],
    ["UPDATE", 1677239624.52669, {"0": {"id": 3675, "x": 515, "y": 791, "pressure": 75, "orientation": 3, "touch_minor": 17, "touch_major": 17}}],
    ["UPDATE", 1677239624.538621, {"0": {"id": 3675, "x": 488, "y": 794, "pressure": 76, "orientation": 4, "touch_minor": 17, "touch_major": 17}}],
    ["UPDATE", 1677239624.550521, {"0": {"id": 3675, "x": 462, "y": 797, "pressure": 78, "orientation": 3, "touch_minor": 17, "touch_major": 17}}],
    ["UPDATE", 1677239624.562394, {"0": {"id": 3675, "x": 438, "y": 800, "pressure": 79, "orientation": 2, "touch_minor": 8, "touch_major": 17}}],
    ["UPDATE", 1677239624.574244, {"0": {"id": 3675, "x": 416, "y": 803, "pressure": 78, "orientation": 4, "touch_minor": 17, "touch_major": 17}}],
    ["UPDATE", 1677239624.586075, {"0": {"id": 3675, "x": 397, "y": 806, "pressure": 79, "orientation": 3, "touch_minor": 17, "touch_major": 17}}],
    ["UPDATE", 1677239624.598035, {"0": {"id": 3675, "x": 379, "y": 808, "pressure": 79, "orientation": 2, "touch_minor": 8, "touch_major": 17}}],
    ["UPDATE", 1677239624.609936, {"0": {"id": 3675, "x": 363, "y": 809, "pressure": 79, "orientation": 3, "touch_minor": 17, "touch_major": 17}}],
    ["UPDATE", 1677239624.621807, {"0": {"id": 3675, "x": 348, "y": 810, "pressure": 77, "orientation": 4, "touch_minor": 17, "touch_major": 17}}],
    ["UPDATE", 1677239624.633653, {"0": {"id": 3675, "x": 334, "y": 810, "pressure": 75, "orientation": 4, "touch_minor": 17, "touch_major": 17}}],
    ["UPDATE", 1677239624.645549, {"0": {"id": 3675, "x": 321, "y": 809, "pressure": 69, "orientation": 3, "touch_minor": 17, "touch_major": 17}}],
    ["UPDATE", 1677239624.657321, {"0": {"id": 3675, "x": 310, "y": 806, "pressure": 50, "orientation": 1, "touch_minor": 8, "touch_major": 8}}],
    ["RELEASE", 1677239624.692669, {"0": {}}],
]

EMUL_NEXT = [
    ["UPDATE", 1677239631.534614, {"0": {"id": 3676, "x": 415, "y": 784, "pressure": 64, "orientation": 2, "touch_minor": 17}}],
    ["UPDATE", 1677239631.551358, {"0": {"id": 3676, "x": 422, "y": 784, "pressure": 65, "orientation": 2, "touch_minor": 17}}],
    ["UPDATE", 1677239631.561477, {"0": {"id": 3676, "x": 429, "y": 784, "pressure": 63, "orientation": 2, "touch_minor": 17}}],
    ["UPDATE", 1677239631.573318, {"0": {"id": 3676, "x": 439, "y": 784, "pressure": 65, "orientation": 1, "touch_minor": 8}}],
    ["UPDATE", 1677239631.585088, {"0": {"id": 3676, "x": 454, "y": 784, "pressure": 64, "orientation": 2, "touch_minor": 17}}],
    ["UPDATE", 1677239631.597212, {"0": {"id": 3676, "x": 473, "y": 784, "pressure": 65, "orientation": 1, "touch_minor": 8}}],
    ["UPDATE", 1677239631.609111, {"0": {"id": 3676, "x": 495, "y": 783, "pressure": 65, "orientation": 2, "touch_minor": 17}}],
    ["UPDATE", 1677239631.621011, {"0": {"id": 3676, "x": 519, "y": 783, "pressure": 64, "orientation": 2, "touch_minor": 17}}],
    ["UPDATE", 1677239631.632884, {"0": {"id": 3676, "x": 546, "y": 782, "pressure": 64, "orientation": 1, "touch_minor": 8}}],
    ["UPDATE", 1677239631.644809, {"0": {"id": 3676, "x": 574, "y": 782, "pressure": 62, "orientation": 2, "touch_minor": 17}}],
    ["UPDATE", 1677239631.656685, {"0": {"id": 3676, "x": 606, "y": 781, "pressure": 64, "orientation": 2, "touch_minor": 17}}],
    ["UPDATE", 1677239631.668583, {"0": {"id": 3676, "x": 634, "y": 781, "pressure": 63, "orientation": 2, "touch_minor": 17}}],
    ["UPDATE", 1677239631.680481, {"0": {"id": 3676, "x": 665, "y": 781, "pressure": 63, "orientation": 2, "touch_minor": 17}}],
    ["UPDATE", 1677239631.692298, {"0": {"id": 3676, "x": 692, "y": 783, "pressure": 67, "orientation": 1, "touch_minor": 8}}],
    ["UPDATE", 1677239631.704103, {"0": {"id": 3676, "x": 719, "y": 785, "pressure": 67, "orientation": 2, "touch_minor": 17}}],
    ["UPDATE", 1677239631.716001, {"0": {"id": 3676, "x": 744, "y": 788, "pressure": 69, "orientation": 2, "touch_minor": 8, "touch_major": 17}}],
    ["UPDATE", 1677239631.727881, {"0": {"id": 3676, "x": 769, "y": 791, "pressure": 67, "orientation": 3, "touch_minor": 17, "touch_major": 17}}],
    ["UPDATE", 1677239631.739379, {"0": {"id": 3676, "x": 792, "y": 794, "pressure": 67, "orientation": 3, "touch_minor": 17, "touch_major": 17}}],
    ["UPDATE", 1677239631.75174, {"0": {"id": 3676, "x": 814, "y": 796, "pressure": 68, "orientation": 2, "touch_minor": 8, "touch_major": 17}}],
    ["UPDATE", 1677239631.76362, {"0": {"id": 3676, "x": 833, "y": 798, "pressure": 68, "orientation": 3, "touch_minor": 17, "touch_major": 17}}],
    ["UPDATE", 1677239631.775247, {"0": {"id": 3676, "x": 850, "y": 800, "pressure": 66, "orientation": 4, "touch_minor": 17, "touch_major": 17}}],
    ["UPDATE", 1677239631.787263, {"0": {"id": 3676, "x": 865, "y": 801, "pressure": 67, "orientation": 4, "touch_minor": 17, "touch_major": 17}}],
    ["UPDATE", 1677239631.799288, {"0": {"id": 3676, "x": 878, "y": 802, "pressure": 68, "orientation": 2, "touch_minor": 8, "touch_major": 17}}],
    ["UPDATE", 1677239631.811124, {"0": {"id": 3676, "x": 890, "y": 802, "pressure": 67, "orientation": 2, "touch_minor": 8, "touch_major": 17}}],
    ["UPDATE", 1677239631.823055, {"0": {"id": 3676, "x": 901, "y": 802, "pressure": 68, "orientation": 2, "touch_minor": 8, "touch_major": 17}}],
    ["UPDATE", 1677239631.834901, {"0": {"id": 3676, "x": 910, "y": 802, "pressure": 68, "orientation": 3, "touch_minor": 17, "touch_major": 17}}],
    ["UPDATE", 1677239631.846796, {"0": {"id": 3676, "x": 918, "y": 802, "pressure": 67, "orientation": 3, "touch_minor": 17, "touch_major": 17}}],
    ["UPDATE", 1677239631.858728, {"0": {"id": 3676, "x": 925, "y": 802, "pressure": 67, "orientation": 3, "touch_minor": 17, "touch_major": 17}}],
    ["UPDATE", 1677239631.870568, {"0": {"id": 3676, "x": 931, "y": 802, "pressure": 67, "orientation": 3, "touch_minor": 17, "touch_major": 17}}],
    ["UPDATE", 1677239631.882498, {"0": {"id": 3676, "x": 936, "y": 802, "pressure": 64, "orientation": 3, "touch_minor": 17, "touch_major": 17}}],
    ["UPDATE", 1677239631.894284, {"0": {"id": 3676, "x": 940, "y": 802, "pressure": 65, "orientation": 3, "touch_minor": 17, "touch_major": 17}}],
    ["UPDATE", 1677239631.90609, {"0": {"id": 3676, "x": 944, "y": 802, "pressure": 65, "orientation": 3, "touch_minor": 17, "touch_major": 17}}],
    ["UPDATE", 1677239631.918052, {"0": {"id": 3676, "x": 947, "y": 802, "pressure": 65, "orientation": 2, "touch_minor": 17, "touch_major": 8}}],
    ["UPDATE", 1677239631.930013, {"0": {"id": 3676, "x": 951, "y": 801, "pressure": 65, "orientation": 2, "touch_minor": 17, "touch_major": 8}}],
    ["UPDATE", 1677239631.941798, {"0": {"id": 3676, "x": 955, "y": 800, "pressure": 64, "orientation": 1, "touch_minor": 8, "touch_major": 8}}],
    ["UPDATE", 1677239631.953671, {"0": {"id": 3676, "x": 960, "y": 799, "pressure": 63, "orientation": 1, "touch_minor": 8, "touch_major": 8}}],
    ["UPDATE", 1677239631.965048, {"0": {"id": 3676, "x": 965, "y": 798, "pressure": 61, "orientation": 1, "touch_minor": 8, "touch_major": 8}}],
    ["UPDATE", 1677239631.97741, {"0": {"id": 3676, "x": 972, "y": 797, "pressure": 57, "orientation": 2, "touch_minor": 17, "touch_major": 8}}],
    ["UPDATE", 1677239631.989369, {"0": {"id": 3676, "x": 978, "y": 795, "pressure": 37, "orientation": 2, "touch_minor": 17, "touch_major": 8}}],
    ["RELEASE", 1677239632.024423, {"0": {}}],
]

EMUL_HOME = [
    ["UPDATE", 1677239637.951058, {"0": {"id": 3677, "x": 555, "y": 1826, "pressure": 72, "orientation": 4, "touch_major": 17}}],
    ["UPDATE", 1677239637.991081, {"0": {"id": 3677, "x": 553, "y": 1827, "pressure": 79, "orientation": 4, "touch_major": 17}}],
    ["UPDATE", 1677239638.002851, {"0": {"id": 3677, "x": 553, "y": 1828, "pressure": 79, "orientation": 4, "touch_major": 17}}],
    ["UPDATE", 1677239638.014508, {"0": {"id": 3677, "x": 552, "y": 1828, "pressure": 81, "orientation": 4, "touch_major": 17}}],
    ["UPDATE", 1677239638.050445, {"0": {"id": 3677, "x": 552, "y": 1826, "pressure": 81, "orientation": 4, "touch_major": 17}}],
    ["UPDATE", 1677239638.062358, {"0": {"id": 3677, "x": 553, "y": 1821, "pressure": 79, "orientation": 2, "touch_major": 8}}],
    ["UPDATE", 1677239638.074059, {"0": {"id": 3677, "x": 555, "y": 1814, "pressure": 80, "orientation": 3, "touch_major": 17}}],
    ["UPDATE", 1677239638.085975, {"0": {"id": 3677, "x": 557, "y": 1805, "pressure": 85, "orientation": 3, "touch_major": 17}}],
    ["UPDATE", 1677239638.097842, {"0": {"id": 3677, "x": 560, "y": 1794, "pressure": 82, "orientation": 3, "touch_major": 17}}],
    ["UPDATE", 1677239638.109786, {"0": {"id": 3677, "x": 562, "y": 1780, "pressure": 80, "orientation": 3, "touch_major": 17}}],
    ["UPDATE", 1677239638.121478, {"0": {"id": 3677, "x": 564, "y": 1765, "pressure": 84, "orientation": 2, "touch_minor": 8, "touch_major": 17}}],
    ["UPDATE", 1677239638.133618, {"0": {"id": 3677, "x": 565, "y": 1746, "pressure": 78, "orientation": 2, "touch_minor": 17, "touch_major": 8}}],
    ["UPDATE", 1677239638.145096, {"0": {"id": 3677, "x": 565, "y": 1726, "pressure": 80, "orientation": 3, "touch_minor": 17, "touch_major": 17}}],
    ["UPDATE", 1677239638.157082, {"0": {"id": 3677, "x": 565, "y": 1701, "pressure": 79, "orientation": 3, "touch_minor": 17, "touch_major": 17}}],
    ["UPDATE", 1677239638.169108, {"0": {"id": 3677, "x": 564, "y": 1676, "pressure": 74, "orientation": 2, "touch_minor": 17, "touch_major": 8}}],
    ["UPDATE", 1677239638.181096, {"0": {"id": 3677, "x": 561, "y": 1649, "pressure": 76, "orientation": 4, "touch_minor": 17, "touch_major": 17}}],
    ["UPDATE", 1677239638.192963, {"0": {"id": 3677, "x": 558, "y": 1616, "pressure": 74, "orientation": 2, "touch_minor": 17, "touch_major": 8}}],
    ["UPDATE", 1677239638.204522, {"0": {"id": 3677, "x": 554, "y": 1588, "pressure": 73, "orientation": 2, "touch_minor": 17, "touch_major": 8}}],
    ["UPDATE", 1677239638.216115, {"0": {"id": 3677, "x": 549, "y": 1556, "pressure": 76, "orientation": 3, "touch_minor": 17, "touch_major": 17}}],
    ["UPDATE", 1677239638.228524, {"0": {"id": 3677, "x": 545, "y": 1529, "pressure": 70, "orientation": 1, "touch_minor": 8, "touch_major": 8}}],
    ["UPDATE", 1677239638.240422, {"0": {"id": 3677, "x": 540, "y": 1503, "pressure": 73, "orientation": 2, "touch_minor": 8, "touch_major": 17}}],
    ["UPDATE", 1677239638.252317, {"0": {"id": 3677, "x": 535, "y": 1477, "pressure": 70, "orientation": 1, "touch_minor": 8, "touch_major": 8}}],
    ["UPDATE", 1677239638.264255, {"0": {"id": 3677, "x": 530, "y": 1453, "pressure": 70, "orientation": 2, "touch_minor": 17, "touch_major": 8}}],
    ["UPDATE", 1677239638.276242, {"0": {"id": 3677, "x": 526, "y": 1432, "pressure": 73, "orientation": 3, "touch_minor": 17, "touch_major": 17}}],
    ["UPDATE", 1677239638.287988, {"0": {"id": 3677, "x": 523, "y": 1414, "pressure": 71, "orientation": 3, "touch_minor": 17, "touch_major": 17}}],
    ["UPDATE", 1677239638.299872, {"0": {"id": 3677, "x": 519, "y": 1398, "pressure": 68, "orientation": 2, "touch_minor": 17, "touch_major": 8}}],
    ["UPDATE", 1677239638.31179, {"0": {"id": 3677, "x": 516, "y": 1384, "pressure": 67, "orientation": 2, "touch_minor": 17, "touch_major": 8}}],
    ["UPDATE", 1677239638.323637, {"0": {"id": 3677, "x": 514, "y": 1372, "pressure": 67, "orientation": 2, "touch_minor": 17, "touch_major": 8}}],
    ["UPDATE", 1677239638.335656, {"0": {"id": 3677, "x": 512, "y": 1362, "pressure": 66, "orientation": 2, "touch_minor": 17, "touch_major": 8}}],
    ["UPDATE", 1677239638.347277, {"0": {"id": 3677, "x": 510, "y": 1354, "pressure": 65, "orientation": 2, "touch_minor": 17, "touch_major": 8}}],
    ["UPDATE", 1677239638.359313, {"0": {"id": 3677, "x": 507, "y": 1346, "pressure": 51, "orientation": 3, "touch_minor": 17, "touch_major": 17}}],
    ["RELEASE", 1677239638.394528, {"0": {}}],
]

EMUL_RECENT = [
    ["UPDATE", 1677239646.332618, {"0": {"id": 3678, "x": 508, "y": 1731, "pressure": 53}, "1": {"id": 3679, "x": 715, "y": 1747, "pressure": 44, "orientation": 1, "touch_minor": 8}}],
    ["UPDATE", 1677239646.354335, {"1": {"id": 3679, "x": 715, "y": 1745, "pressure": 49, "orientation": 1, "touch_minor": 8}}],
    ["UPDATE", 1677239646.365659, {"1": {"id": 3679, "x": 715, "y": 1741, "pressure": 53, "orientation": 2, "touch_minor": 8, "touch_major": 17}}],
    ["UPDATE", 1677239646.377602, {"0": {"id": 3678, "x": 508, "y": 1728, "pressure": 58}, "1": {"id": 3679, "x": 715, "y": 1736, "pressure": 52, "orientation": 2, "touch_minor": 8, "touch_major": 17}}],
    ["UPDATE", 1677239646.39012, {"0": {"id": 3678, "x": 508, "y": 1724, "pressure": 57, "orientation": 2, "touch_major": 8}, "1": {"id": 3679, "x": 715, "y": 1728, "pressure": 49, "orientation": 2, "touch_minor": 17, "touch_major": 8}}],
    ["UPDATE", 1677239646.401834, {"0": {"id": 3678, "x": 508, "y": 1715, "pressure": 55, "orientation": 2, "touch_major": 8}, "1": {"id": 3679, "x": 714, "y": 1718, "pressure": 52, "orientation": 2, "touch_minor": 17, "touch_major": 8}}],
    ["UPDATE", 1677239646.412896, {"0": {"id": 3678, "x": 508, "y": 1706, "pressure": 62, "orientation": 3, "touch_major": 17}, "1": {"id": 3679, "x": 712, "y": 1705, "pressure": 52, "orientation": 3, "touch_minor": 17, "touch_major": 17}}],
    ["UPDATE", 1677239646.425572, {"0": {"id": 3678, "x": 508, "y": 1694, "pressure": 57, "orientation": 2, "touch_major": 8}, "1": {"id": 3679, "x": 711, "y": 1689, "pressure": 47, "orientation": 2, "touch_minor": 17, "touch_major": 8}}],
    ["UPDATE", 1677239646.436952, {"0": {"id": 3678, "x": 508, "y": 1679, "pressure": 58, "orientation": 2, "touch_major": 8}, "1": {"id": 3679, "x": 709, "y": 1672, "pressure": 54, "orientation": 4, "touch_minor": 17, "touch_major": 17}}],
    ["UPDATE", 1677239646.449473, {"0": {"id": 3678, "x": 508, "y": 1663, "pressure": 59, "orientation": 3, "touch_major": 17}, "1": {"id": 3679, "x": 707, "y": 1653, "pressure": 48, "orientation": 2, "touch_minor": 17, "touch_major": 8}}],
    ["UPDATE", 1677239646.460595, {"0": {"id": 3678, "x": 507, "y": 1644, "pressure": 56, "orientation": 2, "touch_major": 8}, "1": {"id": 3679, "x": 704, "y": 1632, "pressure": 57, "orientation": 4, "touch_minor": 17, "touch_major": 17}}],
    ["UPDATE", 1677239646.473027, {"0": {"id": 3678, "x": 505, "y": 1625, "pressure": 62, "orientation": 4, "touch_major": 17}, "1": {"id": 3679, "x": 702, "y": 1610, "pressure": 49, "orientation": 2, "touch_minor": 17, "touch_major": 8}}],
    ["UPDATE", 1677239646.484565, {"0": {"id": 3678, "x": 504, "y": 1604, "pressure": 55, "orientation": 2, "touch_major": 8}, "1": {"id": 3679, "x": 698, "y": 1587, "pressure": 57, "orientation": 2, "touch_minor": 8, "touch_major": 17}}],
    ["UPDATE", 1677239646.496172, {"0": {"id": 3678, "x": 502, "y": 1584, "pressure": 64, "orientation": 4, "touch_major": 17}, "1": {"id": 3679, "x": 695, "y": 1563, "pressure": 49, "orientation": 2, "touch_minor": 17, "touch_major": 8}}],
    ["UPDATE", 1677239646.508724, {"0": {"id": 3678, "x": 501, "y": 1562, "pressure": 56, "orientation": 2, "touch_major": 8}, "1": {"id": 3679, "x": 691, "y": 1540, "pressure": 57, "orientation": 2, "touch_minor": 8, "touch_major": 17}}],
    ["UPDATE", 1677239646.520776, {"0": {"id": 3678, "x": 499, "y": 1540, "pressure": 64, "orientation": 3, "touch_major": 17}, "1": {"id": 3679, "x": 687, "y": 1516, "pressure": 48, "orientation": 1, "touch_minor": 8, "touch_major": 8}}],
    ["UPDATE", 1677239646.532607, {"0": {"id": 3678, "x": 498, "y": 1519, "pressure": 54, "orientation": 2, "touch_major": 8}, "1": {"id": 3679, "x": 683, "y": 1493, "pressure": 55, "orientation": 2, "touch_minor": 8, "touch_major": 17}}],
    ["UPDATE", 1677239646.544443, {"0": {"id": 3678, "x": 496, "y": 1498, "pressure": 59, "orientation": 2, "touch_major": 8}, "1": {"id": 3679, "x": 680, "y": 1471, "pressure": 52, "orientation": 1, "touch_minor": 8, "touch_major": 8}}],
    ["UPDATE", 1677239646.555427, {"0": {"id": 3678, "x": 495, "y": 1478, "pressure": 62, "orientation": 4, "touch_major": 17}, "1": {"id": 3679, "x": 677, "y": 1450, "pressure": 49, "orientation": 2, "touch_minor": 17, "touch_major": 8}}],
    ["UPDATE", 1677239646.567114, {"0": {"id": 3678, "x": 494, "y": 1460, "pressure": 54, "orientation": 2, "touch_major": 8}, "1": {"id": 3679, "x": 675, "y": 1432, "pressure": 52, "orientation": 2, "touch_minor": 8, "touch_major": 17}}],
    ["UPDATE", 1677239646.580004, {"0": {"id": 3678, "x": 492, "y": 1442, "pressure": 54, "orientation": 2, "touch_major": 8}, "1": {"id": 3679, "x": 674, "y": 1415, "pressure": 53, "orientation": 2, "touch_minor": 8, "touch_major": 17}}],
    ["UPDATE", 1677239646.59181, {"0": {"id": 3678, "x": 492, "y": 1427, "pressure": 58, "orientation": 2, "touch_major": 8}, "1": {"id": 3679, "x": 674, "y": 1401, "pressure": 49, "orientation": 2, "touch_minor": 8, "touch_major": 17}}],
    ["UPDATE", 1677239646.603953, {"0": {"id": 3678, "x": 491, "y": 1414, "pressure": 60, "orientation": 3, "touch_major": 17}, "1": {"id": 3679, "x": 674, "y": 1389, "pressure": 47, "orientation": 1, "touch_minor": 8, "touch_major": 8}}],
    ["UPDATE", 1677239646.615341, {"0": {"id": 3678, "x": 490, "y": 1403, "pressure": 59, "orientation": 3, "touch_major": 17}, "1": {"id": 3679, "x": 674, "y": 1378, "pressure": 46, "orientation": 1, "touch_minor": 8, "touch_major": 8}}],
    ["UPDATE", 1677239646.62764, {"0": {"id": 3678, "x": 489, "y": 1393, "pressure": 56, "orientation": 2, "touch_minor": 8, "touch_major": 17}, "1": {"id": 3679, "x": 674, "y": 1369, "pressure": 44, "orientation": 1, "touch_minor": 8, "touch_major": 8}}],
    ["UPDATE", 1677239646.638164, {"0": {"id": 3678, "x": 488, "y": 1382, "pressure": 52, "orientation": 1, "touch_minor": 8, "touch_major": 8}, "1": {"id": 3679, "x": 674, "y": 1362, "pressure": 43, "orientation": 1, "touch_minor": 8, "touch_major": 8}}],
    ["UPDATE", 1677239646.651424, {"0": {"id": 3678, "x": 486, "y": 1372, "pressure": 46, "orientation": 1, "touch_minor": 8, "touch_major": 8}, "1": {"id": 3679, "x": 675, "y": 1355, "pressure": 41, "orientation": 1, "touch_minor": 8, "touch_major": 8}}],
    ["UPDATE", 1677239646.66215, {"0": {"id": 3678, "x": 483, "y": 1361, "pressure": 27, "orientation": 1, "touch_minor": 8, "touch_major": 8}}],
    ["RELEASE", 1677239646.685691, {"1": {}}],
    ["UPDATE", 1677239646.685691, {"1": {"id": 3679, "x": 675, "y": 1355, "pressure": 41, "orientation": 1, "touch_minor": 8, "touch_major": 8}}],
    ["RELEASE", 1677239646.69694, {"0": {}}],
    ["UPDATE", 1677239646.69694, {"0": {"id": 3678, "x": 483, "y": 1361, "pressure": 27, "orientation": 1, "touch_minor": 8, "touch_major": 8}}],
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

    def update(self, finger):
        if finger.down_duration < 0.3:
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
