# -*- Python -*-
from lxml import etree
import os
import re

__all__ = ["Alternator", "Enum", "Command", "Argument", "Config", "read_config"]

class Alternator:
    def __init__(self):
        self.name = ""
        self.alters = []

    def __iter__(self):
        return iter(self.alters)

    @staticmethod
    def from_node(node):
        init = Alternator()
        init.name   = node.get("Name")
        init.alters = [a.get("Name") for a in node.iter("Alternative")]
        return init

    def to_node(self):
        node = etree.Element("Alternator", Name=self.name)
        for a in self.alters:
            etree.SubElement(node, "Alternative", Name=a)
        return node

class Enum:
    def __init__(self):
        self.name = ""
        self.is_global = False  # global is a python keyword
        self.constants = {}

    @staticmethod
    def from_node(node):
        init = Enum()
        init.name       = node.get("Name")
        init.is_global  = _str2bool(node.get("Global", "false"))
        init.constants  = {}
        last_value = -1
        for a in node.iter("Constant"):
            maybe_value = a.get("Value")
            last_value = int(maybe_value, 0) if maybe_value is not None else last_value + 1
            init.constants[a.get("Name")] = last_value
        return init

    def to_node(self):
        last_value = -1
        node = etree.Element("Enum", Name=self.name)
        if self.is_global:
            node.set("Global", _bool2str(self.is_global))
        for k,v in sorted(self.constants.items(), key=lambda x: x[1]):
            if v == last_value + 1:
                etree.SubElement(node, "Constant", Name=k)
            else:
                etree.SubElement(node, "Constant", Name=k, Value=str(v))
            last_value = v
        return node

class Command:
    def __init__(self):
        self.name = ""
        self.id = None
        self.hash = None
        self.supported = False
        self.internal = False
        self.extension = False
        self.args = []

    def __eq__(self, other):
        return self.name == other.name and\
               self.id == other.id and\
               self.supported == other.supported and\
               self.args == other.args

    def same_behaviour(self, other):
        if self.id == other.id and len(self.args) == len(other.args):
            return all(a.same_behaviour(b) for a,b in zip(self.args, other.args))
        return False

    def has_optional(self):
        return len(self.args) > 0 and self.args[-1].optional == True

    def get_arg(self, i):
        if i < len(self.args):
            return self.args[i]
        elif self.has_optional():
            return self.args[-1]
        else:
            return None

    @staticmethod
    def from_node(node):
        init = Command()
        cmdid = node.get("ID", None)
        cmdhash = node.get("Hash", None)
        init.name = node.get("Name")
        init.id = int(cmdid, 0) if cmdid is not None else None
        init.hash = int(cmdhash, 0) if cmdhash is not None else None
        init.supported = _str2bool(node.get("Supported", "true"))
        init.internal = _str2bool(node.get("Internal", "false"))
        init.extension = _str2bool(node.get("Extension", "false"))
        init.args = []
        node_args = node.find("Args")
        if node_args is not None:
            for a in node_args.iter("Arg"):
                init.args.append(Argument.from_node(a))
        return init

    def to_node(self):
        node = etree.Element("Command")
        if self.id is not None:
            node.set("ID", hex(self.id))
        node.set("Name", self.name)
        if self.hash is not None:
            node.set("Hash", "0x%.8x" % self.hash)
        if self.supported == False:
            node.set("Supported", _bool2str(self.supported))
        if self.internal == True:
            node.set("Internal", _bool2str(self.internal))
        if self.extension == True:
            node.set("Extension", _bool2str(self.extension))
        if len(self.args) > 0:
            node_args = etree.SubElement(node, "Args")
            for a in self.args:
                node_args.append(a.to_node())
        return node

class Argument:
    def __init__(self):
        self.type = "ANY"
        self.desc = ""
        self.out = False
        self.ref = False
        self.optional = False
        self.allow_const = False
        self.allow_gvar = False
        self.allow_lvar = False
        self.entity = None
        self.enums = []
        self.allow_text_label = False # valid only for PARAM types
        self.allow_pointer = False
        self.preserve_case = False

    def __eq__(self, other):
        return self.__dict__ == other.__dict__

    def same_behaviour(self, other):
        return self.type == other.type and\
               self.out == other.out and\
               self.ref == other.ref and\
               self.optional == other.optional

    def has_enum(self, name):
        return any(x == name for x in self.enums)

    @staticmethod
    def from_node(node):
        init = Argument()
        init.type = node.get("Type")
        init.desc = node.get("Desc", "")
        init.out  = _str2bool(node.get("Out", "false"))
        init.ref  = _str2bool(node.get("Ref", "false"))
        init.optional = _str2bool(node.get("Optional", "false"))
        init.allow_const = _str2bool(node.get("AllowConst", "false" if init.out else "true"))
        init.allow_gvar = _str2bool(node.get("AllowGlobalVar", "true" if init.type != "LABEL" else "false"))
        init.allow_lvar = _str2bool(node.get("AllowLocalVar", "true" if init.type != "LABEL" else "false"))
        init.allow_text_label = _str2bool(node.get("AllowTextLabel", "false"))
        init.allow_pointer = _str2bool(node.get("AllowPointer", "false"))
        init.preserve_case = _str2bool(node.get("PreserveCase", "false"))
        init.entity = node.get("Entity", None)
        init.enums = node.get("Enum", None)
        init.enums = [init.enums] if init.enums else []
        return init
        
    def to_node(self):
        default_allow_var = True if self.type != "LABEL" else False
        node = etree.Element("Arg", Type=self.type)
        if self.desc.strip() != "":
            node.set("Desc", self.desc)
        if self.out != False:
            node.set("Out", _bool2str(self.out))
        if self.ref != False:
            node.set("Ref", _bool2str(self.ref))
        if self.optional != False:
            node.set("Optional", _bool2str(self.optional))
        if self.allow_const == False and self.out == False:
            node.set("AllowConst", _bool2str(self.allow_const))
        if self.allow_gvar != default_allow_var:
            node.set("AllowGlobalVar", _bool2str(self.allow_gvar))
        if self.allow_lvar != default_allow_var:
            node.set("AllowLocalVar", _bool2str(self.allow_lvar))
        if self.allow_text_label == True:
            node.set("AllowTextLabel", _bool2str(self.allow_text_label))
        if self.allow_pointer == True:
            node.set("AllowPointer", _bool2str(self.allow_pointer))
        if self.preserve_case == True:
            node.set("PreserveCase", _bool2str(self.preserve_case))
        if self.entity != None:
            node.set("Entity", self.entity)
        if len(self.enums) != 0:
            assert len(self.enums) == 1
            node.set("Enum", self.enums[0])
        return node
    
class Config:
    def __init__(self):
        self.commands = []
        self.enums = []
        self.alternators = []

    def get_alternator(self, name):
        return next((x for x in self.alternators if x.name == name), None)

    def read_config(self, file):
        tree = etree.parse(file)
        for item in tree.getroot():
            if item.tag == "Alternators":
                for subitem in item:
                    if subitem.tag == "Alternator":
                        self.alternators.append(Alternator.from_node(subitem))
            elif item.tag == "Commands":
                for subitem in item:
                    if subitem.tag == "Command":
                        self.commands.append(Command.from_node(subitem))
            elif item.tag == "Constants":
                for subitem in item:
                    if subitem.tag == "Enum":
                        self.enums.append(Enum.from_node(subitem))

    def save_config(self, file, pretty_print=True):
        root = etree.Element("GTA3Script")
        if len(self.enums) > 0:
            base = etree.SubElement(root, "Constants") 
            for c in self.enums:
                base.append(c.to_node())
        if len(self.alternators) > 0:
            base = etree.SubElement(root, "Alternators") 
            for c in self.alternators:
                base.append(c.to_node())
        if len(self.commands) > 0:
            base = etree.SubElement(root, "Commands") 
            for c in self.commands:
                base.append(c.to_node())

        tree = etree.ElementTree(root)
        tree.write(file, encoding="utf-8", pretty_print=pretty_print, xml_declaration=True)


def read_config(filename):
    c = Config()
    if os.path.isdir(filename):
        for subfile in os.listdir(filename):
            if subfile.endswith(".xml"):
                c.read_config(os.path.join(filename, subfile))
    else:
        c.read_config(filename)
    return c

def read_commandline(configpath):
    result = []
    with open(os.path.join(configpath, "commandline.txt")) as f:
        for command in re.split(r"[\r\n\t ]", f.read()):
            split = command.split('=')
            left  = split[0]
            right = split[1] if len(split) > 1 else True
            if left.startswith("-fno-") or left.startswith("-mno-"):
                assert right == True
                left = left[:2] + left[5:]
                right = False
            result.append((left, right))
    return result


def _str2bool(x):
    if x == "true":
        return True
    if x == "false":
        return False
    print(x)
    assert False

def _bool2str(x):
    if x == True:
        return "true"
    if x == False:
        return "false"
    print(type(x))
    assert False

def one_at_a_time(key):
    result = 0
    for i in range(0, len(key)):
        result += ord(key[i]);                 result &= 0xFFFFFFFF
        result += (result << 10) & 0xFFFFFFFF; result &= 0xFFFFFFFF
        result ^= (result >> 6) & 0xFFFFFFFF;  result &= 0xFFFFFFFF
    result += (result << 3) & 0xFFFFFFFF; result &= 0xFFFFFFFF
    result ^= (result >> 11) & 0xFFFFFFFF; result &= 0xFFFFFFFF
    result += (result << 15) & 0xFFFFFFFF; result &= 0xFFFFFFFF
    return result


if __name__ == "__main__":
    import sys
    cfg = Config()
    cfg.read_config(sys.argv[1])
    cfg.save_config(sys.argv[1])
