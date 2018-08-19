#!/usr/bin/env python2
"""
  This utility scans a script in search for entity information missing in the commands definition file.

  Please use IR2 scripts decompiled using linear-sweep!

  Scripts with erroneous entity information (e.g. those built with SCM assemblers) are prone
  to trigger an assertion.

  Examples:
    $GTA3SC --config=gtasa main.scm -emit-ir2 -o main.ir2
    py discover_entity_commands.py main.ir2 ../config/gtasa
"""
import sys
import gta3sc
from gta3sc.bytecode import Scope
from itertools import chain
from collections import defaultdict
from bisect import *

def find_le(a, x):
    'Find rightmost value less than or equal to x'
    i = bisect_right(a, x)
    return a[i-1] if i else None

class VariableInfo:
    def __init__(self, ir2, scopes):
        self.gvars = {}
        self.local_scopes = {scope: {} for scope in scopes}
        self.global_arrays = ir2.discover_global_arrays()
        self.local_arrays = {scope: ir2.discover_local_arrays(scope) for scope in scopes}
        self.global_arrays_keys = sorted(voff for voff in self.global_arrays.iterkeys())
        self.local_arrays_keys = {scope: sorted(voff for voff in arrays.iterkeys()) for scope, arrays in self.local_arrays.iteritems()}
        self.globals_arrays_keys = []
        self.local_arrays_keys = {scope: [] for scope, arrays in self.local_arrays.iteritems() }

    def get_var_base(self, arg, scope):
        assert not arg.is_array()
        start_offset = None
        end_offset = None

        if arg.is_local():
            voff = find_le(self.local_arrays_keys[scope], arg.offset)
            if voff != None:
                start_offset = voff
                end_offset = start_offset + self.local_arrays[scope][voff]
        else:
            voff = find_le(self.global_arrays_keys, arg.offset)
            if voff != None:
                start_offset = voff
                end_offset = start_offset + self.global_arrays[voff]

        if start_offset != None and arg.offset >= start_offset and arg.offset < end_offset:
            return start_offset
        return arg.offset

    def register_var(self, arg, entity_type, scope):
        assert arg.is_var()
        arg = arg.base if arg.is_array() else arg
        offset = self.get_var_base(arg, scope)
        if arg.is_local():
            assert (offset % 4) == 0
            return self.register_local_in_scope(scope, offset / 4, entity_type)
        else:
            assert self.gvars.get(offset) in (None, entity_type)
            self.gvars[offset] = entity_type

    def register_local_in_scope(self, scope, index, entity_type):
        # TODO array base
        var_offset = index * 4
        assert self.local_scopes[scope].get(var_offset) in (None, entity_type)
        self.local_scopes[scope][var_offset] = entity_type

    def get_entity_type(self, arg, scope):
        assert arg.is_var()
        arg = arg.base if arg.is_array() else arg
        offset = self.get_var_base(arg, scope)
        if arg.is_local():
           return self.local_scopes[scope].get(offset)
        else:
            return self.gvars.get(offset)

def main(ir2file, xmlfile):
    config = gta3sc.read_config(xmlfile)
    ir2 = gta3sc.read_ir2(ir2file)

    scopes = ir2.discover_scopes()
    current_scope = None
    first_scope = scopes[0] if len(scopes) > 0 else None

    commands = {cmd.name: cmd for cmd in config.commands}
    cmds_set = set(config.get_alternator("SET"))
    cmds_is_thing_equal_to_thing = set(config.get_alternator("IS_THING_EQUAL_TO_THING"))
    cmds_all_alternatives = set(chain.from_iterable(map(lambda x: x.alters, config.alternators)))

    varinfo = VariableInfo(ir2, scopes)
    commands_to_tweak = defaultdict(set)

    print("--------------------------")

    for off, data in ir2:

        if current_scope == None:
            if first_scope != None and off >= first_scope.start:
                current_scope = Scope.from_offset(off, scopes)
                assert current_scope != None
        elif not current_scope.owns_offset(off):
            current_scope = Scope.from_offset(off, scopes)
            assert current_scope != None

        if data.is_command() and data.name in ("START_NEW_SCRIPT", "START_NEW_STREAMED_SCRIPT"):
            if data.name == "START_NEW_SCRIPT":
                assert data.args[0].is_label()
                script_offset = ir2.offset_from_label(data.args[0].value)
                script_scope  = Scope.from_offset(script_offset, scopes)
            else: # START_NEW_STREAMED_SCRIPT
                assert data.args[0].is_number()
                script_offset = ir2.offset_from_streamed(data.args[0].value)
                script_scope = Scope.from_offset(script_offset, scopes)
            assert script_scope != None
            for i, arg in enumerate(data.args[1:]):
                if arg.is_var():
                    entity_type = varinfo.get_entity_type(arg, current_scope)
                    if entity_type:
                        varinfo.register_local_in_scope(script_scope, i, entity_type)
        elif data.is_command() and data.name in cmds_set:
            assert data.args[0].is_var()
            if data.args[1].is_var():
                rhs_entity = varinfo.get_entity_type(data.args[1], current_scope)
                if rhs_entity:
                    varinfo.register_var(data.args[0], rhs_entity, current_scope)
        elif data.is_command() and data.name in cmds_all_alternatives:
            # ignore commands which are part of alternators
            pass
        elif data.is_command():
            cmd = commands.get(data.name)
            for i, arg in enumerate(data.args):
                cmdarg = cmd.get_arg(i)
                if cmdarg.out and cmdarg.entity:
                    varinfo.register_var(arg, cmdarg.entity, current_scope)
                elif arg.is_var():
                    var_entity_type = varinfo.get_entity_type(arg, current_scope)
                    if var_entity_type != None and cmdarg.entity != var_entity_type:
                        commands_to_tweak[cmd.name].add((i, var_entity_type))
                    elif var_entity_type == None and cmdarg.entity != None:
                        # this check does not work as intended since we don't have enough information
                        # about the source code (e.g. arrays always indexed by a literal)
                        #print(str(data), i, cmdarg.entity, varinfo.get_var_base(arg, current_scope),
                        #        current_scope.find_script_name(ir2), off, current_scope)
                        pass

    # Prone to mistakes,so not going to update the XML automatically.
    for cmdname, args in commands_to_tweak.iteritems():
        for info in args:
            print("Command %s argument %d is missing entity %s" % (cmdname, info[0], info[1]))




if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: discover_entity_commands.py <ir2_script> <xmlfile>")
        sys.exit(1)
    main(sys.argv[1], sys.argv[2])
