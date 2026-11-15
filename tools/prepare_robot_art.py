"""Encode generated PNG originals as game WebP assets without changing artwork.

Run with a Python environment containing Pillow. Alpha is checked losslessly;
no cropping, repainting, background removal or rescaling is performed here.
"""

import hashlib
import json
from pathlib import Path

from PIL import Image, ImageChops

ROOT = Path(__file__).resolve().parents[1]
ORIGINALS = ROOT / "artwork/robot_collection"
OUTPUT = ROOT / "src/assets/art"
OUTPUT.mkdir(parents=True, exist_ok=True)
manifest = json.loads((ORIGINALS / "prompts.json").read_text(encoding="utf-8-sig"))
layouts = {}
encoded = []

for record in manifest:
    key = record["key"]
    source = ORIGINALS / f"{key}.png"
    target = OUTPUT / f"{key}.webp"
    with Image.open(source) as image:
        alpha = None
        if record["transparent"]:
            assert image.mode == "RGBA", f"Missing alpha: {key}"
            alpha = image.getchannel("A")
            assert alpha.getextrema() == (0, 255), f"Invalid transparency: {key}"
            bbox = alpha.point(lambda value: 255 if value >= 128 else 0).getbbox()
            assert bbox, f"Empty sprite: {key}"
            layouts[f"art/{key}.webp"] = [image.width, image.height, *bbox]
        image.save(target, "WEBP", quality=92 if alpha else 86, method=6, exact=True)
        if alpha:
            with Image.open(target) as result:
                assert (
                    ImageChops.difference(alpha, result.getchannel("A")).getbbox()
                    is None
                ), f"Alpha changed: {key}"
        encoded.append(
            {
                "asset": f"art/{key}.webp",
                "dimensions": list(image.size),
                "bytes": target.stat().st_size,
                "sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
                "alpha_preserved": alpha is not None,
            }
        )

(ROOT / "src/asset_layout.py").write_text(
    '"""Generated sprite bounds used to place feet on incubation pedestals."""\n\n'
    + "SPRITE_BOUNDS = "
    + repr(layouts)
    + "\n",
    encoding="utf-8",
)
(ORIGINALS / "encoded-assets.json").write_text(
    json.dumps(encoded, indent=2) + "\n", encoding="utf-8"
)
print(
    json.dumps(
        {
            "assets": len(encoded),
            "webp_bytes": sum(item["bytes"] for item in encoded),
            "png_bytes": sum(
                (ORIGINALS / f"{item['key']}.png").stat().st_size for item in manifest
            ),
            "transparent_sprites": len(layouts),
        },
        indent=2,
    )
)
