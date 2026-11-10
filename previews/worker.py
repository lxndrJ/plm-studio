"""Preview worker (M4): polls the preview_jobs table and generates derivatives
(thumbnails for raster images, PNG export for AI/EPS via Inkscape/Ghostscript).
Originals are never modified; derivatives get is_original=false and point back
via preview_file_id."""

import json
import logging
import os
import sys
import threading
import time
from pathlib import Path
from urllib.parse import parse_qs, urlparse

_here = Path(__file__).resolve().parent
for _cand in (_here / "backend", _here.parent / "backend"):
    if (_cand / "app").is_dir():
        sys.path.insert(0, str(_cand))
        break

from app.core.db import SessionLocal  # noqa: E402
from app.core.logging import install_logging, recent_logs  # noqa: E402
from app.services.preview_service import process_next_job  # noqa: E402

POLL_SECONDS = float(os.environ.get("PREVIEW_POLL_SECONDS", "2"))
LOGS_PORT = int(os.environ.get("PREVIEW_LOGS_PORT", "8002"))

log = logging.getLogger("previews")


def serve_logs(port: int) -> None:
    """Tiny read-only HTTP endpoint for the UI log page: GET /health, GET /logs."""
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    class Handler(BaseHTTPRequestHandler):
        def _json(self, code: int, payload: dict) -> None:
            body = json.dumps(payload).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            if parsed.path == "/health":
                self._json(200, {"status": "ok"})
            elif parsed.path == "/logs":
                q = parse_qs(parsed.query)
                lines = int(q.get("lines", ["200"])[0])
                level = q.get("level", ["INFO"])[0]
                self._json(
                    200,
                    {
                        "service": "previews",
                        "level": level,
                        "logs": recent_logs(lines, level),
                    },
                )
            else:
                self._json(404, {"detail": "not found"})

        def log_message(self, *args) -> None:
            pass

    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()


def main() -> None:
    install_logging()
    threading.Thread(target=serve_logs, args=(LOGS_PORT,), daemon=True).start()
    log.info("preview worker started (polling preview_jobs, logs on :%d)", LOGS_PORT)
    while True:
        db = SessionLocal()
        try:
            job = process_next_job(db)
            if job is not None:
                log.info("job %s: %s (file %s)", job.id, job.status, job.doc_file_id)
        except Exception as exc:
            log.error("worker error: %s", exc)
            db.rollback()
        finally:
            db.close()
        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()
