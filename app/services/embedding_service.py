"""
文本向量生成服务 - 默认使用本地中文模型 moka-ai/m3e-base
- 768 维输出，专为中文语料训练
- lazy-load：首次调用才加载模型，避免无意义内存占用
- 网络 fallback：优先 HuggingFace，失败则切换到 ModelScope（国内）
"""
import logging
import time
from typing import List, Optional

import numpy as np

from app.config import settings

logger = logging.getLogger("app")

_model = None
_model_name: Optional[str] = None
_model_ready: bool = False


def _load_model():
    """懒加载 embedding 模型；多进程下每个进程独立一份"""
    global _model, _model_name, _model_ready
    if _model_ready and _model is not None:
        return

    target = settings.RAG_EMBEDDING_MODEL or "moka-ai/m3e-base"
    logger.info("[RAG] 开始加载 embedding 模型：%s", target)
    start = time.time()

    # 先尝试 sentence-transformers（HuggingFace 源）
    try:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer(target)
        _model_name = target
        _model_ready = True
        logger.info("[RAG] 模型 %s 加载完毕，耗时 %.1fs", target, time.time() - start)
        return
    except Exception as e:
        logger.warning("[RAG] HuggingFace 源加载失败: %s，尝试 ModelScope", e)

    # fallback：ModelScope（国内不需要梯子）
    try:
        from modelscope.pipelines import pipeline
        from modelscope.utils.constant import Tasks
        _model = pipeline(task=Tasks.sentence_embedding, model=target)
        _model_name = f"modelscope://{target}"
        _model_ready = True
        logger.info("[RAG] 模型 %s 已从 ModelScope 加载，耗时 %.1fs", target, time.time() - start)
        return
    except Exception as e2:
        logger.error("[RAG] Embedding 模型加载失败，无法启用向量检索: %s", e2)
        _model = None
        _model_ready = False


def is_ready() -> bool:
    """模型是否已加载并就绪"""
    return _model_ready and _model is not None


def ensure_ready():
    """确保模型已加载（供外部显式调用）"""
    if not _model_ready:
        _load_model()


def get_vector_dim() -> int:
    return settings.RAG_VECTOR_DIM or 768


def encode(text: str) -> Optional[List[float]]:
    """生成单段文本的 embedding（list[float]）"""
    if not text or not text.strip():
        return None
    return encode_batch([text])[0]


def encode_batch(texts: List[str]) -> List[List[float]]:
    """批量生成 embedding"""
    if not texts:
        return []

    # 统一懒加载
    if not _model_ready:
        _load_model()
    if _model is None:
        raise RuntimeError(
            "Embedding 模型未加载，可能网络不可用或缺少 sentence-transformers / modelscope 依赖"
        )

    start = time.time()
    try:
        # sentence-transformers 的输出：np.ndarray (N, D)
        if hasattr(_model, "encode"):
            vecs = _model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
            if isinstance(vecs, np.ndarray):
                result = [vec.tolist() for vec in vecs]
            else:
                # 如果是 list 或其他可迭代
                result = [list(v) for v in vecs]
        else:
            # modelscope pipeline 产出 {'text_embedding': ...}
            outs = _model(input={"source_sentence": texts})
            embeddings = outs.get("text_embedding") if isinstance(outs, dict) else outs
            if isinstance(embeddings, np.ndarray):
                result = [v.tolist() for v in embeddings]
            else:
                result = [list(v) for v in embeddings]

        logger.info("[RAG] 生成 %d 段 embedding，耗时 %.2fs", len(texts), time.time() - start)
        return result
    except Exception as e:
        logger.error("[RAG] 生成 embedding 失败: %s", e)
        raise
