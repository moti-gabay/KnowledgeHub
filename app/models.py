from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def _utcnow() -> datetime:
    """Naive UTC: SQLite has no tz type, so storing naive keeps the value written
    and the value read back identical."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Asset(Base):
    """One uploaded file. Source of truth; the vector index is derived from this."""

    __tablename__ = "assets"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    kind: Mapped[str] = mapped_column(String(16), index=True)  # "text" | "image"
    original_name: Mapped[str] = mapped_column(String(255))
    stored_name: Mapped[str] = mapped_column(String(64), unique=True)
    mime_type: Mapped[str] = mapped_column(String(128))
    size_bytes: Mapped[int] = mapped_column(Integer)

    # AI-generated metadata (filled in Phase 2)
    description: Mapped[str] = mapped_column(Text, default="")
    tags: Mapped[list] = mapped_column(JSON, default=list)
    metadata_ok: Mapped[bool] = mapped_column(Boolean, default=False)

    # Full text for text assets; None for images.
    text_content: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    @property
    def url(self) -> str:
        return f"/files/{self.stored_name}"
