#!/usr/bin/env python2
"""
  Examples:
    py simplify.py gtasa/commands.xml
    py simplify.py gtasa/commands.xml any_2nd_arg_will_trigger_clear_useless
"""
import gta3sc
import sys

AMBIGOUS_DESCRIPTION_ENTITY = {
    "Task sequence handle": ("SEQUENCE_TASK"),
    "Searchlight handle": ("SEARCHLIGHT"),
    "Pickup": ("PICKUP"),
    "Decision maker": ("DECISION_MAKER"),
    "Character/ped": ("CHAR"),
    "En/Ex marker": ("USER_3D_MARKER"),
    #"Helicopter": ("CAR"),
    "Particle FX": ("FX_SYSTEM"),
    #"Train carriage": ("CAR"),
    "Sphere handle": ("SPHERE"),
    "Blip": ("BLIP"),
    "Fire": ("SCRIPT_FIRE"),
    #"Train": ("CAR"),
    "Object": ("OBJECT"),
    #"Plane": ("CAR"),
    "Group handle": ("GROUP"),
    "Car generator": ("CAR_GENERATOR"),
    "Car/vehicle": ("CAR"),
    "Player": ("PLAYER"),
    "Phone handle": ("PHONE"),
    "Attractor handle": ("ATTRACTOR"),
}

AMBIGOUS_DESCRIPTION_ENUM = {
    "Model ID": ("DEFAULTMODEL", "MODEL"),

    "Button ID": ("BUTTON"),
    "Weapon ID": ("WEAPONTYPE"),
    "Vehicle action ID": ("TEMPACT"),
    "Camera mode ID": ("CAMMODE"),
    "Weather ID": ("WEATHER"),
    "Car colour ID": ("CARCOLOUR"),
    "Blip sprite ID": ("RADAR_SPRITE"),
    "Ped type": ("PEDTYPE"),
    "Pickup ID": ("PICKUP"),
    "Pad ID": ("PAD"),
    "Gang ID": ("GANG"),
    "Explosion ID": ("EXPLOSION"),
}

def main(xmlfile, clear_useless_data):
    config = gta3sc.read_config(xmlfile)
    commands = config.commands

    # Remove description from where Entity and Enum information is enough.
    for cmd in commands:
        for arg in cmd.args:
            amb_entity = AMBIGOUS_DESCRIPTION_ENTITY.get(arg.desc)
            amb_enum   = AMBIGOUS_DESCRIPTION_ENUM.get(arg.desc)
            if amb_entity and arg.entity and arg.entity in amb_entity:
                arg.desc = ""
            if amb_enum and len(arg.enums) > 0 and arg.enums[0] in amb_enum:
                arg.desc = ""

    if clear_useless_data:
        new_commands = []
        for cmd in commands:
            if cmd.supported == False:
                continue
            for a in cmd.args:
                a.desc   = ""
                a.entity = None
                a.enums  = []
                a.allow_const = True
                a.allow_gvar = True
                a.allow_lvar = True
            new_commands.append(cmd)
    else:
        # Simply rewriting the XML will simplify it.
        new_commands = commands

    config.commands = new_commands
    config.save_config(xmlfile, pretty_print=(not clear_useless_data))

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: simplify.py <xmlfile> <[clear_useless_data]>")
        sys.exit(1)
    main(sys.argv[1], len(sys.argv) > 2)
