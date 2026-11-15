"""Author the editable, script-free Spark rig. Build with the official Rive CLI.

All RML names/property keys below were checked with rive 1.9.2 schema/docs.
Art, timeline poses, facial expressions and bindings live in Rive; the native
host integrates locomotion distance and feeds the wheel/track bindings.
"""

import math
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent
STATES = ("idle", "move", "attack", "defend", "charge", "hit", "victory", "defeat")
PROPERTIES = {
    "x": 13,
    "y": 14,
    "rotation": 15,
    "scaleX": 16,
    "scaleY": 17,
    "opacity": 18,
}


class Rig:
    def __init__(self):
        self.next_id = 100
        self.ids = {}
        self.defaults = {}
        self.root = ET.Element("Rive", version="1", kind="fragment")
        self.vm = ET.SubElement(
            self.root,
            "ViewModel",
            name="SparkMotion",
            id="0:10",
            defaultInstanceId="0:11",
        )
        self.instance = ET.SubElement(
            self.vm, "ViewModelInstance", name="Default", id="0:11", exports="true"
        )
        self.fields = {}
        self.field("mode", 0)
        self.field("wheelAngle", 0)
        self.field("lookX", 0)
        self.field("lookY", 0)
        self.board = ET.SubElement(
            self.root,
            "Artboard",
            width="420",
            height="440",
            name="Spark",
            id="0:2",
            styleId="0:3",
            defaultStateMachineId="0:20",
            viewModelId="0:10",
            viewModelInstanceId="0:11",
        )
        ET.SubElement(
            self.board, "LayoutComponentStyle", name="Artboard Style", id="0:3"
        )

    def element(self, parent, tag, name=None, **props):
        attrs = {k: str(v) for k, v in props.items()}
        if name:
            attrs["name"] = name
            attrs["id"] = self.ids.setdefault(name, f"0:{self.next_id}")
            self.next_id += 1
            self.defaults[name] = props.copy()
        return ET.SubElement(parent, tag, attrs)

    def field(self, name, value):
        if name not in self.fields:
            identity = f"0:{20_000 + len(self.fields)}"
            ET.SubElement(self.vm, "ViewModelPropertyNumber", name=name, id=identity)
            ET.SubElement(
                self.instance,
                "ViewModelInstanceNumber",
                viewModelPropertyId=identity,
                propertyValue=str(value),
            )
            self.fields[name] = identity
        return self.fields[name]

    def bind(self, element, prop, field, value=0):
        identity = self.field(field, value)
        ET.SubElement(
            element,
            "DataBindContext",
            propertyKey=str(PROPERTIES[prop]),
            sourcePathIds=f"0:10-{identity}",
        )

    def paint(self, shape, color, *, stroke=0):
        paint = ET.SubElement(
            shape,
            "Stroke" if stroke else "Fill",
            **(
                {"thickness": str(stroke), "cap": "round", "join": "round"}
                if stroke
                else {}
            ),
        )
        if isinstance(color, tuple):
            gradient = ET.SubElement(
                paint,
                "LinearGradient",
                startX="-60",
                startY="-60",
                endX="60",
                endY="65",
            )
            for i, value in enumerate(color):
                ET.SubElement(
                    gradient,
                    "GradientStop",
                    position=str(i / (len(color) - 1)),
                    colorValue=value,
                )
        else:
            ET.SubElement(paint, "SolidColor", colorValue=color)

    def shape(
        self,
        parent,
        name,
        x,
        y,
        w,
        h,
        color,
        *,
        radius=0,
        ellipse=False,
        rotation=0,
        outline=None,
    ):
        shape = self.element(parent, "Shape", name, x=x, y=y, rotation=rotation)
        ET.SubElement(
            shape,
            "Ellipse" if ellipse else "Rectangle",
            width=str(w),
            height=str(h),
            originX="0.5",
            originY="0.5",
            **({} if ellipse else {"cornerRadiusTL": str(radius)}),
        )
        if outline:
            self.paint(shape, outline, stroke=2)
        self.paint(shape, color)
        return shape

    def path(self, parent, name, points, color, *, stroke=0, closed=True):
        shape = self.element(parent, "Shape", name)
        path = ET.SubElement(
            shape, "PointsPath", isClosed=str(closed).lower(), isClockwise="true"
        )
        for x, y in points:
            ET.SubElement(path, "StraightVertex", x=str(x), y=str(y), radius="3")
        self.paint(shape, color, stroke=stroke)
        return shape

    def key(self, timeline, name, prop, values, *, linear=False):
        obj = ET.SubElement(timeline, "KeyedObject", objectId=self.ids[name])
        keyed = ET.SubElement(obj, "KeyedProperty", propertyKey=str(PROPERTIES[prop]))
        for frame, value in values:
            key = ET.SubElement(
                keyed,
                "KeyFrameDouble",
                frame=str(frame),
                value=str(value),
                interpolationType="linear" if linear else "cubic",
            )
            if not linear:
                ET.SubElement(
                    key, "CubicEaseInterpolator", x1="0.36", y1="0", x2="0.24", y2="1"
                )

    def build(self):
        r = self.element(self.board, "Node", "Robot", x=210, y=276)
        self.shape(
            r, "Antenna light", 0, -196, 13, 13, ("FFFFE8A0", "FFFFA340"), ellipse=True
        )
        self.shape(r, "Antenna stem", 0, -182, 5, 22, "FF506177", radius=2)
        head = self.element(r, "Node", "Head", x=0, y=-117)
        gaze = self.element(head, "Node", "Gaze", x=0, y=0)
        self.bind(gaze, "x", "lookX")
        self.bind(gaze, "y", "lookY")
        eyes = self.element(gaze, "Node", "Eyes", y=-3, scaleY=1)
        for x, side in ((-31, "L"), (31, "R")):
            self.shape(eyes, f"Eye glint {side}", x - 2, -3, 4, 7, "FFEDFFFF", radius=2)
            self.shape(
                eyes, f"Eye {side}", x, 0, 17, 26, ("FFBBFFFF", "FF3DE0EF"), radius=8
            )
            brow = self.element(head, "Node", f"Brow {side}", x=x, y=-26, rotation=0)
            self.shape(brow, f"Brow line {side}", 0, 0, 24, 4, "FF74F4F9", radius=2)
        smile = self.element(gaze, "Node", "Smile", opacity=1)
        self.path(
            smile,
            "Smile curve",
            [(-15, 20), (-9, 25), (0, 27), (9, 25), (15, 20)],
            "FF8FF8FC",
            stroke=4,
            closed=False,
        )
        focus = self.element(gaze, "Node", "Focus mouth", opacity=0)
        self.shape(focus, "Focus line", 0, 24, 24, 4, "FFA7FFFF", radius=2)
        sad = self.element(gaze, "Node", "Sad mouth", opacity=0)
        self.path(
            sad,
            "Sad curve",
            [(-13, 28), (-6, 23), (6, 23), (13, 28)],
            "FF8FA9BE",
            stroke=3,
            closed=False,
        )
        self.shape(
            head,
            "Glass reflection",
            -42,
            -26,
            43,
            6,
            "365DBDDF",
            radius=3,
            rotation=-0.2,
        )
        self.shape(
            head,
            "Face gasket",
            0,
            0,
            157,
            87,
            ("FF213A55", "FF081524"),
            radius=33,
            outline="FF304C67",
        )
        self.shape(
            head, "Head crest", 0, -54, 61, 11, ("FFFFCF6D", "FFF29A31"), radius=5
        )
        for x, side in ((-98, "L"), (98, "R")):
            self.shape(head, f"Ear hub {side}", x, 0, 11, 21, "FF526B83", radius=5)
            self.shape(
                head,
                f"Ear shell {side}",
                x,
                0,
                30,
                52,
                ("FFFFD473", "FFE79A39"),
                radius=15,
                outline="FF667C94",
            )
        self.shape(
            head,
            "Head shell",
            0,
            0,
            185,
            115,
            ("FFFFFFFF", "FFEAF1F5", "FF97AFC4"),
            radius=47,
            outline="FF5F7893",
        )

        for x, side in ((-89, "L"), (89, "R")):
            arm = self.element(r, "Node", f"Arm {side}", x=x, y=-48, rotation=0)
            forearm = self.element(
                arm, "Node", f"Forearm {side}", x=0, y=40, rotation=0
            )
            for dx in (-7, 0, 7):
                self.shape(
                    forearm, f"Finger {side} {dx}", dx, 31, 4, 13, "FF8296AB", radius=2
                )
            self.shape(
                forearm,
                f"Hand {side}",
                0,
                26,
                35,
                31,
                ("FF47617A", "FF20374E"),
                radius=12,
                outline="FF8DA3B7",
            )
            self.shape(
                forearm,
                f"Forearm band {side}",
                0,
                0,
                28,
                11,
                ("FFFFCA6C", "FFF2A03B"),
                radius=4,
            )
            self.shape(
                forearm,
                f"Forearm shell {side}",
                0,
                -3,
                28,
                40,
                ("FFFDFEFE", "FFA9BCCE"),
                radius=11,
            )
            self.shape(
                arm,
                f"Elbow {side}",
                0,
                35,
                22,
                22,
                "FF4A627A",
                ellipse=True,
                outline="FF98ADBE",
            )
            self.shape(
                arm,
                f"Upper arm {side}",
                0,
                18,
                22,
                36,
                ("FFF6FBFF", "FF9EB4C9"),
                radius=10,
            )
            self.shape(
                arm,
                f"Shoulder {side}",
                0,
                0,
                34,
                34,
                ("FF627E99", "FF293E57"),
                ellipse=True,
                outline="FFA6B5C2",
            )
            self.shape(
                arm, f"Shoulder light {side}", 0, 0, 11, 11, "FF83EAF3", ellipse=True
            )

        torso = self.element(r, "Node", "Body", x=0, y=0, rotation=0)
        glow = self.element(torso, "Node", "Core glow", opacity=0.8)
        self.shape(glow, "Core light", 0, -9, 38, 9, ("FFC8FFFF", "FF5CD6F1"), radius=4)
        self.shape(
            torso,
            "Core bezel",
            0,
            -9,
            53,
            20,
            "FF28465E",
            radius=10,
            outline="FF8EACC1",
        )
        for y, w in ((37, 30), (45, 25)):
            self.shape(torso, f"Vent {y}", 0, y, w, 3, "FF536C84", radius=1)
        self.path(
            torso,
            "Belly armor",
            [(-44, 24), (44, 24), (34, 54), (0, 63), (-34, 54)],
            ("FFFFCF6D", "FFED9A34"),
        )
        self.path(
            torso,
            "Chest stripe",
            [(-51, -44), (-23, -34), (23, -34), (51, -44), (42, -28), (-42, -28)],
            ("FFFFDA80", "FFEFA443"),
        )
        for x in (-52, 52):
            self.shape(torso, f"Bolt {x}", x, -2, 7, 7, "FF607E97", ellipse=True)
        self.path(
            torso,
            "Torso shell",
            [
                (-53, -50),
                (0, -63),
                (53, -50),
                (63, 10),
                (50, 52),
                (0, 70),
                (-50, 52),
                (-63, 10),
            ],
            ("FFFFFFFF", "FFE5EDF5", "FF94ADC4"),
        )
        self.shape(
            torso, "Neck piston", 0, -62, 33, 34, ("FF344B64", "FF819BB1"), radius=9
        )

        chassis = self.element(r, "Node", "Tracks", x=0, y=80)
        for i in range(16):
            x, y, angle = tread_pose(i * track_length() / 16)
            tread = self.element(
                chassis, "Node", f"Tread {i:02}", x=x, y=y, rotation=angle
            )
            self.shape(tread, f"Tread plate {i:02}", 0, 0, 15, 6, "FF8D9FAF", radius=2)
            self.bind(tread, "x", f"tread{i}X", x)
            self.bind(tread, "y", f"tread{i}Y", y)
            self.bind(tread, "rotation", f"tread{i}R", angle)
        for x, side in ((-65, "L"), (65, "R")):
            wheel = self.element(chassis, "Node", f"Wheel {side}", x=x, y=0, rotation=0)
            for spoke in range(5):
                n = self.element(
                    wheel,
                    "Node",
                    f"Spoke {side} {spoke}",
                    rotation=spoke * math.tau / 5,
                )
                self.shape(
                    n, f"Spoke bar {side} {spoke}", 0, -12, 7, 19, "FFB1C2D0", radius=3
                )
            self.shape(
                wheel, f"Wheel hub {side}", 0, 0, 13, 13, "FFFFB94D", ellipse=True
            )
            self.shape(
                wheel,
                f"Wheel rim {side}",
                0,
                0,
                47,
                47,
                ("FF60778D", "FF233C53"),
                ellipse=True,
                outline="FFB7C7D4",
            )
            self.bind(wheel, "rotation", "wheelAngle")
        self.shape(chassis, "Belt interior", 0, 0, 196, 57, "FF24384D", radius=28)
        self.shape(
            chassis,
            "Track belt",
            0,
            0,
            209,
            73,
            ("FF42566A", "FF172B40"),
            radius=36,
            outline="FF738BA0",
        )

        shield = self.element(r, "Node", "Shield", opacity=0)
        self.path(
            shield,
            "Shield shell",
            [(125, -100), (89, -119), (70, -94), (75, -6), (104, 18), (131, -6)],
            "9967E9FA",
            stroke=4,
        )
        self.shape(r, "Ground shadow", 0, 126, 215, 18, "3820344B", ellipse=True)
        aura = self.element(
            r, "Node", "Charge aura", x=0, y=-45, opacity=0, scaleX=1, scaleY=1
        )
        self.shape(aura, "Aura outer", 0, 0, 290, 332, "1229DCFF", ellipse=True)
        self.shape(aura, "Aura inner", 0, 0, 250, 293, "183EDCFF", ellipse=True)
        self.machine()
        return self.root

    def machine(self):
        machine = ET.SubElement(
            self.board, "StateMachine", name="RobotMotion", id="0:20"
        )
        layer = ET.SubElement(machine, "StateMachineLayer", name="Action", id="0:21")
        any_state = ET.SubElement(layer, "AnyState", x="-200", y="-240")
        ET.SubElement(layer, "ExitState", x="1400", y="-240")
        entry = ET.SubElement(layer, "EntryState", x="-200", y="0")
        ET.SubElement(entry, "StateTransition", stateToId="0:30")
        for i, state in enumerate(STATES):
            target = f"0:{30 + i}"
            transition = ET.SubElement(
                any_state,
                "StateTransition",
                stateToId=target,
                duration="80",
                enableEarlyExit="true",
            )
            cond = ET.SubElement(
                transition, "TransitionViewModelCondition", opValue="equal"
            )
            comparator = ET.SubElement(cond, "TransitionPropertyViewModelComparator")
            prop = ET.SubElement(comparator, "BindablePropertyNumber")
            ET.SubElement(
                prop,
                "DataBindContext",
                sourcePathIds=f"0:10-{self.fields['mode']}",
                propertyKey="636",
            )
            ET.SubElement(cond, "TransitionValueNumberComparator", value=str(i))
            ET.SubElement(
                layer,
                "AnimationState",
                id=target,
                stateName=state,
                animationId=f"0:{50 + i}",
                x=str(i * 195),
                y=str((i % 2) * 145),
            )
            duration = (168, 48, 66, 96, 108, 48, 120, 90)[i]
            timeline = ET.SubElement(
                self.board,
                "LinearAnimation",
                id=f"0:{50 + i}",
                name=state,
                fps="60",
                duration=str(duration),
                quantize="false",
                loopValue="loop"
                if state in {"idle", "move", "defend", "charge", "victory"}
                else "oneShot",
            )
            poses = {
                ("Robot", "x"): [(0, 210), (duration, 210)],
                ("Robot", "y"): [(0, 276), (duration, 276)],
                ("Robot", "rotation"): [(0, 0), (duration, 0)],
                ("Head", "rotation"): [(0, 0), (duration // 2, -0.035), (duration, 0)],
                ("Body", "y"): [(0, 0), (duration // 2, -2), (duration, 0)],
                ("Head", "y"): [(0, -117), (duration // 2, -120), (duration, -117)],
                ("Arm L", "rotation"): [
                    (0, 0.04),
                    (duration // 2, -0.05),
                    (duration, 0.04),
                ],
                ("Arm R", "rotation"): [
                    (0, -0.04),
                    (duration // 2, 0.05),
                    (duration, -0.04),
                ],
                ("Forearm L", "rotation"): [(0, 0), (duration, 0)],
                ("Forearm R", "rotation"): [(0, 0), (duration, 0)],
                ("Eyes", "scaleY"): [
                    (0, 1),
                    (120 if state == "idle" else duration // 2, 1),
                    (125 if state == "idle" else duration - 1, 1),
                    (duration, 1),
                ],
                ("Smile", "opacity"): [
                    (0, 1 if state in {"idle", "move", "victory"} else 0)
                ],
                ("Focus mouth", "opacity"): [
                    (0, 1 if state in {"attack", "charge", "defend", "hit"} else 0)
                ],
                ("Sad mouth", "opacity"): [(0, 1 if state == "defeat" else 0)],
                ("Brow L", "rotation"): [
                    (
                        0,
                        0.28
                        if state in {"attack", "charge", "defend"}
                        else -0.15
                        if state == "defeat"
                        else 0,
                    )
                ],
                ("Brow R", "rotation"): [
                    (
                        0,
                        -0.28
                        if state in {"attack", "charge", "defend"}
                        else 0.15
                        if state == "defeat"
                        else 0,
                    )
                ],
                ("Shield", "opacity"): [
                    (0, 0.75 if state == "defend" else 0),
                    (duration // 2, 1 if state == "defend" else 0),
                    (duration, 0.75 if state == "defend" else 0),
                ],
                ("Charge aura", "opacity"): [
                    (0, 0.2 if state == "charge" else 0),
                    (duration // 2, 0.85 if state == "charge" else 0),
                    (duration, 0.2 if state == "charge" else 0),
                ],
                ("Core glow", "opacity"): [
                    (0, 0.8),
                    (duration // 2, 1),
                    (duration, 0.8),
                ],
            }
            if state == "idle":
                poses[("Eyes", "scaleY")] = [
                    (0, 1),
                    (119, 1),
                    (123, 0.08),
                    (127, 1),
                    (168, 1),
                ]
            elif state == "move":
                poses[("Body", "y")] = [(0, 0), (12, -3), (24, 0), (36, -3), (48, 0)]
                poses[("Head", "rotation")] = [(0, -0.025), (24, 0.025), (48, -0.025)]
            elif state == "attack":
                # Anticipation -> release/impact -> recoil -> recovery.
                poses[("Robot", "x")] = [
                    (0, 210),
                    (12, 196),
                    (20, 233),
                    (26, 220),
                    (44, 207),
                    (66, 210),
                ]
                poses[("Robot", "rotation")] = [
                    (0, 0),
                    (12, -0.05),
                    (20, 0.07),
                    (28, -0.025),
                    (66, 0),
                ]
                poses[("Arm R", "rotation")] = [
                    (0, 0),
                    (12, 0.4),
                    (20, -1.65),
                    (28, -1.2),
                    (45, -0.6),
                    (66, 0),
                ]
                poses[("Forearm R", "rotation")] = [
                    (0, 0),
                    (12, -1.2),
                    (20, -0.2),
                    (30, -0.6),
                    (66, 0),
                ]
                poses[("Head", "rotation")] = [(0, 0), (12, -0.09), (20, 0.05), (66, 0)]
            elif state == "defend":
                poses[("Arm R", "rotation")] = [(0, -1.2), (48, -1.27), (96, -1.2)]
                poses[("Forearm R", "rotation")] = [(0, -0.8), (96, -0.8)]
                poses[("Robot", "rotation")] = [(0, -0.035), (96, -0.035)]
            elif state == "charge":
                for side, sign in (("L", -1), ("R", 1)):
                    poses[(f"Arm {side}", "rotation")] = [
                        (0, sign * -0.3),
                        (54, sign * -0.48),
                        (108, sign * -0.3),
                    ]
                poses[("Body", "y")] = [(0, 0), (54, -4), (108, 0)]
            elif state == "hit":
                poses[("Robot", "x")] = [
                    (0, 210),
                    (5, 189),
                    (12, 198),
                    (24, 206),
                    (48, 210),
                ]
                poses[("Robot", "rotation")] = [
                    (0, 0),
                    (5, -0.13),
                    (12, 0.045),
                    (24, -0.02),
                    (48, 0),
                ]
                poses[("Head", "rotation")] = [(0, 0), (5, -0.2), (17, 0.08), (48, 0)]
                poses[("Eyes", "scaleY")] = [
                    (0, 1),
                    (4, 0.15),
                    (16, 0.35),
                    (36, 1),
                    (48, 1),
                ]
            elif state == "victory":
                poses[("Arm L", "rotation")] = [
                    (0, 2.5),
                    (30, 2.2),
                    (60, 2.5),
                    (90, 2.2),
                    (120, 2.5),
                ]
                poses[("Arm R", "rotation")] = [
                    (0, -2.5),
                    (30, -2.2),
                    (60, -2.5),
                    (90, -2.2),
                    (120, -2.5),
                ]
                poses[("Robot", "y")] = [
                    (0, 276),
                    (24, 266),
                    (48, 276),
                    (72, 267),
                    (96, 276),
                    (120, 276),
                ]
            elif state == "defeat":
                poses[("Head", "rotation")] = [(0, 0), (35, 0.23), (90, 0.23)]
                poses[("Head", "y")] = [(0, -117), (35, -107), (90, -107)]
                poses[("Core glow", "opacity")] = [(0, 0.8), (50, 0.15), (90, 0.15)]
                poses[("Eyes", "scaleY")] = [(0, 1), (35, 0.35), (90, 0.35)]
            for (part, prop), values in poses.items():
                self.key(timeline, part, prop, values)


def track_length():
    return 2 * 134 + math.tau * 29


def tread_pose(distance):
    """Constant arc length around a capsule, clockwise along the upper run."""
    s = distance % track_length()
    if s < 134:
        return -67 + s, -29, 0
    s -= 134
    if s < math.pi * 29:
        a = s / 29 - math.pi / 2
        return 67 + 29 * math.cos(a), 29 * math.sin(a), a + math.pi / 2
    s -= math.pi * 29
    if s < 134:
        return 67 - s, 29, math.pi
    a = (s - 134) / 29 + math.pi / 2
    return -67 + 29 * math.cos(a), 29 * math.sin(a), a + math.pi / 2


def main():
    root = Rig().build()
    ET.indent(root, space="  ")
    target = ROOT / "spark/scene.rml"
    ET.ElementTree(root).write(target, encoding="utf-8", xml_declaration=True)
    print(f"Wrote {target}")


if __name__ == "__main__":
    main()
