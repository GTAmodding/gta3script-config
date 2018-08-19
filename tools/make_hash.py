#!/usr/bin/env python2
"""
"""
import gta3sc
from gta3sc.config import one_at_a_time
import sys

def main(xmlfile):
    config = gta3sc.read_config(xmlfile)

    for cmd in config.commands:
        cmd.hash = one_at_a_time(cmd.name)

    config.save_config(xmlfile)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: make_hash.py <xmlfile>")
        sys.exit(1)
    main(sys.argv[1])
