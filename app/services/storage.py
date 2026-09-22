import mimetypes
from pathlib import Path
from uuid import uuid4

from app.config import settings

TEXT_EXTENSIONS = {".txt", ".md"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}


def detect_kind(filename: str) -> str | None:
    """Return "text", "image", or None when the extension is not allowed."""
    ext = Path(filename).suffix.lower()
    if ext in TEXT_EXTENSIONS:
        return "text"
    if ext in IMAGE_EXTENSIONS:
        return "image"
    return None


def new_asset_id() -> str:
    return uuid4().hex


def stored_name_for(asset_id: str, filename: str) -> str:
    return f"{asset_id}{Path(filename).suffix.lower()}"


def guess_mime(filename: str, fallback: str | None) -> str:
    return fallback or mimetypes.guess_type(filename)[0] or "application/octet-stream"


def save_bytes(stored_name: str, raw: bytes) -> Path:
    path = settings.uploads_dir / stored_name
    path.write_bytes(raw)
    return path


def decode_text(raw: bytes) -> str:
    return raw.decode("utf-8", errors="replace")
