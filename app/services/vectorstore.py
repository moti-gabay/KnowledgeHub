"""Chroma index. Derived data: every vector can be rebuilt from SQLite, which
stays the source of truth."""

import chromadb

from app.config import settings

COLLECTION = "assets"

_collection = None


def collection():
    global _collection
    if _collection is None:
        client = chromadb.PersistentClient(path=str(settings.chroma_dir))
        # Vectors are supplied by us, so Chroma never downloads its default
        # embedding model.
        _collection = client.get_or_create_collection(
            name=COLLECTION,
            metadata={"hnsw:space": "cosine"},
        )
    return _collection


def index(asset_id: str, embedding: list[float], document: str, kind: str) -> None:
    collection().upsert(
        ids=[asset_id],
        embeddings=[embedding],
        documents=[document],
        metadatas=[{"kind": kind}],
    )


def search(embedding: list[float], limit: int) -> list[tuple[str, float]]:
    """Return (asset_id, similarity) best first. Chroma's cosine space returns a
    distance, and similarity is 1 - distance."""
    count = collection().count()
    if count == 0:
        return []
    result = collection().query(query_embeddings=[embedding], n_results=min(limit, count))
    ids = result["ids"][0]
    distances = result["distances"][0]
    return [(i, 1.0 - d) for i, d in zip(ids, distances)]
