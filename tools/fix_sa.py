#!/usr/bin/env python2
"""
    This script was once used to help in the fixing gtasa/ definitions and is currently useless.
    It may be useful again in the future, so we're leaving it in the repository.
"""

import gta3sc
from collections import defaultdict, namedtuple

def print_once(iterator):
    printed = set()
    for x in iterator:
        if x not in printed:
            printed.add(x)
            print(x)

def copy_properties(gta3_commands, gtavc_commands, gtasa_commands):
    for cmdid, sacmd in gtasa_commands.iteritems():
        print("Copying properties for %s:%s..." % (hex(cmdid), sacmd.name))
        vccmd = gtavc_commands.get(cmdid)
        g3cmd = gtavc_commands.get(cmdid)
        if vccmd is not None and sacmd.same_behaviour(vccmd):
            #print(hex(cmdid), vccmd.name, sacmd.name)     
            assert vccmd.name == sacmd.name or vccmd.name in ('SWITCH_HELICOPTER', 'SET_CAR_CHANGE_LANE')

            for s,v in zip(sacmd.args, vccmd.args):
                assert s.ref == v.ref
                assert s.out == v.out
                assert s.entity == None or s.entity == v.entity
                assert len(s.enums) == 0 or s.enums == v.enums
                assert s.allow_const or s.allow_const == v.allow_const
                assert s.allow_gvar or s.allow_gvar == v.allow_gvar
                assert s.allow_lvar or s.allow_lvar == v.allow_lvar
                s.allow_const = v.allow_const
                s.allow_gvar  = v.allow_gvar
                s.allow_lvar  = v.allow_lvar
                s.entity      = v.entity
                s.enums       = v.enums

        elif g3cmd is not None and sacmd.same_behaviour(g3cmd):
            assert False
        else:
            if len(sacmd.args) == 0 and not sacmd.supported:
                pass
            elif sacmd.id > 0x5a8:
                #print(sacmd.name)
                pass
            else:
                #print(sacmd.name)
                #could add a sacmd.name in ('',...) check
                pass

def commands_with_model_args(commands):
    for cmd in commands.itervalues():
        for arg in cmd.args:
            if any(arg.has_enum("MODEL") for arg in cmd.args):
                yield cmd.name

def argument_descriptions(commands):
    for cmd in commands.itervalues():
        for arg in cmd.args:
            yield arg.desc

def discover_properties_from_description(commands):

    temp_all_descs = list(argument_descriptions(commands))
    assert len(set(temp_all_descs)) == len(set(x.upper() for x in temp_all_descs))
    del temp_all_descs

    Enum = namedtuple('Enum', ['defined_at', 'name'])
    Entity = namedtuple('Entity', ['defined_at', 'name'])

    dictionary = {}
    used_in_cmds = defaultdict(list)
    for cmd in commands.itervalues():
        for arg in cmd.args:
            if arg.desc:
                if arg.desc in ("Model ID",):
                    continue
                used_in_cmds[arg.desc].append(cmd)
                mydata = dictionary.get(arg.desc)
                newdata = None
                try:
                    if mydata is None:
                        if len(arg.enums) > 0:
                            newdata = Enum(cmd, arg.enums[0])
                            assert len(arg.enums) == 1
                            assert arg.entity is None
                        if arg.entity is not None:
                            newdata = Entity(cmd, arg.entity)
                            assert len(arg.enums) == 0
                        if newdata is not None:
                            mydata = newdata
                            dictionary[arg.desc] = newdata
                    elif isinstance(mydata, Enum):
                        assert arg.entity is None
                        if len(arg.enums) > 0:
                            assert len(arg.enums) == 1
                            assert mydata.name == arg.enums[0]
                    elif isinstance(mydata, Entity):
                        assert len(arg.enums) == 0
                        if arg.entity is not None:
                            assert mydata.name == arg.entity
                except AssertionError: # HACKY
                    print("======= PROPERTIES CONFLICT ==========")
                    print("Argument Description: %s" % (arg.desc))
                    if mydata is not None:
                        print("Previous property found in %s with value %s and type %s." % (mydata.defined_at.name, mydata.name, type(mydata).__name__))
                    else:
                        print("Previous data never found.")
                    if newdata is not None:
                        print("Currently parsing data is in %s with value %s and type %s" % (newdata.defined_at.name, newdata.name, type(newdata).__name__))
                    else:
                        print("Currently parsing data is in %s" % (cmd.name))
                    print("=====================================")
                    raise 

    #print(dictionary.get("Boolean true/false").defined_at.name)
    assert dictionary.get("Model ID") == None
    assert dictionary.get("Boolean true/false") == None

    for desc, data in dictionary.iteritems():
        print("%s: %s of type %s" % (desc, data.name, type(data).__name__))
        for cmd in used_in_cmds.get(desc):
            print("    %s" % (cmd.name))
        print("")

    for cmd in commands.itervalues():
        for arg in cmd.args:
            data = dictionary.get(arg.desc)
            if data is None:
                pass
            elif isinstance(data, Enum):
                if not arg.enums:
                    arg.enums.append(data.name)
            elif isinstance(data, Entity):
                if not arg.entity:
                    arg.entity = data.name

def find_missing_properties_from_command_name(commands_notfiltered):

    entity_types = set()
    enum_types = set()
    for cmd in commands_notfiltered.itervalues():
        for arg in cmd.args:
            if arg.enums:  enum_types.add(arg.enums[0])
            if arg.entity: entity_types.add(arg.entity)

    commands = {c.id: c for c in commands_notfiltered.itervalues() if c.supported}

    entity_missing = defaultdict(list)
    enum_missing = defaultdict(list)

    for cmd in commands.itervalues():
        for name in entity_types:
            if name in cmd.name:
                if not any(a.entity == name for a in cmd.args):
                    entity_missing[name].append(cmd)

    for cmd in commands.itervalues():
        for name in enum_types:
            if name in cmd.name:
                if not any(a.enums and a.enums[0] == name for a in cmd.args):
                    enum_missing[name].append(cmd)

    print("============================================")
    print("Possible Entities Missing")
    print("============================================")
    for name, cmdlist in entity_missing.iteritems():
        print("    %s" % (name))
        for cmd in cmdlist:
            print("        %s" % (cmd.name))
        print("")

    print("============================================")
    print("Possible Enums Missing")
    print("============================================")
    for name, cmdlist in enum_missing.iteritems():
        print("    %s" % (name))
        for cmd in cmdlist:
            print("        %s" % (cmd.name))
        print("")


def remove_enums_from_outputs(commands):
    for cmd in commands.itervalues():
        for arg in cmd.args:
            if arg.out and len(arg.enums) > 0:
                print(cmd.name)
                arg.enums = []

def add_allow_const_false_to_out_params(commands):
    for cmd in commands.itervalues():
        for arg in cmd.args:
            if arg.out:
                arg.allow_const = False

def main():
    gtasa = gta3sc.read_config("gtasa/commands.xml")
    gtavc = gta3sc.read_config("gtavc/commands.xml")
    gta3  = gta3sc.read_config("gta3/commands.xml")

    gtasa_commands = {c.id: c for c in gtasa.commands}
    gtavc_commands = {c.id: c for c in gtavc.commands}
    gta3_commands  = {c.id: c for c in gta3.commands}

    discover_properties_from_description(gtasa_commands)

    gtasa.save_config("gtasa/commands.xml")



if __name__ == "__main__":
    main()


