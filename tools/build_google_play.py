"""Build an isolated, upload-signed Google Play testing bundle."""

import argparse
import ast
import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

import tomllib

ROOT = Path(__file__).resolve().parents[1]
SIGNING = ROOT / ".signing"
TEST_APP_ID = "ca-app-pub-3940256099942544~3347511713"
TEST_BANNER_ID = "ca-app-pub-3940256099942544/6300978111"
TEST_REWARDED_ID = "ca-app-pub-3940256099942544/5224354917"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def set_string_constant(source, name, value):
    tree = ast.parse(source)
    assignments = [
        node
        for node in tree.body
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == name
            for target in node.targets
        )
    ]
    if len(assignments) != 1 or not isinstance(assignments[0].value, ast.Constant):
        raise ValueError(f"Expected one constant assignment: {name}")
    node = assignments[0]
    lines = source.splitlines(keepends=True)
    lines[node.lineno - 1 : node.end_lineno] = [f'{name} = "{value}"\n']
    result = "".join(lines)
    ast.parse(result)
    return result


def prepare_stage(root, stage, *, number, version, ads_mode):
    """Only copy app input; keys, saves and root build output stay outside it."""
    files = {
        str(path.relative_to(root)).replace("\\", "/"): digest(path)
        for path in (root / "src").rglob("*")
        if path.is_file()
        and "__pycache__" not in path.parts
        and ".flet" not in path.relative_to(root / "src").parts
        and path.suffix not in {".pyc", ".pyo"}
    }
    expected = {
        "build_number": number,
        "build_version": version,
        "ads_mode": ads_mode,
        "base_pyproject_sha256": digest(root / "pyproject.toml"),
        "base_sources": files,
    }
    manifest = stage / "build-input.json"
    if manifest.exists():
        previous = json.loads(manifest.read_text(encoding="utf-8"))
        if previous["input"] != expected:
            raise ValueError(
                "Build inputs changed. Use a new build number; existing stages are retained."
            )
        for name, expected_hash in previous["staged_sources"].items():
            if digest(stage / name) != expected_hash:
                raise ValueError(f"Staged source changed: {name}")
        if digest(stage / "pyproject.toml") != previous["staged_pyproject_sha256"]:
            raise ValueError("Staged build settings changed")
        return previous
    if (stage / "src").exists():
        raise ValueError("Incomplete stage exists; use a new build number")
    stage.mkdir(parents=True, exist_ok=True)
    shutil.copytree(
        root / "src",
        stage / "src",
        ignore=shutil.ignore_patterns(".flet", "__pycache__", "*.pyc", "*.pyo"),
    )
    project = (root / "pyproject.toml").read_text(encoding="utf-8")
    settings = tomllib.loads(project)
    overrides = settings["tool"]["flet"]["flutter"]["pubspec"]["dependency_overrides"]
    for package, config in overrides.items():
        if "path" in config:
            project = project.replace(
                f'path = "{config["path"]}"',
                f'path = "{(root / "extensions" / package).as_posix()}"',
            )
    if ads_mode == "test":
        (stage/'src/assets/config').mkdir(parents=True,exist_ok=True)
        (stage/'src/assets/config/billing.json').write_text(json.dumps({'sandbox':True}),encoding='utf-8')
        app_id = settings["tool"]["flet"]["android"]["meta_data"][
            "com.google.android.gms.ads.APPLICATION_ID"
        ]
        project = project.replace(app_id, TEST_APP_ID)
        for filename, name, value in (
            ("advertising.py", "BANNER_UNIT_ID", TEST_BANNER_ID),
            ("rewarded_ads.py", "REWARDED_UNIT_ID", TEST_REWARDED_ID),
        ):
            path = stage / "src" / filename
            path.write_text(
                set_string_constant(path.read_text(encoding="utf-8"), name, value),
                encoding="utf-8",
            )
    (stage / "pyproject.toml").write_text(project, encoding="utf-8")
    # Parse again before invoking any build process.
    tomllib.loads(project)
    result = {
        "input": expected,
        "staged_sources": {name: digest(stage / name) for name in files},
        "staged_pyproject_sha256": digest(stage / "pyproject.toml"),
    }
    manifest.write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return result


def build_environment():
    metadata = json.loads((SIGNING / "upload-key.json").read_text(encoding="utf-8"))
    password = (SIGNING / metadata["password_file"]).read_text(encoding="utf-8").strip()
    keystore = SIGNING / metadata["keystore_file"]
    if not keystore.is_file() or len(password) < 20:
        raise ValueError(
            "Upload signing files are incomplete; do not regenerate an existing Play key"
        )
    env = dict(os.environ)
    env.update(
        {
            "PYTHONUTF8": "1",
            "PYTHONIOENCODING": "utf-8",
            "PYTHONUNBUFFERED": "1",
            "JAVA_HOME": str(Path.home() / "java/17.0.13+11"),
            "FLET_ANDROID_SIGNING_KEY_STORE": str(keystore),
            "FLET_ANDROID_SIGNING_KEY_STORE_PASSWORD": password,
            "FLET_ANDROID_SIGNING_KEY_PASSWORD": password,
            "FLET_ANDROID_SIGNING_KEY_ALIAS": metadata["alias"],
        }
    )
    env["PATH"] = (
        str(Path.home() / "flutter/3.47.9/bin")
        + os.pathsep
        + str(Path(env["JAVA_HOME"]) / "bin")
        + os.pathsep
        + env["PATH"]
    )
    return env, password


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build-number", type=int, default=17)
    parser.add_argument("--build-version", default="0.1.1")
    parser.add_argument("--ads-mode", choices=("test", "live"), default="test")
    parser.add_argument("--prepare-only", action="store_true")
    args = parser.parse_args()
    if args.build_number < 17:
        parser.error("The Play build number must be at least 17")
    stage = ROOT / f".cache/play-{args.ads_mode}-v{args.build_number}"
    prepare_stage(
        ROOT,
        stage,
        number=args.build_number,
        version=args.build_version,
        ads_mode=args.ads_mode,
    )
    if args.prepare_only:
        print(f"Prepared {stage}")
        return
    output = ROOT / f"build/play-{args.ads_mode}-v{args.build_number}"
    output.mkdir(parents=True, exist_ok=True)
    env, password = build_environment()
    command = [
        str(ROOT / ".venv/Scripts/flet.exe"),
        "build",
        "aab",
        str(stage),
        "--output",
        str(output),
        "--build-number",
        str(args.build_number),
        "--build-version",
        args.build_version,
        "--no-rich-output",
    ]
    log = ROOT / f".cache/play-{args.ads_mode}-build-{args.build_number}.log"
    with log.open("w", encoding="utf-8") as stream:
        result = subprocess.run(
            command, cwd=stage, env=env, stdout=stream, stderr=subprocess.STDOUT
        )
    contents = log.read_text(encoding="utf-8", errors="replace")
    if password in contents:
        # Do not display or retain a credential if an upstream tool printed it.
        log.write_text(contents.replace(password, "[REDACTED]"), encoding="utf-8")
        raise RuntimeError("Build tool printed a signing secret; log was redacted")
    print("\n".join(contents.splitlines()[-18:]))
    if result.returncode:
        raise SystemExit(result.returncode)
    print(f"Play testing bundle: {output / 'clicker.aab'}")
    print(
        "Signing passwords were supplied through the process environment, not command arguments."
    )


if __name__ == "__main__":
    main()
