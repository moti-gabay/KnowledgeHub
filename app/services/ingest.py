"""Turning bytes into a searchable asset.

Lives outside the router because two callers need it: the upload endpoint and
the startup seeder.
"""

import logging

from sqlalchemy.orm import Session

from app.models import Asset
from app.services import ai, storage, vectorstore

logger = logging.getLogger(__name__)


class UnsupportedFile(ValueError):
    pass


def ingest(db: Session, filename: str, raw: bytes, content_type: str | None) -> Asset:
    kind = storage.detect_kind(filename)
    if kind is None:
        raise UnsupportedFile(filename)

    asset_id = storage.new_asset_id()
    stored_name = storage.stored_name_for(asset_id, filename)
    storage.save_bytes(stored_name, raw)
    mime_type = storage.guess_mime(filename, content_type)
    text_content = storage.decode_text(raw) if kind == "text" else None

    # The asset is already on disk. A failing AI service must not lose it, so the
    # upload still succeeds and the record is flagged for a later re-index.
    try:
        metadata = (
            ai.describe_image(raw, mime_type)
            if kind == "image"
            else ai.describe_text(text_content or "")
        )
        description, tags, metadata_ok = metadata.description, metadata.tags, True
    except Exception:
        logger.exception("Metadata generation failed for %s", filename)
        description, tags, metadata_ok = "", [], False

    asset = Asset(
        id=asset_id,
        kind=kind,
        original_name=filename,
        stored_name=stored_name,
        mime_type=mime_type,
        size_bytes=len(raw),
        description=description,
        tags=tags,
        metadata_ok=metadata_ok,
        text_content=text_content,
    )
    db.add(asset)
    db.commit()

    # SQLite first, then the derived index: a failure here costs searchability,
    # not the asset.
    if metadata_ok:
        try:
            embed_text = ai.build_embed_text(description, tags, text_content)
            vectorstore.index(asset_id, ai.embed(embed_text, "RETRIEVAL_DOCUMENT"), embed_text, kind)
        except Exception:
            logger.exception("Indexing failed for %s", asset_id)
            asset.metadata_ok = False
            db.commit()

    return asset
