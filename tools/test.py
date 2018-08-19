#!/usr/bin/env python2
import gta3sc
import sys

def main(xmlfile, clear_useless_data):
    config = gta3sc.read_config(xmlfile)
    commands = config.commands

    myset = set()
    for cmd in commands:
        for arg in cmd.args:
            if arg.desc:
                if arg.desc[0] in ['X', 'Y', 'Z'] or arg.desc in ["Radius", "Angle", "Rotation"]:
                    arg.desc = arg.desc
                elif arg.desc.startswith("Script ID"):
                    arg.desc = "Streamed Script"
                elif arg.desc.startswith("Time"):
                    arg.desc = "Time"
                elif arg.desc.startswith("Boolean"):
                    arg.desc = "Bool"
                elif arg.desc.startswith("Width"):
                    arg.desc = "Width"
                elif arg.desc.startswith("Height"):
                    arg.desc = "Height"
                elif arg.desc == "Red (0-255)":
                    arg.desc = "Red"
                elif arg.desc == "Green (0-255)":
                    arg.desc = "Green"
                elif arg.desc == "Blue (0-255)":
                    arg.desc = "Blue"
                elif arg.desc == "Alpha (0-255)":
                    arg.desc = "Alpha"
                elif arg.desc == "2D Pixel X":
                    arg.desc = "2D Pixel X"
                elif arg.desc == "2D Pixel Y":
                    arg.desc = "2D Pixel Y"
                else:
                    arg.desc = ""

    config.save_config(xmlfile)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: test.py <xmlfile>")
        sys.exit(1)
    main(sys.argv[1], len(sys.argv) > 2)
