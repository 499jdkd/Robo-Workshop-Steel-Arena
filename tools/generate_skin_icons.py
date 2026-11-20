"""Editable cosmetic thumbnails derived from the same authored robot SVG."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from cosmetic_catalog import SKINS, SKIN_COLORS


def main():
    source = (ROOT / "src/assets/art/portraits/spark.svg").read_text(encoding="utf-8")
    output = ROOT / "src/assets/art/skins"
    output.mkdir(exist_ok=True)
    for identity, color in zip(SKINS, SKIN_COLORS):
        light = "#" + "".join(
            f"{min(255, int(color[n : n + 2], 16) + 45):02X}" for n in (1, 3, 5)
        )
        (output / f"{identity}.svg").write_text(
            source.replace("#FFB83F", color).replace("#FFEF76", light), encoding="utf-8"
        )
    print("Six authored cosmetic thumbnails written")


if __name__ == "__main__":
    main()
