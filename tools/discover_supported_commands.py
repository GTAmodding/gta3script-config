#!/usr/bin/env python2
"""
"""
import sys
import gta3sc
from gta3sc.bytecode import Scope
from itertools import chain
from collections import defaultdict
from bisect import *

def main(ir2file, xmlfile):
    config = gta3sc.read_config(xmlfile)
    ir2 = gta3sc.read_ir2(ir2file)

    commands = {cmd.name: cmd for cmd in config.commands}

    for off, data in ir2:
        if data.is_command():
            if not data.name in commands:
                print("Missing command %s" % data.name)
            else:
                cmd = commands[data.name]
                if not cmd.supported:
                    cmd.supported = True
                    print("Command %s is actually supported" % data.name)

    config.save_config(xmlfile)

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: discover_supported_commands.py <ir2_script> <xmlfile>")
        sys.exit(1)
    main(sys.argv[1], sys.argv[2])
