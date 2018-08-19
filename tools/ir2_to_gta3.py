#!/usr/bin/env python2
"""
  Examples:
    py ir2_to_gta3.py main.ir2 ../config/gta3 output/
"""
import sys, os, errno
import gta3sc
from gta3sc.bytecode import VarInfo, Scope
from gta3sc.bytecode import DATATYPE_GLOBALVAR_NUMBER
from gta3sc.bytecode import DATATYPE_GLOBALVAR_TEXTLABEL
from gta3sc.bytecode import DATATYPE_GLOBALVAR_TEXTLABEL16
from gta3sc.bytecode import BYTECODE_OFFSET_MAIN
from gta3sc.bytecode import BYTECODE_OFFSET_MISSION
from gta3sc.bytecode import BYTECODE_OFFSET_STREAMED
from collections import defaultdict

TIMER_INDICES = (-1, -1)
MISSION_LVAR_BEGIN = 0

STREAM_COMMANDS = set([
    "REGISTER_STREAMED_SCRIPT_INTERNAL",
    "REGISTER_SCRIPT_BRAIN_FOR_CODE_USE",
    "REGISTER_ATTRACTOR_SCRIPT_BRAIN_FOR_CODE_USE",
    "STREAM_SCRIPT",
    "HAS_STREAMED_SCRIPT_LOADED",
    "MARK_STREAMED_SCRIPT_AS_NO_LONGER_NEEDED",
    "REMOVE_STREAMED_SCRIPT",
    "REGISTER_STREAMED_SCRIPT",
    "START_NEW_STREAMED_SCRIPT",
    "GET_NUMBER_OF_INSTANCES_OF_STREAMED_SCRIPT",
    "ALLOCATE_STREAMED_SCRIPT_TO_RANDOM_PED",
    "ALLOCATE_STREAMED_SCRIPT_TO_OBJECT",
    "REGISTER_OBJECT_SCRIPT_BRAIN_FOR_CODE_USE",
    "ALLOCATE_STREAMED_SCRIPT_TO_PED_GENERATOR",
    "SWITCH_OBJECT_BRAINS",
])

SA_VAR_ARRAYS = [
#   SCOPE       VAR
    (None,      VarInfo(4*2706, "INT", 15)),
    (None,      VarInfo(4*528, "INT", 4)),
    (None,      VarInfo(4*1717, "INT", 18)),
    ('LA1FIN2', VarInfo(4*233, "INT", 2)),
    ('LA1FIN2', VarInfo(4*235, "INT", 3)),
    ('MUSIC3',  VarInfo(4*66, "INT", 2)),
    ('MUSIC3',  VarInfo(4*69, "INT", 2)),
    ('SCRASH3', VarInfo(4*60, "INT", 3)),
    ('WUZI1',   VarInfo(4*101, "INT", 3)),
    ('STEAL2',  VarInfo(4*92, "INT", 3)),
    ('HEIST2',  VarInfo(4*165, "INT", 2)),
    ('RIOT2',   VarInfo(4*37, "INT", 6)),
    ('RIOT2',   VarInfo(4*43, "INT", 6)),
    ('RIOT2',   VarInfo(4*49, "INT", 6)),
    ('RIOT2',   VarInfo(4*55, "INT", 6)),
    ('RIOT2',   VarInfo(4*61, "INT", 6)),
    ('RIOT2',   VarInfo(4*79, "INT", 6)),
    ('RIOT2',   VarInfo(4*96, "INT", 6)),
    ('RIOT2',   VarInfo(4*102, "INT", 6)),
    ('RIOT2',   VarInfo(4*108, "INT", 6)),
    ('RIOT2',   VarInfo(4*114, "INT", 6)),
    ('RIOT2',   VarInfo(4*120, "INT", 6)),
    ('RIOT2',   VarInfo(4*132, "INT", 6)),
]

def converted_arg(ir2, arg, arginfo, global_vars, local_vars, enums=None, no_index=False):
    if arg.is_number():
        if arg.is_float():
            """
            output = "%.12f" % arg.value
            output = output.rstrip("0")
            if output.endswith("."):
                output += "0"
            """
            output = "%.6f" % arg.value
            output = output.rstrip("0")
            if output.endswith("."):
                output += "0"
            return output
        else:
            if enums != None and len(arginfo.enums) > 0:
                if arginfo.enums[0] == "MODEL":
                    if arg.value < 0:
                        return ir2.get_model(-arg.value - 1) or str(arg.value)
                    else:
                        return enums["DEFAULTMODEL"].get(arg.value) or str(arg.value)
                else:
                    enum = enums.get(arginfo.enums[0])
                    if enum != None:
                        return enum.get(arg.value, str(arg.value))
            elif enums != None and arginfo.desc.startswith("Bool") and arg.value in (0,1):
                return ("FALSE", "TRUE")[arg.value]
            return str(arg.value)
    elif arg.is_label():
        return arg.value.lower()
    elif arg.is_string():
        # TODO escaping and quoted strings?
        if arg.is_buffer128():
            return '"%s"' % arg.value
        else:
            return arg.value.upper()
    elif arg.is_var():
        if arg.is_array():
            base = converted_arg(ir2, arg.base, arginfo, global_vars, local_vars, enums=enums, no_index=True)
            index = converted_arg(ir2, arg.index, None, global_vars, local_vars, enums=None)
            return "%s[%s]" % (base, index)
        elif arg.is_local() and arg.offset in (TIMER_INDICES[0] * 4, TIMER_INDICES[1] * 4):
            if arg.offset == TIMER_INDICES[0] * 4:
                return "timera"
            else:
                return "timerb"
        else:
            assert (arg.offset % 4) == 0
            index = arg.offset / 4
            arrsufix = ""
            prefix = 'l' if arg.is_local() else ''
            var = VarInfo.from_offset(arg.offset, local_vars if arg.is_local() else global_vars)
            if not no_index and var and var.size:
                index = var.start_offset / 4
                arrsufix = "[%d]" % var.index_from_offset(arg.offset)
            if arg.get_datatype() in (DATATYPE_GLOBALVAR_TEXTLABEL, DATATYPE_GLOBALVAR_TEXTLABEL16):
                assert arginfo.optional == False
                return ("$%svar_%s%s" if arginfo.allow_const else "%svar_%s%s") % (prefix, index, arrsufix)
            else:
                return "%svar_%s%s" % (prefix, index, arrsufix)
    else:
        assert False

def find_constant_for_var(argvar, argconst, global_vars, local_vars, enums):
    assert argvar.is_var()
    assert argconst.is_number()

    constant = None

    if argvar.is_local():
        var = VarInfo.from_offset(argvar.get_offset(), local_vars)
    else:
        var = VarInfo.from_offset(argvar.get_offset(), global_vars)

    if len(var.enums) > 0:
        for ve in var.enums:
            enum_dict = enums.get(ve)
            if enum_dict is not None:
                constant = enum_dict.get(argconst.value)
                if constant is not None:
                    break

    if constant is None:
        constant = enums["DEFAULTMODEL"].get(argconst.value)

    #assert constant != None
    if constant == None:
        #print("############## MISSING CONSTANT, USING 9999999")
        #constant = "9999999"
        return str(argconst.value)

    return constant

def get_args_for_expr(ir2, data, cmdinfo, global_vars, local_vars, enums):

    args = [converted_arg(ir2, data.args[0], cmdinfo.get_arg(0), global_vars, local_vars),
            converted_arg(ir2, data.args[1], cmdinfo.get_arg(1), global_vars, local_vars)]

    if data.name.startswith("IS_CONSTANT_") or data.name.endswith("_CONSTANT"):
        tup = (1, 0) if data.name.endswith("_CONSTANT") else (0, 1)
        const_id = tup[0]
        var_id   = tup[1]
        args[const_id] = find_constant_for_var(data.args[var_id], data.args[const_id], global_vars, local_vars, enums)

    return args

def converted_expr(ir2, data, cmdinfo, op, global_vars, local_vars, enums):
    args = get_args_for_expr(ir2, data, cmdinfo, global_vars, local_vars, enums)
    if data.name.startswith("IS_CONSTANT_") or data.name.endswith("_CONSTANT"):
        if args[0].isdigit() or args[1].isdigit(): # couldn't find constant
            return "%s%s %s %s" % ("NOT " if data.not_flag else "", data.name, args[0], args[1])
    return "%s%s %s %s" % ("NOT " if data.not_flag else "", args[0], op, args[1])

def converted_data(ir2, data, commands, alternators, enums, global_vars, local_vars, filename_by_offset=None, alternative_name=None):
    if data.is_label():
        return "%s:" % data.name
    elif data.is_command():
        cmdinfo = commands[data.name]
        not_prefix = "NOT " if data.not_flag else ""
        output = not_prefix
        cmdname = data.name if not alternative_name else alternative_name
        if cmdname in alternators["SET"]:
            return converted_expr(ir2, data, cmdinfo, '=', global_vars, local_vars, enums)
        elif cmdname in alternators["CSET"]:
            return converted_expr(ir2, data, cmdinfo, '=#', global_vars, local_vars, enums)
        elif cmdname in alternators["ADD_THING_TO_THING"]:
            return converted_expr(ir2, data, cmdinfo, '+=', global_vars, local_vars, enums)
        elif cmdname in alternators["SUB_THING_FROM_THING"]:
            return converted_expr(ir2, data, cmdinfo, '-=', global_vars, local_vars, enums)
        elif cmdname in alternators["MULT_THING_BY_THING"]:
            return converted_expr(ir2, data, cmdinfo, '*=', global_vars, local_vars, enums)
        elif cmdname in alternators["DIV_THING_BY_THING"]:
            return converted_expr(ir2, data, cmdinfo, '/=', global_vars, local_vars, enums)
        elif cmdname in alternators["IS_THING_GREATER_THAN_THING"]:
            return converted_expr(ir2, data, cmdinfo, '>', global_vars, local_vars, enums)
        elif cmdname in alternators["IS_THING_GREATER_OR_EQUAL_TO_THING"]:
            return converted_expr(ir2, data, cmdinfo, '>=', global_vars, local_vars, enums)
        elif cmdname in alternators["ADD_THING_TO_THING_TIMED"]:
            return converted_expr(ir2, data, cmdinfo, '+=@', global_vars, local_vars, enums)
        elif cmdname in alternators["SUB_THING_FROM_THING_TIMED"]:
            return converted_expr(ir2, data, cmdinfo, '-=@', global_vars, local_vars, enums)
        elif cmdname in alternators["IS_THING_EQUAL_TO_THING"]:
            if data.name.startswith("IS_CONSTANT_") or data.name.endswith("_CONSTANT"):
                args = get_args_for_expr(ir2, data, cmdinfo, global_vars, local_vars, enums)
                if not args[0].isdigit() and not args[1].isdigit(): # could convert constant
                    return "%s%s %s %s" % (not_prefix, "IS_THING_EQUAL_TO_THING", args[0], args[1])
                else:
                    return "%s%s %s %s" % (not_prefix, data.name, args[0], args[1])
            return converted_data(ir2, data, commands, alternators, enums, global_vars, local_vars, alternative_name='IS_THING_EQUAL_TO_THING')
        elif cmdname in alternators["ABS"]:
            return converted_data(ir2, data, commands, alternators, enums, global_vars, local_vars, alternative_name='ABS')
        elif cmdname in alternators["IS_BIT_SET"]:
            return converted_data(ir2, data, commands, alternators, enums, global_vars, local_vars, alternative_name='IS_BIT_SET')
        elif cmdname in alternators["SET_BIT"]:
            return converted_data(ir2, data, commands, alternators, enums, global_vars, local_vars, alternative_name='SET_BIT')
        elif cmdname in alternators["CLEAR_BIT"]:
            return converted_data(ir2, data, commands, alternators, enums, global_vars, local_vars, alternative_name='CLEAR_BIT')
        elif cmdname in alternators["IS_EMPTY"]:
            return converted_data(ir2, data, commands, alternators, enums, global_vars, local_vars, alternative_name='IS_EMPTY')
        elif cmdname in ("SET_TOTAL_NUMBER_OF_MISSIONS", "SET_PROGRESS_TOTAL", "SET_COLLECTABLE1_TOTAL"):
            return "%s 0" % (cmdname)
        elif cmdname == "SKIP_CUTSCENE_START_INTERNAL":
            return "SKIP_CUTSCENE_START"
        elif cmdname == "GOSUB_FILE":
            assert data.args[1].is_label()
            arg1 = os.path.basename(filename_by_offset[ir2.offset_from_label(data.args[1].value)])
            arg0 = converted_arg(ir2, data.args[0], cmdinfo.get_arg(0), global_vars, local_vars, enums=enums)
            return "GOSUB_FILE %s %s" % (arg0, arg1)
        elif cmdname == "LAUNCH_MISSION":
            assert data.args[0].is_label()
            arg0 = os.path.basename(filename_by_offset[ir2.offset_from_label(data.args[0].value)])
            return "LAUNCH_MISSION %s" % (arg0)
        elif cmdname == "LOAD_AND_LAUNCH_MISSION_INTERNAL":
            assert data.args[0].is_number()
            mission_offset = ir2.offset_from_mission(data.args[0].value)
            return "LOAD_AND_LAUNCH_MISSION %s" % os.path.basename(filename_by_offset[mission_offset])
        elif cmdname in STREAM_COMMANDS:
            assert data.args[0].is_number()
            if cmdname == "REGISTER_STREAMED_SCRIPT_INTERNAL":
                cmdname = "REGISTER_STREAMED_SCRIPT"
            output += cmdname
            for i, arg in enumerate(data.args):
                if i == 0:
                    streamed_offset = ir2.offset_from_streamed(data.args[0].value)
                    output += " %s" % os.path.basename(filename_by_offset[streamed_offset])
                else:
                    output += " %s" % converted_arg(ir2, arg, cmdinfo.get_arg(i), global_vars, local_vars, enums=enums)
            return output
        else:
            output += cmdname
            for i, arg in enumerate(data.args):
                output += " %s" % converted_arg(ir2, arg, cmdinfo.get_arg(i), global_vars, local_vars, enums=enums)
            return output
    else:
        assert False

def print_vars(stream, vars, is_local, is_mission, tab=0):
    any_var = False
    last_var_ending = 0 if is_local else 2
    last_var_sizeb = 4
    pfx = 'l' if is_local else ''
    pfxu = (' ' * (tab*4)) + pfx.upper()
    for v in vars:
        this_var_index = v.start_offset / 4
        if is_local and this_var_index in TIMER_INDICES:
            continue
        any_var = True
        for k in range(last_var_ending, this_var_index):
            if k < MISSION_LVAR_BEGIN and is_mission:
                continue
            if k not in TIMER_INDICES:
                stream.write("%sVAR_INT %svar_%d // unused variable\n" % (pfxu, pfx, k))
        comment = "// unknown type" if not v.type else ""
        if v.size == None:
            stream.write("%sVAR_%s %svar_%d%s\n" % (pfxu, v.type or "INT", pfx, this_var_index, comment))
        else:
            stream.write("%sVAR_%s %svar_%d[%d]%s\n" % (pfxu, v.type, pfx, this_var_index, v.size, comment))
        last_var_ending = v.end_offset / 4
    
    if any_var:
        stream.write("\n")

def main(ir2file, configpath, output_dir):

    cmdline = dict(gta3sc.read_commandline(configpath))
    config = gta3sc.read_config(configpath)
    ir2 = gta3sc.read_ir2(ir2file)

    scopes_before_label = bool(cmdline["-fscope-then-label"])
    timer_index = int(cmdline["-ftimer-index"])
    farrays = bool(cmdline["-farrays"])
    global TIMER_INDICES # HACK!!!!!!!!!!!
    global MISSION_LVAR_BEGIN #
    TIMER_INDICES = (timer_index + 0, timer_index + 1)
    MISSION_LVAR_BEGIN = max(0, int(cmdline["-fmission-var-begin"]))

    commands    = {cmd.name: cmd for cmd in config.commands}
    alternators = defaultdict(set, {alt.name: set(alt.alters) for alt in config.alternators})
    enums       = {enum.name: {v: k for k,v in enum.constants.iteritems()} for enum in config.enums}

    scopes = ir2.discover_scopes()
    filename_by_offset = dict()
    subscripts = dict()
    gosubfiles = dict()
    current_scope = None
    first_scope = scopes[0] if len(scopes) > 0 else None
    current_scope_name = None

    for i in range(len(ir2.mission_blocks)):
        script_offset = ir2.offset_from_mission(i)
        script_name   = Scope.from_offset(script_offset, scopes).find_script_name(ir2)
        filename_by_offset[script_offset] = "missions/%s.sc" % script_name.lower()

    for i in range(len(ir2.streamed_blocks)):
        script_offset = ir2.offset_from_streamed(i)
        stream_name   = ir2.get_stream_name(i)
        filename_by_offset[script_offset] = "streams/%s.sc" % stream_name.lower()

    for off, data in ir2:
        if data.is_command() and data.name == "LAUNCH_MISSION":
            assert data.args[0].is_label()
            script_offset = ir2.offset_from_label(data.args[0].value)
            script_name   = Scope.from_offset(script_offset, scopes).find_script_name(ir2)
            filename = "%s.sc" % script_name.lower() if script_name else "subscript%d.sc" % len(subscripts)
            filename_by_offset[script_offset] = filename
            subscripts[script_offset] = filename
        elif data.is_command() and data.name == "GOSUB_FILE":
            assert data.args[1].is_label()
            filename = "gosub%d.sc" % len(gosubs)
            script_offset = ir2.offset_from_label(data.args[1].value)
            filename_by_offset[script_offset] = filename
            gosubfiles[script_offset] = filename

    if farrays:
        more_info = [v for (s,v) in SA_VAR_ARRAYS if s == None]
    else:
        more_info = None

    global_vars = ir2.discover_global_vars(config=config, more_info=more_info)
    local_vars = None

    print("//--------------------------")

    try:
        os.makedirs(os.path.join(output_dir, "main"))
        os.makedirs(os.path.join(output_dir, "main", "missions"))
        os.makedirs(os.path.join(output_dir, "main", "streams"))
    except OSError as e:
        if e.errno != errno.EEXIST:
            raise

    stream = open(os.path.join(output_dir, "main.sc"), 'w')

    got_mission_terminate = [None] # hack
    is_mission = False
    print_script_terminate_for = None

    print_vars(stream, global_vars, False, False)

    for off, data in ir2:

        if print_script_terminate_for != None:
            if print_script_terminate_for.type != BYTECODE_OFFSET_STREAMED or print_script_terminate_for.block != off.block:
                if print_script_terminate_for.type == BYTECODE_OFFSET_STREAMED:
                    stream.write("}\n")
                stream.write("%s\n" % ("MISSION_END", "MISSION_END", "SCRIPT_END")[print_script_terminate_for.type])
                got_mission_terminate[0] = True
            else:
                stream.write("    TERMINATE_THIS_SCRIPT\n")
            print_script_terminate_for = None

        def on_scope_begin(old_scope, new_scope):
            print("Converting %s" % current_scope_name)
            if new_scope.start in subscripts or (old_scope.start.type != new_scope.start.type or old_scope.start.block != new_scope.start.block):
                if new_scope.start.type != BYTECODE_OFFSET_MAIN or new_scope.start in subscripts:
                    stream.write("%s\n" % ("MISSION_START", "MISSION_START", "SCRIPT_START")[new_scope.start.type])
                    got_mission_terminate[0] = False
        def on_scope_end(old_scope, new_scope):
            if old_scope.start in subscripts or (old_scope.start.type != new_scope.start.type or old_scope.start.block != new_scope.start.block):
                if old_scope.start.type != BYTECODE_OFFSET_MAIN or old_scope.start in subscripts:
                    #stream.write("%s\n" % ("MISSION_END", "MISSION_END", "SCRIPT_END")[old_scope.start.type])
                    got_mission_terminate[0] = None

        def write_data(tab=0):
            tabing = ' ' * (tab*4)
            if data.is_label(): stream.write("\n")
            line = converted_data(ir2, data, commands, alternators, enums, global_vars, local_vars, filename_by_offset=filename_by_offset)
            stream.write("%s%s\n" % (tabing, line))

        if current_scope == None:
            if first_scope != None and off >= first_scope.start:
                current_scope = Scope.from_offset(off, scopes)
                assert current_scope != None
        elif not current_scope.owns_offset(off):
            previous_scope = current_scope
            if current_scope != first_scope and previous_scope.start.type != BYTECODE_OFFSET_STREAMED:
                stream.write("}\n")
            current_scope = Scope.from_offset(off, scopes)
            assert current_scope != None

            current_scope_name = current_scope.find_script_name(ir2)
            if current_scope_name is None:
                current_scope_name = "??"

            on_scope_end(previous_scope, current_scope)

            if off.type != BYTECODE_OFFSET_MAIN:
                stream.close()
                stream = open(os.path.join(output_dir, "main", filename_by_offset[off]), 'w')
            elif off in subscripts or off in gosubfiles:
                filename = subscripts.get(off) or gosubfiles.get(off)
                stream.close()
                stream = open(os.path.join(output_dir, "main", filename), 'w')

            on_scope_begin(previous_scope, current_scope)

            if farrays and current_scope_name != None:
                more_info = [v for (s,v) in SA_VAR_ARRAYS if s == current_scope_name]
            else:
                more_info = None

            local_vars = ir2.discover_local_vars(current_scope, config=config, more_info=more_info)

            is_mission = (current_scope.start.type == BYTECODE_OFFSET_MISSION)
            is_stream  = (current_scope.start.type == BYTECODE_OFFSET_STREAMED)

            if data.is_label():
                if scopes_before_label:
                    stream.write("\n{")
                    write_data(tab=1)
                    print_vars(stream, local_vars, True, is_mission, tab=1)
                    continue
                else:
                    write_data(tab=0)
                    stream.write("{\n")
                    print_vars(stream, local_vars, True, is_mission, tab=1)
                    continue
            else:
                stream.write("{\n")
                print_vars(stream, local_vars, True, is_mission, tab=1)

        if got_mission_terminate[0] == False and\
           data.is_command() and data.name == "TERMINATE_THIS_SCRIPT":
           print_script_terminate_for = off
        else:
            tab = int(current_scope != None and current_scope != first_scope)
            if got_mission_terminate[0] == False and not is_stream:
                tab += 1
            write_data(tab=tab)

    if current_scope != None and current_scope != first_scope:
        stream.write("}\n")

    if print_script_terminate_for != None:
        stream.write("%s\n" % ("MISSION_END", "MISSION_END", "SCRIPT_END")[print_script_terminate_for.type])

    if stream != sys.stdout:
        stream.close()


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: discover_entity_commands.py <ir2_script> <configpath> <output_dir>")
        sys.exit(1)
    main(sys.argv[1], sys.argv[2], sys.argv[3])

