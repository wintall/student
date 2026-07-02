import logging
from typing import Any, Dict, List, Optional

from pymilvus import MilvusClient

from app.config import settings

logger = logging.getLogger("app")

COLLECTION_NAME = settings.RAG_KNOWLEDGE_MILVUS_COLLECTION or "campus_rag_chunks_v1"
_client: Optional[MilvusClient] = None


def get_client() -> MilvusClient:
    global _client
    if _client is None:
        logger.info("[RAG-KB] connect Milvus: %s", settings.RAG_MILVUS_URI)
        _client = MilvusClient(uri=settings.RAG_MILVUS_URI)
    return _client


def ensure_collection(collection_name: str = COLLECTION_NAME, dim: Optional[int] = None) -> str:
    client = get_client()
    dim = dim or settings.RAG_VECTOR_DIM or 768
    if client.has_collection(collection_name):
        try:
            client.load_collection(collection_name)
        except Exception as exc:
            logger.debug("[RAG-KB] load collection skipped: %s", exc)
        return collection_name

    logger.info("[RAG-KB] create Milvus collection: %s dim=%s", collection_name, dim)
    client.create_collection(
        collection_name=collection_name,
        dimension=dim,
        metric_type="COSINE",
        id_type="int",
        auto_id=False,
        primary_field_name="id",
        vector_field_name="embedding",
        max_length=65535,
    )
    try:
        client.load_collection(collection_name)
    except Exception as exc:
        logger.debug("[RAG-KB] load collection skipped: %s", exc)
    return collection_name


def insert_chunks(records: List[Dict[str, Any]], collection_name: str = COLLECTION_NAME) -> int:
    if not records:
        return 0
    ensure_collection(collection_name)
    data = []
    for item in records:
        data.append(
            {
                "id": int(item["id"]),
                "kb_id": int(item["kb_id"]),
                "document_id": int(item["document_id"]),
                "owner_id": int(item["owner_id"]),
                "scope_type": str(item.get("scope_type") or ""),
                "title": str(item.get("title") or ""),
                "chunk_no": int(item.get("chunk_no") or 0),
                "content": str(item.get("content") or ""),
                "embedding": list(item.get("embedding") or []),
            }
        )
    res = get_client().insert(collection_name=collection_name, data=data)
    return int(getattr(res, "insert_count", None) or len(data))


def search_chunks(
    vector: List[float],
    top_k: int,
    kb_ids: Optional[List[int]] = None,
    min_score: float = 0.0,
    collection_name: str = COLLECTION_NAME,
) -> List[Dict[str, Any]]:
    if not vector:
        return []
    ensure_collection(collection_name)

    filter_expr = None
    if kb_ids:
        ids = ", ".join(str(int(i)) for i in kb_ids)
        filter_expr = f"kb_id in [{ids}]"

    try:
        hits = get_client().search(
            collection_name=collection_name,
            data=[vector],
            limit=top_k,
            filter=filter_expr,
            output_fields=["id", "kb_id", "document_id", "owner_id", "scope_type", "title", "chunk_no", "content"],
        )
    except Exception as exc:
        logger.error("[RAG-KB] Milvus search failed: %s", exc)
        return []

    results: List[Dict[str, Any]] = []
    for hit in hits[0] if hits else []:
        entity = getattr(hit, "entity", None) or {}

        def value(key: str):
            return entity.get(key) if isinstance(entity, dict) else getattr(entity, key, None)

        score = float(getattr(hit, "distance", None) or 0.0)
        if min_score and score < min_score:
            continue
        results.append(
            {
                "id": int(value("id") or 0),
                "score": score,
                "kb_id": int(value("kb_id") or 0),
                "document_id": int(value("document_id") or 0),
                "owner_id": int(value("owner_id") or 0),
                "scope_type": str(value("scope_type") or ""),
                "title": str(value("title") or ""),
                "chunk_no": int(value("chunk_no") or 0),
                "content": str(value("content") or ""),
            }
        )
    return results


def delete_chunks(ids: List[int], collection_name: str = COLLECTION_NAME) -> int:
    ids = [int(i) for i in ids if i]
    if not ids:
        return 0
    client = get_client()
    if not client.has_collection(collection_name):
        return 0
    try:
        client.delete(collection_name=collection_name, ids=ids)
        return len(ids)
    except Exception as exc:
        logger.warning("[RAG-KB] delete vectors failed: %s", exc)
        return 0


def health(collection_name: str = COLLECTION_NAME) -> Dict[str, Any]:
    try:
        client = get_client()
        exists = client.has_collection(collection_name)
        count = 0
        if exists:
            stats = client.get_collection_stats(collection_name)
            count = int(stats.get("row_count", 0) if isinstance(stats, dict) else 0)
        return {"milvus": "ok", "collection": collection_name, "exists": exists, "vectors": count}
    except Exception as exc:
        return {"milvus": "error", "collection": collection_name, "error": str(exc)}
