"""Generate the game's small, editable vector room backgrounds."""

from pathlib import Path

ASSETS = Path(__file__).resolve().parents[1] / "src" / "assets"
WALLS = ("#E5F0FF", "#E0F3E8", "#FFF0D8", "#EDE5FF", "#FCE6EB", "#DDF2FA")

for stage, wall in enumerate(WALLS):
    furniture = """<rect x="76" y="256" width="90" height="60" rx="7" fill="#D4AF82"/>
<path d="M76 268h90M118 256v60" stroke="#B58E63" stroke-width="3"/>
<rect x="96" y="244" width="50" height="13" rx="5" fill="#93BBAE"/>"""
    if stage >= 1:
        furniture = """<rect x="42" y="228" width="159" height="16" rx="7" fill="#C49468"/>
<path d="M57 242v87m128-87v87" stroke="#AB7F5A" stroke-width="10" stroke-linecap="round"/>
<rect x="66" y="100" width="123" height="103" rx="12" fill="#D7B68D"/>
<path d="M87 120h80M87 142h80M87 164h80M87 186h80" stroke="#EAD4B6" stroke-width="3"/>
<path d="M99 123v53m0-48-9-6m9 6 10-6" stroke="#5F91B5" stroke-width="9" stroke-linecap="round"/>
<path d="M144 138v39m-12-39h25" stroke="#E7A85C" stroke-width="9" stroke-linecap="round"/>
<rect x="83" y="206" width="71" height="22" rx="5" fill="#81BBAE"/>"""
    if stage >= 2:
        furniture += """<rect x="49" y="60" width="150" height="11" rx="5" fill="#B88D6C"/>
<rect x="67" y="31" width="20" height="29" rx="3" fill="#7097D0"/>
<rect x="90" y="23" width="17" height="37" rx="3" fill="#EFB86B"/>
<rect x="110" y="34" width="22" height="26" rx="3" fill="#DF8F9F"/>
<circle cx="167" cy="43" r="15" fill="#C4DED5"/>
<path d="m163 44 5-8 4 8-6 8" fill="#6DAD97"/>"""
    if stage >= 3:
        furniture += """<rect x="66" y="169" width="112" height="59" rx="8" fill="#52667C"/>
<rect x="73" y="176" width="98" height="44" rx="4" fill="#A2D7E7"/>
<path d="m87 205 13-12 13 8 16-15 23 12" stroke="#FFF" stroke-width="3" fill="none"/>
<path d="M120 228v8m-18 0h36" stroke="#52667C" stroke-width="5" stroke-linecap="round"/>"""
    extras = ""
    if stage >= 4:
        extras += """<rect x="448" y="241" width="85" height="70" rx="11" fill="#F1C884"/>
<rect x="448" y="258" width="85" height="5" fill="#DFB577"/>
<rect x="479" y="277" width="24" height="6" rx="3" fill="#BD9561"/>
<circle cx="485" cy="220" r="24" fill="#A9CFC4"/>
<path d="M484 239v-40m0 19-12-9m12 2 12-10" stroke="#6CA492" stroke-width="5" stroke-linecap="round"/>"""
    city = ""
    if stage == 5:
        city = """<path d="M437 193v-53h20v-27h23v80m9 0v-79h28v79m8 0v-42h21v42" fill="#90B8D5"/>
<path d="M443 151h7m-7 13h7m14-38h8m-8 16h8m26-16h10m-10 16h10m-10 16h10" stroke="#DCF2F7" stroke-width="4"/>"""
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="600" height="400" viewBox="0 0 600 400">
<defs><linearGradient id="wall" x2="0" y2="1"><stop stop-color="{wall}"/><stop offset="1" stop-color="#F8FBFD"/></linearGradient>
<linearGradient id="floor" x2="0" y2="1"><stop stop-color="#EBDAC1"/><stop offset="1" stop-color="#F8EBDD"/></linearGradient></defs>
<rect width="600" height="400" rx="28" fill="url(#wall)"/>
<circle cx="301" cy="117" r="163" fill="#FFF" opacity=".28"/>
<path d="M0 293h600v107H0z" fill="url(#floor)"/><path d="M0 289h600v8H0z" fill="#D8D0C0"/>
<path d="M65 400 147 297m93 103 33-103m90 103-12-103m155 103-80-103" stroke="#D4BEA0" opacity=".45" stroke-width="2"/>
<rect x="421" y="63" width="137" height="151" rx="20" fill="#FFF"/>
<rect x="430" y="72" width="119" height="133" rx="13" fill="#C7E5F5"/>
<circle cx="515" cy="100" r="17" fill="#FFE7A8"/><path d="M435 122c11-13 28-12 39 0 14-2 21 4 20 13h-59z" fill="#FFF" opacity=".85"/>
{city}<path d="M489 70v137m-60-64h121" stroke="#FFF" stroke-width="6"/>
{furniture}{extras}
<ellipse cx="301" cy="350" rx="103" ry="18" fill="#A88A6A" opacity=".16"/>
<circle cx="393" cy="80" r="4" fill="#E8BB63"/><path d="M372 111v13m-6-6h12" stroke="#FFF" stroke-width="3" stroke-linecap="round"/>
</svg>'''
    (ASSETS / f"workshop_{stage}.svg").write_text(svg, encoding="utf-8")
print(f"Created {len(WALLS)} vector scenes")
