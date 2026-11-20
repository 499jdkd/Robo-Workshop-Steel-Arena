"""Plan, then explicitly publish a new APK release and verify its public bytes.

The default mode is read-only. --publish creates a *new* draft, uploads the
APK and its checksum, verifies GitHub's metadata, publishes that draft and
downloads the public APK without credentials to verify its SHA-256.

Credentials come from Git Credential Manager in memory. They are never
printed or saved. Existing releases and Git tags are never overwritten.

REST contracts:
https://docs.github.com/en/rest/releases/releases#create-a-release
https://docs.github.com/en/rest/releases/assets#upload-a-release-asset
https://docs.github.com/en/rest/git/refs#get-a-reference
"""

import argparse
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from urllib.parse import quote, urlparse
import zipfile

import requests


API = "https://api.github.com"
API_VERSION = "2026-03-10"
CHUNK = 1024 * 1024


class ReleaseError(RuntimeError):
    """An error message that is safe to print without credentials."""


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(CHUNK), b""):
            digest.update(chunk)
    return digest.hexdigest()


def credential_token():
    env = dict(os.environ, GIT_TERMINAL_PROMPT="0", GCM_INTERACTIVE="Never")
    try:
        result = subprocess.run(
            ["git", "credential", "fill"],
            input="protocol=https\nhost=github.com\n\n",
            text=True,
            capture_output=True,
            env=env,
            timeout=20,
        )
    except (OSError, subprocess.TimeoutExpired):
        raise ReleaseError("Git Credential Manager was unavailable; no release created") from None
    values = dict(line.split("=", 1) for line in result.stdout.splitlines() if "=" in line)
    if result.returncode or not values.get("password"):
        raise ReleaseError("No GitHub credential was available; no release created")
    return values["password"]


class GitHub:
    def __init__(self, repo, token=None):
        self.repo = repo
        self.session = requests.Session()
        self.session.headers.update(
            {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": API_VERSION,
             "User-Agent": "Robo-Workshop-Volt-Release"}
        )
        if token:
            self.session.headers["Authorization"] = "Bearer " + token

    def request(self, method, path, *, expected=(200,), **kwargs):
        address = path if path.startswith("https://") else API + f"/repos/{self.repo}" + path
        if urlparse(address).hostname not in {"api.github.com", "uploads.github.com"}:
            raise ReleaseError("Refused an unexpected authenticated API host")
        try:
            response = self.session.request(
                method, address, timeout=kwargs.pop("timeout", (20, 60)),
                allow_redirects=False, **kwargs
            )
        except requests.RequestException as error:
            raise ReleaseError(f"GitHub {method} transport failed ({type(error).__name__}); inspect the saved release report before retrying") from None
        if response.status_code not in expected:
            request_id = response.headers.get("X-GitHub-Request-Id", "unknown")
            raise ReleaseError(f"GitHub {method} failed with HTTP {response.status_code} (request {request_id})")
        return response

    def optional(self, path):
        response = self.request("GET", path, expected=(200, 404))
        return None if response.status_code == 404 else response.json()

    def resolved_tag(self, tag):
        ref = self.optional("/git/ref/tags/" + quote(tag, safe=""))
        if ref is None:
            return None
        obj = ref["object"]
        for _ in range(6):
            if obj["type"] == "commit":
                return obj["sha"]
            if obj["type"] != "tag":
                break
            obj = self.request("GET", "/git/tags/" + obj["sha"]).json()["object"]
        raise ReleaseError("Existing tag does not resolve to a commit")

    def release_with_tag(self, tag):
        # Authenticated listing includes drafts, which the tag lookup alone
        # does not reliably expose. Never reuse even an unpublished release.
        for page in range(1, 101):
            releases = self.request("GET", "/releases", params={"per_page": 100, "page": page}).json()
            for release in releases:
                if release.get("tag_name") == tag:
                    return release
            if len(releases) < 100:
                return None
        raise ReleaseError("Release inventory exceeded the preflight limit")


def check_asset(asset, *, name, size, digest):
    if asset.get("name") != name or asset.get("size") != size or asset.get("state") != "uploaded":
        raise ReleaseError("Uploaded asset name, size or state did not match")
    remote_digest = asset.get("digest")
    if remote_digest is not None and remote_digest != "sha256:" + digest:
        raise ReleaseError("GitHub's asset SHA-256 did not match the local file")
    return {"id": asset["id"], "name": name, "bytes": size, "sha256": digest,
            "github_digest": remote_digest, "download_url": asset["browser_download_url"]}


def verify_public_download(address, *, expected_size, expected_sha256, attempts=5):
    if urlparse(address).hostname != "github.com":
        raise ReleaseError("Unexpected public download host")
    last_failure = "public asset unavailable"
    # This fresh session deliberately has no Authorization header or API token.
    with requests.Session() as public:
        public.trust_env = False  # Also exclude implicit .netrc credentials.
        for attempt in range(attempts):
            try:
                with public.get(address, stream=True, timeout=(20, 90),
                                headers={"Cache-Control": "no-cache", "User-Agent": "Robo-Workshop-Download-Verification"}) as response:
                    if response.status_code != 200:
                        last_failure = f"HTTP {response.status_code}"
                    else:
                        size, digest = 0, hashlib.sha256()
                        for chunk in response.iter_content(CHUNK):
                            size += len(chunk)
                            if size > expected_size:
                                raise ReleaseError("Public download exceeded the expected APK size")
                            digest.update(chunk)
                        if size == expected_size and digest.hexdigest() == expected_sha256:
                            return {"http_status": 200, "bytes": size, "sha256": digest.hexdigest(),
                                    "unauthenticated": True, "verified_at": datetime.now(timezone.utc).isoformat()}
                        last_failure = "public bytes did not match the APK"
            except requests.RequestException as error:
                last_failure = type(error).__name__
            if attempt + 1 < attempts:
                time.sleep(min(2 ** attempt, 8))
    raise ReleaseError("Public download verification failed: " + last_failure)


def local_inputs(apk, notes_file):
    apk = Path(apk).resolve(strict=True)
    notes_file = Path(notes_file).resolve(strict=True)
    if apk.suffix.lower() != ".apk" or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*\.apk", apk.name):
        raise ReleaseError("APK needs a simple .apk asset name")
    try:
        with zipfile.ZipFile(apk) as archive:
            if "AndroidManifest.xml" not in archive.namelist() or "assets/app.zip" not in archive.namelist():
                raise ReleaseError("File is not the main Flet game APK")
    except zipfile.BadZipFile:
        raise ReleaseError("APK is not a valid ZIP archive") from None
    notes = notes_file.read_text(encoding="utf-8").strip()
    if not notes or len(notes) > 100_000:
        raise ReleaseError("Release notes must contain 1 to 100000 characters")
    return apk, notes, apk.stat().st_size, sha256_file(apk)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default="499jdkd/Robo-Workshop-Steel-Arena")
    parser.add_argument("--tag", required=True)
    parser.add_argument("--target-sha", required=True)
    parser.add_argument("--apk", type=Path, required=True)
    parser.add_argument("--notes-file", type=Path, required=True)
    parser.add_argument("--title", default=None)
    parser.add_argument("--report", type=Path, default=None)
    parser.add_argument("--publish", action="store_true")
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", args.repo):
        parser.error("--repo must be owner/name")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", args.tag) or ".." in args.tag:
        parser.error("--tag must be a simple, new Git tag")
    if not re.fullmatch(r"[0-9a-fA-F]{40}", args.target_sha):
        parser.error("--target-sha must be a full 40-character commit SHA")
    apk, notes, size, digest = local_inputs(args.apk, args.notes_file)
    target_sha = args.target_sha.lower()
    report_file = (args.report or apk.parent / f"github-release-{args.tag}.json").resolve()
    report = {"repo": args.repo, "tag": args.tag, "target_sha": target_sha,
              "apk": str(apk), "bytes": size, "sha256": digest,
              "mode": "publish" if args.publish else "read-only-plan", "stage": "preflight"}

    def save():
        report_file.parent.mkdir(parents=True, exist_ok=True)
        report_file.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    try:
        api = GitHub(args.repo, credential_token() if args.publish else None)
        metadata = api.request("GET", "").json()
        if metadata.get("private"):
            raise ReleaseError("Public APK verification requires a public repository")
        if args.publish and not metadata.get("permissions", {}).get("push"):
            raise ReleaseError("GitHub credential does not have repository push access")
        commit = api.request("GET", "/commits/" + target_sha).json()
        if commit.get("sha") != target_sha:
            raise ReleaseError("Target commit did not resolve to the exact requested SHA")
        if api.release_with_tag(args.tag) is not None:
            raise ReleaseError("Release tag already has a release; existing releases are never overwritten")
        existing_tag = api.resolved_tag(args.tag)
        if existing_tag is not None and existing_tag != target_sha:
            raise ReleaseError("Existing tag targets another commit; tags are never moved")
        report["tag_already_exists_at_target"] = existing_tag is not None
        report["title"] = args.title or f"Robo Workshop — Volt ({args.tag})"
        report["stage"] = "plan-verified"
        save()
        if not args.publish:
            print(json.dumps(report, ensure_ascii=False, indent=2))
            return

        release = api.request("POST", "/releases", expected=(201,), json={
            "tag_name": args.tag, "target_commitish": target_sha, "name": report["title"],
            "body": notes, "draft": True, "prerelease": False, "make_latest": "false",
        }).json()
        if not release.get("draft") or release.get("tag_name") != args.tag:
            raise ReleaseError("GitHub did not return the requested new draft")
        report.update(release_id=release["id"], release_url=release["html_url"], stage="draft-created")
        save()
        upload_url = release["upload_url"].split("{", 1)[0]
        with apk.open("rb") as stream:
            uploaded = api.request("POST", upload_url, expected=(201,),
                params={"name": apk.name}, data=stream, timeout=(20, 600),
                headers={"Content-Type": "application/vnd.android.package-archive", "Content-Length": str(size)}).json()
        asset = api.request("GET", "/releases/assets/" + str(uploaded["id"])).json()
        report["asset"] = check_asset(asset, name=apk.name, size=size, digest=digest)
        report["stage"] = "apk-verified-on-draft"
        save()
        checksum = f"{digest}  {apk.name}\n".encode("ascii")
        with io.BytesIO(checksum) as stream:
            uploaded_sum = api.request("POST", upload_url, expected=(201,),
                params={"name": apk.name + ".sha256"}, data=stream,
                headers={"Content-Type": "text/plain", "Content-Length": str(len(checksum))}).json()
        report["checksum_asset"] = check_asset(uploaded_sum, name=apk.name + ".sha256",
            size=len(checksum), digest=hashlib.sha256(checksum).hexdigest())
        # A concurrent tag change must not cause a release of different source.
        final_tag = api.resolved_tag(args.tag)
        if final_tag is not None and final_tag != target_sha:
            raise ReleaseError("Tag changed while uploading; draft retained without publishing")
        published = api.request("PATCH", "/releases/" + str(release["id"]),
            json={"draft": False, "make_latest": "true"}).json()
        if published.get("draft") or published.get("tag_name") != args.tag:
            raise ReleaseError("GitHub did not publish the requested release")
        if api.resolved_tag(args.tag) != target_sha:
            raise ReleaseError("Published tag does not match the requested source commit")
        report.update(stage="published", release_url=published["html_url"], published_at=published["published_at"])
        save()
        report["public_download"] = verify_public_download(
            report["asset"]["download_url"], expected_size=size, expected_sha256=digest)
        report["stage"] = "published-and-download-verified"
        save()
        print(json.dumps(report, ensure_ascii=False, indent=2))
    except Exception as error:
        # Print only our deliberately safe errors; HTTP libraries may include
        # signed redirect URLs or transport details in their exception strings.
        safe_error = str(error) if isinstance(error, ReleaseError) else type(error).__name__
        report["error"] = safe_error
        save()
        raise ReleaseError(f"{safe_error}. Safe report: {report_file}; no existing release or tag was overwritten") from None


if __name__ == "__main__":
    try:
        main()
    except (ReleaseError, OSError) as error:
        print(f"Release operation stopped: {error}", file=sys.stderr)
        raise SystemExit(1)
