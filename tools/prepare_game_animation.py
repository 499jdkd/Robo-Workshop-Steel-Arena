"""Reproducible local Rive export and original, gently limited game SFX."""

import json
import math
import os
import random
import shutil
import struct
import subprocess
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOUNDS = {
    "deploy": (0.35, 180, 520, 0.17),
    "aim": (0.48, 720, 1400, 0.02),
    "plasma": (0.5, 950, 95, 0.2),
    "sniper": (0.42, 190, 45, 0.65),
    "electric": (0.62, 160, 620, 0.38),
    "rocket": (0.75, 85, 210, 0.68),
    "impact": (0.52, 120, 35, 0.8),
    "shield": (0.6, 560, 240, 0.12),
    "feed": (0.55, 620, 1240, 0.01),
    "victory": (1.15, 520, 1040, 0.01),
    "laser": (0.55, 1600, 220, 0.06),
    "machinegun": (0.5, 190, 70, 0.85),
    "sword": (0.5, 850, 160, 0.38),
    "flame": (0.8, 90, 75, 0.95),
    "drone": (0.65, 210, 350, 0.2),
}


def make_sounds():
    target = ROOT / "src/assets/audio"
    target.mkdir(parents=True, exist_ok=True)
    for name, (duration, start, end, noise) in SOUNDS.items():
        rng, phase, samples = random.Random(40), 0.0, []
        for i in range(int(22050 * duration)):
            t = i / 22050
            u = t / duration
            frequency = start * (end / start) ** u
            if name == "victory":
                frequency = (523.25, 659.25, 783.99, 1046.5)[min(3, int(u * 4))]
            phase += math.tau * frequency / 22050
            tone = math.sin(phase) + 0.2 * math.sin(phase * 2.01)
            env = min(1, t / 0.012) * (1 - u) ** (1.6 if noise > 0.3 else 0.8)
            value = (tone * (1 - noise) + rng.uniform(-1, 1) * noise) * env * 0.65
            samples.append(struct.pack("<h", int(max(-0.95, min(0.95, value)) * 32767)))
        with wave.open(str(target / f"{name}.wav"), "wb") as audio:
            audio.setnchannels(1)
            audio.setsampwidth(2)
            audio.setframerate(22050)
            audio.writeframes(b"".join(samples))


def main():
    subprocess.run(
        [
            str(ROOT / ".venv/Scripts/python.exe"),
            str(ROOT / "animation/rive/generate_game_robot.py"),
        ],
        check=True,
    )
    cli = shutil.which("rive") or str(
        Path(os.environ["USERPROFILE"]) / ".rive/bin/rive.exe"
    )
    project = ROOT / "animation/rive/game_robot"
    subprocess.run([cli, str(project), "--verify", "--format=json"], check=True)
    result = subprocess.run(
        [cli, "inspect", str(project), "--summary"],
        check=True,
        capture_output=True,
        encoding="utf-8",
    )
    if json.loads(result.stdout).get("problems"):
        raise RuntimeError("Rive source has problems")
    subprocess.run([cli, str(project), "--publish"], check=True)
    target = ROOT / "src/assets/animation/game_robot.riv"
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(project / "build/game_robot.riv", target)
    make_sounds()
    print(
        f"Game rig staged: {target.stat().st_size} bytes; {len(SOUNDS)} original PCM sounds"
    )


if __name__ == "__main__":
    main()
