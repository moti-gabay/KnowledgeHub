from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AssetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    kind: str
    original_name: str
    url: str
    mime_type: str
    size_bytes: int
    description: str
    tags: list[str]
    metadata_ok: bool
    text_content: str | None = None
    created_at: datetime
