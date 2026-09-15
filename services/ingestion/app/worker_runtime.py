import json
import time
from datetime import datetime, timezone
from pathlib import Path


class WorkerHeartbeat:
    def __init__(self, path: Path | None, worker: str, interval_seconds: float = 2.0):
        self.path = path
        self.worker = worker
        self.interval_seconds = interval_seconds
        self.last_write = 0.0

    def update(self, status: str, processed_count: int, force: bool = False, **details) -> None:
        if self.path is None:
            return
        now = time.monotonic()
        if not force and now - self.last_write < self.interval_seconds:
            return
        payload = {
            "schema_version": 1,
            "worker": self.worker,
            "status": status,
            "processed_count": processed_count,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            **details,
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = self.path.with_suffix(self.path.suffix + ".part")
        try:
            temporary_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
            temporary_path.replace(self.path)
        finally:
            temporary_path.unlink(missing_ok=True)
        self.last_write = now
