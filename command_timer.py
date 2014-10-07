#!/usr/bin/env python

import argparse
from maas_common import metric, status_err, status_ok
import os
import shlex
import subprocess
import time

def command_timer(command):
    start = time.time()
    with open(os.devnull, 'w') as devnull:
        subprocess.check_call(shlex.split(command),
                              stdout=devnull,
                              stderr=subprocess.STDOUT)
    return time.time() - start

def main():
    parser = argparse.ArgumentParser(description='Measure time to run '
                                                 ' commands.')
    parser.add_argument('commands',
                        nargs='+',
                        help='Supply one or more arguments in the format: '
                             '"metric1_name=command1"')
    args = parser.parse_args()

    commands = {}
    for arg in args.commands:
        name, cmd = arg.split('=', 1)
        commands[name] = cmd

    times = {}
    for name, cmd in commands.viewitems():
        try:
            time = command_timer(cmd)
        except Exception as e:
            status_err(e)
        else:
           times[name] = time * 1000
    status_ok()
    for name, time in times.viewitems():
        metric(name, 'double', time, 'milliseconds')

if __name__ == '__main__':
    main()
