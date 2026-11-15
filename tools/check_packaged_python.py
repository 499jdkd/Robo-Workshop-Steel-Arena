"""Import the actual APK's pure Python modules with its CPython 3.14 version."""

import argparse
from pathlib import Path
import subprocess
import zipfile

from flutter_cached import environment

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build-number", type=int, default=22)
    args = parser.parse_args()
    output = ROOT / f"build/apk-game-v{args.build_number}/validation"
    output.mkdir(exist_ok=True)
    target = ROOT / f".cache/apk-v{args.build_number}-imports"
    target.mkdir(exist_ok=True)
    with zipfile.ZipFile(output.parent / "clicker.apk") as package:
        for name in ("app.zip", "sitepackages.zip"):
            (target / name).write_bytes(package.read("assets/" + name))
    code = """import sys,json
sys.path[:0]=sys.argv[1:]
import main,gameplay,game_session,game_animation,armory,armory_ui,online_arena,online_ui,online_focus,robot_arena,robot_ui
state=gameplay.GameState.from_dict({'coin':90,'robot_levels':{'spark':5},'active_robot':'spark','egg_id':'','weapon_levels':{'plasma':2},'loadouts':{'spark':['plasma']}})
assert state.coin==90 and state.weapon_levels=={'plasma':2} and state.loadouts=={'spark':['plasma']}
print(json.dumps({'python':sys.version.split()[0],'apk_module_imports':11,'save_load':'passed','physical_android':False}))
"""
    runtime = ROOT / ".cache/game-test-v20/build/flutter/build/build_python_3.14.7/python/python.exe"
    result = subprocess.run([str(runtime), "-S", "-c", code, str(target / "app.zip"), str(target / "sitepackages.zip")],
                            env=environment(), capture_output=True, encoding="utf-8", errors="replace")
    (output / "python-imports.txt").write_text(result.stdout + result.stderr, encoding="utf-8")
    print(result.stdout + result.stderr)
    raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()
