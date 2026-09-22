from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AssetMetadata(BaseModel):
    """AI-generated metadata. Doubles as the response schema handed to Gemini,
    so the model returns exactly these fields and no parsing guesswork is needed."""

    description: str = Field(description="One or two factual sentences describing the asset.")
    tags: list[str] = Field(description="5-12 short lowercase keywords.")


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


class SearchHit(AssetOut):
    """An asset plus how well it matched the query."""

    score: float
