"""Storage failures and free-hosting liveness must not wake or leak the DB."""

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]
import server.app as endpoint
from server.database import StorageUnavailable


class ServerStorageTests(unittest.IsolatedAsyncioTestCase):
    async def test_liveness_does_not_initialize_or_query_neon(self):
        untouched = Mock()
        with (
            patch.dict(
                os.environ,
                {"CLICKER_ARENA_DATABASE_URL": "postgresql://private.invalid/arena"},
            ),
            patch.object(endpoint, "service", untouched),
        ):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=endpoint.app),
                base_url="http://arena.test",
            ) as client:
                result = await client.get("/health")
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json()["storage"], "postgresql")
        self.assertFalse(result.json()["database_checked"])
        self.assertFalse(untouched.mock_calls)

    async def test_render_missing_secret_cannot_silently_use_ephemeral_sqlite(self):
        with patch.dict(
            os.environ, {"RENDER": "true", "CLICKER_ARENA_DATABASE_URL": ""}
        ):
            with self.assertRaises(StorageUnavailable):
                endpoint.storage_target()

    async def test_storage_failure_is_retryable_and_does_not_expose_credentials(self):
        service = Mock()
        service.ready.side_effect = StorageUnavailable(
            "postgresql://secret:password@private.invalid/db"
        )
        with patch.object(endpoint, "service", service):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=endpoint.app),
                base_url="http://arena.test",
            ) as client:
                result = await client.get("/ready")
        self.assertEqual(result.status_code, 503)
        self.assertEqual(result.headers["Retry-After"], "15")
        self.assertNotIn("password", result.text)
        self.assertNotIn("private.invalid", result.text)
