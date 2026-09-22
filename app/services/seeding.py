"""Populate an empty knowledge base from seed/.

Render's free tier has no persistent disk, so every deploy and every wake from
idle starts with nothing. Without this the demo link opens on an empty page.
Runs in a background thread so it never delays the health check.
"""

import logging
from pathlib import Path

from app.db import SessionLocal
from app.models import Asset
from app.services.ingest import ingest
from app.services.storage import detect_kind

logger = logging.getLogger(__name__)

SEED_DIR = Path("seed")


def seed_if_empty() -> None:
    db = SessionLocal()
    try:
        if db.query(Asset).count() > 0:
            return
        if not SEED_DIR.is_dir():
            return

        files = sorted(p for p in SEED_DIR.iterdir() if p.is_file() and detect_kind(p.name))
        logger.info("Empty knowledge base: seeding %d file(s) from %s", len(files), SEED_DIR)
        for path in files:
            try:
                ingest(db, path.name, path.read_bytes(), None)
            except Exception:
                logger.exception("Seeding failed for %s", path.name)
        logger.info("Seeding complete: %d asset(s)", db.query(Asset).count())
    finally:
        db.close()
