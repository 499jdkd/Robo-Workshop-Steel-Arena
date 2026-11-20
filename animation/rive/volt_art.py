"""Volt's serviceable Tesla chassis, authored as independent Rive mechanisms.

Coordinates are robot-local. Coil hinges remain (+/-76, -60), so electrical
effects originate on the actual electrodes rather than on an imaginary gun.
"""

import math
import xml.etree.ElementTree as ET

BLUE = ("FFC3FBFF", "FF39BCE6", "FF116496")
STEEL = ("FFE8F5FC", "FF7DABC0", "FF244B66")
DEEP = ("FF254A64", "FF102C46", "FF07162A")
COPPER = ("FFFFE9BF", "FFD3A565", "FF755633")
LIGHT = ("FFF5FFFF", "FF7FF8FF", "FF239CCF")


def forward(parent, node):
    parent.remove(node)
    parent.insert(0, node)
    return node


def glow(r, parent, name, x, y, w, h, field="voltPower", opacity=1):
    node = r.node(parent, name, x=x, y=y)
    r.bind(node, "opacity", field, opacity)
    r.oval(node, name + " emissive", 0, 0, w, h, LIGHT)
    return node


def pin(r, parent, name, x, y, size=7):
    r.rect(parent, name + " slot", x, y, size * .57, 1.4, "FF194362", r=.5)
    r.oval(parent, name + " cap", x, y, size, size, STEEL)
    r.oval(parent, name + " socket", x, y + 1, size + 3, size + 3, DEEP)


def silhouette(r, parent, name, points, color, radius=9):
    shape = r.path(parent, name, points, color)
    for vertex in shape.find("PointsPath"):
        vertex.set("radius", str(radius))
    return shape


def chassis(r):
    r.head_w, r.head_h, r.head_y = 108, 80, -85
    r.eye = "optic"
    b = r.body
    # Foreground first: a glass energy cell inside a machined, rotating cage.
    core = r.node(b, "Volt reactor", y=8)
    energy = r.node(core, "Volt live core")
    r.bind(energy, "opacity", "voltCore", 1)
    r.oval(energy, "Core hot spot", -5, -5, 9, 13, "FFF8FFFF")
    r.path(energy, "Core current", [(-7, -15), (3, -2), (-4, 1), (8, 15)], "FFEEFFFF", stroke=3)
    disc = r.oval(energy, "Core deep glass", 0, 0, 35, 39, LIGHT)
    gradient = disc.find("Fill/LinearGradient")
    gradient.tag = "RadialGradient"
    gradient.set("startX", "-6")
    gradient.set("startY", "-8")
    gradient.set("endX", "25")
    gradient.set("endY", "18")
    ring = r.joint(core, "Volt turbine ring", 0, 0, 4)
    for i in range(6):
        a = i * math.tau / 6
        r.oval(ring, f"Turbine light {i}", math.cos(a) * 24, math.sin(a) * 24, 4, 4, "FF8AF9FF")
    r.oval(ring, "Turbine inner recess", 0, 0, 43, 47, DEEP)
    r.oval(ring, "Turbine polished ring", 0, 0, 55, 59, STEEL)
    r.oval(core, "Reactor gasket", 0, 2, 66, 71, DEEP)
    for side in (-1, 1):
        for y in (-30, 36):
            pin(r, b, f"Reactor fastener {side}-{y}", side * 26, y, 6)
        plate = r.joint(b, f"Volt service panel {side}", side * 43, 10, 5 if side < 0 else 6)
        r.path(plate, f"Panel light guide {side}", [(side * 7, -27), (side * 17, -18), (side * 18, 12)], "FF9EF9FF", stroke=2)
        for j in range(3):
            r.rect(plate, f"Panel vent {side}-{j}", side * 11, 19 + j * 6, 17, 2.7, "FF173D5B", r=1)
        silhouette(r, plate, f"Sculpted cheek armor {side}", [(-side * 8, -43), (side * 19, -37), (side * 30, -16), (side * 24, 23), (side * 5, 46), (-side * 8, 41)], BLUE, 10)
        r.path(b, f"Copper bus {side}", [(side * 29, -30), (side * 43, -40), (side * 49, -61)], COPPER, stroke=5)
        pin(r, b, f"Chest latch {side}", side * 50, -23)
    r.path(b, "Chest top rim", [(-48, -39), (-24, -51), (25, -51), (48, -39)], "FFB9F2FF", stroke=3)
    r.path(b, "Chest bottom seam", [(-43, 48), (-20, 61), (20, 61), (43, 48)], "FF0B3C61", stroke=4)
    silhouette(r, b, "Volt milled chest", [(-42, -54), (35, -54), (62, -32), (68, 18), (51, 55), (21, 72), (-28, 69), (-57, 48), (-68, 3), (-60, -35)], BLUE, 16)
    silhouette(r, b, "Volt rear metal lip", [(-45, -59), (40, -58), (69, -34), (74, 20), (55, 62), (22, 79), (-30, 76), (-65, 51), (-76, 4), (-67, -37)], DEEP, 17)
    # The segmented bellows and sockets read independently of the floating body.
    neck = r.node(r.robot, "Volt flexible neck", y=-51)
    r.bind(neck, "rotation", "voltAntenna", 0)
    for y in (-11, -4, 3, 10):
        r.rect(neck, f"Neck bellows {y}", 0, y, 39, 5, STEEL, r=2)
    r.rect(neck, "Neck rubber core", 0, 0, 30, 29, DEEP, r=5)
    for side in (-1, 1):
        coil = r.joint(r.robot, f"Tesla mast {side}", side * 76, -60, 0 if side < 0 else 1)
        contacts = r.joint(coil, f"Volt crown contact {side}", 0, -55, 2 if side < 0 else 3)
        for dx in (-12, 12):
            glow(r, contacts, f"Electrode tip {side}-{dx}", dx, -10, 9, 7)
            silhouette(r, contacts, f"Electrode finger {side}-{dx}", [(dx - 4, 1), (dx - 4, -14), (dx + 3, -17), (dx + 5, -1)], STEEL, 3)
        r.rect(contacts, f"Crown coupling {side}", 0, 1, 35, 10, COPPER, r=4)
        # Three distinct materials per winding; no oversized glow hides the metal.
        for i, y in enumerate(range(-45, 5, 10)):
            glow(r, coil, f"Coil live edge {side}-{i}", -2, y - 1, 34, 3)
            r.oval(coil, f"Winding crown {side}-{i}", -2, y - 2, 39, 7, ("FFE8FFFF", "FF80E7FA", "FF2386B6"))
            r.oval(coil, f"Winding copper {side}-{i}", 1, y + 2, 41, 8, ("FF98D5E9", "FF345C7E"))
        r.rect(coil, f"Ceramic spine {side}", 0, -24, 16, 70, ("FFB4DAEB", "FF214C6C"), r=6)
        r.oval(coil, f"Coil universal pin {side}", 0, 14, 13, 13, STEEL)
        r.oval(coil, f"Coil universal hub {side}", 0, 14, 25, 25, DEEP)
        silhouette(r, coil, f"Mast articulated bracket {side}", [(-9, 4), (9, 4), (side * 15, 24), (side * 7, 36), (-side * 4, 34)], STEEL, 4)
        r.path(r.robot, f"Coil flexible cable {side}", [(side * 49, -24), (side * 64, -21), (side * 79, -31), (side * 76, -44)], DEEP, stroke=8)
        # Nozzle body and separate gimbal respond to acceleration and landing.
        thruster = r.joint(r.robot, f"Volt gimbal {side}", side * 43, 78, 8 if side < 0 else 9)
        glow(r, thruster, f"Nozzle charge {side}", 0, 13, 25, 8)
        for dx in (-14, 14):
            pin(r, thruster, f"Gimbal pin {side}-{dx}", dx, 0, 5)
        r.oval(thruster, f"Nozzle mouth {side}", 0, 16, 37, 12, DEEP)
        r.rect(thruster, f"Nozzle shell {side}", 0, 2, 35, 26, STEEL, r=8)
        flame = r.node(thruster, f"Volt ion exhaust {side}", y=18)
        r.bind(flame, "scaleY", "jet", 1)
        r.bind(flame, "opacity", "voltPower", 1)
        r.oval(flame, f"Ion exhaust core {side}", 0, 12, 12, 27, ("CCECFFFF", "0040CBFF"))
        r.oval(flame, f"Ion exhaust halo {side}", 0, 15, 26, 42, ("5577EFFF", "002175C9"))


def face(r):
    h = r.node(r.robot, "Head", y=r.head_y)
    r.bind(h, "y", "Head.y", r.head_y)
    r.bind(h, "rotation", "Head.rotation", 0)
    gaze = r.node(h, "Gaze")
    r.bind(gaze, "x", "lookX", 0)
    r.bind(gaze, "y", "lookY", 0)
    for name, field, points in [
        ("Smile", "Smile.opacity", [(-12, 20), (-6, 24), (4, 25), (13, 20)]),
        ("Focus mouth", "Focus mouth.opacity", [(-11, 23), (11, 23)]),
        ("Sad mouth", "Sad mouth.opacity", [(-12, 24), (-5, 19), (5, 19), (12, 24)]),
    ]:
        mouth = r.node(gaze, name)
        r.bind(mouth, "opacity", field, 1 if name == "Smile" else 0)
        r.path(mouth, name + " phosphor", points, "FFB7FAFF", stroke=3)
    shock = r.node(gaze, "Surprised mouth")
    r.bind(shock, "opacity", "shock", 0)
    r.oval(shock, "Volt surprised mouth", 0, 23, 11, 13, LIGHT)
    eyes = r.node(gaze, "Eyes", y=-9)
    r.bind(eyes, "scaleX", "Eyes.scaleX", 1)
    r.bind(eyes, "scaleY", "Eyes.scaleY", 1)
    iris = r.node(eyes, "Volt optical power")
    r.bind(iris, "opacity", "voltPower", 1)
    r.oval(iris, "Lens glint", -5, -6, 7, 9, "FFFFFFFF")
    r.oval(iris, "Lens inner iris", 0, 0, 15, 19, ("FFEEFFFF", "FF54E5F9"))
    r.oval(iris, "Lens outer iris", 0, 0, 27, 29, ("FF66DBEC", "FF17638D"))
    r.oval(eyes, "Lens dark aperture", 0, 0, 35, 36, DEEP)
    r.oval(eyes, "Lens silver rim", 0, 0, 43, 44, STEEL)
    r.oval(eyes, "Lens recessed rim", 0, 1, 51, 51, "FF071E35")
    for side in (-1, 1):
        brow = r.node(h, f"Brow {side}", x=side * 19, y=-30)
        r.bind(brow, "rotation", "Brow L.rotation" if side < 0 else "Brow R.rotation", 0)
        r.rect(brow, f"Volt brow phosphor {side}", 0, 0, 22, 3, "FF91F1FF", r=1)
        r.rect(brow, f"Volt brow shutter {side}", 0, -1, 27, 7, DEEP, r=3)
        pin(r, h, f"Temple screw {side}", side * 45, -17, 5)
        r.rect(h, f"Temple groove {side}", side * 44, 13, 4, 18, "FF1C5980", r=2)
        r.path(h, f"Helmet seam {side}", [(side * 48, -31), (side * 34, -35), (side * 22, -35)], "FF7BDFF4", stroke=2)
    r.path(h, "Visor reflection", [(-31, -18), (-23, -23), (-15, -23)], "555ACBEA", stroke=3)
    r.rect(h, "Volt inset visor", 0, -1, 79, 63, DEEP, r=24)
    silhouette(r, h, "Volt raised helmet", [(-40, -40), (29, -40), (49, -25), (54, 8), (39, 33), (17, 41), (-30, 38), (-49, 21), (-54, -11)], BLUE, 13)
    silhouette(r, h, "Volt helmet depth", [(-41, -42), (31, -42), (53, -26), (58, 11), (41, 38), (18, 47), (-32, 44), (-54, 24), (-59, -13)], DEEP, 14)
    antenna = r.node(h, "Volt signal aerial", x=30, y=-39)
    r.bind(antenna, "rotation", "voltAntenna", 0)
    glow(r, antenna, "Volt aerial light", 5, -14, 6, 7)
    r.path(antenna, "Volt aerial stalk", [(0, 0), (5, -14)], COPPER, stroke=3)
    r.oval(h, "Neck swivel", 0, 42, 39, 18, STEEL)


def finish_arms(r):
    for side, label in [(-1, "L"), (1, "R")]:
        arm = next(n for n in r.robot if n.get("name") == "Arm " + label)
        fore = next(n for n in arm if n.get("name") == "Forearm " + label)
        detail = forward(arm, r.node(arm, "Volt shoulder detail " + label))
        pin(r, detail, "Shoulder cap " + label, 0, 0, 12)
        r.oval(detail, "Shoulder copper ring " + label, 0, 0, 22, 22, COPPER)
        r.oval(detail, "Shoulder armored rim " + label, 0, 0, 32, 32, BLUE)
        cuff = forward(fore, r.node(fore, "Volt wrist mechanism " + label))
        glow(r, cuff, "Wrist channel " + label, side * 4, 21, 7, 21)
        r.rect(cuff, "Wrist service plate " + label, 0, 20, 29, 37, BLUE, r=9)
        r.path(cuff, "Wrist flexible wire " + label, [(side * 8, 5), (side * 13, 16), (side * 11, 33)], COPPER, stroke=2)

