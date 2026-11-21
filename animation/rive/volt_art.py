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
EDGE = ("FFF0FDFF", "FF87E7F8", "FF298BB7")
SHADE = ("FF238EBA", "FF135D88", "FF07344F")

# Additional independent mechanisms. 0 = open iris, +.45 = half closed,
# +.7 = closed. The visor's useful range is +/- .25 rad. Radiator vanes
# are flush at 0; - .5 on the left / + .5 on the right opens them.
JOINTS = {
    7: "counter-rotating outer reactor ring",
    10: "six pivoting iris blades",
    11: "protective lens brow carrier",
    12: "left radiator vanes",
    13: "right radiator vanes",
}


def fit_materials(parent):
    """Fit highlights to the actual part, not the generic 120px paint box."""
    for shape in parent.iter("Shape"):
        geometry = next((child for child in shape if child.tag in {"Ellipse", "Rectangle", "PointsPath"}), None)
        if geometry is None:
            continue
        if geometry.tag == "PointsPath":
            xs = [float(v.get("x", "0")) for v in geometry]
            ys = [float(v.get("y", "0")) for v in geometry]
            left, right, top, bottom = min(xs), max(xs), min(ys), max(ys)
        else:
            w, h = float(geometry.get("width")), float(geometry.get("height"))
            left, right, top, bottom = -w / 2, w / 2, -h / 2, h / 2
        for gradient in shape.iter("LinearGradient"):
            gradient.set("startX", str(left + (right - left) * .14))
            gradient.set("startY", str(top))
            gradient.set("endX", str(right - (right - left) * .08))
            gradient.set("endY", str(bottom))


def cable(r, parent, name, points, color, stroke):
    shape = r.path(parent, name, points, color, stroke=stroke)
    shape.find("PointsPath").set("isClosed", "false")
    return shape


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
    r.bind(b, "scaleX", "bodyscaleX", 1)
    r.bind(b, "scaleY", "bodyscaleY", 1)
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
    r.oval(ring, "Turbine polished ring", 0, 0, 55, 59, ("FFF2FCFF", "FF93BCCB", "FF36596F", "FFB8E8EE"))
    # Eight separate milled vanes pass the fixed containment claws. This is
    # a second rotor, never a decal rotating with the first ring.
    counter = r.joint(core, "Volt counter rotor", 0, 0, 7)
    core.remove(counter)
    core.insert(1, counter)
    for i in range(8):
        vane = r.node(counter, f"Counter rotor vane {i}", rotation=i * math.tau / 8)
        silhouette(r, vane, f"Counter rotor milled fin {i}", [(24, -4), (33, -7), (36, -1), (33, 7), (28, 8), (29, 2)], STEEL, 2)
        cable(r, vane, f"Counter rotor glint {i}", [(28, -3), (32, -4), (33, 0)], "FFB6F1F7", 1.3)
    cage = forward(core, r.node(core, "Volt fixed containment cage"))
    for side in (-1, 1):
        for vertical in (-1, 1):
            silhouette(r, cage, f"Containment jaw {side}-{vertical}", [
                (side * 16, vertical * 25), (side * 25, vertical * 19),
                (side * 31, vertical * 21), (side * 28, vertical * 32),
                (side * 18, vertical * 36), (side * 12, vertical * 30),
            ], ("FFE0F9FF", "FF6299B1", "FF163B56"), 3)
    cable(r, energy, "Core glass caustic", [(-11, -10), (-13, -3), (-9, 9)], "99FFFFFF", 2)
    silhouette(r, energy, "Core refracted depth", [(3, -17), (13, -9), (15, 7), (6, 15), (10, 3)], "6633769C", 4)
    r.oval(core, "Reactor gasket", 0, 2, 66, 71, DEEP)
    for side in (-1, 1):
        for y in (-30, 36):
            pin(r, b, f"Reactor fastener {side}-{y}", side * 26, y, 6)
        plate = r.joint(b, f"Volt service panel {side}", side * 43, 10, 5 if side < 0 else 6)
        r.path(plate, f"Panel light guide {side}", [(side * 7, -27), (side * 17, -18), (side * 18, 12)], "FF9EF9FF", stroke=2)
        radiator = r.node(plate, f"Volt radiator cassette {side}", x=side * 11, y=25)
        for j in range(3):
            vane = r.joint(radiator, f"Volt cooling vane {side}-{j}", 0, -6 + j * 6, 12 if side < 0 else 13)
            r.rect(vane, f"Panel vent {side}-{j}", 0, 0, 17, 2.7, ("FF83B7C8", "FF173D5B"), r=1)
        r.rect(radiator, f"Radiator fin cavity {side}", 0, 0, 18, 20, DEEP, r=3)
        r.rect(radiator, f"Radiator milled bezel {side}", 0, 0, 23, 25, STEEL, r=4)
        silhouette(r, plate, f"Armor shoulder bevel {side}", [(-side * 6, -40), (side * 17, -34), (side * 25, -17), (side * 20, -20), (side * 12, -28), (-side * 5, -32)], EDGE, 4)
        silhouette(r, plate, f"Armor lower bevel {side}", [(side * 25, 1), (side * 21, 22), (side * 4, 43), (-side * 6, 39), (side * 7, 34), (side * 16, 17)], SHADE, 5)
        silhouette(r, plate, f"Sculpted cheek armor {side}", [(-side * 8, -43), (side * 19, -37), (side * 30, -16), (side * 24, 23), (side * 5, 46), (-side * 8, 41)], BLUE, 10)
        r.path(b, f"Copper bus {side}", [(side * 29, -30), (side * 43, -40), (side * 49, -61)], COPPER, stroke=5)
        pin(r, b, f"Chest latch {side}", side * 50, -23)
    r.path(b, "Chest top rim", [(-48, -39), (-24, -51), (25, -51), (48, -39)], "FFB9F2FF", stroke=3)
    r.path(b, "Chest bottom seam", [(-43, 48), (-20, 61), (20, 61), (43, 48)], "FF0B3C61", stroke=4)
    silhouette(r, b, "Chest upper machined plane", [(-48, -40), (-23, -51), (25, -51), (47, -38), (22, -42), (-19, -42), (-47, -28)], EDGE, 5)
    silhouette(r, b, "Chest left reflected edge", [(-61, -28), (-54, -35), (-58, 7), (-46, 42), (-31, 55), (-40, 52), (-58, 36), (-65, 6)], ("FF8BEAF2", "FF1686AE", "FF0B466D"), 6)
    silhouette(r, b, "Chest lower sculpted plane", [(-31, 55), (-9, 63), (21, 63), (45, 49), (35, 64), (19, 72), (-28, 69), (-44, 55)], SHADE, 5)
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
            r.rect(contacts, f"Electrode ceramic collar {side}-{dx}", dx, 2, 12, 7, ("FFF0F4E7", "FF7DADB9", "FF214C64"), r=2)
        r.rect(contacts, f"Contact crown protective casing {side}", 0, 7, 39, 9, DEEP, r=3)
        r.rect(contacts, f"Crown coupling {side}", 0, 1, 35, 10, COPPER, r=4)
        # Three distinct materials per winding; no oversized glow hides the metal.
        for i, y in enumerate(range(-45, 5, 10)):
            glow(r, coil, f"Coil live edge {side}-{i}", -2, y - 1, 34, 3)
            r.oval(coil, f"Winding crown {side}-{i}", -2, y - 2, 39, 7, ("FFF1FFFF", "FF70CFE6", "FF176E98"))
            r.oval(coil, f"Winding copper {side}-{i}", 1, y + 2, 41, 8, ("FFF4D6A2", "FF9A794E", "FF3C5262"))
        r.oval(coil, f"Upper ceramic terminal {side}", 0, -50, 37, 10, ("FFF4F7E8", "FFA9C6C5", "FF3D788E"))
        r.oval(coil, f"Lower ceramic terminal {side}", 0, 6, 39, 12, ("FFF4F7E8", "FF6B9AA9", "FF214B66"))
        r.rect(coil, f"Ceramic spine {side}", 0, -24, 16, 70, ("FFB4DAEB", "FF214C6C"), r=6)
        r.oval(coil, f"Coil universal pin {side}", 0, 14, 13, 13, STEEL)
        r.oval(coil, f"Coil universal hub {side}", 0, 14, 25, 25, DEEP)
        silhouette(r, coil, f"Mast articulated bracket {side}", [(-9, 4), (9, 4), (side * 15, 24), (side * 7, 36), (-side * 4, 34)], STEEL, 4)
        r.rect(coil, f"Mast chromed piston {side}", side * 14, 28, 5, 20, STEEL, r=2)
        r.rect(coil, f"Mast hydraulic sleeve {side}", side * 14, 16, 9, 12, DEEP, r=3)
        cable(r, r.robot, f"Coil hose reflection {side}", [(side * 49, -24), (side * 64, -21), (side * 79, -31), (side * 76, -44)], "FF59899D", 2)
        cable(r, r.robot, f"Coil flexible cable {side}", [(side * 49, -24), (side * 64, -21), (side * 79, -31), (side * 76, -44)], DEEP, 8)
        # Nozzle body and separate gimbal respond to acceleration and landing.
        label = "L" if side < 0 else "R"
        thruster = r.joint(r.robot, f"Volt gimbal {side}", side * 43, 78, 8 if side < 0 else 9)
        r.bind(thruster, "x", "voltLeg" + label + "X", side * 43)
        r.bind(thruster, "y", "voltLeg" + label + "Y", 78)
        ankle = r.joint(thruster, "Volt ankle " + label, 0, 0, 14 if side < 0 else 15)
        glow(r, ankle, f"Nozzle charge {side}", 0, 13, 25, 8)
        for dx in (-14, 14):
            pin(r, ankle, f"Gimbal pin {side}-{dx}", dx, 0, 5)
        r.oval(ankle, f"Nozzle mouth {side}", 0, 16, 37, 12, DEEP)
        r.rect(ankle, f"Nozzle shell {side}", 0, 2, 35, 26, STEEL, r=8)
        flame = r.node(ankle, f"Volt ion exhaust {side}", y=18)
        r.bind(flame, "scaleY", "jet", 1)
        r.bind(flame, "opacity", "voltPower", 1)
        r.oval(flame, f"Ion exhaust core {side}", 0, 12, 12, 27, ("CCECFFFF", "0040CBFF"))
        r.oval(flame, f"Ion exhaust halo {side}", 0, 15, 26, 42, ("5577EFFF", "002175C9"))
        strut = r.node(r.robot, "Volt suspension " + label, x=side * 43, y=56)
        r.bind(strut, "scaleY", "voltStrut" + label, 1)
        for dx in (-7, 7):
            r.rect(strut, f"Suspension rod {label}-{dx}", dx, 10, 3, 22, STEEL, r=1)
    fit_materials(r.robot)


def face(r):
    h = r.node(r.robot, "Head", y=r.head_y)
    r.bind(h, "y", "Head.y", r.head_y)
    r.bind(h, "rotation", "Head.rotation", 0)
    gaze = r.node(h, "Gaze")
    r.bind(gaze, "x", "lookX", 0)
    r.bind(gaze, "y", "lookY", 0)
    phosphor = r.node(gaze, "Volt phosphor screen")
    r.bind(phosphor, "opacity", "voltFacePower", 1)
    for name, field, points in [
        ("Smile", "Smile.opacity", [(-12, 20), (-6, 24), (4, 25), (13, 20)]),
        ("Focus mouth", "Focus mouth.opacity", [(-11, 23), (11, 23)]),
        ("Sad mouth", "Sad mouth.opacity", [(-12, 24), (-5, 19), (5, 19), (12, 24)]),
    ]:
        mouth = r.node(phosphor, name)
        r.bind(mouth, "opacity", field, 1 if name == "Smile" else 0)
        r.path(mouth, name + " phosphor", points, "FFB7FAFF", stroke=3)
    shock = r.node(phosphor, "Surprised mouth")
    r.bind(shock, "opacity", "shock", 0)
    r.oval(shock, "Volt surprised mouth", 0, 23, 11, 13, LIGHT)
    eyes = r.node(gaze, "Eyes", y=-9)
    r.bind(eyes, "y", "voltOpticY", -9)
    r.bind(eyes, "rotation", "voltOpticRoll", 0)
    r.bind(eyes, "scaleX", "Eyes.scaleX", 1)
    r.bind(eyes, "scaleY", "Eyes.scaleY", 1)
    # Six blades turn about separate eccentric pivots. Positive joint10 closes
    # the pupil; zero leaves a clear central aperture, with no clipping layer.
    for i in range(6):
        orbit = r.node(eyes, f"Volt iris pivot frame {i}", rotation=i * math.tau / 6)
        blade = r.joint(orbit, f"Volt iris blade {i}", 22, 0, 10)
        silhouette(r, blade, f"Iris machined leaf {i}", [(0, -7), (4, -2), (1, 10), (-9, 23), (-21, 18), (-18, 16), (-16, 11), (-11, 7), (-8, -2)],
                   ("FFC9E7ED", "FF527A91", "FF142F49") if i % 2 else ("FFF0FBFF", "FF91B2C3", "FF274B66"), .8)
    iris = r.node(eyes, "Volt optical power")
    r.bind(iris, "opacity", "voltPower", 1)
    r.oval(iris, "Lens glint", -5, -6, 7, 9, "FFFFFFFF")
    r.oval(iris, "Lens inner iris", 0, 0, 21, 25, ("FFEEFFFF", "FF54E5F9"))
    r.oval(iris, "Lens outer iris", 0, 0, 27, 29, ("FF66DBEC", "FF17638D"))
    r.oval(eyes, "Lens dark aperture", 0, 0, 38, 39, DEEP)
    r.oval(eyes, "Lens silver rim", 0, 0, 49, 50, STEEL)
    r.oval(eyes, "Lens recessed rim", 0, 1, 54, 55, "FF071E35")
    brow_carrier = r.joint(h, "Volt protective brow carrier", 0, -31, 11)
    silhouette(r, brow_carrier, "Visor hood edge", [(-35, -5), (-20, -9), (17, -9), (35, -3), (29, 0), (-29, 0)], EDGE, 3)
    silhouette(r, brow_carrier, "Visor hood underside", [(-29, -1), (29, -1), (25, 6), (-25, 6)], DEEP, 3)
    for side in (-1, 1):
        brow = r.node(brow_carrier, f"Brow {side}", x=side * 19, y=1)
        r.bind(brow, "rotation", "Brow L.rotation" if side < 0 else "Brow R.rotation", 0)
        r.rect(brow, f"Volt brow phosphor {side}", 0, 0, 22, 3, "FF91F1FF", r=1)
        r.rect(brow, f"Volt brow shutter {side}", 0, -1, 27, 7, DEEP, r=3)
        pin(r, h, f"Temple screw {side}", side * 45, -17, 5)
        r.rect(h, f"Temple groove {side}", side * 44, 13, 4, 18, "FF1C5980", r=2)
        r.path(h, f"Helmet seam {side}", [(side * 48, -31), (side * 34, -35), (side * 22, -35)], "FF7BDFF4", stroke=2)
    r.path(h, "Visor reflection", [(-31, -18), (-23, -23), (-15, -23)], "555ACBEA", stroke=3)
    r.rect(h, "Volt inset visor", 0, -1, 79, 63, DEEP, r=24)
    silhouette(r, h, "Helmet crown bevel", [(-40, -40), (29, -40), (46, -25), (29, -30), (-30, -30), (-48, -14), (-50, -27)], EDGE, 5)
    silhouette(r, h, "Helmet side shadow", [(34, -29), (49, -23), (54, 8), (39, 33), (33, 29), (41, 6)], SHADE, 5)
    silhouette(r, h, "Helmet reflected side plane", [(-50, -13), (-43, -26), (-38, -17), (-38, 18), (-30, 31), (-41, 25), (-49, 13)], ("FFC9F9FA", "FF37ACD2", "FF0D608C"), 5)
    silhouette(r, h, "Helmet sculpted chin", [(-30, 32), (17, 35), (34, 27), (24, 40), (-25, 38)], ("FF4DADCB", "FF17668D", "FF073A5D"), 4)
    silhouette(r, h, "Volt raised helmet", [(-40, -40), (29, -40), (49, -25), (54, 8), (39, 33), (17, 41), (-30, 38), (-49, 21), (-54, -11)], BLUE, 13)
    silhouette(r, h, "Volt helmet depth", [(-41, -42), (31, -42), (53, -26), (58, 11), (41, 38), (18, 47), (-32, 44), (-54, 24), (-59, -13)], DEEP, 14)
    antenna = r.node(h, "Volt signal aerial", x=30, y=-39)
    r.bind(antenna, "rotation", "voltAntenna", 0)
    glow(r, antenna, "Volt aerial light", 5, -14, 6, 7)
    r.path(antenna, "Volt aerial stalk", [(0, 0), (5, -14)], COPPER, stroke=3)
    r.oval(h, "Neck swivel", 0, 42, 39, 18, STEEL)
    fit_materials(h)


def finish_arms(r):
    for side, label in [(-1, "L"), (1, "R")]:
        arm = next(n for n in r.robot if n.get("name") == "Arm " + label)
        fore = next(n for n in arm if n.get("name") == "Forearm " + label)
        detail = forward(arm, r.node(arm, "Volt shoulder detail " + label))
        r.bind(detail, "rotation", "voltShoulder" + label, 0)
        pin(r, detail, "Shoulder cap " + label, 0, 0, 12)
        r.oval(detail, "Shoulder copper ring " + label, 0, 0, 22, 22, COPPER)
        r.oval(detail, "Shoulder armored rim " + label, 0, 0, 32, 32, BLUE)
        piston = r.node(detail, "Volt piston slider " + label, y=19)
        r.bind(piston, "y", "voltPiston" + label, 19)
        r.rect(piston, "Upper arm chromed piston " + label, side * 5, 0, 5, 25, STEEL, r=2)
        r.rect(detail, "Upper arm rod coupling " + label, side * 5, 31, 10, 6, DEEP, r=2)
        cable(r, detail, "Elbow service hose " + label, [(side * 12, 8), (side * 15, 23), (side * 9, 36)], COPPER, 2.3)
        cuff = forward(fore, r.node(fore, "Volt wrist mechanism " + label))
        glow(r, cuff, "Wrist channel " + label, side * 4, 21, 7, 21)
        silhouette(r, cuff, "Wrist bright bevel " + label, [(-13, 3), (-6, 0), (10, 0), (13, 6), (-7, 5), (-10, 34), (-14, 31)], EDGE, 3)
        silhouette(r, cuff, "Wrist sculpted shade " + label, [(10, 4), (15, 10), (15, 33), (7, 40), (-9, 39), (6, 33)], SHADE, 3)
        r.rect(cuff, "Wrist service plate " + label, 0, 20, 29, 37, BLUE, r=9)
        r.path(cuff, "Wrist flexible wire " + label, [(side * 8, 5), (side * 13, 16), (side * 11, 33)], COPPER, stroke=2)
        fit_materials(detail)
        fit_materials(cuff)

