import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.models import Asset
from app.schemas import AssetOut, SearchHit
from app.services import ai, vectorstore

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["search"])


@router.get("/search", response_model=list[SearchHit])
def search(
    q: str = Query(..., min_length=1, description="Natural-language query."),
    limit: int = Query(default=settings.search_limit, ge=1, le=50),
    db: Session = Depends(get_db),
) -> list[SearchHit]:
    """Semantic search over AI-generated descriptions. Images and text files share
    one text embedding space, so a query matches both kinds of asset."""
    try:
        query_vector = ai.embed(q, "RETRIEVAL_QUERY")
    except Exception:
        logger.exception("Query embedding failed for %r", q)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Search is unavailable because the AI service could not be reached.",
        )

    hits = vectorstore.search(query_vector, limit)
    if not hits:
        return []

    assets = {a.id: a for a in db.query(Asset).filter(Asset.id.in_([h[0] for h in hits]))}
    results = []
    for asset_id, score in hits:
        asset = assets.get(asset_id)
        if asset is None or score < settings.min_similarity:
            continue
        results.append(SearchHit(**AssetOut.model_validate(asset).model_dump(), score=round(score, 4)))
    return results
