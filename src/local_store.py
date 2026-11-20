"""Small atomic saves in Flet's durable, app-private data directory."""

import json
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)


class MemoryStore:
    def __init__(self, payload=None):
        self.payload = payload

    def load(self):
        return json.loads(json.dumps(self.payload)) if self.payload else None

    def save(self, payload):
        self.payload = json.loads(json.dumps(payload))


class LocalStore:
    def __init__(self, directory: str | Path | None = None):
        data_path = directory or os.getenv("FLET_APP_STORAGE_DATA")
        if not data_path:
            data_path = (
                Path(os.getenv("APPDATA", str(Path.home() / ".local")))
                / "Clicker"
                / "data"
            )
        self.directory = Path(data_path)
        self.path = self.directory / "workshop-save-v2.json"
        self.backup = self.directory / "workshop-save-v2.backup.json"

    def load(self):
        for path in (self.path, self.backup):
            try:
                if path.stat().st_size > 4_000_000:
                    continue
                data = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(data, dict) and data.get("schema") == 2:
                    return data
            except FileNotFoundError:
                continue
            except (OSError, ValueError) as error:
                logger.warning("Could not read local save %s: %s", path.name, error)
        return None

    def save(self, payload):
        self.directory.mkdir(parents=True, exist_ok=True)
        text = json.dumps(
            payload, ensure_ascii=False, separators=(",", ":"), allow_nan=False
        )
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(text, encoding="utf-8")
        # A backup is replaced only with a known valid save, never a corrupt file.
        if self.path.exists():
            try:
                previous = self.path.read_text(encoding="utf-8")
                previous_data = json.loads(previous)
                # Immutable archive is kept before the first v3 collection save.
                # The normal rotating backup remains independent of this archive.
                migration_backup = (
                    self.directory / "workshop-save-before-collection-v3.json"
                )
                old_collection = previous_data.get("state", {}).get("collection", {})
                if (
                    payload.get("state", {}).get("collection", {}).get("version") == 3
                    and old_collection.get("version") != 3
                    and not migration_backup.exists()
                ):
                    with migration_backup.open("x", encoding="utf-8") as archive:
                        archive.write(previous)
                self.backup.write_text(previous, encoding="utf-8")
            except (OSError, ValueError):
                pass
        os.replace(temporary, self.path)
