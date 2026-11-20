"""Publication guardrails run entirely offline; no releases or credentials touched."""

import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
import zipfile

from tools import publish_volt_release as release


class PublicationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.apk = self.root / "volt.apk"
        with zipfile.ZipFile(self.apk, "w") as archive:
            archive.writestr("AndroidManifest.xml", b"synthetic test manifest")
            archive.writestr("assets/app.zip", b"synthetic game code")
        self.notes = self.root / "notes.md"
        self.notes.write_text("Volt QA build. Physical Android not tested.", encoding="utf-8")
        self.report = self.root / "report.json"
        self.sha = "1" * 40
        self.argv = ["publish_volt_release.py", "--repo", "example/game", "--tag", "volt-v33",
                     "--target-sha", self.sha, "--apk", str(self.apk),
                     "--notes-file", str(self.notes), "--report", str(self.report)]
        self.api = Mock()
        self.api.release_with_tag.return_value = None
        self.api.resolved_tag.return_value = None
        self.writes = []
        self.digest = release.sha256_file(self.apk)
        self.api.request.side_effect = self.api_response

    def asset(self, name=None, data=None):
        name = name or self.apk.name
        data = self.apk.read_bytes() if data is None else data
        return {"id": 11, "name": name, "size": len(data), "state": "uploaded",
                "digest": "sha256:" + hashlib.sha256(data).hexdigest(),
                "browser_download_url": "https://github.com/example/game/releases/download/volt-v33/" + name}

    def api_response(self, method, path, **kwargs):
        if method != "GET":
            self.writes.append((method, path))
        if path == "":
            data = {"private": False, "permissions": {"push": True}}
        elif path == "/commits/" + self.sha:
            data = {"sha": self.sha}
        elif method == "POST" and path == "/releases":
            data = {"id": 1, "draft": True, "tag_name": "volt-v33",
                    "html_url": "https://github.com/example/game/releases/tag/volt-v33",
                    "upload_url": "https://uploads.github.com/repos/example/game/releases/1/assets{?name,label}"}
        elif method == "GET" and path == "/releases/assets/11":
            data = self.asset()
        elif method == "GET" and path == "/releases/1/assets":
            checksum = f"{self.digest}  {self.apk.name}\n".encode("ascii")
            data = [self.asset(), {**self.asset(self.apk.name + ".sha256", checksum), "id": 12}]
        elif method == "POST" and path.startswith("https://uploads.github.com/"):
            name = kwargs["params"]["name"]
            if name == self.apk.name:
                # The uploader passes a stream instead of materializing the APK.
                self.assertTrue(hasattr(kwargs["data"], "read"))
                self.assertEqual(kwargs["headers"]["Content-Length"], str(self.apk.stat().st_size))
                data = {"id": 11}
            else:
                checksum = f"{self.digest}  {self.apk.name}\n".encode("ascii")
                data = self.asset(name, checksum)
        elif method == "PATCH" and path == "/releases/1":
            data = {"draft": False, "tag_name": "volt-v33", "published_at": "2026-11-19T12:00:00Z",
                    "html_url": "https://github.com/example/game/releases/tag/volt-v33"}
        else:
            self.fail(f"Unexpected API request: {method} {path}")
        return Mock(json=lambda: data)

    def test_default_plan_has_no_writes_and_does_not_request_credentials(self):
        with patch.object(release, "GitHub", return_value=self.api), \
             patch.object(release, "credential_token") as credential, \
             patch("sys.argv", self.argv), patch("builtins.print"):
            release.main()
        credential.assert_not_called()
        self.assertEqual(self.writes, [])
        self.assertEqual(json.loads(self.report.read_text())["stage"], "plan-verified")

    def test_existing_draft_is_never_reused_or_overwritten(self):
        self.api.release_with_tag.return_value = {"id": 99, "draft": True}
        with patch.object(release, "GitHub", return_value=self.api), \
             patch("sys.argv", self.argv), self.assertRaisesRegex(release.ReleaseError, "already has a release"):
            release.main()
        self.assertEqual(self.writes, [])

    def test_existing_tag_at_other_commit_prevents_creation(self):
        self.api.resolved_tag.return_value = "2" * 40
        with patch.object(release, "GitHub", return_value=self.api), \
             patch("sys.argv", self.argv), self.assertRaisesRegex(release.ReleaseError, "tags are never moved"):
            release.main()
        self.assertEqual(self.writes, [])

    def test_mismatched_uploaded_digest_cannot_be_published(self):
        original = self.api_response

        def mismatch(method, path, **kwargs):
            response = original(method, path, **kwargs)
            if path == "/releases/assets/11":
                data = response.json()
                data["digest"] = "sha256:" + "0" * 64
                return Mock(json=lambda: data)
            return response

        self.api.request.side_effect = mismatch
        with patch.object(release, "GitHub", return_value=self.api), \
             patch.object(release, "credential_token", return_value="never-write-this-credential"), \
             patch("sys.argv", self.argv + ["--publish"]), \
             self.assertRaisesRegex(release.ReleaseError, "SHA-256 did not match"):
            release.main()
        self.assertFalse(any(method == "PATCH" for method, _ in self.writes))
        report = self.report.read_text()
        self.assertNotIn("never-write-this-credential", report)
        self.assertEqual(json.loads(report)["stage"], "draft-created")

    def test_publication_orders_draft_upload_verification_publish_and_public_check(self):
        self.api.resolved_tag.side_effect = [None, None, self.sha]
        with patch.object(release, "GitHub", return_value=self.api), \
             patch.object(release, "credential_token", return_value="never-write-this-credential"), \
             patch.object(release, "verify_public_download", return_value={"unauthenticated": True}) as public_check, \
             patch("sys.argv", self.argv + ["--publish"]), patch("builtins.print"):
            release.main()
        self.assertEqual([method for method, _ in self.writes], ["POST", "POST", "POST", "PATCH"])
        public_check.assert_called_once_with(self.asset()["browser_download_url"],
            expected_size=self.apk.stat().st_size, expected_sha256=self.digest)
        text = self.report.read_text()
        self.assertNotIn("never-write-this-credential", text)
        self.assertEqual(json.loads(text)["stage"], "published-and-download-verified")

    def test_public_download_requires_exact_bytes_without_authorization(self):
        payload = self.apk.read_bytes()
        response = Mock(status_code=200)
        response.iter_content.return_value = [payload[:30], payload[30:]]
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        session = Mock()
        session.get.return_value = response
        session.__enter__ = Mock(return_value=session)
        session.__exit__ = Mock(return_value=False)
        with patch.object(release.requests, "Session", return_value=session):
            verified = release.verify_public_download(self.asset()["browser_download_url"],
                expected_size=len(payload), expected_sha256=self.digest, attempts=1)
        self.assertTrue(verified["unauthenticated"])
        self.assertIs(session.trust_env, False)
        self.assertEqual(verified["sha256"], self.digest)
        self.assertNotIn("Authorization", session.get.call_args.kwargs["headers"])

    def test_published_asset_url_is_refreshed_after_untagged_draft_changes(self):
        original = self.api_response
        def draft_url(method, path, **kwargs):
            response = original(method, path, **kwargs)
            if path == "/releases/assets/11":
                data = response.json()
                data["browser_download_url"] = "https://github.com/example/game/releases/download/untagged-draft/" + self.apk.name
                return Mock(json=lambda: data)
            return response
        self.api.request.side_effect = draft_url
        self.api.resolved_tag.side_effect = [None, None, self.sha]
        with patch.object(release, "GitHub", return_value=self.api), \
             patch.object(release, "credential_token", return_value="never-write-this-credential"), \
             patch.object(release, "verify_public_download", return_value={"unauthenticated":True}) as verify, \
             patch("sys.argv", self.argv + ["--publish"]), patch("builtins.print"):
            release.main()
        self.assertEqual(verify.call_args.args[0], self.asset()["browser_download_url"])
        self.assertNotIn("untagged-", json.loads(self.report.read_text())["asset"]["download_url"])


if __name__ == "__main__":
    unittest.main()
