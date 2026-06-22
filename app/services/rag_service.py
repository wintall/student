"""RAG 检索主服务 - 基于四大名著知识库的问答
- 向量检索：用户问题 → embedding → Milvus 搜索 → 返回最相关段落
- 答案生成：检索到的段落 + 用户问题 → DeepSeek Chat 生成自然语言回答
- 降级机制：Milvus 不可用时，自动降级为 MySQL LIKE 关键词召回
"""

import json
import logging
import time
import urllib.request
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from app.config import settings
from app.models.rag import RagBook, RagSection

logger = logging.getLogger("app")


# ====== embedding 懒加载（直接用 transformers，避免 Windows symlink 问题） ======
_tokenizer = None
_model = None
_embedding_model_name = "shibing624/text2vec-base-chinese"


def _get_embedding_model():
    global _tokenizer, _model
    if _model is None:
        try:
            import torch
            from transformers import AutoTokenizer, AutoModel
        except Exception as e:
            raise RuntimeError(f"缺少 torch 或 transformers 依赖: {e}")
        logger.info(f"[RAG] 加载 embedding 模型: {_embedding_model_name}")
        _tokenizer = AutoTokenizer.from_pretrained(_embedding_model_name)
        _model = AutoModel.from_pretrained(_embedding_model_name)
        _model.eval()
    return _tokenizer, _model, None


def _encode(text: str) -> Optional[List[float]]:
    try:
        import torch
        tokenizer, model, _ = _get_embedding_model()
        enc = tokenizer([text], padding=True, truncation=True, return_tensors="pt", max_length=256)
        with torch.no_grad():
            out = model(**enc)
        vec = out.last_hidden_state[:, 0, :]
        vec = torch.nn.functional.normalize(vec, p=2, dim=1)
        return vec[0].numpy().tolist()
    except Exception as e:
        logger.warning("[RAG] embedding 失败（%s），降级到关键词检索", e)
        return None


# ====== 书籍元数据 ======

def list_books(db: Session) -> List[Dict]:
    books = db.query(RagBook).filter(RagBook.status == 1).order_by(RagBook.id.asc()).all()
    result = []
    for b in books:
        cnt = db.query(RagSection).filter(
            RagSection.book_id == b.id, RagSection.status == 1
        ).count()
        result.append({
            "id": b.id, "code": b.code, "name": b.name, "author": b.author or "",
            "dynasty": b.dynasty or "", "summary": b.summary or "",
            "total_chapters": b.total_chapters or 0, "total_sections": cnt,
        })
    return result


# ====== 向量检索（主路径） ======

def _retrieve_by_vector(question: str, book_codes: Optional[List[str]], top_k: int) -> List[Dict]:
    try:
        from app.services import milvus_client as milvus
    except Exception as e:
        logger.warning("[RAG] Milvus 客户端不可用，跳过向量检索: %s", e)
        return []

    col_name = getattr(settings, "RAG_MILVUS_COLLECTION", "sic_rag_four_books_v1")

    question_vec = _encode(question.strip())
    if not question_vec:
        return []

    try:
        min_score = float(getattr(settings, "RAG_MIN_SCORE", 0.5))
        hits = milvus.search_by_vector(
            question_vec, top_k=top_k, book_codes=book_codes,
            min_score=min_score, collection_name=col_name,
        )
    except Exception as e:
        logger.warning("[RAG] Milvus 搜索异常，跳过向量检索: %s", e)
        return []

    seen = set()
    result = []
    for h in hits:
        if h["id"] in seen or not h["text"]:
            continue
        seen.add(h["id"])
        result.append({
            "id": h["id"],
            "book_code": h.get("book_code", ""),
            "book_name": h.get("book_name", ""),
            "chapter_no": h.get("chapter_no", 0),
            "chapter_title": h.get("chapter_title", ""),
            "section_no": h.get("section_no", 0),
            "text": h["text"],
            "keywords": h.get("keywords", ""),
            "score": h["score"],
        })
    return result


# ====== MySQL 关键词召回（降级路径） ======

def _retrieve_by_keyword(db: Session, question: str,
                         book_codes: Optional[List[str]], top_k: int) -> List[Dict]:
    logger.info("[RAG] 降级路径：MySQL 关键词检索")
    from sqlalchemy import or_

    # 简单提取中文关键词（整句 + 2-4 字滑窗）
    cleaned = "".join(ch for ch in question if ch.isalnum() or "\u4e00" <= ch <= "\u9fff")
    kws = []
    for size in (3, 2):
        for j in range(0, len(cleaned) - size + 1):
            w = cleaned[j:j + size]
            if w and w not in kws:
                kws.append(w)
        if len(kws) >= 10:
            break

    query = db.query(RagSection).join(RagBook, RagSection.book_id == RagBook.id).filter(
        RagSection.status == 1, RagBook.status == 1
    )
    if book_codes:
        query = query.filter(RagBook.code.in_(book_codes))
    if kws:
        like_cond = or_(*[RagSection.text.like(f"%{w}%") for w in kws])
        title_cond = or_(*[RagSection.chapter_title.like(f"%{w}%") for w in kws])
        query = query.filter(or_(like_cond, title_cond))

    items = query.limit(top_k * 3).all()
    scored = []
    for it in items:
        text = (it.text or "").lower()
        hit = sum(1 for w in kws if w and w.lower() in text)
        if hit > 0:
            scored.append({
                "id": it.id,
                "book_code": it.book.code,
                "book_name": it.book.name,
                "chapter_no": it.chapter_no or 0,
                "chapter_title": it.chapter_title or "",
                "section_no": it.section_no or 0,
                "text": it.text or "",
                "keywords": it.keywords or "",
                "score": float(hit) / max(1, len(kws)),
            })
    scored.sort(key=lambda r: r["score"], reverse=True)
    return scored[:top_k]


# ====== 统一入口 ======

def retrieve(db: Session, question: str,
             book_codes: Optional[List[str]] = None, top_k: int = 0) -> List[Dict]:
    if not question or not question.strip():
        return []
    top_k = top_k or int(getattr(settings, "RAG_TOP_K", 5))

    t0 = time.time()
    sources = _retrieve_by_vector(question, book_codes, top_k)
    if not sources:
        sources = _retrieve_by_keyword(db, question, book_codes, top_k)
    logger.info(f"[RAG] 检索完成 ({time.time()-t0:.2f}s) 命中 {len(sources)} 段")
    return sources


# ====== LLM 组织答案 ======

def _call_deepseek_chat(system_prompt: str, user_message: str) -> Optional[str]:
    if not settings.DEEPSEEK_API_KEY:
        logger.warning("[RAG] 未配置 DeepSeek API Key, 跳过 LLM 答案生成")
        return None
    url = settings.DEEPSEEK_API_URL or "https://api.deepseek.com/v1/chat/completions"
    payload = {
        "model": settings.DEEPSEEK_MODEL or "deepseek-chat",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        "max_tokens": 600,
        "temperature": 0.5,
    }
    try:
        req = urllib.request.Request(
            url, data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json",
                     "Authorization": f"Bearer {settings.DEEPSEEK_API_KEY}"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=45) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        choice = data.get("choices", [{}])[0] if data.get("choices") else {}
        msg = choice.get("message", {}) if isinstance(choice, dict) else {}
        reply = msg.get("content", "") if isinstance(msg, dict) else ""
        return reply.strip() if isinstance(reply, str) and reply.strip() else None
    except Exception as e:
        logger.error(f"[RAG] 调用 DeepSeek 失败: {e}")
        return None


def answer_by_llm(question: str, sources: List[Dict]) -> str:
    if not sources:
        return "知识库中没有找到相关内容。可以换一个关键词再试试。"

    system_prompt = (
        "你是一位博学的中国古典文学助手，熟读四大名著。"
        "请严格基于用户提供的知识库检索片段来回答问题，不要虚构情节，"
        "不要引用片段之外的信息。回答简洁流畅，并可在合适位置提及出处。"
    )
    parts = [f"【片段{i+1}】《{s['book_name']}》（{s.get('chapter_title', '')}）\n{s['text']}"
             for i, s in enumerate(sources)]
    user_message = f"用户问题：{question.strip()}\n\n" + "\n\n".join(parts)

    reply = _call_deepseek_chat(system_prompt, user_message)
    if reply:
        return reply

    # 降级：直接拼接片段原文
    fallback = ["以下是知识库检索到的相关片段（LLM 不可用）：\n"]
    for s in sources:
        loc = f"《{s['book_name']}》"
        if s.get("chapter_title"):
            loc += f"（{s['chapter_title']}）"
        fallback.append(f"● {loc}\n{s['text']}\n")
    return "\n".join(fallback)


# ====== 对外主入口 ======

def ask_question(db: Session, question: str,
                 book_codes: Optional[List[str]] = None, top_k: int = 0) -> Dict:
    question = (question or "").strip()
    if not question:
        return {"answer": "请先输入问题。", "sources": [],
                "question": "", "book_filter": []}

    logger.info(f"[RAG] 新问题: {question} (book_codes={book_codes})")
    t0 = time.time()
    sources = retrieve(db, question, book_codes=book_codes, top_k=top_k)
    answer = answer_by_llm(question, sources)
    logger.info(f"[RAG] 回答生成完成 ({time.time()-t0:.2f}s)")
    return {"answer": answer, "sources": sources,
            "question": question, "book_filter": book_codes or []}


# ====== 健康检查 ======

def health_check(db: Session) -> Dict:
    col_name = getattr(settings, "RAG_MILVUS_COLLECTION", "sic_rag_four_books_v1")
    books = db.query(RagBook).count()
    sections = db.query(RagSection).count()

    try:
        from app.services import milvus_client as milvus
        milvus_count = milvus.count_vectors(collection_name=col_name)
    except Exception as e:
        logger.warning("[RAG] 读取 Milvus 统计失败: %s", e)
        milvus_count = -1

    return {
        "mysql_books": books,
        "mysql_sections": sections,
        "milvus_vectors": milvus_count,
        "milvus_collection": col_name,
        "embedding_model": _embedding_model_name,
    }
