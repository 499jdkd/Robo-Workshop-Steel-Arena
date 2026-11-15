"""Production scene rig, built on Spark's verified Rive hierarchy.

The original lab stays reproducible. Combat poses are additive data bindings,
evaluated in Flutter against the game's semantic events, never in Python/frame.
"""

import shutil
import xml.etree.ElementTree as ET
from pathlib import Path

from generate_spark import PROPERTIES, Rig

ROOT = Path(__file__).resolve().parent


def build():
    rig = Rig()
    root = rig.build()
    board = rig.board
    nodes = {e.get("name"): e for e in root.iter() if e.get("name")}
    # Keep the state machine/secondary glow timelines. The pose bindings below
    # own only articulated transforms, so there is no timeline/host contention.
    driven = {
        "Robot": {"x": 210, "y": 276, "rotation": 0},
        "Head": {"y": -117, "rotation": 0},
        "Body": {"y": 0, "rotation": 0},
        "Arm L": {"rotation": 0},
        "Arm R": {"rotation": 0},
        "Forearm L": {"rotation": 0},
        "Forearm R": {"rotation": 0},
        "Eyes": {"scaleX": 1, "scaleY": 1},
        "Smile": {"opacity": 1},
        "Focus mouth": {"opacity": 0},
        "Sad mouth": {"opacity": 0},
        "Brow L": {"rotation": 0},
        "Brow R": {"rotation": 0},
        "Shield": {"opacity": 0},
        "Charge aura": {"opacity": 0},
    }
    for name, props in driven.items():
        for timeline in board.findall("LinearAnimation"):
            for obj in list(timeline.findall("KeyedObject")):
                if obj.get("objectId") != rig.ids[name]:
                    continue
                for prop in list(obj):
                    if int(prop.get("propertyKey")) in {PROPERTIES[p] for p in props}:
                        obj.remove(prop)
                if not len(obj):
                    timeline.remove(obj)
        for prop, default in props.items():
            rig.bind(nodes[name], prop, f"{name}.{prop}", default)

    hand = rig.element(nodes["Forearm R"], "Node", "Palm", opacity=1)
    # Move, don't duplicate, the original hand underneath a retractable palm.
    for child in list(nodes["Forearm R"]):
        if (child.get("name") or "").startswith(("Hand R", "Finger R")):
            nodes["Forearm R"].remove(child)
            hand.append(child)
    rig.bind(hand, "opacity", "palm", 1)
    rig.bind(hand, "scaleY", "palm", 1)

    def weapon(name):
        n = rig.element(nodes["Forearm R"], "Node", name, y=18, opacity=0)
        nodes["Forearm R"].remove(n)
        nodes["Forearm R"].insert(0, n)  # Rive draws first siblings above later ones.
        rig.bind(n, "opacity", name.lower(), 0)
        rig.bind(n, "scaleY", "deploy", 0.02)
        rig.bind(n, "y", "barrelY", 18)
        return n

    plasma = weapon("Plasma")
    for y in (49, 69, 89):
        rig.shape(plasma, f"Plasma ring {y}", 0, y, 49, 8, ("FFBCFFFF", "FF1DBBD5"), radius=4)
    rig.shape(plasma, "Plasma muzzle", 0, 108, 41, 15, ("FFEAFFFF", "FF1693AA"), radius=5)
    rig.shape(plasma, "Plasma core", 0, 55, 21, 76, ("FF61F8FF", "FF35679E"), radius=9)
    rig.shape(plasma, "Plasma barrel", 0, 52, 43, 104, ("FFDBF0FF", "FF293F61"), radius=14, outline="FF6B96B5")
    for dx in (-28, 28):
        fin = rig.element(plasma, "Node", f"Plasma fin {dx}", x=dx, y=34)
        rig.bind(fin, "rotation", "fin" if dx > 0 else "finBack", 0)
        rig.shape(fin, f"Plasma armor fin {dx}", 0, 0, 13, 58, ("FFFFE4A0", "FFD78F29"), radius=5)

    sniper = weapon("Sniper")
    rig.shape(sniper, "Sniper muzzle brake", 0, 175, 24, 19, "FF394C6C", radius=4)
    for y in (174, 179):
        rig.shape(sniper, f"Muzzle slot {y}", 0, y, 21, 3, "FF0D192A", radius=1)
    rig.shape(sniper, "Sniper long barrel", 0, 113, 11, 115, ("FF96ADCB", "FF283A55"), radius=3)
    rig.shape(sniper, "Scope lens", -29, 69, 16, 9, "FFED6279", ellipse=True)
    rig.shape(sniper, "Scope", -29, 41, 17, 53, ("FF7C96B6", "FF28364E"), radius=6)
    rig.shape(sniper, "Scope mount", -14, 34, 22, 12, "FF384F6C", radius=3)
    rig.shape(sniper, "Sniper receiver", 0, 34, 38, 81, ("FFE5ECF9", "FF556783"), radius=8)
    rig.shape(sniper, "Sniper magazine", 27, 28, 28, 33, "FF3B5272", radius=5, rotation=-.25)

    fist = weapon("Fist")
    for dx in (-17, 0, 17):
        rig.shape(fist, f"Charged knuckle {dx}", dx, 66, 14, 18, ("FFECFFFF", "FF5BE9FF"), radius=6)
    rig.shape(fist, "Electric gauntlet", 0, 42, 65, 65, ("FFFEFFFF", "FF476F9D"), radius=16, outline="FF72EAFB")
    rig.shape(fist, "Gauntlet coil", 0, 10, 53, 16, "FF39DDF6", radius=6)

    rocket = weapon("Rocket")
    for i, dx in enumerate((-20, 20)):
        n = rig.element(rocket, "Node", f"Missile {i}", x=dx, y=34)
        rig.bind(n, "y", f"missile{i}", 34)
        rig.shape(n, f"Rocket tip {i}", 0, 47, 18, 23, ("FFFFA366", "FFF15754"), radius=8)
        rig.shape(n, f"Rocket hull {i}", 0, 16, 18, 48, ("FFF0F4FA", "FF9AACC3"), radius=6)
        rig.shape(rocket, f"Launcher aperture {i}", dx, 57, 24, 12, "FF1D2B44", radius=5)
    rig.shape(rocket, "Launcher armor", 0, 27, 66, 71, ("FFFFCB87", "FFBD6544"), radius=13, outline="FF536D85")
    laser = weapon("Laser")
    rig.shape(laser, "Laser emitter", 0, 105, 31, 14, "FFFF6EAB", radius=6)
    for x in (-20, 20):
        rig.shape(laser, f"Laser rail {x}", x, 65, 10, 80, ("FFCBECFA", "FF4C638B"), radius=4)
    rig.shape(laser, "Laser capacitor", 0, 33, 46, 65, ("FFFFDCEB", "FF675583"), radius=12)
    electric = weapon("Electric")
    for y in range(28, 105, 14):
        rig.shape(electric, f"Tesla coil {y}", 0, y, 39, 6, "FF87EFFF", radius=2)
    rig.shape(electric, "Tesla core", 0, 55, 24, 110, ("FFB4CBED", "FF355074"), radius=10)
    machinegun = weapon("Machinegun")
    rotor = rig.element(machinegun, "Node", "Minigun rotor", y=38)
    for i,x in enumerate((-13, 0, 13)):
        barrel=rig.shape(rotor, f"Minigun barrel {x}", x, 49, 9, 109, ("FF8EABC2", "FF2A3A58"), radius=3)
        rig.bind(barrel,"x",f"barrel{i}X",x)
    rig.shape(machinegun, "Minigun receiver", 0, 12, 53, 54, ("FFE0EDF4", "FF546D89"), radius=12)
    sword = weapon("Sword")
    rig.shape(sword, "Energy blade core", 0, 110, 12, 157, "FFEBFFFF", radius=4)
    rig.shape(sword, "Energy blade edge", 0, 110, 26, 167, ("AA6FF9FC", "445BE3ED"), radius=9)
    rig.shape(sword, "Sword guard", 0, 24, 66, 12, ("FFE3FAFF", "FF7385A5"), radius=5)
    rig.shape(sword, "Sword grip", 0, 3, 20, 35, "FF304B67", radius=5)
    flame = weapon("Flame")
    rig.shape(flame, "Flame nozzle", 0, 101, 37, 19, "FFFFB476", radius=5)
    rig.shape(flame, "Flame barrel", 0, 60, 26, 87, ("FFABBFD2", "FF45566F"), radius=7)
    rig.shape(flame, "Fuel tank", -26, 30, 31, 70, ("FFFFA97A", "FFAB5A4C"), radius=12)
    drone = weapon("Drone")
    for x in (-39, 39):
        propeller = rig.element(drone, "Node", f"Drone rotor {x}", x=x, y=55)
        rig.bind(propeller, "rotation", "gunRotor", 0)
        rig.shape(propeller, f"Drone blade {x}", 0, 0, 56, 6, "CC9FDDE9", radius=3)
    rig.shape(drone, "Drone eyes", 0, 67, 24, 7, "FF81F5FF", radius=3)
    rig.shape(drone, "Drone body", 0, 55, 51, 35, ("FFE3E9FA", "FF7F75AF"), radius=14)

    head = nodes["Head"]
    shock = rig.element(head, "Node", "Surprised mouth", opacity=0)
    head.remove(shock)
    head.insert(0, shock)
    rig.bind(shock, "opacity", "shock", 0)
    rig.shape(shock, "Mouth O", 0, 24, 16, 21, "FFB2FFFF", ellipse=True)
    robot = nodes["Robot"]
    for node, field, props in (
        (nodes["Body"], "body", ("scaleX", "scaleY")),
        (head, "head", ("scaleX", "scaleY")),
    ):
        for prop in props:
            rig.bind(node, prop, field + prop, 1)
    rig.bind(nodes["Tracks"], "opacity", "tracks", 1)
    # Existing robot silhouettes keep their own mobility, not recolored tracks.
    legs = rig.element(robot, "Node", "Walking chassis", y=74, opacity=0)
    rig.bind(legs, "opacity", "legs", 0)
    for x, side in ((-47, "L"), (47, "R")):
        leg = rig.element(legs, "Node", f"Leg {side}", x=x)
        rig.bind(leg, "rotation", f"leg{side}", 0)
        rig.shape(leg, f"Foot sole {side}", 5, 41, 55, 18, ("FF809EB6", "FF273B55"), radius=8)
        rig.shape(leg, f"Shin piston {side}", 0, 14, 18, 38, ("FFE9F7FF", "FF7593AD"), radius=7)
        rig.shape(leg, f"Knee joint {side}", 0, 0, 28, 28, "FF4E6F87", ellipse=True)
    hover = rig.element(robot, "Node", "Hover chassis", y=83, opacity=0)
    rig.bind(hover, "opacity", "hover", 0)
    for x in (-55, 55):
        jet = rig.element(hover, "Node", f"Hover jet {x}", x=x, y=12)
        rig.bind(jet, "scaleY", "jet", 1)
        rig.shape(jet, f"Jet core {x}", 0, 12, 18, 48, ("AA8FFAFF", "0027BCF7"), ellipse=True)
        rig.shape(hover, f"Thruster nozzle {x}", x, 0, 44, 22, ("FFCFEBF9", "FF354D6B"), radius=8)
    rig.shape(hover, "Hover skirt", 0, -8, 174, 37, ("FFFEFFFF", "FF738FAE"), radius=18)
    wheels = rig.element(robot, "Node", "Wheel chassis", y=83, opacity=0)
    rig.bind(wheels, "opacity", "wheels", 0)
    for x in (-68, 68):
        wheel = rig.element(wheels, "Node", f"Road wheel {x}", x=x, rotation=0)
        rig.bind(wheel, "rotation", "wheelAngle", 0)
        for i in range(8):
            spoke = rig.element(wheel, "Node", f"Road spoke {x}-{i}", rotation=i * 3.14159265 / 4)
            rig.shape(spoke, f"Road spoke metal {x}-{i}", 0, -17, 5, 25, "FFAFC2D4", radius=2)
        rig.shape(wheel, f"Road hub {x}", 0, 0, 20, 20, "FF98EFFF", ellipse=True)
        rig.shape(wheel, f"Road tire {x}", 0, 0, 67, 67, ("FF435B72", "FF13283C"), ellipse=True, outline="FF8EA9BF")
    for name, visibility in (("Leaf crest", "leaf"), ("Crown fins", "fins"), ("Solar crown", "sun")):
        ornament = rig.element(head, "Node", name, y=-60, opacity=0)
        head.remove(ornament)
        head.insert(0, ornament)
        rig.bind(ornament, "opacity", visibility, 0)
        for i, x in enumerate((-35, 0, 35)):
            rig.shape(ornament, f"{name} vane {i}", x, -7-abs(x)*.25, 16 if visibility != "leaf" else 28, 42, "FF7DCDB0" if visibility == "leaf" else ("FFFFE6A2", "FF72CFEA"), radius=7, rotation=(i-1)*.4)
    # Mechanical detail lives in Rive too and follows travelled distance.
    gears = rig.element(nodes["Body"], "Node", "Exposed gear", x=36, y=33)
    nodes["Body"].remove(gears)
    nodes["Body"].insert(0, gears)
    rig.bind(gears, "rotation", "gearAngle", 0)
    for i in range(8):
        tooth = rig.element(gears, "Node", f"Gear tooth {i}", rotation=i*3.14159265/4)
        rig.shape(tooth, f"Gear tooth metal {i}", 0, -12, 5, 9, "FF8099B0", radius=1)
    rig.shape(gears, "Gear face", 0, 0, 22, 22, ("FFC8DFE9", "FF56728E"), ellipse=True)
    # A VM color and separate chassis/crests preserve each robot's identity.
    color_id = "0:25000"
    ET.SubElement(rig.vm, "ViewModelPropertyColor", name="accent", id=color_id)
    ET.SubElement(rig.instance, "ViewModelInstanceColor", viewModelPropertyId=color_id, propertyValue="FFFFB94D")
    for name in ("Belly armor", "Chest stripe", "Head crest", "Ear shell L", "Ear shell R", "Forearm band L", "Forearm band R", "Wheel hub L", "Wheel hub R"):
        shape = nodes[name]
        fill = shape.find("Fill")
        if fill is not None:
            fill.clear()
            solid = ET.SubElement(fill, "SolidColor", colorValue="FFFFB94D")
            ET.SubElement(solid, "DataBindContext", propertyKey="37", sourcePathIds=f"0:10-{color_id}")

    from generate_collection_rigs import extend_collection
    root = extend_collection(root)
    target = ROOT / "game_robot"
    target.mkdir(exist_ok=True)
    shutil.copy2(ROOT / "spark/AGENTS.md", target / "AGENTS.md")
    (target / "rive.yaml").write_text("name: game_robot\n", encoding="utf-8")
    ET.indent(root)
    ET.ElementTree(root).write(target / "scene.rml", encoding="utf-8", xml_declaration=True)
    print(f"Authored {target}: {len(rig.fields)} numeric bindings, 4 articulated weapons, accent color")


if __name__ == "__main__":
    build()
