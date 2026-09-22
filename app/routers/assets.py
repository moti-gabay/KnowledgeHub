import logging

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.models import Asset
from app.schemas import AssetOut
from app.services import ai, storage

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["assets"])


@router.post("/upload", response_model=AssetOut, status_code=status.HTTP_201_CREATED)
def upload(file: UploadFile = File(...), db: Session = Depends(get_db)) -> Asset:
    """Sync endpoint on purpose: FastAPI runs it in a threadpool, so the blocking
    file write and SQLite calls never touch the event loop."""
    kind = storage.detect_kind(file.filename or "")
    if kind is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported file type. Allowed: .txt, .md, .png, .jpg, .jpeg, .webp, .gif",
        )

    raw = file.file.read()
    if len(raw) > settings.max_upload_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds {settings.max_upload_bytes // (1024 * 1024)} MB limit.",
        )
    if not raw:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty file.")

    asset_id = storage.new_asset_id()
    stored_name = storage.stored_name_for(asset_id, file.filename or "")
    storage.save_bytes(stored_name, raw)
    mime_type = storage.guess_mime(file.filename or "", file.content_type)
    text_content = storage.decode_text(raw) if kind == "text" else None

    # The asset is already on disk. A failing AI service must not lose it, so the
    # upload still succeeds and the record is flagged for a later re-index.
    try:
        if kind == "image":
            metadata = ai.describe_image(raw, mime_type)
        else:
            metadata = ai.describe_text(text_content or "")
        description, tags, metadata_ok = metadata.description, metadata.tags, True
    except Exception:
        logger.exception("Metadata generation failed for %s", file.filename)
        description, tags, metadata_ok = "", [], False

    asset = Asset(
        id=asset_id,
        kind=kind,
        original_name=file.filename or stored_name,
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
    return asset


@router.get("/assets", response_model=list[AssetOut])
def list_assets(db: Session = Depends(get_db)) -> list[Asset]:
    return list(db.scalars(select(Asset).order_by(Asset.created_at.desc())))


@router.get("/assets/{asset_id}", response_model=AssetOut)
def get_asset(asset_id: str, db: Session = Depends(get_db)) -> Asset:
    asset = db.get(Asset, asset_id)
    if asset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found.")
    return asset
