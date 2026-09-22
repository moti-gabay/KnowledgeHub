from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.models import Asset
from app.schemas import AssetOut
from app.services import storage

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

    asset = Asset(
        id=asset_id,
        kind=kind,
        original_name=file.filename or stored_name,
        stored_name=stored_name,
        mime_type=storage.guess_mime(file.filename or "", file.content_type),
        size_bytes=len(raw),
        description="",
        tags=[],
        metadata_ok=False,
        text_content=storage.decode_text(raw) if kind == "text" else None,
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
