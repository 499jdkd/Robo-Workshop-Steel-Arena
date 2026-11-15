"""Verify, export with the official CLI, and stage the script-free Rive rig.

Needs `rive login` for the official publish command. Does not upload the game,
publish a web page, edit the game package, or access a player save.
"""

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    cli = shutil.which("rive") or str(
        Path(os.environ["USERPROFILE"]) / ".rive/bin/rive.exe"
    )
    project = ROOT / "animation/rive/spark"
    subprocess.run([cli, str(project), "--verify", "--format=json"], check=True)
    inspected = subprocess.run(
        [cli, "inspect", str(project), "--summary"],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    data = json.loads(inspected.stdout)
    if data.get("problems"):
        raise SystemExit(
            "Rive inspect reported problems; fix the source before exporting."
        )
    subprocess.run([cli, str(project), "--publish"], check=True)
    source = project / "build/spark.riv"
    output = ROOT / "prototypes/rive_robot/assets/spark.riv"
    output.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, output)
    flutter_asset = ROOT / "prototypes/rive_robot/flutter/assets/spark.riv"
    flutter_asset.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, flutter_asset)
    print(
        json.dumps(
            {
                "asset": str(output),
                "bytes": output.stat().st_size,
                "sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
                "game_data_accessed": False,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
