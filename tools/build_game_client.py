"""Build only the custom animation client used by source desktop/web runs."""

from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from desktop_startup import write_contract
from flutter_cached import command, environment


def main():
    subprocess.run(
        [
            *command(),
            "build",
            "web",
            "--release",
            "--no-web-resources-cdn",
            "--no-wasm-dry-run",
            "--dart-define=RIVE_NATIVE_WASM_HOST=/rive/",
        ],
        cwd=ROOT / "tools/game_client",
        env=environment(),
        check=True,
    )
    from build_windows_game import bundle_wasm

    client = ROOT / "tools/game_client/build/web"
    bundle_wasm(client / "rive")
    write_contract(ROOT, client)
    print("Custom game client ready: GameRive, GameCountdown, GameFactory")


if __name__ == "__main__":
    main()
