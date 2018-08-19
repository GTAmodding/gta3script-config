#!/usr/bin/env python2
"""
"""
import sys
import gta3sc
from gta3sc.bytecode import Scope, VarInfo
from collections import defaultdict
from itertools import chain

CONST_COMMANDS = set([
    "SET_VAR_INT_TO_CONSTANT",
    "SET_LVAR_INT_TO_CONSTANT",
    "IS_INT_VAR_EQUAL_TO_CONSTANT",
    "IS_INT_LVAR_EQUAL_TO_CONSTANT",
    "IS_INT_VAR_GREATER_THAN_CONSTANT",
    "IS_INT_LVAR_GREATER_THAN_CONSTANT",
    "IS_CONSTANT_GREATER_THAN_INT_VAR",
    "IS_CONSTANT_GREATER_THAN_INT_LVAR",
    "IS_INT_VAR_GREATER_OR_EQUAL_TO_CONSTANT",
    "IS_INT_LVAR_GREATER_OR_EQUAL_TO_CONSTANT",
    "IS_CONSTANT_GREATER_OR_EQUAL_TO_INT_VAR",
    "IS_CONSTANT_GREATER_OR_EQUAL_TO_INT_LVAR",
    "IS_GLOBAL_VAR_BIT_SET_CONST",
    "IS_LOCAL_VAR_BIT_SET_CONST",
    "SET_GLOBAL_VAR_BIT_CONST",
    "SET_LOCAL_VAR_BIT_CONST",
    "CLEAR_GLOBAL_VAR_BIT_CONST",
    "CLEAR_LOCAL_VAR_BIT_CONST",
])

SET_MODELS_ENUMS = set(["DEFAULTMODEL", "MODEL"])


def main(ir2file, xmlfile):
    config = gta3sc.read_config(xmlfile)
    ir2 = gta3sc.read_ir2(ir2file)

    commands    = {cmd.name: cmd for cmd in config.commands}
    alternators = defaultdict(set, {alt.name: set(alt.alters) for alt in config.alternators})
    enums       = {enum.name: {v: k for k,v in enum.constants.iteritems()} for enum in config.enums}

    scopes = ir2.discover_scopes()
    current_scope = None
    first_scope = scopes[0] if len(scopes) > 0 else None

    global_vars = ir2.discover_global_vars(config=config)
    local_vars = None

    commands = {cmd.name: cmd for cmd in config.commands}
    cmds_all_alternatives = set(chain.from_iterable(map(lambda x: x.alters, config.alternators)))

    enum_args = defaultdict(set)   # All values used for a enum that exists
    unknown_values = set()          # Values without a matching enum
    commands_enum = set()           # Commands missing enum info

    highest_default_id = max(enums["DEFAULTMODEL"].iterkeys())

    print("--------------------------")

    for off, data in ir2:

        if current_scope == None:
            if first_scope != None and off >= first_scope.start:
                current_scope = Scope.from_offset(off, scopes)
                assert current_scope != None
        elif not current_scope.owns_offset(off):
            current_scope = Scope.from_offset(off, scopes)
            assert current_scope != None
            local_vars = ir2.discover_local_vars(current_scope, config=config)

        if data.is_command() and data.name in CONST_COMMANDS:
            argvar   = data.args[0] if not data.name.startswith("IS_CONSTANT_") else data.args[1]
            argconst = data.args[1] if not data.name.startswith("IS_CONSTANT_") else data.args[0]
            assert argvar.is_var()
            assert argconst.is_number()
            varlist  = local_vars if argvar.is_local() else global_vars
            var = VarInfo.from_offset(argvar.get_offset(), varlist)
            if len(var.enums) > 0:
                for ve in var.enums:
                    enum_args[ve].add(argconst.value)
            else:
                print("Unknown value %d at %s" % (argconst.value, str(data)))
        elif data.is_command() and data.name in cmds_all_alternatives:
            pass
        elif data.is_command():
            cmdinfo = commands[data.name]
            for i, arg in enumerate(data.args):
                arginfo = cmdinfo.get_arg(i)
                if len(arginfo.enums) > 0:
                    assert len(arginfo.enums) == 1
                    enum_name = arginfo.enums[0]
                    if arg.is_number():
                        enum_args[enum_name].add(arg.value)
                        pass
                    else:
                        pass # TODO
                elif not arginfo.out:
                    if arg.is_var():
                        varlist = local_vars if arg.is_local() else global_vars
                        var = VarInfo.from_offset(arg.get_offset(), varlist)
                        if len(var.enums) > 0:
                            for enum_name in var.enums:
                                commands_enum.add((cmdinfo.name, i, enum_name))

    for info in commands_enum:
        print("Command %s has enum %s at argument %d" % (info[0], info[2], info[1]))

    for name, values in enum_args.iteritems():
        
        if name == "MODEL":
            missing = sorted(v for v in values if v > highest_default_id)
        elif name == "DEFAULTMODEL":
            enum = enums[name]
            missing = sorted(v for v in values if v >= 0 and v not in enum)
        else:
            enum = enums.get(name, {})
            missing = sorted(v for v in values if v not in enum)
        
        if len(missing) > 0:
            print("Values missing from enum %s: %s" % (name, missing))


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: discover_constants.py <ir2_script> <xmlfile>")
        sys.exit(1)
    main(sys.argv[1], sys.argv[2])
