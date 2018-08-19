# -*- Python -*-

from collections import namedtuple
from itertools import chain
import re

__all__ = [
    "Bytecode", "Offset", "VarInfo", "Scope", "Data", "Arg", "Label", "Hex", "Command", 
     "ArgNumber", "ArgLabel", "ArgString", "ArgVariable", "ArgArray",
     "read_ir2",
]

DATA_HEX     = 0
DATA_LABEL   = 1
DATA_COMMAND = 2

DATATYPE_INT8                         = 0
DATATYPE_INT16                        = 1
DATATYPE_INT32                        = 2
DATATYPE_LOCAL_LABEL                  = 3
DATATYPE_GLOBAL_LABEL                 = 4
DATATYPE_FLOAT                        = 5
DATATYPE_GLOBALVAR_NUMBER             = 6
DATATYPE_GLOBALVAR_TEXTLABEL          = 7
DATATYPE_GLOBALVAR_TEXTLABEL16        = 8
DATATYPE_LOCALVAR_NUMBER              = 9
DATATYPE_LOCALVAR_TEXTLABEL           = 10
DATATYPE_LOCALVAR_TEXTLABEL16         = 11
DATATYPE_GLOBALVAR_ARRAY_NUMBER       = 12
DATATYPE_GLOBALVAR_ARRAY_TEXTLABEL    = 13
DATATYPE_GLOBALVAR_ARRAY_TEXTLABEL16  = 14
DATATYPE_LOCALVAR_ARRAY_NUMBER        = 15
DATATYPE_LOCALVAR_ARRAY_TEXTLABEL     = 16
DATATYPE_LOCALVAR_ARRAY_TEXTLABEL16   = 17
DATATYPE_TEXTLABEL8                   = 18
DATATYPE_TEXTLABEL16                  = 19
DATATYPE_STRING                       = 20
DATATYPE_BUFFER128                    = 21

DATATYPES_LABEL = (DATATYPE_LOCAL_LABEL, DATATYPE_GLOBAL_LABEL)
DATATYPES_NUMERIC = (DATATYPE_INT8, DATATYPE_INT16, DATATYPE_INT32, DATATYPE_FLOAT)
DATATYPES_STRING  = (DATATYPE_TEXTLABEL8, DATATYPE_TEXTLABEL16, DATATYPE_STRING, DATATYPE_BUFFER128)
DATATYPES_GLOBALVARS = (DATATYPE_GLOBALVAR_NUMBER, DATATYPE_GLOBALVAR_TEXTLABEL, DATATYPE_GLOBALVAR_TEXTLABEL16)
DATATYPES_LOCALVARS  = (DATATYPE_LOCALVAR_NUMBER, DATATYPE_LOCALVAR_TEXTLABEL, DATATYPE_LOCALVAR_TEXTLABEL16)
DATATYPES_GLOBALVARS_ARRAY = (DATATYPE_GLOBALVAR_ARRAY_NUMBER, DATATYPE_GLOBALVAR_ARRAY_TEXTLABEL, DATATYPE_GLOBALVAR_ARRAY_TEXTLABEL16)
DATATYPES_LOCALVARS_ARRAY  = (DATATYPE_LOCALVAR_ARRAY_NUMBER, DATATYPE_LOCALVAR_ARRAY_TEXTLABEL, DATATYPE_LOCALVAR_ARRAY_TEXTLABEL16)
DATATYPES_GLOBAVARS_ALL = DATATYPES_GLOBALVARS + DATATYPES_GLOBALVARS_ARRAY
DATATYPES_LOCALVARS_ALL = DATATYPES_LOCALVARS + DATATYPES_LOCALVARS_ARRAY
DATATYPES_VARS_ALL = DATATYPES_GLOBAVARS_ALL + DATATYPES_LOCALVARS_ALL

ARRAY_ELEM_TYPE_INT = 0
ARRAY_ELEM_TYPE_FLOAT = 1
ARRAY_ELEM_TYPE_TEXTLABEL = 2
ARRAY_ELEM_TYPE_TEXTLABEL16 = 3
ARRAY_ELEM_TYPES = (ARRAY_ELEM_TYPE_INT, ARRAY_ELEM_TYPE_FLOAT, ARRAY_ELEM_TYPE_TEXTLABEL, ARRAY_ELEM_TYPE_TEXTLABEL16)

BYTECODE_OFFSET_MAIN = 0
BYTECODE_OFFSET_MISSION = 1
BYTECODE_OFFSET_STREAMED = 2

TABLE_SCOPE_SPAWNERS = {
#   Name                ArgId
    "GOSUB_FILE":       1,
    "START_NEW_SCRIPT": 0,
    "LAUNCH_MISSION":   0,
    "CALL":             3,
    "CALLNOT":          3,
}

class Bytecode:

    def __init__(self, main_block, mission_blocks=[], streamed_blocks=[], models=[], stream_names=[]):
        self.main_block = main_block
        self.mission_blocks = mission_blocks
        self.streamed_blocks = streamed_blocks
        self.models = models
        self.stream_names = stream_names

        self.label_table = {}
        for off, data in self:
            if data.is_label():
                self.label_table[data.name] = off

    def __str__(self):
        lines = []
        lines.extend(str(data) for data in self.main_block)
        for i, block in enumerate(self.mission_blocks):
            lines.append("#MISSION_BLOCK_START %d" % i)
            lines.extend(str(data) for data in block)
            lines.append("#MISSION_BLOCK_END")
        for i, block in enumerate(self.streamed_blocks):
            lines.append("#STREAMED_BLOCK_START %d" % i)
            lines.extend(str(data) for data in block)
            lines.append("#STREAMED_BLOCK_END")
        return "\n".join(lines)

    def __iter__(self):
        for i, data in enumerate(self.main_block):
            yield (Offset(BYTECODE_OFFSET_MAIN, 0, i), data)
        for block_id, block in enumerate(self.mission_blocks):
            for i, data in enumerate(block):
                yield (Offset(BYTECODE_OFFSET_MISSION, block_id, i), data)
        for block_id, block in enumerate(self.streamed_blocks):
            for i, data in enumerate(block):
                yield (Offset(BYTECODE_OFFSET_STREAMED, block_id, i), data)

    def get(self, offset):
        the_block = None
        if offset.type == BYTECODE_OFFSET_MAIN:
            assert offset.block == 0
            the_block = self.main_block
        elif offset.type == BYTECODE_OFFSET_MISSION:
            the_block = self.mission_blocks[offset.block]
        elif offset.type == BYTECODE_OFFSET_STREAMED:
            the_block = self.streamed_blocks[offset.block]
        if the_block != None and offset.index < len(the_block):
            return the_block[offset.index]
        return None

    def get_model(self, i):
        return self.models[i] if i < len(self.models) else None

    def get_stream_name(self, i):
        return self.stream_names[i] if i < len(self.stream_names) else None

    def offset_from_label(self, name):
        return self.label_table.get(name)

    def offset_from_mission(self, i):
        return Offset(BYTECODE_OFFSET_MISSION, i, 0)

    def offset_from_streamed(self, i):
        return Offset(BYTECODE_OFFSET_STREAMED, i, 0)

    def discover_scopes(self): # -> sorted [Scope, ...]
        scopes_at = []
        result = []
        last_off = None

        for off, data in self:
            if data.is_command():
                argid = TABLE_SCOPE_SPAWNERS.get(data.name)
                if argid != None:
                    scopes_at.append(self.offset_from_label(data.args[argid].value))

            if last_off is None or off.type != last_off.type or off.block != last_off.block:
                scopes_at.append(off)
                last_off = off
        
        scopes_at = sorted(set(scopes_at))
        for i, off in enumerate(scopes_at):
            if i + 1 == len(scopes_at):
                result.append(Scope(off, None))
            else:
                result.append(Scope(off, scopes_at[i+1]))

        return result

    def discover_global_vars(self, config=None, more_info=None):  # -> sorted [VarInfo, ...]
        return _discover_vars(iter(self), False, config=config, more_info=more_info)

    def discover_local_vars(self, scope, config=None, more_info=None):  # -> sorted [VarInfo, ...]
        return _discover_vars(iter(scope.iter_data(self)), True, config=config, more_info=more_info)

    def discover_global_arrays(self): # -> { offset: end_offset, ... }
        return _discover_arrays(iter(self), False)

    def discover_local_arrays(self, scope): # -> { offset: end_offset, ... }
        return _discover_arrays(scope.iter_data(self), True)


Offset = namedtuple("Offset", ['type', 'block', 'index'])

ScopeBase = namedtuple('ScopeBase', ['start', 'end'])

class VarInfo:
    def __init__(self, start_offset, typestring, arraysize):
        self.type = typestring # may be None, meaning unknown type

        if self.type in ("INT", "FLOAT"):
            self.elem_size = 4
        elif self.type == "TEXT_LABEL":
            self.elem_size = 8
        elif self.type == "TEXT_LABEL16":
            self.elem_size = 16
        else:
            self.elem_size = None

        self.start_offset = start_offset
        self.end_offset = start_offset + (self.elem_size or 4) * (arraysize or 1)
        
        self.size = arraysize  # None means not array
        self.enums = set()
        self.entities = set()

    @staticmethod
    def from_offset(offset, varlist): # varlist should be sorted
        # see comments in Scope.from_offset for details
        for v in varlist:
            if offset >= v.end_offset:
                continue
            if offset >= v.start_offset:
                return v
            return None

    def index_from_offset(self, offset):
        assert offset >= self.start_offset and offset < self.end_offset
        return (offset - self.start_offset) / self.elem_size


class Scope(ScopeBase):
    # assert self.start until self.end doesn't change blocks/script types

    def iter_data(self, bytecode):
        off = self.start
        while True:
            data = bytecode.get(off)
            if data is None or (self.end != None and off >= self.end):
                return
            yield (off, data)
            off = Offset(off.type, off.block, off.index + 1)

    @staticmethod
    def from_offset(offset, scopelist): # scopelist shall be sorted
        # think of this as a rectangle scanning lines in search for one line
        for scope in scopelist:
            if scope.end == None:
                return scope if offset >= scope.start else None
            if offset >= scope.end: # find the first scope in which the offset is before the scope end
                continue
            if offset >= scope.start: # once found, check if the offset is inside such scope
                return scope
            return None # not inside any scope

    def owns_offset(self, offset):
        if self.end == None:
            return offset >= self.start
        return offset >= self.start and offset < self.end

    def find_script_name(self, bytecode):
        for off, data in self.iter_data(bytecode):
            if data.is_command() and data.name == "SCRIPT_NAME":
                assert data.args[0].is_string()
                return data.args[0].value


class Data:
    def __init__(self, xtype):   # no need to call
        self.type = xtype

    def __str__(self):
        raise NotImplementedError # derived shall implement

    def is_hex(self):
        return self.type == DATA_HEX

    def is_label(self):
        return self.type == DATA_LABEL

    def is_command(self):
        return self.type == DATA_COMMAND

class Arg:
    def __init__(self, datatype): # no need to call
        self.type = datatype

    def __str__(self):
        raise NotImplementedError # derived shall implement

    def is_number(self):
        return False

    def is_label(self):
        return False

    def is_string(self):
        return False

    def is_var(self): # returns true for both Var and Array
        return False

    def is_array(self): # returns false for Var
        return False

class Label(Data):
    def __init__(self, name):
        self.type = DATA_LABEL
        self.name = name

    def __str__(self):
        return "%s:" % self.name

class Hex(Data):
    def __init__(self, bytearray_object):
        self.type = DATA_HEX
        self.bytes = bytearray_object

    def __str__(self):
        output = "IR2_HEX"
        for i in self.bytes:
            output += ' '
            output += str(i - 256 if i > 127 else i) + 'i8'
        return output

class Command(Data):
    def __init__(self, not_flag, name, args):
        self.type = DATA_COMMAND
        self.not_flag = not_flag
        self.name = name.upper()
        self.args = args

    def __str__(self):
        output = "NOT " if self.not_flag else ""
        output += self.name
        for a in self.args:
            output += ' '
            output += str(a)
        return output

class ArgNumber(Arg):
    def __init__(self, numtype, value):
        assert numtype in DATATYPES_NUMERIC
        self.type = numtype
        self.value = value

    def is_number(self):
        return True

    def is_float(self):
        return self.type == DATATYPE_FLOAT

    def __str__(self):
        if self.type == DATATYPE_INT8:
            return "%di8" % self.value
        if self.type == DATATYPE_INT16:
            return "%di16" % self.value
        if self.type == DATATYPE_INT32:
            return "%di32" % self.value
        if self.type == DATATYPE_FLOAT:
            return "%.6af" % self.value
        assert False

class ArgLabel(Arg):
    def __init__(self, labtype, value):
        assert labtype in DATATYPES_LABEL
        self.type = labtype
        self.value = value

    def is_label(self):
        return True

    def __str__(self):
        if self.type == DATATYPE_GLOBAL_LABEL:
            return "@%s" % self.value
        if self.type == DATATYPE_LOCAL_LABEL:
            return "%%%s" % self.value
        assert False

class ArgString(Arg):
    def __init__(self, strtype, value):
        assert strtype in DATATYPES_STRING
        self.type = strtype
        self.value = value

    def is_string(self):
        return True

    def is_buffer128(self):
        return self.type == DATATYPE_BUFFER128

    def __str__(self):
        # TODO unescape
        if self.type == DATATYPE_TEXTLABEL8:
            return "'%s'" % self.value
        if self.type == DATATYPE_TEXTLABEL16:
            return "v'%s'" % self.value
        if self.type == DATATYPE_STRING:
            return "\"%s\"" % self.value
        if self.type == DATATYPE_BUFFER128:
            return "b\"%s\"" % self.value
        assert False

class ArgVariable(Arg):
    def __init__(self, vartype, offset):
        assert vartype in DATATYPES_GLOBALVARS or vartype in DATATYPES_LOCALVARS
        self.type = vartype
        self.offset = offset # i*1 for globals, i*4 for locals

    def is_var(self):
        return True

    def is_global(self):
        return self.type in DATATYPES_GLOBALVARS

    def is_local(self):
        return self.type in DATATYPES_LOCALVARS

    def get_datatype(self): # returns the GLOBALVAR version of the datatype
        if self.is_local():
            return DATATYPES_GLOBALVARS[DATATYPES_LOCALVARS.index(self.type)]
        else:
            return self.type

    def get_offset(self):
        return self.offset

    def size_in_bytes(self):
        datatype = self.get_datatype();
        if datatype == DATATYPE_GLOBALVAR_NUMBER:
            return 4
        elif datatype == DATATYPE_GLOBALVAR_TEXTLABEL:
            return 8
        elif datatype == DATATYPE_GLOBALVAR_TEXTLABEL16:
            return 16
        else:
            assert False

    def __str__(self):
        # TODO unescape
        c = _char_from_vartype(self.type)
        if self.is_global():
            return c + ("&%s" % (self.offset))
        else:
            return ("%s@" % (self.offset / 4)) + c
        assert False

class ArgArray(Arg):
    def __init__(self, base, index, size, elem_type):
        assert elem_type in ARRAY_ELEM_TYPES
        self.type = ArgArray._type_from_base(base)
        self.base = base
        self.index = index
        self.size = size
        self.elem_type = elem_type

    def is_var(self):
        return True

    def is_array(self):
        return True

    def is_global(self):
        return self.base.is_global()

    def is_local(self):
        return self.base.is_local()

    def get_offset(self):
        return self.base.get_offset()

    def __str__(self):
        etc = _char_from_elemtype(self.elem_type)
        return "%s(%s,%d%c)" % (self.base, self.index, self.size, etc)

    @staticmethod
    def _type_from_base(base):
        if base.type in DATATYPES_GLOBALVARS:
            return DATATYPES_GLOBALVARS_ARRAY[DATATYPES_GLOBALVARS.index(base.type)]
        elif base.type in DATATYPES_LOCALVARS:
            return DATATYPES_LOCALVARS_ARRAY[DATATYPES_LOCALVARS.index(base.type)]
        else:
            raise ValueError("base is not a variable")



def read_ir2(file):
    try:
        lines = file.readlines()
    except AttributeError:
        with open(file) as f:
            return read_ir2(f)

    RE_INT8 = re.compile(r"^(-?[0-9]+)i8$")
    RE_INT16 = re.compile(r"^(-?[0-9]+)i16$")
    RE_INT32 = re.compile(r"^(-?[0-9]+)i32$")
    RE_FLOAT = re.compile(r"^(-?0x[01]\.[0-9a-f]{6}p[+-][0-9]+)f$")
    RE_GLOBALOFF = re.compile(r"^@([_A-Z][_A-Z0-9]*)$")
    RE_LOCALOFF = re.compile(r"^%([_A-Z][_A-Z0-9]*)$")
    RE_GLOBALVAR = re.compile(r"^([sv]?)&([0-9]+)$")
    RE_LOCALVAR = re.compile(r"^([0-9]+)@([sv]?)$")
    RE_ARRAY = re.compile(r"^([sv&@0-9]+)\(([&@0-9]+),([0-9]+)([ifsv])\)$")
    RE_TEXTLABEL = re.compile(r"^'([\x20-\x7E]*)'$")
    RE_TEXTLABEL16 = re.compile(r"^v'([\x20-\x7E]*)'$")
    RE_BUFFER128 = re.compile(r"^b\"([\x20-\x7E]*)\"$")
    RE_STRING = re.compile(r"^\"([\x20-\x7E]*)\"$")

    def escape(string):
        return string # TODO

    def var_datatype_from_char(c, tup):
        if c == '': return tup[0]
        if c == 's': return tup[1]
        if c == 'v': return tup[2]
        return None

    def var_from_token(token):
        m = RE_GLOBALVAR.match(token)
        if m != None:
            datatype = var_datatype_from_char(m.group(1), DATATYPES_GLOBALVARS)
            return ArgVariable(datatype, int(m.group(2)))

        m = RE_LOCALVAR.match(token)
        if m != None:
            datatype = var_datatype_from_char(m.group(2), DATATYPES_LOCALVARS)
            return ArgVariable(datatype, 4 * int(m.group(1)))

        return None

    def elem_from_token(token):
        if token == 'i': return ARRAY_ELEM_TYPE_INT
        if token == 'f': return ARRAY_ELEM_TYPE_FLOAT
        if token == 's': return ARRAY_ELEM_TYPE_TEXTLABEL
        if token == 'v': return ARRAY_ELEM_TYPE_TEXTLABEL16
        return None

    def arg_from_token(token):
        m = RE_INT8.match(token)
        if m != None: return ArgNumber(DATATYPE_INT8, int(m.group(1)))

        m = RE_INT16.match(token)
        if m != None: return ArgNumber(DATATYPE_INT16, int(m.group(1)))
            
        m = RE_INT32.match(token)
        if m != None: return ArgNumber(DATATYPE_INT32, int(m.group(1)))

        m = RE_FLOAT.match(token)
        if m != None: return ArgNumber(DATATYPE_FLOAT, float.fromhex(m.group(1)))

        m = RE_GLOBALOFF.match(token)
        if m != None: return ArgLabel(DATATYPE_GLOBAL_LABEL, m.group(1))

        m = RE_LOCALOFF.match(token)
        if m != None: return ArgLabel(DATATYPE_LOCAL_LABEL, m.group(1))

        a = var_from_token(token)
        if a != None: return a

        m = RE_ARRAY.match(token)
        if m != None:
            base = var_from_token(m.group(1))
            index = var_from_token(m.group(2))
            size = int(m.group(3))
            elem = elem_from_token(m.group(4))
            return ArgArray(base, index, size, elem)

        m = RE_TEXTLABEL.match(token)
        if m != None: return ArgString(DATATYPE_TEXTLABEL8, escape(m.group(1)))

        m = RE_TEXTLABEL16.match(token)
        if m != None: return ArgString(DATATYPE_TEXTLABEL16, escape(m.group(1)))        

        m = RE_BUFFER128.match(token)
        if m != None: return ArgString(DATATYPE_BUFFER128, escape(m.group(1)))

        m = RE_STRING.match(token)
        if m != None: return ArgString(DATATYPE_STRING, escape(m.group(1)))

        print(token)
        assert False

    main_block = []
    mission_blocks = []
    streamed_blocks = []
    models = []
    stream_names = []

    current_block = main_block

    for line in lines:
        line = line.rstrip('\r\n')
        assert len(line) > 0 and not line[0].isspace() and not line[-1].isspace()
        if line[0] == '#':
            tokens = line.split()
            if tokens[0] == "#MISSION_BLOCK_START":
                assert len(mission_blocks) == int(tokens[1])
                current_block = []
            elif tokens[0] == "#STREAMED_BLOCK_START":
                assert len(streamed_blocks) == int(tokens[1])
                current_block = []
            elif  tokens[0] == "#MISSION_BLOCK_END":
                mission_blocks.append(current_block)
                current_block = None
            elif tokens[0] == "#STREAMED_BLOCK_END":
                streamed_blocks.append(current_block)
                current_block = None
            elif tokens[0] == "#DEFINE_MODEL":
                models.append(tokens[1])
            elif tokens[0] == "#DEFINE_STREAM":
                stream_names.append(tokens[1])
        elif line[-1] == ':':
            label = Label(line[:-1])
            current_block.append(label)
        else:
            tokens = [p for p in re.split("( |b?\\\".*?\\\"|v?'.*?')", line) if p.strip()]
            not_flag = (tokens[0] == "NOT")
            cmdname  = tokens[not_flag].upper()
            cmdargs = [arg_from_token(tokens[i]) for i in range(1 + not_flag, len(tokens))]
            if cmdname == "IR2_HEX":
                bytedata = bytearray([(i + 256 if i < 0 else i) for i in map(lambda a: a.value, cmdargs)])
                current_block.append(Hex(bytedata))
            else:
                current_block.append(Command(not_flag, cmdname, cmdargs))

    return Bytecode(main_block, mission_blocks, streamed_blocks, models, stream_names)


def _char_from_vartype(vartype):
    assert vartype in DATATYPES_GLOBALVARS or vartype in DATATYPES_LOCALVARS
    if vartype in DATATYPES_LOCALVARS:
        return _char_from_vartype(DATATYPES_GLOBALVARS[DATATYPES_LOCALVARS.index(vartype)])
    if vartype == DATATYPE_GLOBALVAR_NUMBER:
        return ''
    if vartype == DATATYPE_GLOBALVAR_TEXTLABEL:
        return 's'
    if vartype == DATATYPE_GLOBALVAR_TEXTLABEL16:
        return 's'
    assert False

def _char_from_elemtype(elem):
    assert elem in ARRAY_ELEM_TYPES
    if elem == ARRAY_ELEM_TYPE_INT: return 'i'
    if elem == ARRAY_ELEM_TYPE_FLOAT: return 'f'
    if elem == ARRAY_ELEM_TYPE_TEXTLABEL: return 's'
    if elem == ARRAY_ELEM_TYPE_TEXTLABEL16: return 'v'
    assert False

def _discover_arrays(bytecode_iter, is_local): # -> { offset: arraysize_in_bytes, ... }
    arrays = dict()
    if is_local:
        check_var_kind = lambda x: x.is_local()
    else:
        check_var_kind = lambda x: x.is_global()
    for off, data in filter(lambda (o, d): d.is_command(), bytecode_iter):
        for arg in filter(lambda a: a.is_array(), data.args):
            if check_var_kind(arg.base):
                arrays[arg.base.offset] = arg.size * arg.base.size_in_bytes()
    return arrays


def _discover_vars(bytecode_iter, is_local, config=None, more_info=None): # -> sorted [VarInfo, ...]

    # probably optimizable, but this is Python mate!

    commands = {cmd.name: cmd for cmd in config.commands}
    cmds_set = set(config.get_alternator("SET"))

    vardict = dict()

    if is_local:
        check_var_kind = lambda x: x.is_local()
    else:
        check_var_kind = lambda x: x.is_global()

    if more_info != None:
        for v in more_info:
            vardict[v.start_offset] = v

    for off, data in filter(lambda (o, d): d.is_command(), bytecode_iter):
        cmdinfo = commands.get(data.name, None) if commands else None
        for i, arg in enumerate(data.args):
            if arg.is_var() and check_var_kind(arg):

                arginfo = cmdinfo.get_arg(i) if cmdinfo else None

                if arg.is_array():
                    offset_start = arg.base.offset
                    offset_end   = offset_start + (arg.size * arg.base.size_in_bytes())
                    array_size   = arg.size
                    datatype     = arg.base.get_datatype()
                else:
                    offset_start = arg.offset
                    offset_end   = offset_start + arg.size_in_bytes()
                    array_size   = None
                    datatype     = arg.get_datatype()

                vartype = None
                if datatype == DATATYPE_GLOBALVAR_NUMBER:
                    if arginfo is None:
                        pass
                    elif arginfo.type == "INT":
                        vartype = "INT"
                    elif arginfo.type == "FLOAT":
                        vartype = "FLOAT"
                    elif arginfo.type == "PARAM":
                        vartype = None
                    else:
                        assert False
                elif datatype == DATATYPE_GLOBALVAR_TEXTLABEL:
                    vartype = "TEXT_LABEL"
                elif datatype == DATATYPE_GLOBALVAR_TEXTLABEL16:
                    vartype = "TEXT_LABEL16"                    
                
                var = vardict.get(offset_start)
                if var != None:
                    assert var.type == vartype or var.type == None or vartype == None
                    assert var.size == array_size or var.size == None or array_size == None 
                    if vartype != None:
                        var.type = vartype
                    if array_size != None:
                        var.size = array_size
                        var.end_offset = offset_end
                else:
                    vardict[offset_start] = VarInfo(offset_start, vartype, array_size)
                    var = vardict[offset_start]

                if arginfo != None:
                    if len(arginfo.enums) > 0:
                        assert len(arginfo.enums) == 1
                        var.enums.add(arginfo.enums[0])
                    if arginfo.entity:
                        var.entities.add(arginfo.entity)

    # run again for entity/constant assignment discovery
    for off, data in filter(lambda (o, d): d.is_command(), bytecode_iter):
        if data.name in cmds_set and data.args[0].is_var() and data.args[1].is_var():
            lhs_var = vardict[data.args[0].get_offset()]
            rhs_var = vardict[data.args[1].get_offset()]
            lhs_var.enums.update(rhs_var.enums)
            lhs_var.entities.update(rhs_var.entities)
            rhs_var.enums.update(lhs_var.enums)
            rhs_var.entities.update(lhs_var.entities)

    result = list()

    varlist = sorted(vardict.itervalues(), key=lambda k: k.start_offset)
    for v in varlist:
        if len(result) > 0:
            if v.start_offset < result[-1].end_offset:
                result[-1].enums.update(v.enums)
                result[-1].entities.update(v.entities)
                continue

        result.append(v)

    return result

if __name__ == "__main__":
    import sys
    ir2 = read_ir2(sys.argv[1])
    sys.stdout.write(str(ir2))
