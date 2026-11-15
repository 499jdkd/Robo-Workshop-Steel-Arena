"""Finish a staged APK using identical, previously compiled dependency caches."""

import argparse
import os
from pathlib import Path
import shutil
import struct
import subprocess
import tomllib

from flutter_cached import SDK, command, environment

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build-number", type=int, default=22)
    parser.add_argument("--cache-number", type=int, default=20)
    args = parser.parse_args()
    stage = ROOT / f".cache/game-test-v{args.build_number}"
    cached = ROOT / f".cache/game-test-v{args.cache_number}"
    settings = tomllib.loads((stage / "pyproject.toml").read_text(encoding="utf-8"))
    previous = tomllib.loads((cached / "pyproject.toml").read_text(encoding="utf-8"))
    assert settings["project"]["dependencies"] == previous["project"]["dependencies"]
    assert (cached / "build/.python-version").read_text().strip() == "3.14"
    (stage / "build").mkdir(exist_ok=True)
    (stage / "build/.python-version").write_text("3.14", encoding="utf-8")
    excludes = set(settings["tool"]["flet"]["app"]["exclude"])
    if not (stage / "build/python-app/main.pyc").is_file():
        package = [str(SDK / "bin/cache/dart-sdk/bin/dart.exe"), "run", "--suppress-analytics",
                   "serious_python:main", "package", str(stage / "src"),
                   "--platform", "Android", "--python-version", "3.14",
                   "--arch", "arm64-v8a,x86_64,armeabi-v7a", "--skip-site-packages", "--compile-app"]
        for requirement in settings["project"]["dependencies"]:
            package.extend(["-r", requirement])
        for name in [*sorted(excludes), ".flet"]:
            package.extend(["--exclude", name])
        print("Packaging current Python app with official serious_python; dependency install skipped", flush=True)
        package_env = environment()
        package_env.update(SERIOUS_PYTHON_APP=str(stage / "build/python-app"),
                           SERIOUS_PYTHON_SITE_PACKAGES=str(stage / "build/site-packages"))
        subprocess.run(package, cwd=cached / "build/flutter", env=package_env, check=True)
    for source in (stage / "src").glob("*.py"):
        if source.name in excludes:
            continue
        compiled = (stage / "build/python-app" / source.with_suffix(".pyc").name).read_bytes()
        assert struct.unpack("<III", compiled[4:16])[2] == source.stat().st_size, source.name
    for abi in ("arm64-v8a", "armeabi-v7a", "x86_64"):
        for dependency in ("flet", "flet_ads", "flet_rive", "httpx"):
            assert (cached / "build/site-packages" / abi / dependency).is_dir(), (abi, dependency)
    project = cached / "build/flutter"
    props = project / "android/gradle.properties"
    text = props.read_text(encoding="utf-8")
    text = "\n".join(line for line in text.splitlines()
                     if not line.startswith(("org.gradle.jvmargs=", "org.gradle.workers.max=")))
    props.write_text(text + "\norg.gradle.jvmargs=-Xmx3G -XX:MaxMetaspaceSize=1G\norg.gradle.workers.max=2\n", encoding="utf-8")
    env = environment()
    env.update(SERIOUS_PYTHON_VERSION="3.14", SERIOUS_PYTHON_APP=str(stage / "build/python-app"),
               SERIOUS_PYTHON_SITE_PACKAGES=str(cached / "build/site-packages"))
    for key in list(env):
        if key.startswith("FLET_ANDROID_SIGNING_"):
            env.pop(key)
    output = ROOT / f"build/apk-game-v{args.build_number}"
    output.mkdir(exist_ok=True)
    if (output / "clicker.apk").exists():
        raise RuntimeError("Retain the existing APK; use a new build number")
    print(f"Verified package cache v{args.cache_number}; bundling current v{args.build_number} Python app", flush=True)
    subprocess.run([*command(), "build", "apk", "--release", "--build-name", "0.2.0",
                    "--build-number", str(args.build_number)], cwd=project, env=env, check=True)
    shutil.copy2(project / "build/app/outputs/flutter-apk/app-release.apk", output / "clicker.apk")
    print(output / "clicker.apk", flush=True)


if __name__ == "__main__":
    main()
