"""Preview worker (M4): polls the preview_jobs table and generates derivatives
(thumbnails for raster images, PNG export for AI/EPS via Inkscape/Ghostscript).
Originals are never modified; derivatives get is_original=false and point back
via preview_file_id."""

import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.core.db import SessionLocal  # noqa: E402
from app.services.preview_service import process_next_job  # noqa: E402

POLL_SECONDS = float(os.environ.get("PREVIEW_POLL_SECONDS", "2"))


def main() -> None:
    print("preview worker started (polling preview_jobs)", flush=True)
    while True:
        db = SessionLocal()
        try:
            job = process_next_job(db)
            if job is not None:
                print(f"job {job.id}: {job.status} (file {job.doc_file_id})", flush=True)
        except Exception as exc:
            print(f"worker error: {exc}", flush=True)
            db.rollback()
        finally:
            db.close()
        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()
