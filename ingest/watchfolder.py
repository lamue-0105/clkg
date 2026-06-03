"""File-system watcher that auto-ingests new files dropped under inbox/{region}/.

Run as: python -m ingest.watchfolder

It watches ~/clkg/inbox/{region}/ for new files and routes them to the right
pipeline based on filename pattern. v1 only routes Mustang CSVs.
"""
from __future__ import annotations

import logging
import time
import uuid
from pathlib import Path

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from .pipelines import mustang as mustang_pipeline

log = logging.getLogger(__name__)

INBOX = Path.home() / "clkg" / "inbox"


class _Handler(FileSystemEventHandler):
    def __init__(self, region: str):
        self.region = region

    def on_created(self, event):
        if event.is_directory:
            return
        path = Path(event.src_path)
        if path.suffix.lower() not in (".csv", ".xlsx"):
            return
        # Wait briefly to ensure the file is fully written.
        time.sleep(2)
        bid = uuid.uuid5(uuid.NAMESPACE_URL, f"watchfolder:{path}:{path.stat().st_mtime}")
        log.info("[watchfolder] %s detected, batch_id=%s", path.name, bid)
        try:
            if self.region == "mustang":
                mustang_pipeline.run(csv_path=path, batch_id=bid)
            else:
                log.warning("no pipeline registered for region %s", self.region)
        except Exception:
            log.exception("[watchfolder] ingest failed for %s", path)


def main() -> int:
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    INBOX.mkdir(parents=True, exist_ok=True)

    observer = Observer()
    for region_dir in INBOX.iterdir() if INBOX.exists() else []:
        if region_dir.is_dir():
            observer.schedule(_Handler(region_dir.name), str(region_dir), recursive=False)
            log.info("[watchfolder] watching %s", region_dir)

    # If no subdirs exist yet, create mustang/ as a default.
    mustang_inbox = INBOX / "mustang"
    if not mustang_inbox.exists():
        mustang_inbox.mkdir(parents=True)
        observer.schedule(_Handler("mustang"), str(mustang_inbox), recursive=False)
        log.info("[watchfolder] created and watching %s", mustang_inbox)

    observer.start()
    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
