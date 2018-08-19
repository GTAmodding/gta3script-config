#!/usr/bin/env python2
"""
  Examples:
    py cmp_scmini.py ../config/gta3/commands.xml SCM.ini
    py cmp_scmini.py ../config/gtavc/commands.xml VCSCM.ini
    py cmp_scmini.py ../config/gtasa/commands.xml SASCM.ini
"""
import gta3sc
import sys

def read_scmini(filename):
    import re
    output = []
    indefs = False
    with open(filename) as f:
        for line in f.readlines():
            line = line.strip()
            if line == "" or line[0] == ';':
                continue
            if not indefs:
                indefs = (line == "[OPCODES]")
                continue
            match = re.match("^([A-Fa-f0-9]+)=([-\d]+),(.*)", line)
            assert match != None
            output.append((int(match.group(1), 16), int(match.group(2)), match.group(3).strip()))
        assert len(output) > 0
        return output

def main(xmlname, ininame):
    commands = gta3sc.read_config(xmlname).commands
    inidata  = read_scmini(ininame)

    commands_dict = {c.id: c for c in commands}
    inidata_dict  = {d[0]: d for d in inidata}

    count_bad = 0

    for entry in inidata:
        xcmd = commands_dict.get(entry[0])
        if xcmd is None:
            if not entry[0] in [0x416]: # Ignore NOPy LOAD_AND_LAUNCH_MISSION
                print("Missing opcode %.4X on XML." % (entry[0]))
                count_bad += 1
            continue

        if len(xcmd.args) != entry[1]:
            if not xcmd.name in ["SAVE_STRING_TO_DEBUG_FILE"]:
                if entry[1] != -1 or not xcmd.has_optional():
                    print("Mismatch on the number of arguments (%.4X:%s): INI %d != XML %d" %
                        (entry[0], xcmd.name, entry[1], len(xcmd.args)))
                    count_bad += 1
                continue

    if False: # III/VC SCM.INI are too old for those checks
        for xcmd in commands:
            if xcmd.supported:
                if inidata_dict.get(xcmd.id) == None:
                    print("Found a possibly unsupported opcode (%.4X:%s) as it's not present on INI." %
                        (xcmd.id, xcmd.name))
                    count_bad += 1


    if count_bad == 0:
        print("Everything correct.")
    else:
        sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: cmp_scmini.py <xmlfile> <inifile>")
        sys.exit(1)
    main(sys.argv[1], sys.argv[2])
