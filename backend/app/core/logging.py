"""In-memory ring buffer for recent log records, exposed via GET /admin/logs
(backend) and GET /logs (agent service). Lets the UI show per-service logs
without mounting the Docker socket. Not a replacement for stdout/log drivers."""

import logging
from collections import deque
from datetime import UTC, datetime


class RingBufferHandler(logging.Handler):
    def __init__(self, capacity: int = 500):
        super().__init__(level=logging.INFO)
        self.records: deque[dict] = deque(maxlen=capacity)

    def emit(self, record: logging.LogRecord) -> None:
        try:
            message = record.getMessage()
        except Exception:  # noqa: BLE001
            message = str(record.msg)
        self.records.append(
            {
                "ts": datetime.fromtimestamp(record.created, UTC).isoformat(),
                "level": record.levelname,
                "levelno": record.levelno,
                "logger": record.name,
                "message": message,
            }
        )


ring_handler = RingBufferHandler()


def install_logging() -> None:
    root = logging.getLogger()
    if ring_handler not in root.handlers:
        root.addHandler(ring_handler)
    if root.level == logging.NOTSET or root.level > logging.INFO:
        root.setLevel(logging.INFO)


def recent_logs(lines: int = 200, level: str = "INFO") -> list[dict]:
    min_level = getattr(logging, level.upper(), logging.INFO)
    recs = [r for r in ring_handler.records if r["levelno"] >= min_level]
    return [{k: v for k, v in r.items() if k != "levelno"} for r in reversed(recs[-lines:])]
