"""Editable metal/energy item icons matching the game's existing SVG assets."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from armory import WEAPONS
from equipment_catalog import MODULES


def svg(content, color="#69DBFF"):
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="96" height="96" viewBox="0 0 96 96"><defs>
    <linearGradient id="metal" x1="0" y1="0" x2=".8" y2="1"><stop stop-color="#F2FBFF"/><stop offset=".46" stop-color="#9FBAD4"/><stop offset="1" stop-color="#3F567C"/></linearGradient>
    <linearGradient id="paint" x1="0" y1="0" x2=".8" y2="1"><stop stop-color="#F4FAFF"/><stop offset=".22" stop-color="{color}"/><stop offset="1" stop-color="#314362"/></linearGradient>
    <radialGradient id="glow"><stop stop-color="#EEFFFF"/><stop offset=".4" stop-color="{color}"/><stop offset="1" stop-color="{color}" stop-opacity="0"/></radialGradient>
    </defs><ellipse cx="48" cy="83" rx="37" ry="7" fill="#040B1A" opacity=".6"/>{content}</svg>'''


def rect(x, y, w, h, fill="url(#metal)", r=5):
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" fill="{fill}" stroke="#1A2D4B" stroke-width="2"/>'


def circle(x, y, r, fill="url(#paint)"):
    return f'<circle cx="{x}" cy="{y}" r="{r}" fill="{fill}" stroke="#254665" stroke-width="2"/>'


def weapon_art(identity):
    if identity == "sniper":
        return (
            '<g transform="rotate(-25 48 48)">'
            + rect(22, 37, 48, 20)
            + rect(65, 42, 24, 8)
            + rect(12, 34, 17, 27)
            + rect(38, 26, 27, 8, "url(#paint)", 3)
            + rect(39, 54, 12, 22, "#273B59")
            + "</g>"
        )
    if identity in {"shield", "emp"}:
        return (
            (
                '<path d="M48 11L80 25L76 61L48 83L20 61L16 25Z" fill="url(#metal)" stroke="#3A6D9A" stroke-width="3"/><path d="M48 24L66 32L63 55L48 68L33 55L30 32Z" fill="url(#paint)"/>'
            )
            if identity == "shield"
            else circle(48, 48, 31)
            + circle(48, 48, 19, "url(#glow)")
            + '<path d="M45 18L30 50H48L39 78L69 40H50L61 18Z" fill="#B7FFFF"/>'
        )
    if identity == "drone":
        return (
            "".join(
                circle(x, y, 13, "url(#metal)")
                + rect(x - 15, y - 3, 30, 6, "url(#paint)", 2)
                for x, y in [(18, 25), (78, 25), (18, 69), (78, 69)]
            )
            + rect(28, 25, 40, 42)
            + circle(48, 47, 10, "#5FEAFF")
        )
    if identity == "sword":
        return (
            '<path d="M66 8L83 11L82 28L42 69L28 56Z" fill="url(#paint)" stroke="#B2F8FF" stroke-width="2"/>'
            + rect(18, 52, 36, 9, "url(#metal)", 2)
            + '<g transform="rotate(40 26 71)">'
            + rect(19, 59, 14, 27, "#203553")
            + "</g>"
        )
    if identity == "fist":
        return (
            "".join(rect(18 + i * 15, 20, 14, 28, "url(#paint)", 4) for i in range(4))
            + rect(21, 41, 59, 30)
            + rect(24, 70, 44, 12, "#3CD0ED")
        )
    if identity == "rocket":
        return rect(18, 27, 62, 45, "url(#paint)") + "".join(
            circle(34 + i * 28, 35 + j * 24, 10, "#20324B")
            + circle(34 + i * 28, 35 + j * 24, 5, "#FFAC6E")
            for i in range(2)
            for j in range(2)
        )
    if identity == "drill":
        return (
            '<path d="M15 62L77 17L84 29L42 80Z" fill="url(#metal)" stroke="#253B59" stroke-width="2"/><path d="M33 52L55 58M45 42L64 47M58 32L72 37" stroke="#EEC66C" stroke-width="8"/>'
            + rect(12, 58, 24, 24, "url(#paint)")
        )
    if identity == "disc":
        return "".join(
            circle(37 + i * 11, 59 - i * 15, 22, "url(#metal)")
            + circle(37 + i * 11, 59 - i * 15, 8, "#4DDCFB")
            for i in range(3)
        )
    if identity == "magnetic":
        return (
            '<path d="M20 20V55A28 28 0 0 0 76 55V20H58V53A10 10 0 0 1 38 53V20Z" fill="url(#metal)" stroke="#284867" stroke-width="3"/>'
            + rect(18, 16, 22, 18, "#F17E94")
            + rect(56, 16, 22, 18, "#65C4FF")
        )
    if identity == "grenade":
        return (
            circle(45, 50, 28, "url(#metal)")
            + "".join(
                circle(
                    45 + 20 * __import__("math").cos(i * __import__("math").tau / 5),
                    50 + 20 * __import__("math").sin(i * __import__("math").tau / 5),
                    6,
                    "#203653",
                )
                for i in range(5)
            )
            + rect(65, 36, 24, 16, "url(#paint)")
        )
    body = rect(20, 36, 53, 36, "url(#paint)") + rect(33, 67, 16, 17, "#223855")
    if identity == "machinegun":
        return body + "".join(
            rect(57, 27 + i * 14, 30, 9, "url(#metal)", 3) for i in range(3)
        )
    if identity == "electric":
        return body + "".join(
            rect(46 + i * 9, 19, 6, 53, "#75E9FF", 2) for i in range(4)
        )
    if identity == "flame":
        return (
            body
            + rect(9, 39, 17, 35, "#F09A54")
            + '<path d="M72 44L89 35L84 51L91 61L72 64Z" fill="#FFC567"/>'
        )
    if identity == "cryo":
        return (
            body
            + '<path d="M69 13V70M48 26L89 58M89 26L48 58M59 20L69 29L79 20M59 62L69 53L79 62" stroke="#9EF7FF" stroke-width="5"/>'
        )
    if identity == "repair":
        return (
            body
            + circle(70, 43, 17, "#62D8AD")
            + '<path d="M70 32V54M59 43H81" stroke="#ECFFF8" stroke-width="7"/>'
        )
    if identity == "blaster":
        return (
            body
            + rect(60, 30, 28, 13, "url(#metal)")
            + rect(60, 51, 28, 13, "url(#metal)")
        )
    if identity == "ion":
        return (
            body
            + circle(72, 44, 21, "url(#metal)")
            + circle(72, 44, 14, "url(#glow)")
            + '<path d="M64 20L83 68M55 28L89 58" stroke="#C3A4FF" stroke-width="4"/>'
        )
    if identity == "laser":
        return (
            body + rect(60, 31, 28, 30, "url(#metal)") + rect(84, 35, 5, 22, "#FF77B7")
        )
    return body + circle(73, 45, 19, "url(#metal)") + circle(73, 45, 12, "url(#glow)")


def main():
    target = ROOT / "src/assets/art/weapons"
    target.mkdir(parents=True, exist_ok=True)
    for item in WEAPONS:
        (target / f"{item.id}.svg").write_text(
            svg(
                weapon_art(item.id),
                "#B997FF" if item.rarity in {"epic", "legendary"} else "#68D8FA",
            ),
            encoding="utf8",
        )
    target = ROOT / "src/assets/art/modules"
    target.mkdir(parents=True, exist_ok=True)
    for i, item in enumerate(MODULES):
        art = rect(17, 15, 62, 65, "url(#metal)", 12) + rect(
            26, 25, 44, 44, "#173452", 8
        )
        if item.slot == "core":
            art += circle(48, 47, 18, "url(#glow)") + circle(48, 47, 9, "#BBFBFF")
        elif item.slot == "armor":
            art += (
                '<path d="M48 29L64 37L61 54L48 65L35 54L32 37Z" fill="url(#paint)"/>'
            )
        elif item.slot == "drive":
            art += circle(48, 47, 17) + circle(48, 47, 7, "#18334A")
        elif item.slot == "defense":
            art += '<path d="M31 33H65V52L48 65L31 52Z" fill="url(#paint)"/>'
        else:
            art += (
                '<path d="M34 44H62M48 30V62" stroke="#8BF1FF" stroke-width="6"/>'
                + circle(48, 47, 10, "#5FCDF4")
            )
        art += "".join(
            circle(x, y, 3, "#9FE9FF")
            for x, y in [(25, 22), (71, 22), (25, 72), (71, 72)]
        )
        (target / f"{item.id}.svg").write_text(
            svg(art, "#FFCE71" if i % 2 else "#77DCFC"), encoding="utf8"
        )
    icons = ROOT / "src/assets/art/icons"
    (icons / "crystal.svg").write_text(
        svg(
            '<path d="M14 34L29 14H67L83 34L48 82Z" fill="#AB66F4" stroke="#D4BCFF" stroke-width="3"/><path d="M14 34H83M29 14L37 34L48 82L59 34L67 14" fill="none" stroke="#EDDBFF" stroke-width="2"/>',
            "#BA8FFF",
        ),
        encoding="utf8",
    )
    (icons / "container.svg").write_text(
        svg(
            rect(12, 25, 72, 51, "url(#paint)", 9)
            + rect(43, 26, 12, 47, "#132B48", 3)
            + rect(35, 42, 26, 18, "url(#metal)", 4)
            + '<path d="M17 21L45 10L79 21L50 34Z" fill="url(#metal)"/>',
            "#77DBFF",
        ),
        encoding="utf8",
    )
    print("20 weapon icons, 10 modules and resources written")


if __name__ == "__main__":
    main()
