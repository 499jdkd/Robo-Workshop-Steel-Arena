"""Create and back up the first Google Play upload key without printing secrets."""

import hashlib
import json
import os
import secrets
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PRIVATE = ROOT / ".signing"
BACKUP = Path.home() / ".android/play-upload-backups/clicker"
KEYTOOL = Path.home() / "java/17.0.13+11/bin/keytool.exe"


def restrict_directory(path):
    path.mkdir(parents=True, exist_ok=True)
    sid = subprocess.check_output(
        [
            "powershell",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            "[System.Security.Principal.WindowsIdentity]::GetCurrent().User.Value",
        ],
        text=True,
    ).strip()
    subprocess.run(
        [
            "icacls",
            str(path),
            "/inheritance:r",
            "/grant:r",
            f"*{sid}:(OI)(CI)F",
            "*S-1-5-18:(OI)(CI)F",
        ],
        check=True,
        capture_output=True,
    )


def run_keytool(args, env):
    result = subprocess.run([str(KEYTOOL), *args], env=env, capture_output=True)
    if result.returncode:
        raise RuntimeError(result.stderr.decode(errors="replace"))
    return result


def main():
    restrict_directory(PRIVATE)
    metadata_file = PRIVATE / "upload-key.json"
    key = PRIVATE / "clicker-upload.jks"
    password_file = PRIVATE / "upload-password.txt"
    alias = "clicker-upload"
    if metadata_file.exists():
        metadata = json.loads(metadata_file.read_text(encoding="utf-8"))
        if not key.is_file() or not password_file.is_file():
            raise RuntimeError(
                "Existing signing metadata is incomplete; restore its backup instead of creating another key"
            )
    else:
        if key.exists() or password_file.exists():
            raise RuntimeError(
                "Partial signing files found; refusing to overwrite a key"
            )
        password_file.write_text(secrets.token_urlsafe(36) + "\n", encoding="utf-8")
        env = dict(os.environ)
        env["CLICKER_UPLOAD_STORE_PASSWORD"] = password_file.read_text(
            encoding="utf-8"
        ).strip()
        run_keytool(
            [
                "-genkeypair",
                "-noprompt",
                "-keystore",
                str(key),
                "-storetype",
                "JKS",
                "-alias",
                alias,
                "-keyalg",
                "RSA",
                "-keysize",
                "4096",
                "-validity",
                "10000",
                "-dname",
                "CN=Clicker Google Play Upload",
                "-storepass:env",
                "CLICKER_UPLOAD_STORE_PASSWORD",
                "-keypass:env",
                "CLICKER_UPLOAD_STORE_PASSWORD",
            ],
            env,
        )
        metadata = {
            "keystore_file": key.name,
            "password_file": password_file.name,
            "alias": alias,
        }
    env = dict(os.environ)
    env["CLICKER_UPLOAD_STORE_PASSWORD"] = password_file.read_text(
        encoding="utf-8"
    ).strip()
    for filename, extra in (
        ("upload-certificate.der", []),
        ("upload-certificate.pem", ["-rfc"]),
    ):
        run_keytool(
            [
                "-exportcert",
                "-keystore",
                str(key),
                "-alias",
                alias,
                "-storepass:env",
                "CLICKER_UPLOAD_STORE_PASSWORD",
                "-file",
                str(PRIVATE / filename),
                *extra,
            ],
            env,
        )
    fingerprint = hashlib.sha256(
        (PRIVATE / "upload-certificate.der").read_bytes()
    ).hexdigest()
    if metadata.get("certificate_sha256", fingerprint) != fingerprint:
        raise RuntimeError("Upload certificate differs from recorded metadata")
    metadata.update(
        {
            "certificate_sha256": fingerprint,
            "algorithm": "RSA 4096",
            "purpose": "Google Play upload signing",
        }
    )
    metadata_file.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    (PRIVATE / "KEEP-PRIVATE.txt").write_text(
        "Google Play upload key for Clicker. Keep this entire directory together.\n"
        "The JKS and upload-password.txt are private. Do not upload them with the app.\n"
        "Only upload-certificate.pem is public. A protected second local copy is in\n"
        + str(BACKUP)
        + "\nAlso keep a secure external backup.\n",
        encoding="utf-8",
    )
    restrict_directory(BACKUP)
    existing = BACKUP / "upload-key.json"
    if (
        existing.exists()
        and json.loads(existing.read_text(encoding="utf-8")).get("certificate_sha256")
        != fingerprint
    ):
        raise RuntimeError(
            "A different upload key already exists in the backup directory"
        )
    for path in PRIVATE.iterdir():
        if path.is_file():
            shutil.copy2(path, BACKUP / path.name)
    print(
        json.dumps(
            {
                "signing_directory": str(PRIVATE),
                "backup_directory": str(BACKUP),
                "certificate_sha256": fingerprint,
                "passwords_printed": False,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
