"""Run this project's installed Flutter SDK using its official cached CLI.

The Windows .bat bootstrap runs PowerShell to re-check the engine on every
invocation. This machine sometimes stalls there. This entry point uses the
already installed, versioned SDK; it does not modify the SDK or skip build checks.
"""

import os
from pathlib import Path
import subprocess
import sys

SDK = Path.home() / "flutter/3.44.8"


def command():
    runtime = SDK / "bin/cache/dart-sdk/bin/dart.exe"
    snapshot = SDK / "bin/cache/flutter_tools.snapshot"
    packages = SDK / "packages/flutter_tools/.dart_tool/package_config.json"
    if not all(p.is_file() for p in (runtime, snapshot, packages)):
        raise RuntimeError("Flutter 3.44.8 must be installed and initialized first")
    return [str(runtime), f"--packages={packages}", str(snapshot)]


def environment():
    env = dict(os.environ, FLUTTER_ROOT=str(SDK))
    # Some task runners provide a minimal environment rather than a shell's.
    for key, value in {
        "PATHEXT": ".COM;.EXE;.BAT;.CMD",
        "SystemRoot": "C:\\Windows",
        "WINDIR": "C:\\Windows",
        "COMSPEC": "C:\\Windows\\System32\\cmd.exe",
        "USERPROFILE": str(Path.home()),
        "HOMEDRIVE": Path.home().drive,
        "HOMEPATH": str(Path.home())[len(Path.home().drive):],
        "PROGRAMFILES": "C:\\Program Files",
        "PROGRAMFILES(X86)": "C:\\Program Files (x86)",
        "PROGRAMW6432": "C:\\Program Files",
        "SystemDrive": "C:",
        "TEMP": str(Path.home() / "AppData/Local/Temp"),
        "TMP": str(Path.home() / "AppData/Local/Temp"),
        "LOCALAPPDATA": str(Path.home() / "AppData/Local"),
        "APPDATA": str(Path.home() / "AppData/Roaming"),
        "ANDROID_HOME": str(Path.home() / "Android/sdk"),
        "JAVA_HOME": str(Path.home() / "java/17.0.13+11"),
    }.items():
        if not env.get(key):
            env[key] = value
    rive = Path.home() / "AppData/Local/Pub/Cache/hosted/pub.dev/rive_native-0.1.11/windows/bin/lib/release"
    paths = [SDK / "bin", SDK / "bin/mingit/cmd", Path(env["JAVA_HOME"]) / "bin",
             rive, Path(env["SystemRoot"]) / "System32", Path("C:/Program Files/Git/cmd")]
    env["PATH"] = os.pathsep.join(str(p) for p in paths) + os.pathsep + env.get("PATH", "")
    return env


if __name__ == "__main__":
    raise SystemExit(subprocess.run([*command(), *sys.argv[1:]], env=environment()).returncode)
