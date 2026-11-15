"""Build original SVG robot parts, arena stages and interface badges."""

import hashlib
import json
import math
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "src/assets/art"
written = []


def svg(name, width, height, content, color="#F3AC49"):
    prefix = name.replace("/", "_").replace(".", "_")
    defs = f'''<defs>
    <linearGradient id="metal" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#FFFFFF"/><stop offset=".45" stop-color="#EAF0F8"/><stop offset="1" stop-color="#8496B3"/></linearGradient>
    <linearGradient id="paint" x1="0" y1="0" x2=".8" y2="1"><stop stop-color="#FFFFFF"/><stop offset=".15" stop-color="{color}"/><stop offset="1" stop-color="{color}" stop-opacity=".7"/></linearGradient>
    <linearGradient id="glass" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#354F6A"/><stop offset=".45" stop-color="#101E34"/><stop offset="1" stop-color="#071125"/></linearGradient>
    <radialGradient id="glow"><stop stop-color="#B1F6FF"/><stop offset="1" stop-color="#27B9E0" stop-opacity="0"/></radialGradient>
    </defs>'''
    text = f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">{defs}{content}</svg>'
    for key in ("metal", "paint", "glass", "glow"):
        text = text.replace(f'id="{key}"', f'id="{prefix}_{key}"').replace(
            f"url(#{key})", f"url(#{prefix}_{key})"
        )
    path = ASSETS / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    written.append(
        {
            "asset": "art/" + name,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }
    )


def robots():
    for identity, color, mobility in (
        ("spark", "#F4AC41", "tracks"),
        ("volt", "#42C4EB", "hover"),
        ("flora", "#54CBA5", "legs"),
        ("forge", "#EE8757", "tracks"),
        ("nova", "#B696EF", "hover"),
        ("glacier", "#80D7EF", "hover"),
        ("aegis", "#D77566", "tracks"),
        ("solar", "#F5BE57", "hover"),
    ):
        ears = (
            '<path d="M48 28 L51 2 L74 15 M147 16 L168 2 L171 30" fill="url(#paint)" stroke="#596A88" stroke-width="3"/>'
            if identity == "flora"
            else '<path d="M104 17 L102 5" stroke="#52647D" stroke-width="6"/><circle cx="102" cy="5" r="5" fill="url(#paint)"/>'
        )
        if identity == "volt":
            ears = '<path d="M63 20 L51 4 M154 20 L168 4" stroke="#3EA9CF" stroke-width="5"/><circle cx="50" cy="4" r="5" fill="#85EDFF"/><circle cx="169" cy="4" r="5" fill="#85EDFF"/>'
        elif identity == "glacier":
            ears = '<path d="M69 24 L79 3 L99 16 L114 0 L130 16 L148 3 L157 27" fill="#B4F6FF" stroke="#6099BB" stroke-width="3"/>'
        elif identity == "aegis":
            ears = '<path d="M60 28 L72 7 H149 L164 29" fill="#687C91" stroke="#B4C8D4" stroke-width="4"/><path d="M109 7 V29" stroke="#F2B06A" stroke-width="6"/>'
        elif identity == "nova":
            ears = '<ellipse cx="109" cy="17" rx="83" ry="13" fill="none" stroke="#D2B6FF" stroke-width="6"/><path d="M31 24 L17 12 L18 50 M188 24 L202 12 L202 50" fill="#A49ADE"/>'
        elif identity == "solar":
            ears = (
                '<circle cx="110" cy="57" r="51" fill="none" stroke="#F9C35D" stroke-width="6"/>'
                + "".join(
                    f'<path d="M{110 + 54 * math.cos(a):.1f} {57 + 54 * math.sin(a):.1f} L{110 + 67 * math.cos(a):.1f} {57 + 67 * math.sin(a):.1f}" stroke="#FFD66F" stroke-width="5" stroke-linecap="round"/>'
                    for a in [i * math.pi / 6 for i in range(12)]
                )
            )
        radius = (
            16
            if identity in {"forge", "aegis"}
            else 27
            if identity in {"volt", "glacier"}
            else 43
            if identity in {"nova", "solar"}
            else 37
        )
        head = f'''{ears}<rect x="23" y="35" width="29" height="43" rx="14" fill="url(#paint)" stroke="#5D6C88" stroke-width="3"/>
        <rect x="166" y="35" width="29" height="43" rx="14" fill="url(#paint)" stroke="#5D6C88" stroke-width="3"/>
        <rect x="34" y="14" width="151" height="88" rx="{radius}" fill="url(#metal)" stroke="#637693" stroke-width="3"/>
        <rect x="43" y="23" width="134" height="71" rx="{max(10, radius - 9)}" fill="url(#glass)" stroke="#8095AD" stroke-width="3"/>
        <path d="M56 38 Q96 21 143 31" fill="none" stroke="#94C8E5" stroke-opacity=".25" stroke-width="5" stroke-linecap="round"/>
        <rect x="84" y="14" width="51" height="9" rx="4" fill="url(#paint)"/>
        <circle cx="39" cy="56" r="7" fill="#6D7D99"/><circle cx="178" cy="56" r="7" fill="#6D7D99"/>'''
        if mobility == "tracks":
            base = '<rect x="27" y="98" width="164" height="40" rx="20" fill="#26364C" stroke="#6C7D96" stroke-width="4"/><path d="M49 101 H170 M49 134 H170" stroke="#8594AD" stroke-width="3"/>'
        elif mobility == "hover":
            base = '<ellipse cx="110" cy="129" rx="65" ry="11" fill="#4ACFEA" opacity=".2"/><ellipse cx="110" cy="119" rx="46" ry="9" fill="url(#paint)" stroke="#6D7C97" stroke-width="3"/><path d="M79 122 L72 143 M110 126 V147 M140 122 L148 143" stroke="#66EDFF" stroke-width="4" stroke-linecap="round"/>'
        else:
            base = '<path d="M78 91 L70 128 M143 91 L150 128" stroke="#536C85" stroke-width="14"/><rect x="47" y="123" width="48" height="14" rx="7" fill="url(#metal)"/><rect x="125" y="123" width="48" height="14" rx="7" fill="url(#metal)"/>'
        body = f"""{base}<rect x="96" y="0" width="28" height="24" rx="9" fill="#3E526F"/>
        <path d="M66 16 Q110 -3 154 16 L164 70 Q156 109 110 114 Q63 107 57 70 Z" fill="url(#metal)" stroke="#637693" stroke-width="3"/>
        <path d="M72 19 Q109 34 149 19 L142 33 Q110 48 78 33 Z" fill="url(#paint)"/>
        <rect x="88" y="47" width="45" height="17" rx="8" fill="#243E56" stroke="#8FA6BD" stroke-width="3"/>
        <rect x="95" y="52" width="31" height="7" rx="3" fill="#73F6FF"/>
        <path d="M78 77 Q111 65 145 77 L138 99 Q111 115 84 99 Z" fill="url(#paint)" stroke="#8291A9" stroke-width="2"/>
        <path d="M99 84 H124 M101 91 H122" stroke="#34485F" stroke-width="3" stroke-linecap="round"/>
        <circle cx="70" cy="60" r="4" fill="#677D98"/><circle cx="151" cy="60" r="4" fill="#677D98"/>"""
        if identity == "flora":
            body += '<path d="M111 44 Q142 39 137 69 Q114 79 105 61 Q82 73 81 49 Q101 41 111 44" fill="#68CBA6" stroke="#439B84" stroke-width="2"/><path d="M109 67 V45" stroke="#DEFCEB" stroke-width="3"/>'
        elif identity in {"forge", "aegis"}:
            body += '<path d="M72 26 L110 15 L148 26 L140 75 L110 91 L80 75 Z" fill="url(#paint)" stroke="#647789" stroke-width="4"/><path d="M110 29 V73 M90 45 H131" stroke="#FFE2AF" stroke-width="6" stroke-linecap="round"/>'
        elif identity in {"volt", "glacier"}:
            body += '<circle cx="110" cy="59" r="27" fill="#253F5D" stroke="#7DDBF2" stroke-width="4"/>'
            body += (
                '<path d="M114 34 L96 60 H110 L103 82 L126 53 H113 Z" fill="#89F1FF"/>'
                if identity == "volt"
                else '<path d="M110 37 V81 M91 47 L129 70 M91 70 L129 47" stroke="#B5F6FF" stroke-width="5" stroke-linecap="round"/>'
            )
        elif identity in {"nova", "solar"}:
            body += '<path d="M110 31 L119 50 L140 53 L124 68 L128 89 L110 79 L91 89 L95 68 L79 53 L101 50 Z" fill="url(#paint)" stroke="#E8E3F4" stroke-width="3"/>'
        arm = """<circle cx="25" cy="15" r="13" fill="#30445E" stroke="#8D9DB1" stroke-width="3"/>
        <rect x="13" y="23" width="24" height="40" rx="11" fill="url(#metal)" stroke="#657A95" stroke-width="2"/>
        <rect x="13" y="40" width="24" height="10" rx="4" fill="url(#paint)"/>
        <rect x="10" y="61" width="31" height="23" rx="10" fill="#405777" stroke="#91A4BE" stroke-width="2"/>
        <path d="M20 67 V77 M29 67 V78" stroke="#A0B1C7" stroke-width="2"/>"""
        svg(f"rig/{identity}_head.svg", 220, 110, head, color)
        svg(f"rig/{identity}_body.svg", 220, 150, body, color)
        svg(f"rig/{identity}_arm.svg", 50, 90, arm, color)
    spokes = "".join(
        f'<path d="M32 32 L{32 + 23 * math.cos(a):.2f} {32 + 23 * math.sin(a):.2f}" stroke="#BAC7DA" stroke-width="3"/>'
        for a in [i * math.pi / 4 for i in range(8)]
    )
    svg(
        "rig/wheel.svg",
        64,
        64,
        f'<circle cx="32" cy="32" r="30" fill="#182A41" stroke="#7186A2" stroke-width="4"/><circle cx="32" cy="32" r="24" fill="url(#glass)"/>{spokes}<circle cx="32" cy="32" r="14" fill="url(#paint)" stroke="#E8D0A1" stroke-width="2"/><circle cx="32" cy="32" r="5" fill="#455C76"/>',
    )
    for name, path in (
        ("smile", "M4 3 Q14 18 24 3"),
        ("focus", "M4 10 H24"),
        ("oh", "M14 4 C3 4 3 19 14 19 C25 19 25 4 14 4"),
    ):
        svg(
            f"rig/mouth_{name}.svg",
            28,
            24,
            f'<path d="{path}" fill="none" stroke="#6AF5FF" stroke-width="3" stroke-linecap="round"/>',
        )
    for identity in ("glacier", "aegis", "solar"):

        def part(name, x, y, width, height, tag):
            text = (ASSETS / name).read_text(encoding="utf-8")
            text = re.sub(r'(id=")([^"]+)', lambda m: m[1] + tag + "_" + m[2], text)
            text = text.replace("url(#", "url(#" + tag + "_")
            # Flutter's SVG decoder omits nested SVG viewports. Flatten parts
            # into transformed groups so portraits render like animated rigs.
            viewbox = re.search(r'viewBox="0 0 ([\d.]+) ([\d.]+)"', text)
            source_width, source_height = map(float, viewbox.groups())
            inner = text[text.index(">") + 1 : text.rindex("</svg>")]
            return (
                f'<g transform="translate({x} {y}) scale({width / source_width:g} {height / source_height:g})">'
                + inner
                + "</g>"
            )

        content = part(f"rig/{identity}_arm.svg", 24, 110, 50, 90, "a") + part(
            f"rig/{identity}_arm.svg", 149, 110, 50, 90, "b"
        )
        content += part(f"rig/{identity}_body.svg", 0, 90, 220, 150, "c")
        if identity == "aegis":
            content += part("rig/wheel.svg", 39, 185, 43, 43, "d") + part(
                "rig/wheel.svg", 137, 185, 43, 43, "e"
            )
        content += part(f"rig/{identity}_head.svg", 0, 0, 220, 110, "f")
        content += (
            '<rect x="77" y="49" width="14" height="16" rx="7" fill="#74F3FF"/><rect x="127" y="49" width="14" height="16" rx="7" fill="#74F3FF"/>'
            + part("rig/mouth_smile.svg", 97, 69, 25, 20, "g")
        )
        svg(f"portraits/{identity}.svg", 220, 240, content)


def arenas():
    for index, (dark, accent) in enumerate(
        (("#142942", "#4AD8EF"), ("#251E48", "#BA8CFF"), ("#153D43", "#62E5C5"))
    ):
        towers = "".join(
            f'<path d="M{x} 300 V{h} H{x + 45} V300" fill="#182C48" stroke="{accent}" stroke-opacity=".2" stroke-width="2"/>'
            for x, h in (
                (5, 132),
                (70, 92),
                (142, 171),
                (768, 140),
                (833, 88),
                (905, 166),
            )
        )
        stars = "".join(
            f'<circle cx="{x}" cy="{y}" r="2" fill="{accent}" opacity=".5"/>'
            for x, y in (
                (60, 50),
                (210, 75),
                (303, 29),
                (630, 46),
                (799, 52),
                (910, 100),
            )
        )
        scene = f'''<rect width="960" height="500" fill="{dark}"/>{stars}{towers}
        <ellipse cx="480" cy="235" rx="350" ry="180" fill="url(#glow)" opacity=".12"/>
        <path d="M0 320 Q480 245 960 320 V500 H0 Z" fill="#213752"/>
        <path d="M0 372 H960 M0 425 H960 M480 290 L245 500 M480 290 L710 500" stroke="{accent}" opacity=".12" stroke-width="2"/>
        <path d="M330 280 V127 Q480 -20 630 127 V280" fill="none" stroke="{accent}" opacity=".2" stroke-width="15"/>
        <path d="M346 280 V133 Q480 2 614 133 V280" fill="none" stroke="{accent}" opacity=".65" stroke-width="3"/>
        <ellipse cx="233" cy="410" rx="170" ry="43" fill="#0B1B2E"/><ellipse cx="233" cy="399" rx="164" ry="38" fill="#344D6C" stroke="#7AE2F6" stroke-width="4"/>
        <ellipse cx="730" cy="410" rx="170" ry="43" fill="#0B1B2E"/><ellipse cx="730" cy="399" rx="164" ry="38" fill="#344D6C" stroke="#BCA2F4" stroke-width="4"/>
        <ellipse cx="233" cy="399" rx="138" ry="29" fill="none" stroke="#7AE2F6" stroke-opacity=".3" stroke-width="2"/>
        <ellipse cx="730" cy="399" rx="138" ry="29" fill="none" stroke="#BCA2F4" stroke-opacity=".3" stroke-width="2"/>
        <path d="M58 465 H902" stroke="{accent}" stroke-width="3" opacity=".6"/>'''
        svg(f"arena/stage_{index}.svg", 960, 500, scene, accent)


def badges():
    for name, color, shape in (
        (
            "credits",
            "#F5B442",
            '<ellipse cx="32" cy="43" rx="16" ry="7" fill="#FFE8AA" stroke="#D99726" stroke-width="2"/><path d="M16 34 V43 M48 34 V43" stroke="#FFF7D3" stroke-width="3"/><ellipse cx="32" cy="34" rx="16" ry="7" fill="#FFF4CD" stroke="#D99726" stroke-width="2"/><path d="M16 26 V34 M48 26 V34" stroke="#FFF7D3" stroke-width="3"/><ellipse cx="32" cy="26" rx="16" ry="7" fill="#FFF8DF" stroke="#D99726" stroke-width="2"/>',
        ),
        (
            "food",
            "#46BEA2",
            '<rect x="21" y="20" width="23" height="27" rx="8" fill="#DFFFF1"/><path d="M27 16 H37" stroke="#DFFFF1" stroke-width="5" stroke-linecap="round"/><path d="M33 25 L28 34 H35 L31 42" stroke="#32A48B" fill="none" stroke-width="3"/>',
        ),
        (
            "arena",
            "#738CEB",
            '<path d="M32 17 L46 23 V34 Q42 45 32 49 Q22 45 18 34 V23 Z" fill="#F2F4FF"/><path d="M27 25 L38 37 M38 25 L26 37" stroke="#6D7DD0" stroke-width="4" stroke-linecap="round"/>',
        ),
        (
            "clock",
            "#A48BD8",
            '<circle cx="32" cy="32" r="16" fill="#F8F4FF"/><path d="M32 21 V32 L40 37" stroke="#8B70C5" stroke-width="4" fill="none" stroke-linecap="round"/>',
        ),
        (
            "profile",
            "#56B2D1",
            '<circle cx="32" cy="25" r="9" fill="#E5FAFF"/><path d="M17 46 Q17 33 32 34 Q47 33 47 46 Z" fill="#E5FAFF"/>',
        ),
    ):
        svg(
            f"icons/{name}.svg",
            64,
            64,
            f'<path d="M32 3 L57 17 V46 L32 61 L7 46 V17 Z" fill="url(#paint)" stroke="{color}" stroke-width="2"/><path d="M12 19 L32 8 L51 19" fill="none" stroke="#FFFFFF" stroke-opacity=".45" stroke-width="3"/>{shape}',
            color,
        )


def extras():
    svg(
        "icons/parts.svg",
        64,
        64,
        '<path d="M27 4 H38 L40 13 L48 18 L57 16 L62 28 L54 34 L51 43 L54 52 L43 59 L35 53 L26 53 L18 59 L7 51 L11 42 L8 33 L1 27 L7 15 L17 18 L25 13 Z" fill="url(#paint)" stroke="#5E8CA6" stroke-width="2"/><circle cx="32" cy="32" r="11" fill="#ECF9FF" stroke="#6E9CB8" stroke-width="3"/>',
        "#5AB8D4",
    )
    for identity, color, mark in (
        (
            "builder",
            "#ECAC51",
            '<path d="M22 42 L43 21 M34 19 L44 17 L48 27 L41 29" stroke="#FFF5D8" stroke-width="7" fill="none" stroke-linecap="round"/>',
        ),
        (
            "champion",
            "#B28AE2",
            '<path d="M21 19 H45 V33 Q43 45 33 47 Q23 45 21 33 Z M22 23 H12 V31 Q14 40 25 38 M45 23 H54 V31 Q51 40 42 38 M33 47 V55 M23 56 H43" stroke="#FFF5D8" stroke-width="4" fill="none"/>',
        ),
        (
            "explorer",
            "#5BBEAB",
            '<path d="M32 13 L40 30 L54 33 L40 40 L32 55 L25 40 L11 33 L25 27 Z" fill="#E9FFF5"/>',
        ),
        (
            "collector",
            "#DC7F9C",
            '<path d="M14 24 L33 15 L52 24 V47 L33 56 L14 47 Z M14 24 L33 34 L52 24 M33 34 V56" fill="none" stroke="#FFF1F6" stroke-width="4"/>',
        ),
        (
            "master",
            "#5AA7D6",
            '<path d="M23 44 L29 25 L25 23 L33 11 L41 23 L37 25 L43 44 Z" fill="#FFF2C6"/><path d="M23 49 H43" stroke="#E8F7FF" stroke-width="5" stroke-linecap="round"/>',
        ),
    ):
        svg(
            f"avatars/{identity}.svg",
            66,
            66,
            f'<circle cx="33" cy="33" r="30" fill="url(#paint)" stroke="#FFFFFF" stroke-width="4"/><circle cx="33" cy="33" r="25" fill="none" stroke="#FFFFFF" stroke-opacity=".45" stroke-width="2"/>{mark}',
            color,
        )
    for element, color, shape in (
        (
            "steel",
            "#F6B95C",
            '<path d="M8 49 L62 31 L51 54 L113 24 L99 49 L151 32 L103 64 L113 44 L52 72 L62 49 Z" fill="#FFF1AC" stroke="#F8BD54" stroke-width="2"/>',
        ),
        (
            "pulse",
            "#6BDFFF",
            '<path d="M5 53 L43 39 L58 60 L76 25 L89 48 L139 37" fill="none" stroke="#D2FFFF" stroke-width="6" stroke-linejoin="round"/><ellipse cx="122" cy="42" rx="25" ry="24" fill="none" stroke="#7EEAFF" stroke-width="4"/>',
        ),
        (
            "nature",
            "#7EE7B3",
            '<path d="M35 58 Q73 4 129 25 Q126 72 71 64 Z" fill="#A2F5C6" stroke="#3FB48C" stroke-width="3"/><path d="M35 58 L109 34" stroke="#E3FFE9" stroke-width="4"/>',
        ),
        (
            "cosmic",
            "#CFA3FF",
            '<path d="M6 49 L96 23 L88 37 L115 4 L124 28 L151 31 L133 50 L140 75 L115 63 L92 76 L97 54 Z" fill="#F2D2FF" stroke="#B985FF" stroke-width="3"/>',
        ),
    ):
        svg(
            f"effects/{element}.svg",
            160,
            80,
            f'<ellipse cx="99" cy="43" rx="57" ry="35" fill="url(#glow)" opacity=".55"/>{shape}',
            color,
        )
    svg(
        "projects/lamp.svg",
        240,
        140,
        '<path d="M115 48 L238 12 V132 L115 96 Z" fill="#FFF0A6" opacity=".28"/><path d="M41 47 L120 40 L130 99 L49 105 Q23 103 21 79 Q20 54 41 47 Z" fill="url(#paint)" stroke="#97724C" stroke-width="4"/><ellipse cx="120" cy="70" rx="22" ry="35" fill="#537B9B" stroke="#D6E6E9" stroke-width="5"/><ellipse cx="124" cy="70" rx="14" ry="25" fill="#FFF6B4"/><rect x="48" y="37" width="25" height="13" rx="6" fill="#82F2F1" stroke="#4C8E9F" stroke-width="3"/><path d="M39 59 L92 55 M39 91 L96 88" stroke="#FFF4DD" stroke-width="4" stroke-linecap="round"/>',
        "#F1B456",
    )
    svg(
        "projects/scooter.svg",
        200,
        140,
        '<circle cx="45" cy="108" r="22" fill="#2E4863" stroke="#7B9DB6" stroke-width="5"/><circle cx="157" cy="108" r="22" fill="#2E4863" stroke="#7B9DB6" stroke-width="5"/><path d="M44 98 H132 L147 39 H168 M145 39 L152 106" stroke="#53C7D2" stroke-width="11" fill="none" stroke-linecap="round"/><path d="M138 32 H169" stroke="#435D78" stroke-width="9" stroke-linecap="round"/>',
        "#60C6D9",
    )
    svg(
        "projects/robot.svg",
        200,
        140,
        '<rect x="44" y="22" width="112" height="73" rx="24" fill="url(#metal)" stroke="#718CA8" stroke-width="4"/><rect x="55" y="33" width="90" height="49" rx="19" fill="url(#glass)"/><circle cx="79" cy="57" r="8" fill="#86F5FF"/><circle cx="122" cy="57" r="8" fill="#86F5FF"/><path d="M75 99 V121 M128 99 V121 M30 50 L20 79 M170 50 L181 79" stroke="#9A85D4" stroke-width="12" stroke-linecap="round"/>',
        "#A793E8",
    )
    for identity, color in (("beacon", "#5DC5CC"), ("solar", "#EFB44B")):
        svg(
            f"projects/{identity}.svg",
            200,
            140,
            '<path d="M54 125 L77 45 H123 L147 125 Z" fill="url(#metal)" stroke="#667F9B" stroke-width="4"/><ellipse cx="100" cy="42" rx="48" ry="24" fill="url(#paint)" stroke="#D5F7FF" stroke-width="5"/><path d="M100 11 V0 M39 24 L22 13 M161 24 L178 13" stroke="#8FEFFF" stroke-width="5" stroke-linecap="round"/><path d="M87 70 H115 V103 H87 Z" fill="#65E8F0"/>',
            color,
        )
    svg(
        "icons/crate.svg",
        160,
        140,
        '<path d="M18 48 L80 21 L143 48 V109 L80 137 L18 109 Z" fill="url(#paint)" stroke="#97744F" stroke-width="4"/><path d="M18 48 L80 76 L143 48 M80 76 V137" stroke="#FFF1C9" stroke-width="5"/><path d="M60 30 L120 57 V82 L100 91 V66 L41 39 Z" fill="#738AD0"/><rect x="67" y="84" width="25" height="30" rx="7" fill="#FFF4CA"/><circle cx="80" cy="97" r="4" fill="#997543"/>',
        "#ECAB52",
    )


if __name__ == "__main__":
    robots()
    arenas()
    badges()
    extras()
    path = ROOT / "artwork/robot_collection/motion-assets.json"
    path.write_text(json.dumps(written, indent=2) + "\n", encoding="utf-8")
    print(f"Generated {len(written)} original SVG assets")
