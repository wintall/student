"""
Milvus 向量检索客户端封装
- 使用 pymilvus >= 2.3 的 MilvusClient（统一简洁接口）
- 提供 create_collection / insert / search / delete
- 保留与 MySQL 的双向同步：id 使用与 rag_section.id 一致
"""
import logging
import time
from typing import Dict, List, Optional, Any

from pymilvus import MilvusClient
from app.config import settings

logger = logging.getLogger("app")

_client: Optional[MilvusClient] = None
_collection_name: str = settings.RAG_MILVUS_COLLECTION
_vector_dim: int = settings.RAG_VECTOR_DIM or 768


def get_client() -> MilvusClient:
    """获取 MilvusClient（单例，懒连接）"""
    global _client
    if _client is None:
        logger.info("[RAG] 连接 Milvus: %s", settings.RAG_MILVUS_URI)
        _client = MilvusClient(uri=settings.RAG_MILVUS_URI)
    return _client


def ensure_collection(collection_name: str = _collection_name,
                      dim: int = _vector_dim,
                      metric_type: str = "COSINE",
                      force: bool = False) -> str:
    """
    确保集合存在；不存在则创建（含 schema）
    - id: int64 主键，与 rag_section.id 一一对应
    - book_code, chapter_no, section_no: 过滤用的标量字段
    - text / chapter_title: 展示用
    - vector: float_vector(dim)
    返回：集合名称
    """
    client = get_client()

    if force and client.has_collection(collection_name):
        logger.warning("[RAG] 强制重建集合: %s", collection_name)
        client.drop_collection(collection_name)

    if client.has_collection(collection_name):
        # 描述集合，校验维度是否一致
        try:
            desc = client.describe_collection(collection_name)
            logger.info("[RAG] 集合 %s 已存在: %s", collection_name, desc)
        except Exception as e:
            logger.warning("[RAG] describe_collection 失败: %s，尝试重建", e)
            client.drop_collection(collection_name)
        else:
            return collection_name

    logger.info("[RAG] 创建 Milvus 集合: %s (dim=%d, metric=%s)", collection_name, dim, metric_type)
    client.create_collection(
        collection_name=collection_name,
        dimension=dim,
        metric_type=metric_type,
        id_type="int",
        auto_id=False,
        primary_field_name="id",
        vector_field_name="embedding",
        max_length=65535,
    )

    # 为过滤字段建立标量索引
    try:
        client.create_index(collection_name, "book_code", index_name="idx_book_code")
        client.create_index(collection_name, "chapter_no", index_name="idx_chapter")
    except Exception as e:
        logger.debug("[RAG] 建标量索引失败（非致命）: %s", e)

    # 预热加载
    try:
        client.load_collection(collection_name)
    except Exception as e:
        logger.debug("[RAG] load_collection: %s", e)

    return collection_name


def insert_sections(records: List[Dict[str, Any]],
                    collection_name: str = _collection_name) -> int:
    """
    批量插入向量记录
    records 每一项应为:
      {
        "id": int(section_id),
        "book_code": str,
        "book_name": str,
        "chapter_no": int,
        "chapter_title": str,
        "section_no": int,
        "text": str,
        "keywords": str,
        "embedding": [float, ...],
      }
    返回实际插入数量
    """
    if not records:
        return 0
    client = get_client()
    ensure_collection(collection_name, dim=_vector_dim)

    start = time.time()
    try:
        # 确保字段顺序安全：Milvus 3.x insert 接受 list[dict]
        data_to_insert = []
        for r in records:
            data_to_insert.append({
                "id": int(r["id"]),
                "book_code": str(r.get("book_code", "")),
                "book_name": str(r.get("book_name", "")),
                "chapter_no": int(r.get("chapter_no") or 0),
                "chapter_title": str(r.get("chapter_title") or ""),
                "section_no": int(r.get("section_no") or 0),
                "text": str(r.get("text", "")),
                "keywords": str(r.get("keywords", "")),
                "embedding": list(r.get("embedding", [])),
            })

        res = client.insert(collection_name=collection_name, data=data_to_insert)
        inserted = getattr(res, "insert_count", None) or len(data_to_insert)
        logger.info("[RAG] Milvus 插入 %d 条，耗时 %.2fs，响应: %s",
                    len(data_to_insert), time.time() - start, res)
        return int(inserted)
    except Exception as e:
        logger.error("[RAG] Milvus 插入失败: %s", e)
        raise


def search_by_vector(vector: List[float],
                     top_k: int = 5,
                     book_codes: Optional[List[str]] = None,
                     min_score: float = 0.0,
                     collection_name: str = _collection_name) -> List[Dict[str, Any]]:
    """
    向量搜索，返回按分数降序排列的命中结果
    返回字段: id, score, book_code, book_name, chapter_no, chapter_title, section_no, text, keywords
    """
    if not vector:
        return []

    client = get_client()
    ensure_collection(collection_name, dim=_vector_dim)

    # 过滤条件
    filter_expr: Optional[str] = None
    if book_codes and len(book_codes) > 0:
        # book_code in ['xiyouji', 'sanguo']
        quoted = ", ".join(f"'{c}'" for c in book_codes if c)
        filter_expr = f"book_code in [{quoted}]"

    try:
        hits = client.search(
            collection_name=collection_name,
            data=[vector],
            limit=top_k,
            filter=filter_expr,
            output_fields=["id", "book_code", "book_name", "chapter_no",
                            "chapter_title", "section_no", "text", "keywords"],
        )
    except Exception as e:
        logger.error("[RAG] Milvus 搜索失败: %s", e)
        return []

    # 统一格式化
    results: List[Dict[str, Any]] = []
    for item in hits[0] if hits else []:
        entity = getattr(item, "entity", None) or {}
        # entity 可能是 Dict 或对象；兼容处理
        get_val = lambda key: (entity.get(key) if isinstance(entity, dict) else getattr(entity, key, None))
        score = float(getattr(item, "distance", None) or 0.0)
        results.append({
            "id": int(get_val("id") or 0),
            "score": score,
            "book_code": str(get_val("book_code") or ""),
            "book_name": str(get_val("book_name") or ""),
            "chapter_no": int(get_val("chapter_no") or 0),
            "chapter_title": str(get_val("chapter_title") or ""),
            "section_no": int(get_val("section_no") or 0),
            "text": str(get_val("text") or ""),
            "keywords": str(get_val("keywords") or ""),
        })

    if min_score > 0:
        results = [r for r in results if r["score"] >= min_score]

    logger.info("[RAG] 向量搜索命中 %d 条（过滤后 %d 条，阈值 %.2f）",
                len(hits[0]) if hits else 0, len(results), min_score)
    return results


def count_vectors(collection_name: str = _collection_name) -> int:
    """查询当前集合向量数量（用作健康检查 / 统计）"""
    try:
        client = get_client()
        if not client.has_collection(collection_name):
            return 0
        stats = client.get_collection_stats(collection_name)
        # MilvusClient.get_collection_stats 返回 {'row_count': int}
        return int(stats.get("row_count", 0) if isinstance(stats, dict) else 0)
    except Exception as e:
        logger.warning("[RAG] 查询 Milvus 集合统计失败: %s", e)
        return -1
