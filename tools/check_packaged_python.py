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
    parser.add_argument("--check-server", action="store_true")
    args = parser.parse_args()
    output = ROOT / f"build/apk-game-v{args.build_number}/validation"
    output.mkdir(exist_ok=True)
    target = ROOT / f".cache/apk-v{args.build_number}-imports"
    target.mkdir(exist_ok=True)
    with zipfile.ZipFile(output.parent / "clicker.apk") as package:
        for name in ("app.zip", "sitepackages.zip"):
            (target / name).write_bytes(package.read("assets/" + name))
    app_dir = target / "app"
    app_dir.mkdir(exist_ok=True)
    with zipfile.ZipFile(target / "app.zip") as app:
        app.extractall(app_dir)
    code = """import sys,json
sys.path[:0]=sys.argv[1:3]
import main,gameplay,game_session,game_animation,armory,armory_ui,online_arena,online_ui,online_focus,robot_arena,robot_ui
import network_config,app_paths
import combat_info,robot_abilities,robot_preview,collection_ui,feature_screens
assert len(robot_abilities.ABILITIES)==32
state=gameplay.GameState.from_dict({'coin':90,'robot_levels':{'spark':5},'active_robot':'spark','egg_id':'','weapon_levels':{'plasma':2},'loadouts':{'spark':['plasma']}})
assert state.coin==90 and state.weapon_levels=={'plasma':2} and state.loadouts=={'spark':['plasma']}
url=network_config.arena_url()
assert url==json.loads(app_paths.asset_path('config/network.json').read_text())['arena_url']
server_checked=False
if '--check-server' in sys.argv[3:]:
 import httpx
 with httpx.Client(timeout=20) as client:
  response=client.get(url+'/health')
 response.raise_for_status()
 assert response.json()['rules_version']==3
 server_checked=True
print(json.dumps({'python':sys.version.split()[0],'apk_module_imports':18,'save_load':'passed','physical_android':False,'arena_url':url,'public_https_checked':server_checked}))
"""
    runtime = ROOT / ".cache/game-test-v20/build/flutter/build/build_python_3.14.7/python/python.exe"
    env = environment()
    env.pop("CLICKER_ARENA_URL", None)
    result = subprocess.run([str(runtime), "-S", "-c", code, str(app_dir), str(target / "sitepackages.zip"), *(["--check-server"] if args.check_server else [])],
                            env=env, capture_output=True, encoding="utf-8", errors="replace")
    (output / "python-imports.txt").write_text(result.stdout + result.stderr, encoding="utf-8")
    print(result.stdout + result.stderr)
    raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()
