"""Measure the same main-game scenarios before/after on this desktop only."""

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from urllib.request import urlopen

from collect_volt_metrics import summarise

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / ".cache/volt-refinement/performance/paired"


def python(script, *args):
    # Start the actual interpreter, not the Windows venv forwarding launcher,
    # so terminating our owned child also terminates its loopback server.
    return [sys._base_executable, "-c",
            "import site,sys,runpy;site.addsitedir(sys.argv[1]);p=sys.argv[2];sys.argv=sys.argv[2:];runpy.run_path(p,run_name='__main__')",
            str(Path(sys.prefix) / "Lib/site-packages"), str(ROOT / "tools" / script), *map(str, args)]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=OUT)
    parser.add_argument('--baseline-source', type=Path, default=ROOT / '.cache/volt-refinement/before/src')
    parser.add_argument('--before-client', type=Path, default=ROOT / '.cache/volt-refinement/before-profile-client')
    parser.add_argument('--after-client', type=Path, default=ROOT / '.cache/volt-refinement/after-profile-client')
    parser.add_argument('--revision', choices=['all','before','after'], default='all')
    args = parser.parse_args()
    output = args.out.resolve()
    output.mkdir(parents=True, exist_ok=True)
    reports = json.loads((output/'summary.json').read_text()) if (output/'summary.json').exists() else {}
    for index, (revision, scenario) in enumerate((
        ("before", "workshop"), ("after", "workshop"),
        ("before", "combat"), ("after", "combat"),
    )):
        if args.revision != 'all' and revision != args.revision:
            continue
        name = f"{revision}-{scenario}"
        folder = output / name
        folder.mkdir(exist_ok=True)
        port = 18575 + index
        metrics = folder / "frames.jsonl"
        source = args.baseline_source.resolve() if revision == "before" else ROOT / "src"
        client = (args.before_client if revision == 'before' else args.after_client).resolve()
        assert (client / "main.dart.js").is_file(), client
        env = dict(os.environ, PYTHONUTF8="1")
        children, streams = [], []
        try:
            for label, command in [
                ("metrics", python("collect_volt_metrics.py", "--out", metrics)),
                ("server", python("profile_interactive_game.py", "--source", source,
                                  "--out", folder, "--port", port, "--mode", "battle" if scenario == "combat" else "workshop",
                                  "--robot", "volt", "--silent")),
            ]:
                stream = (folder / f"{label}.log").open("w", encoding="utf-8")
                streams.append(stream)
                children.append(subprocess.Popen(command, cwd=ROOT, env=env, stdout=stream, stderr=stream,
                                                 creationflags=subprocess.CREATE_NO_WINDOW))
            for _ in range(100):
                try:
                    urlopen(f"http://127.0.0.1:{port}", timeout=.3).close()
                    break
                except OSError:
                    if any(child.poll() is not None for child in children):
                        raise RuntimeError(f"{name}: helper stopped; see logs")
                    time.sleep(.1)
            else:
                raise RuntimeError(f"{name}: game server did not start")
            width, height, dpr = (390, 844, 3) if scenario == "workshop" else (844, 390, 2)
            capture_name = f"{output.parent.name}-{name}"
            subprocess.run(python("capture_game_renderer.py", "--name", capture_name,
                                  "--port", port, "--client", client, "--width", width,
                                  "--height", height, "--dpr", dpr, "--seconds", 30),
                           cwd=ROOT, env=env, check=True, timeout=90)
            summarise(metrics, folder / "summary.json")
            report = json.loads((folder / "summary.json").read_text(encoding="utf-8"))
            report["first_render"] = json.loads((folder / "first-render.json").read_text(encoding="utf-8"))
            report["first_native_paint"] = json.loads((folder / "first-paint.jsonl").read_text(encoding="utf-8").splitlines()[0])
            report["dpr"] = dpr
            report["capture"] = capture_name
            report['memory'] = json.loads((ROOT/'.cache/rework-review'/capture_name/'memory.json').read_text())
            reports[name] = report
            (output / "summary.json").write_text(json.dumps(reports, indent=2), encoding="utf-8")
            print(f"Completed {name}: {report['samples_after_warmup']} windows, median unique FPS {report['median_unique_vsync_fps']:.1f}", flush=True)
        finally:
            for child in reversed(children):
                if child.poll() is None:
                    child.terminate()
                child.wait(timeout=10)
            for stream in streams:
                stream.close()
    print(output / "summary.json", flush=True)


if __name__ == "__main__":
    main()
