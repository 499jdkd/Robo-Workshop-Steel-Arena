"""Replace only Volt's Rive artboard/view model and its collection portrait.

The other 31 authored artboards are checked structurally and left byte-for-byte
in the RML document. Run the official Rive verify/inspect/publish afterwards.
"""

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "src"))
from robot_designs import DESIGNS
from generate_collection_rigs import CollectionRig, export_svg


def untouched(root):
    return {
        (child.tag, child.get("name")): hashlib.sha256(ET.tostring(child)).hexdigest()
        for child in root
        if child.get("name") not in {"volt", "Motion_volt"}
    }


def main():
    project = HERE / "game_robot/scene.rml"
    source = project.read_text(encoding="utf-8")
    original = ET.fromstring(source)
    before = untouched(original)
    template = ET.Element("Rive", version="1", kind="fragment")
    for name in ("Motion_spark", "Spark"):
        template.append(deepcopy(next(n for n in original if n.get("name") == name)))
    model = CollectionRig(template, DESIGNS["volt"])
    fresh = model.build(template)
    # The static SVG shares authored geometry; keep its preview origin at zero.
    preview = deepcopy(fresh)
    preview.find("Artboard").set("x", "0")
    preview.find("Artboard").set("y", "0")
    for gradient in preview.iter("RadialGradient"):
        gradient.tag = "LinearGradient"
    export_svg(preview, ROOT / "src/assets/art/portraits/volt.svg")
    old = next(n for n in original if n.tag == "Artboard" and n.get("name") == "volt")
    fresh.find("Artboard").set("x", old.get("x", "0"))
    fresh.find("Artboard").set("y", old.get("y", "0"))
    offset = int(old.get("id").split(":")[1]) - 2
    for node in fresh.iter():
        for key, value in list(node.attrib.items()):
            node.set(key, re.sub(r"0:(\d+)", lambda match: f"0:{int(match[1]) + offset}", value))
    result = source
    for child in fresh:
        name = child.get("name")
        ET.indent(child, space="  ", level=1)
        child.tail = None
        replacement = "  " + ET.tostring(child, encoding="unicode")
        pattern = rf'(?ms)^  <{child.tag}\b(?=[^\n]*\bname="{re.escape(name)}")[^\n]*>.*?^  </{child.tag}>'
        result, count = re.subn(pattern, lambda _: replacement, result)
        assert count == 1, (name, count)
    assert untouched(ET.fromstring(result)) == before, "A different robot was modified"
    project.write_text(result, encoding="utf-8")
    out = ROOT / ".cache/volt-refinement/rig"
    out.mkdir(parents=True, exist_ok=True)
    (out / "scope.json").write_text(json.dumps({
        "updated_artboard": "volt", "unchanged_artboards": 31,
        "unchanged_other_view_models": 31, "shape_count": len(list(fresh.iter("Shape"))),
        "independent_coil_hinges": ["joint0", "joint1", "joint2", "joint3"],
        "independent_core_and_panels": ["joint4", "joint5", "joint6"],
        "unmodified_objects": [{"type": tag, "name": name, "sha256": digest} for (tag, name), digest in before.items()],
    }, indent=2), encoding="utf-8")
    print(f"Updated only Volt: {len(list(fresh.iter('Shape')))} shapes, 31 other robots unchanged")


if __name__ == "__main__":
    main()
