"""Gemini calls: turn an asset into searchable metadata, and text into a vector.

Both images and text are reduced to a natural-language description before they
are embedded, so a single text embedding space covers both kinds of asset.
"""

import logging

from google import genai
from google.genai import types

from app.config import settings
from app.schemas import AssetMetadata

logger = logging.getLogger(__name__)

# Text sent to the LLM is capped so a huge upload cannot blow up a request.
MAX_PROMPT_CHARS = 8_000

_PROMPT = (
    "You are indexing an asset for a semantic search engine.\n"
    "Write one or two factual sentences describing what it contains. Name concrete, "
    "searchable attributes: objects, people and their visible attributes such as hair "
    "colour and clothing, any document or text visible, the setting, and the topics covered.\n"
    "Then list 5-12 short lowercase tags covering those same attributes.\n"
    "Describe only what is actually present. Do not speculate."
)

_client: genai.Client | None = None


def client() -> genai.Client:
    """Lazy singleton so importing this module never requires a key."""
    global _client
    if _client is None:
        if not settings.gemini_api_key:
            raise RuntimeError("GEMINI_API_KEY is not set.")
        _client = genai.Client(api_key=settings.gemini_api_key)
    return _client


def _generate(parts: list) -> AssetMetadata:
    response = client().models.generate_content(
        model=settings.gemini_chat_model,
        contents=parts,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=AssetMetadata,
            temperature=0.2,
        ),
    )
    metadata = response.parsed
    if not isinstance(metadata, AssetMetadata):
        raise ValueError(f"Unexpected Gemini response: {response.text!r}")
    metadata.tags = [t.strip().lower() for t in metadata.tags if t.strip()]
    return metadata


def describe_image(raw: bytes, mime_type: str) -> AssetMetadata:
    return _generate([types.Part.from_bytes(data=raw, mime_type=mime_type), _PROMPT])


def describe_text(content: str) -> AssetMetadata:
    excerpt = content[:MAX_PROMPT_CHARS]
    return _generate([f"{_PROMPT}\n\n--- FILE CONTENTS ---\n{excerpt}"])
