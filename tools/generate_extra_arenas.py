"""Original lightweight vector arenas; no raster filters or online resources."""

from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def arena(index, sky, accent, name):
    stars=''.join(f'<circle cx="{(i*73+31)%480}" cy="{(i*37+9)%170}" r="{1+i%2}" fill="{accent}" opacity=".45"/>' for i in range(24))
    towers=''.join(f'<path d="M{x} 210V{80+(i%3)*28}l22 -22 22 22V210Z" fill="#162D48" stroke="{accent}" stroke-opacity=".3"/><path d="M{x+12} {110+(i%3)*20}h20m-20 17h20" stroke="{accent}" opacity=".5"/>' for i,x in enumerate((-20,35,92,345,408,462)))
    grid=''.join(f'<path d="M240 174L{x} 280" stroke="{accent}" opacity=".11"/>' for x in range(-600,1100,130))
    ground=''.join(f'<path d="M0 {y}H480" stroke="{accent}" opacity=".1"/>' for y in (197,218,247,279))
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="480" height="280" viewBox="0 0 480 280">
<defs><linearGradient id="sky" x2="0" y2="1"><stop stop-color="{sky}"/><stop offset="1" stop-color="#102039"/></linearGradient><radialGradient id="sun"><stop stop-color="{accent}" stop-opacity=".45"/><stop offset="1" stop-color="{accent}" stop-opacity="0"/></radialGradient><linearGradient id="floor" x2="0" y2="1"><stop stop-color="#25425B"/><stop offset="1" stop-color="#11243A"/></linearGradient></defs>
<rect width="480" height="280" fill="url(#sky)"/>{stars}
<circle cx="240" cy="99" r="104" fill="url(#sun)"/><circle cx="240" cy="99" r="55" fill="none" stroke="{accent}" stroke-opacity=".3" stroke-width="2"/>
<path d="M173 170V94a67 67 0 0 1 134 0v76" fill="#1B324B" fill-opacity=".3" stroke="{accent}" stroke-opacity=".3" stroke-width="4"/>{towers}
<path d="M0 190Q240 161 480 190V280H0Z" fill="url(#floor)"/>{grid}{ground}
<ellipse cx="115" cy="226" rx="87" ry="26" fill="#102739" stroke="{accent}" stroke-opacity=".75" stroke-width="2"/><ellipse cx="365" cy="226" rx="87" ry="26" fill="#17233F" stroke="#BD9DF6" stroke-opacity=".75" stroke-width="2"/>
<ellipse cx="115" cy="226" rx="67" ry="18" fill="none" stroke="{accent}" stroke-opacity=".2"/><ellipse cx="365" cy="226" rx="67" ry="18" fill="none" stroke="#BD9DF6" stroke-opacity=".2"/>
<path d="M0 264H480" stroke="{accent}" opacity=".3"/><title>{name}</title></svg>'''


if __name__=='__main__':
    for index,sky,accent,name in ((3,'#402838','#FFB469','Кузница звёзд'),(4,'#183B40','#86EED3','Аврора')):
        (ROOT/f'src/assets/art/arena/stage_{index}.svg').write_text(arena(index,sky,accent,name),encoding='utf-8')
