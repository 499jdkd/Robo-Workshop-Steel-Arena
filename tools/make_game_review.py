"""Contact sheets of real main-game Flutter captures for visual review."""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / ".cache/ui-rendered"
OUTPUT = ROOT / "build/game-verification-v21"


def sheet(name, entries, columns, width=500):
    height = round(width * 585 / 1266)
    rows = (len(entries) + columns - 1) // columns
    result = Image.new("RGB", (width * columns, (height + 28) * rows), "#e9eef8")
    draw = ImageDraw.Draw(result)
    font = ImageFont.truetype("C:/Windows/Fonts/segoeui.ttf", 16)
    for i, entry in enumerate(entries):
        frame = Image.open(SOURCE / f"{entry}.png").convert("RGB")
        frame.thumbnail((width, height), Image.Resampling.LANCZOS)
        x, y = (i % columns) * width, (i // columns) * (height + 28)
        draw.text((x + 8, y + 4), entry.removeprefix("motion-"), fill="#243753", font=font)
        result.paste(frame, (x, y + 28))
    result.save(OUTPUT / f"{name}.png")


OUTPUT.mkdir(parents=True, exist_ok=True)
sheet("robots", ["motion-robot-" + x for x in
      ["spark", "volt", "flora", "forge", "nova", "glacier", "aegis", "solar"]], 2)
sheet("weapons-flight", ["motion-weapon-" + x + "-flight" for x in
      ["plasma", "sniper", "electric", "rocket", "shield", "laser", "machinegun", "sword", "flame", "drone"]], 2)
sheet("weapons-impact", ["motion-weapon-" + x + "-impact" for x in
      ["plasma", "sniper", "electric", "rocket", "shield", "laser", "machinegun", "sword", "flame", "drone"]], 2)
sheet("emotions", ["motion-emotion-" + x for x in
      ["joy", "anger", "fear", "surprise", "victory", "defeat"]], 2)
print(OUTPUT)
