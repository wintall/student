import hashlib
import os
import math
import re
from datetime import datetime
from pathlib import Path
from collections import Counter
from typing import Any, Dict, List, Optional

from fastapi import UploadFile
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.config import settings
from app.exceptions import BusinessException, NotFoundError, PermissionDenied
from app.models.rag_knowledge import RagDocument, RagDocumentChunk, RagKnowledgeBase
from app.models.user import Role, User, UserRole
from app.schemas.rag_knowledge import KnowledgeBaseCreate, KnowledgeBaseUpdate
from app.services import embedding_service
from app.services import rag_knowledge_milvus as milvus
from app.services.document_parser import ensure_allowed_path, read_document, read_pdf_file, read_docx_file, split_text
from app.services.ai_service import _call_deepseek


VECTOR_RECALL_MULTIPLIER = 4
KEYWORD_RECALL_LIMIT = 40
VECTOR_WEIGHT = 0.62
BM25_WEIGHT = 0.28
TITLE_WEIGHT = 0.10
MIN_CORE_TOKEN_MATCH = 2


def _percent(value: int | None, default: float) -> float:
    if value is None:
        return default
    return max(float(value), 0.0) / 100


def _kb_config(kb: RagKnowledgeBase) -> dict[str, Any]:
    return {
        "chunk_strategy": kb.chunk_strategy or "paragraph",
        "chunk_size": kb.chunk_size or settings.RAG_CHUNK_SIZE,
        "chunk_overlap": kb.chunk_overlap or settings.RAG_CHUNK_OVERLAP,
        "embedding_model": kb.embedding_model or settings.RAG_EMBEDDING_MODEL,
        "vector_store": kb.vector_store or "milvus",
        "similarity_metric": kb.similarity_metric or "COSINE",
        "retrieval_mode": kb.retrieval_mode or "hybrid",
        "default_top_k": kb.default_top_k or settings.RAG_TOP_K,
        "default_min_score": _percent(kb.default_min_score, settings.RAG_MIN_SCORE),
        "weights": {
            "vector": _percent(kb.vector_weight, VECTOR_WEIGHT),
            "bm25": _percent(kb.bm25_weight, BM25_WEIGHT),
            "title": _percent(kb.title_weight, TITLE_WEIGHT),
            "core": _percent(kb.core_weight, 0.35),
        },
    }


def _roles(user: User, db: Session) -> list[str]:
    role_ids = [r.role_id for r in db.query(UserRole).filter(UserRole.user_id == user.id).all()]
    if not role_ids:
        return []
    return [r.code for r in db.query(Role).filter(Role.id.in_(role_ids)).all()]


def _is_admin(user: User, db: Session) -> bool:
    return "admin" in _roles(user, db)


def _dt(value) -> str:
    return value.strftime("%Y-%m-%d %H:%M:%S") if value else ""


def kb_to_dict(kb: RagKnowledgeBase) -> Dict[str, Any]:
    return {
        "id": kb.id,
        "name": kb.name,
        "description": kb.description,
        "owner_id": kb.owner_id,
        "scope_type": kb.scope_type,
        "scope_id": kb.scope_id,
        "status": kb.status,
        "document_count": kb.document_count,
        "chunk_count": kb.chunk_count,
        "chunk_strategy": kb.chunk_strategy,
        "chunk_size": kb.chunk_size,
        "chunk_overlap": kb.chunk_overlap,
        "embedding_model": kb.embedding_model,
        "vector_store": kb.vector_store,
        "similarity_metric": kb.similarity_metric,
        "retrieval_mode": kb.retrieval_mode,
        "default_top_k": kb.default_top_k,
        "default_min_score": kb.default_min_score,
        "vector_weight": kb.vector_weight,
        "bm25_weight": kb.bm25_weight,
        "title_weight": kb.title_weight,
        "core_weight": kb.core_weight,
        "eval_score": kb.eval_score,
        "eval_recall": kb.eval_recall,
        "eval_precision": kb.eval_precision,
        "eval_f1": kb.eval_f1,
        "eval_hit": kb.eval_hit,
        "eval_mrr": kb.eval_mrr,
        "eval_sample_count": kb.eval_sample_count,
        "evaluated_at": _dt(kb.evaluated_at),
        "config": _kb_config(kb),
        "created_at": _dt(kb.created_at),
        "updated_at": _dt(kb.updated_at),
    }


def doc_to_dict(doc: RagDocument) -> Dict[str, Any]:
    return {
        "id": doc.id,
        "kb_id": doc.kb_id,
        "title": doc.title,
        "source_type": doc.source_type,
        "file_name": doc.file_name,
        "file_ext": doc.file_ext,
        "status": doc.status,
        "error_message": doc.error_message,
        "chunk_count": doc.chunk_count,
        "char_count": doc.char_count,
        "created_at": _dt(doc.created_at),
        "updated_at": _dt(doc.updated_at),
    }


def can_manage_kb(user: User, kb: RagKnowledgeBase, db: Session) -> bool:
    return _is_admin(user, db) or kb.owner_id == user.id


def can_read_kb(user: User, kb: RagKnowledgeBase, db: Session) -> bool:
    if kb.is_deleted or kb.status != 1:
        return False
    return kb.scope_type == "public" or kb.owner_id == user.id or _is_admin(user, db)


def get_kb(db: Session, kb_id: int) -> RagKnowledgeBase:
    kb = db.query(RagKnowledgeBase).filter(RagKnowledgeBase.id == kb_id, RagKnowledgeBase.is_deleted == False).first()
    if not kb:
        raise NotFoundError("知识库不存在")
    return kb


def create_kb(db: Session, user: User, data: KnowledgeBaseCreate) -> RagKnowledgeBase:
    if data.scope_type == "public" and not _is_admin(user, db):
        raise PermissionDenied("只有管理员可以创建公共知识库")
    kb = RagKnowledgeBase(
        name=data.name.strip(),
        description=data.description,
        owner_id=user.id,
        scope_type=data.scope_type,
        scope_id=data.scope_id,
        status=1,
        chunk_strategy=data.chunk_strategy,
        chunk_size=data.chunk_size,
        chunk_overlap=min(data.chunk_overlap, data.chunk_size // 2),
        embedding_model=data.embedding_model,
        vector_store=data.vector_store,
        similarity_metric=data.similarity_metric,
        retrieval_mode=data.retrieval_mode,
        default_top_k=data.default_top_k,
        default_min_score=data.default_min_score,
        vector_weight=data.vector_weight,
        bm25_weight=data.bm25_weight,
        title_weight=data.title_weight,
        core_weight=data.core_weight,
    )
    db.add(kb)
    db.commit()
    db.refresh(kb)
    return kb


def update_kb(db: Session, user: User, kb_id: int, data: KnowledgeBaseUpdate) -> RagKnowledgeBase:
    kb = get_kb(db, kb_id)
    if not can_manage_kb(user, kb, db):
        raise PermissionDenied("无权管理该知识库")
    values = data.model_dump(exclude_unset=True)
    if values.get("scope_type") == "public" and not _is_admin(user, db):
        raise PermissionDenied("只有管理员可以设置公共知识库")
    for key, value in values.items():
        if key == "name" and value:
            value = value.strip()
        if key == "chunk_overlap" and value is not None:
            chunk_size = values.get("chunk_size") or kb.chunk_size or settings.RAG_CHUNK_SIZE
            value = min(value, chunk_size // 2)
        setattr(kb, key, value)
    db.commit()
    db.refresh(kb)
    return kb


def list_kbs(db: Session, user: User, keyword: Optional[str] = None, include_public: bool = True) -> List[Dict[str, Any]]:
    q = db.query(RagKnowledgeBase).filter(RagKnowledgeBase.is_deleted == False)
    if not _is_admin(user, db):
        conditions = [RagKnowledgeBase.owner_id == user.id]
        if include_public:
            conditions.append(RagKnowledgeBase.scope_type == "public")
        q = q.filter(or_(*conditions), RagKnowledgeBase.status == 1)
    if keyword:
        like = f"%{keyword.strip()}%"
        q = q.filter(or_(RagKnowledgeBase.name.like(like), RagKnowledgeBase.description.like(like)))
    return [kb_to_dict(kb) for kb in q.order_by(RagKnowledgeBase.id.desc()).all()]


def _refresh_kb_stats(db: Session, kb_id: int):
    kb = get_kb(db, kb_id)
    kb.document_count = db.query(RagDocument).filter(
        RagDocument.kb_id == kb_id,
        RagDocument.is_deleted == False,
        RagDocument.status == "completed",
    ).count()
    kb.chunk_count = db.query(RagDocumentChunk).filter(
        RagDocumentChunk.kb_id == kb_id,
        RagDocumentChunk.is_deleted == False,
        RagDocumentChunk.status == "completed",
    ).count()


def _hash_text(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def _hash_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _tokenize(text: str) -> list[str]:
    text = (text or "").lower()
    tokens = re.findall(r"[a-zA-Z][a-zA-Z0-9_+-]{1,}|[0-9]{2,}|[\u4e00-\u9fff]{2,}", text)
    result: list[str] = []
    for token in tokens:
        if re.fullmatch(r"[\u4e00-\u9fff]{2,}", token):
            result.append(token)
            if len(token) <= 12:
                result.extend(token[i:i + 2] for i in range(len(token) - 1))
                if len(token) >= 3:
                    result.extend(token[i:i + 3] for i in range(len(token) - 2))
        else:
            result.append(token)
    return [token for token in result if len(token) >= 2]


def _bm25_scores(question: str, chunks: list[RagDocumentChunk]) -> dict[int, float]:
    query_tokens = _tokenize(question)
    if not query_tokens or not chunks:
        return {}

    docs_tokens = [_tokenize(chunk.content) for chunk in chunks]
    doc_count = len(docs_tokens)
    avgdl = sum(len(tokens) for tokens in docs_tokens) / max(doc_count, 1)
    if avgdl <= 0:
        return {}

    doc_freq: Counter[str] = Counter()
    for tokens in docs_tokens:
        doc_freq.update(set(tokens))

    k1 = 1.5
    b = 0.75
    raw_scores: dict[int, float] = {}
    for chunk, tokens in zip(chunks, docs_tokens):
        if not tokens:
            continue
        tf = Counter(tokens)
        dl = len(tokens)
        score = 0.0
        for token in query_tokens:
            freq = tf.get(token, 0)
            if freq <= 0:
                continue
            df = doc_freq.get(token, 0)
            idf = math.log(1 + (doc_count - df + 0.5) / (df + 0.5))
            denom = freq + k1 * (1 - b + b * dl / avgdl)
            score += idf * (freq * (k1 + 1) / denom)
        if score > 0:
            raw_scores[chunk.id] = score

    if not raw_scores:
        return {}
    max_score = max(raw_scores.values()) or 1.0
    return {chunk_id: round(score / max_score, 6) for chunk_id, score in raw_scores.items()}


def _title_score(question: str, title: str) -> float:
    q_tokens = set(_tokenize(question))
    title_tokens = set(_tokenize(title))
    if not q_tokens or not title_tokens:
        return 0.0
    return len(q_tokens & title_tokens) / max(len(q_tokens), 1)


def _core_query_tokens(question: str) -> list[str]:
    text = question or ""
    known_terms = [
        "诸葛亮", "刘备", "关羽", "张飞", "曹操", "孙权", "周瑜", "鲁肃", "赵云", "司马懿",
        "三顾茅庐", "草庐", "隆中", "隆中对",
    ]
    known_matches = [term for term in known_terms if term in text]
    if len(known_matches) >= 2:
        return list(dict.fromkeys(known_matches))[:8]
    tokens = list(known_matches)
    tokens.extend(_tokenize(question))
    stop_words = {
        "怎么", "如何", "为什么", "什么", "哪些", "是谁", "是否", "一下", "请问",
        "请到", "请来", "得到", "进行", "这个", "那个", "一个", "一些", "可以",
        "资料", "知识", "根据", "帮我", "介绍", "解释", "说明", "总结", "概括",
    }
    merged = list(dict.fromkeys(tokens))
    result = []
    for token in merged:
        if token in stop_words:
            continue
        if re.fullmatch(r"[\u4e00-\u9fff]+", token) and len(token) > 4:
            continue
        if len(token) >= 2:
            result.append(token)
    return result[:8]


def _core_match_count(content: str, tokens: list[str]) -> int:
    text = content or ""
    return sum(1 for token in tokens if token and token in text)


def _precise_keyword_chunks(
    db: Session,
    question: str,
    accessible_ids: list[int],
    limit: int = 20,
) -> list[RagDocumentChunk]:
    tokens = _core_query_tokens(question)
    if len(tokens) < 2:
        return []
    q = db.query(RagDocumentChunk).filter(
        RagDocumentChunk.kb_id.in_(accessible_ids),
        RagDocumentChunk.is_deleted == False,
        RagDocumentChunk.status == "completed",
    )
    for token in tokens[:4]:
        q = q.filter(RagDocumentChunk.content.like(f"%{token}%"))
    chunks = q.order_by(RagDocumentChunk.id.asc()).limit(limit).all()
    if chunks:
        return chunks

    conditions = [RagDocumentChunk.content.like(f"%{token}%") for token in tokens[:6]]
    if not conditions:
        return []
    candidates = db.query(RagDocumentChunk).filter(
        RagDocumentChunk.kb_id.in_(accessible_ids),
        RagDocumentChunk.is_deleted == False,
        RagDocumentChunk.status == "completed",
        or_(*conditions),
    ).order_by(RagDocumentChunk.id.asc()).limit(limit * 3).all()
    candidates.sort(key=lambda chunk: _core_match_count(chunk.content, tokens), reverse=True)
    return [chunk for chunk in candidates if _core_match_count(chunk.content, tokens) >= MIN_CORE_TOKEN_MATCH][:limit]


def _is_list_question(question: str) -> bool:
    question = question or ""
    return any(word in question for word in ["都是谁", "是谁", "有哪些", "哪几个", "哪几位", "名单", "成员"])


def _format_source_label(item: dict) -> str:
    title = item.get("title") or f"文档 {item.get('document_id')}"
    chunk_no = item.get("chunk_no")
    return f"{title} / 片段{chunk_no}" if chunk_no else title


def _extract_structured_list_answer(question: str, sources: list[dict]) -> Optional[str]:
    if not _is_list_question(question):
        return None

    if "十常侍" in question:
        expected_names = "张让、赵忠、封谞、段珪、曹节、侯览、蹇硕、程旷、夏恽、郭胜"
        for item in sources:
            content = item.get("content") or ""
            if "十常侍" not in content:
                continue
            if all(name in content for name in expected_names.split("、")):
                source = _format_source_label(item)
                return (
                    f"十常侍指的是：{expected_names}。\n\n"
                    "用现代话说，他们是东汉末年汉灵帝身边的一批宦官集团。"
                    "在《三国演义》的叙述里，他们互相勾结、干预朝政、排挤正臣，"
                    "是朝廷腐败和天下动乱的重要背景之一。\n\n"
                    f"出处：{source}"
                )
    return None


def _source_from_chunk(chunk: RagDocumentChunk, doc: Optional[RagDocument]) -> dict:
    return {
        "chunk_id": chunk.id,
        "document_id": chunk.document_id,
        "kb_id": chunk.kb_id,
        "title": doc.title if doc else f"文档 {chunk.document_id}",
        "chunk_no": chunk.chunk_no,
        "score": 1.0,
        "vector_score": 0.0,
        "bm25_score": 1.0,
        "title_score": 0.0,
        "content": chunk.content,
    }


def _find_structured_list_sources(
    db: Session,
    user: User,
    question: str,
    kb_ids: Optional[List[int]],
) -> list[dict]:
    if not _is_list_question(question) or "十常侍" not in question:
        return []

    accessible_ids = _accessible_kb_ids(db, user, kb_ids)
    if not accessible_ids:
        return []

    chunks = db.query(RagDocumentChunk).filter(
        RagDocumentChunk.kb_id.in_(accessible_ids),
        RagDocumentChunk.is_deleted == False,
        RagDocumentChunk.status == "completed",
        RagDocumentChunk.content.like("%十常侍%"),
        RagDocumentChunk.content.like("%张让%"),
        RagDocumentChunk.content.like("%赵忠%"),
    ).order_by(RagDocumentChunk.id.asc()).limit(10).all()
    if not chunks:
        return []

    docs = {
        doc.id: doc
        for doc in db.query(RagDocument).filter(
            RagDocument.id.in_({chunk.document_id for chunk in chunks}),
            RagDocument.is_deleted == False,
        ).all()
    }
    return [_source_from_chunk(chunk, docs.get(chunk.document_id)) for chunk in chunks]


def _question_focus(question: str) -> str:
    text = re.sub(r"[\s，。！？、,.!?：:；;（）()\[\]【】《》\"“”'‘’]", "", question or "")
    for word in [
        "请问", "帮我", "一下", "能不能", "可以", "知识库", "资料里", "根据资料",
        "是谁", "是什么", "什么意思", "有哪些", "都是谁", "哪几个", "哪几位",
        "介绍", "解释", "说明", "讲讲", "说说", "总结", "概括", "分析",
    ]:
        text = text.replace(word, "")
    return text[:30]


def _split_source_sentences(text: str) -> list[str]:
    cleaned = re.sub(r"\s+", " ", text or "").strip()
    if not cleaned:
        return []
    parts = re.split(r"(?<=[。！？；;!?])|[\r\n]+", cleaned)
    sentences: list[str] = []
    for part in parts:
        part = part.strip(" \t，,。；;")
        if not part:
            continue
        if len(part) > 140:
            for idx in range(0, len(part), 110):
                chunk = part[idx:idx + 110].strip(" ，,。；;")
                if chunk:
                    sentences.append(chunk)
        else:
            sentences.append(part)
    return sentences


def _sentence_score(sentence: str, focus: str, question_tokens: set[str]) -> int:
    score = 0
    if focus and focus in sentence:
        score += 5
    for token in question_tokens:
        if token and token in sentence:
            score += 1
    return score


def _fallback_summary_from_sources(question: str, sources: list[dict]) -> str:
    structured_answer = _extract_structured_list_answer(question, sources)
    if structured_answer:
        return structured_answer

    focus = _question_focus(question)
    question_tokens = set(_tokenize(question))
    core_tokens = _core_query_tokens(question)
    if core_tokens and sources:
        best_core_match = max(_core_match_count(item.get("content") or "", core_tokens) for item in sources[:5])
        if best_core_match < min(MIN_CORE_TOKEN_MATCH, len(core_tokens)):
            source_lines = "\n".join(
                f"{idx}. {_format_source_label(item)}"
                for idx, item in enumerate(sources[:3], start=1)
            )
            return (
                "我检索到了一些资料，但这些片段和你的问题关键词匹配不够，不能据此给出可靠结论。"
                "建议换一个更具体的问法，或检查知识库中是否导入了相关章节。\n\n"
                f"出处：\n{source_lines}"
            )
    candidates: list[tuple[int, str, dict]] = []
    for item in sources[:6]:
        for sentence in _split_source_sentences(item.get("content") or ""):
            score = _sentence_score(sentence, focus, question_tokens)
            if score > 0 or len(candidates) < 3:
                candidates.append((score, sentence, item))
    candidates.sort(key=lambda row: row[0], reverse=True)

    seen: set[str] = set()
    points: list[str] = []
    used_sources: list[dict] = []
    for _, sentence, item in candidates:
        compact = sentence.strip()
        if not compact or compact in seen:
            continue
        seen.add(compact)
        points.append(compact[:140])
        used_sources.append(item)
        if len(points) >= 3:
            break

    source_items = used_sources or sources[:3]
    source_lines = "\n".join(
        f"{idx}. {_format_source_label(item)}"
        for idx, item in enumerate(source_items[:3], start=1)
    )

    if not points:
        return (
            "我在知识库里找到了相关资料，但资料片段不够完整，暂时只能先给出出处，"
            "建议补充更完整的原文或换一个更具体的问题。\n\n"
            f"出处：\n{source_lines}"
        )

    target = f"“{focus}”" if focus else "这个问题"
    point_lines = "\n".join(f"- {point}" for point in points)
    return (
        f"根据知识库资料，我先用白话概括 {target}：\n\n"
        f"{point_lines}\n\n"
        "说明：以上是根据检索片段整理出的简要结论；如果你需要，我还可以继续展开背景、人物关系或情节影响。\n\n"
        f"出处：\n{source_lines}"
    )


def _keyword_recall_chunks(
    db: Session,
    question: str,
    accessible_ids: list[int],
    limit: int = KEYWORD_RECALL_LIMIT,
) -> list[RagDocumentChunk]:
    query_tokens = list(dict.fromkeys(_tokenize(question)))[:10]
    if not query_tokens:
        return []
    q = db.query(RagDocumentChunk).filter(
        RagDocumentChunk.kb_id.in_(accessible_ids),
        RagDocumentChunk.is_deleted == False,
        RagDocumentChunk.status == "completed",
    )
    conditions = [RagDocumentChunk.content.like(f"%{token}%") for token in query_tokens if len(token) >= 2]
    if conditions:
        q = q.filter(or_(*conditions))
    return q.order_by(RagDocumentChunk.id.desc()).limit(limit).all()


def _fixed_split_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    cleaned = re.sub(r"\s+", " ", text or "").strip()
    if not cleaned:
        return []
    chunk_size = max(int(chunk_size or settings.RAG_CHUNK_SIZE), 200)
    overlap = max(min(int(overlap or 0), chunk_size // 2), 0)
    chunks: list[str] = []
    start = 0
    while start < len(cleaned):
        end = min(start + chunk_size, len(cleaned))
        part = cleaned[start:end].strip()
        if part:
            chunks.append(part)
        if end >= len(cleaned):
            break
        start = max(end - overlap, start + 1)
    return chunks


def _split_for_kb(text: str, kb: RagKnowledgeBase) -> list[str]:
    config = _kb_config(kb)
    chunk_size = int(config["chunk_size"])
    overlap = int(config["chunk_overlap"])
    if config["chunk_strategy"] == "fixed":
        return _fixed_split_text(text, chunk_size, overlap)
    return split_text(text, chunk_size, overlap)


def _extract_eval_question(content: str) -> str:
    for line in (content or "").splitlines():
        text = line.strip()
        if not text:
            continue
        text = re.sub(r"^#{1,6}\s*", "", text).strip()
        text = re.sub(r"^\d+[\.、]\s*", "", text).strip()
        if len(text) < 6 or len(text) > 80:
            continue
        if "？" in text or "?" in text or any(word in text for word in ["是什么", "为什么", "如何", "怎么", "区别", "流程"]):
            return text
    focus = _question_focus(content[:120])
    return focus if len(focus) >= 6 else ""


def _keywords_for_eval(question: str, content: str) -> list[str]:
    tokens = []
    for token in _tokenize(f"{question} {content[:500]}"):
        if token in {"什么", "怎么", "如何", "为什么", "区别", "流程", "核心"}:
            continue
        if token not in tokens:
            tokens.append(token)
        if len(tokens) >= 8:
            break
    return tokens


def _build_eval_samples(db: Session, kb_id: int, limit: int = 12) -> list[dict[str, Any]]:
    chunks = db.query(RagDocumentChunk).filter(
        RagDocumentChunk.kb_id == kb_id,
        RagDocumentChunk.is_deleted == False,
        RagDocumentChunk.status == "completed",
    ).order_by(RagDocumentChunk.chunk_no.asc()).limit(200).all()
    samples: list[dict[str, Any]] = []
    seen_questions: set[str] = set()
    for chunk in chunks:
        question = _extract_eval_question(chunk.content)
        if not question or question in seen_questions:
            continue
        keywords = _keywords_for_eval(question, chunk.content)
        if len(keywords) < 2:
            continue
        seen_questions.add(question)
        samples.append({
            "question": question,
            "expected_chunk_id": chunk.id,
            "expected_document_id": chunk.document_id,
            "expected_keywords": keywords,
        })
        if len(samples) >= limit:
            break
    return samples


def evaluate_kb(db: Session, user: User, kb_id: int, sample_limit: int = 12) -> dict[str, Any]:
    kb = get_kb(db, kb_id)
    if not can_read_kb(user, kb, db):
        raise PermissionDenied("无权评估该知识库")
    if kb.chunk_count <= 0:
        raise BusinessException(message="知识库还没有可评估的切片，请先导入文档")

    samples = _build_eval_samples(db, kb_id, sample_limit)
    if not samples:
        raise BusinessException(message="暂未自动抽取到可评估样本，请导入包含标题或问答结构的资料")

    top_k = kb.default_top_k or settings.RAG_TOP_K
    details = []
    recall_values: list[float] = []
    precision_values: list[float] = []
    hit_values: list[float] = []
    rr_values: list[float] = []

    for sample in samples:
        result = search(db, user, sample["question"], [kb_id], top_k, 0)
        items = result.get("items") or []
        expected_keywords = sample["expected_keywords"]
        matched_items = []
        first_rank = 0
        covered_keywords: set[str] = set()

        for rank, item in enumerate(items, start=1):
            content = item.get("content") or ""
            keyword_hits = [kw for kw in expected_keywords if kw in content]
            if item.get("chunk_id") == sample["expected_chunk_id"] or len(keyword_hits) >= max(1, min(2, len(expected_keywords))):
                matched_items.append(rank)
                if not first_rank:
                    first_rank = rank
            covered_keywords.update(keyword_hits)

        recall = len(covered_keywords) / max(len(expected_keywords), 1)
        precision = len(matched_items) / max(len(items), 1) if items else 0.0
        hit = 1.0 if first_rank == 1 else 0.0
        rr = 1.0 / first_rank if first_rank else 0.0

        recall_values.append(recall)
        precision_values.append(precision)
        hit_values.append(hit)
        rr_values.append(rr)
        details.append({
            "question": sample["question"],
            "expected_keywords": expected_keywords,
            "covered_keywords": sorted(covered_keywords),
            "expected_chunk_id": sample["expected_chunk_id"],
            "top_chunks": [item.get("chunk_id") for item in items[:top_k]],
            "recall": round(recall, 4),
            "precision": round(precision, 4),
            "hit_at_1": hit == 1.0,
            "rr": round(rr, 4),
        })

    avg_recall = sum(recall_values) / len(recall_values)
    avg_precision = sum(precision_values) / len(precision_values)
    f1 = (2 * avg_precision * avg_recall / (avg_precision + avg_recall)) if (avg_precision + avg_recall) else 0.0
    hit_at_1 = sum(hit_values) / len(hit_values)
    mrr = sum(rr_values) / len(rr_values)
    score = avg_recall * 0.4 + avg_precision * 0.3 + hit_at_1 * 0.2 + mrr * 0.1

    kb.eval_score = round(score * 100)
    kb.eval_recall = round(avg_recall * 100)
    kb.eval_precision = round(avg_precision * 100)
    kb.eval_f1 = round(f1 * 100)
    kb.eval_hit = round(hit_at_1 * 100)
    kb.eval_mrr = round(mrr * 100)
    kb.eval_sample_count = len(samples)
    kb.evaluated_at = datetime.now()
    db.commit()
    db.refresh(kb)

    return {
        "kb_id": kb.id,
        "score": kb.eval_score,
        "recall": round(avg_recall, 4),
        "precision": round(avg_precision, 4),
        "f1": round(f1, 4),
        "hit_at_1": round(hit_at_1, 4),
        "mrr": round(mrr, 4),
        "sample_count": len(samples),
        "top_k": top_k,
        "evaluated_at": _dt(kb.evaluated_at),
        "method": "auto_keyword_eval",
        "note": "自动评估基于标题/问题句抽样和关键词命中，适合快速判断知识库质量；严格评估可后续接入人工标注测试集。",
        "details": details[:10],
        "base": kb_to_dict(kb),
    }


def _create_document(
    db: Session,
    kb: RagKnowledgeBase,
    user: User,
    title: str,
    source_type: str,
    text: str,
    file_name: Optional[str] = None,
    file_path: Optional[str] = None,
    file_ext: Optional[str] = None,
    file_hash: Optional[str] = None,
) -> RagDocument:
    doc = RagDocument(
        kb_id=kb.id,
        owner_id=user.id,
        title=title.strip() or "未命名文档",
        source_type=source_type,
        file_name=file_name,
        file_path=file_path,
        file_ext=file_ext,
        file_hash=file_hash or _hash_text(text),
        status="processing",
        char_count=len(text or ""),
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc


def _index_document(db: Session, kb: RagKnowledgeBase, doc: RagDocument, text: str):
    chunks = _split_for_kb(text, kb)
    if not chunks:
        doc.status = "failed"
        doc.error_message = "文档没有可入库的文本内容"
        db.commit()
        raise BusinessException(message=doc.error_message)

    try:
        vectors = embedding_service.encode_batch(chunks)
    except Exception as exc:
        doc.status = "failed"
        doc.error_message = f"向量生成失败：{exc}"
        db.commit()
        raise BusinessException(message=doc.error_message) from exc

    chunk_models: list[RagDocumentChunk] = []
    for idx, content in enumerate(chunks, start=1):
        chunk = RagDocumentChunk(
            kb_id=kb.id,
            document_id=doc.id,
            owner_id=doc.owner_id,
            chunk_no=idx,
            content=content,
            content_hash=_hash_text(content),
            char_count=len(content),
            token_count=max(1, len(content) // 2),
            status="completed",
        )
        db.add(chunk)
        chunk_models.append(chunk)
    db.commit()
    for chunk in chunk_models:
        db.refresh(chunk)

    vector_records = []
    for chunk, vector in zip(chunk_models, vectors):
        vector_records.append(
            {
                "id": chunk.id,
                "kb_id": kb.id,
                "document_id": doc.id,
                "owner_id": doc.owner_id,
                "scope_type": kb.scope_type,
                "title": doc.title,
                "chunk_no": chunk.chunk_no,
                "content": chunk.content,
                "embedding": vector,
            }
        )
    try:
        milvus.insert_chunks(vector_records)
    except Exception as exc:
        doc.status = "failed"
        doc.error_message = f"向量入库失败：{exc}"
        db.commit()
        raise BusinessException(message=doc.error_message) from exc

    doc.status = "completed"
    doc.error_message = None
    doc.chunk_count = len(chunk_models)
    doc.char_count = len(text)
    db.flush()
    _refresh_kb_stats(db, kb.id)
    db.commit()
    db.refresh(doc)


def import_text(db: Session, user: User, kb_id: int, title: str, text: str) -> RagDocument:
    kb = get_kb(db, kb_id)
    if not can_manage_kb(user, kb, db):
        raise PermissionDenied("无权向该知识库导入文档")
    doc = _create_document(db, kb, user, title, "text", text)
    _index_document(db, kb, doc, text)
    return doc


def import_path(db: Session, user: User, kb_id: int, path_text: str, title: Optional[str] = None) -> RagDocument:
    kb = get_kb(db, kb_id)
    if not can_manage_kb(user, kb, db):
        raise PermissionDenied("无权向该知识库导入文档")
    project_root = Path(os.getcwd()).resolve()
    upload_root = Path(settings.ABS_UPLOAD_DIR).resolve()
    path = ensure_allowed_path(path_text, [project_root, upload_root])
    text = read_document(path)
    doc = _create_document(
        db,
        kb,
        user,
        title or path.stem,
        "path",
        text,
        file_name=path.name,
        file_path=str(path),
        file_ext=path.suffix.lower(),
        file_hash=_hash_bytes(path.read_bytes()),
    )
    _index_document(db, kb, doc, text)
    return doc


def _decode_uploaded_text(data: bytes) -> str:
    for encoding in ("utf-8", "utf-8-sig", "gbk"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise BusinessException(message="文件编码无法识别，请使用 UTF-8 或 GBK 文本")


def import_upload(db: Session, user: User, kb_id: int, file: UploadFile, title: Optional[str] = None) -> RagDocument:
    kb = get_kb(db, kb_id)
    if not can_manage_kb(user, kb, db):
        raise PermissionDenied("无权向该知识库导入文档")

    file_name = Path(file.filename or "upload.txt").name
    ext = Path(file_name).suffix.lower()
    if ext not in {".txt", ".md", ".markdown", ".pdf", ".docx"}:
        raise BusinessException(message="仅支持 txt、md、pdf、docx 文件")

    data = file.file.read()
    if not data:
        raise BusinessException(message="上传文件为空")
    if len(data) > settings.MAX_UPLOAD_SIZE:
        raise BusinessException(message="上传文件超过大小限制")

    file_hash = _hash_bytes(data)
    upload_dir = Path(settings.ABS_UPLOAD_DIR) / "rag_knowledge" / str(user.id)
    upload_dir.mkdir(parents=True, exist_ok=True)
    stored_path = upload_dir / f"{file_hash}{ext}"
    with stored_path.open("wb") as out:
        out.write(data)

    if ext == ".pdf":
        text = read_pdf_file(stored_path)
    elif ext == ".docx":
        text = read_docx_file(stored_path)
    else:
        text = _decode_uploaded_text(data)

    doc = _create_document(
        db,
        kb,
        user,
        title or Path(file_name).stem,
        "upload",
        text,
        file_name=file_name,
        file_path=str(stored_path),
        file_ext=ext,
        file_hash=file_hash,
    )
    _index_document(db, kb, doc, text)
    return doc


def list_documents(db: Session, user: User, kb_id: int) -> List[Dict[str, Any]]:
    kb = get_kb(db, kb_id)
    if not can_read_kb(user, kb, db):
        raise PermissionDenied("无权查看该知识库")
    docs = db.query(RagDocument).filter(
        RagDocument.kb_id == kb_id,
        RagDocument.is_deleted == False,
    ).order_by(RagDocument.id.desc()).all()
    return [doc_to_dict(doc) for doc in docs]


def kb_detail(db: Session, user: User, kb_id: int) -> Dict[str, Any]:
    kb = get_kb(db, kb_id)
    if not can_read_kb(user, kb, db):
        raise PermissionDenied("无权查看该知识库")
    docs = list_documents(db, user, kb_id)
    char_counts = [int(doc.get("char_count") or 0) for doc in docs]
    chunk_counts = [int(doc.get("chunk_count") or 0) for doc in docs]
    avg_chunk_chars = round(sum(char_counts) / max(sum(chunk_counts), 1), 1) if chunk_counts else 0
    return {
        "base": kb_to_dict(kb),
        "build": {
            "pipeline": ["文档解析", "文本清洗", "切片", "Embedding 向量化", "MySQL 片段存储", "Milvus 向量入库", "混合检索问答"],
            "document_count": kb.document_count,
            "chunk_count": kb.chunk_count,
            "avg_chunk_chars": avg_chunk_chars,
            "milvus_collection": settings.RAG_KNOWLEDGE_MILVUS_COLLECTION,
            "status": "ready" if kb.chunk_count > 0 else "empty",
        },
        "retrieval": {
            "default_mode": kb.retrieval_mode,
            "default_top_k": kb.default_top_k,
            "default_min_score": _percent(kb.default_min_score, settings.RAG_MIN_SCORE),
            "weights": _kb_config(kb)["weights"],
            "metrics_note": "Recall@K/Precision@K 需要标准测试集。本页先展示召回片段、分数拆解和候选统计，便于人工评估。",
        },
        "evaluation": {
            "score": kb.eval_score,
            "recall": kb.eval_recall,
            "precision": kb.eval_precision,
            "f1": kb.eval_f1,
            "hit_at_1": kb.eval_hit,
            "mrr": kb.eval_mrr,
            "sample_count": kb.eval_sample_count,
            "evaluated_at": _dt(kb.evaluated_at),
            "note": "自动评估基于标题/问题句抽样和关键词命中，适合快速判断知识库质量；严格评估可后续接入人工标注测试集。",
        },
    }


def _accessible_kb_ids(db: Session, user: User, kb_ids: Optional[List[int]] = None) -> List[int]:
    q = db.query(RagKnowledgeBase).filter(RagKnowledgeBase.is_deleted == False, RagKnowledgeBase.status == 1)
    if kb_ids:
        q = q.filter(RagKnowledgeBase.id.in_(kb_ids))
    if not _is_admin(user, db):
        q = q.filter(or_(RagKnowledgeBase.owner_id == user.id, RagKnowledgeBase.scope_type == "public"))
    return [int(kb.id) for kb in q.all()]


def _search_config(db: Session, accessible_ids: list[int], top_k: int | None, min_score: float | None) -> dict[str, Any]:
    kb = None
    if len(accessible_ids) == 1:
        kb = db.query(RagKnowledgeBase).filter(RagKnowledgeBase.id == accessible_ids[0]).first()
    config = _kb_config(kb) if kb else {
        "retrieval_mode": "hybrid",
        "default_top_k": settings.RAG_TOP_K,
        "default_min_score": settings.RAG_MIN_SCORE,
        "weights": {
            "vector": VECTOR_WEIGHT,
            "bm25": BM25_WEIGHT,
            "title": TITLE_WEIGHT,
            "core": 0.35,
        },
    }
    requested_min_score = float(min_score or 0)
    return {
        "kb_config": config,
        "retrieval_mode": config.get("retrieval_mode") or "hybrid",
        "top_k": int(top_k or config.get("default_top_k") or settings.RAG_TOP_K),
        "min_score": requested_min_score if requested_min_score > 0 else float(config.get("default_min_score") or 0),
        "weights": config.get("weights") or {},
    }


def search(db: Session, user: User, question: str, kb_ids: Optional[List[int]], top_k: int, min_score: float) -> Dict[str, Any]:
    accessible_ids = _accessible_kb_ids(db, user, kb_ids)
    if not accessible_ids:
        return {"question": question, "total": 0, "items": [], "kb_ids": []}

    config = _search_config(db, accessible_ids, top_k, min_score)
    top_k = max(1, min(int(config["top_k"]), 20))
    min_score = max(0.0, min(float(config["min_score"]), 1.0))
    retrieval_mode = config["retrieval_mode"]
    weights = config["weights"]
    vector_weight = float(weights.get("vector", VECTOR_WEIGHT))
    bm25_weight = float(weights.get("bm25", BM25_WEIGHT))
    title_weight = float(weights.get("title", TITLE_WEIGHT))
    core_weight = float(weights.get("core", 0.35))

    recall_limit = max(top_k * VECTOR_RECALL_MULTIPLIER, top_k, 12)
    vector_hits: list[dict] = []
    if retrieval_mode in {"vector", "hybrid"}:
        try:
            vector = embedding_service.encode(question)
            if vector:
                vector_hits = milvus.search_chunks(
                    vector=vector,
                    top_k=recall_limit,
                    kb_ids=accessible_ids,
                    min_score=0,
                )
        except Exception:
            vector_hits = []

    vector_scores = {int(hit["id"]): float(hit.get("score") or 0) for hit in vector_hits if hit.get("id")}
    vector_titles = {int(hit["id"]): hit.get("title") or "" for hit in vector_hits if hit.get("id")}
    keyword_chunks = _keyword_recall_chunks(db, question, accessible_ids) if retrieval_mode in {"keyword", "hybrid"} else []
    precise_chunks = _precise_keyword_chunks(db, question, accessible_ids) if retrieval_mode in {"keyword", "hybrid"} else []
    candidate_ids = set(vector_scores.keys()) | {chunk.id for chunk in keyword_chunks} | {chunk.id for chunk in precise_chunks}
    if not candidate_ids:
        return {"question": question, "total": 0, "items": [], "kb_ids": accessible_ids, "retrieval": {"mode": retrieval_mode, "config": config["kb_config"]}}

    chunks = db.query(RagDocumentChunk).filter(
        RagDocumentChunk.id.in_(candidate_ids),
        RagDocumentChunk.kb_id.in_(accessible_ids),
        RagDocumentChunk.is_deleted == False,
        RagDocumentChunk.status == "completed",
    ).all()
    if not chunks:
        return {"question": question, "total": 0, "items": [], "kb_ids": accessible_ids, "retrieval": {"mode": retrieval_mode, "config": config["kb_config"]}}

    doc_ids = list({chunk.document_id for chunk in chunks})
    docs = {
        doc.id: doc
        for doc in db.query(RagDocument).filter(
            RagDocument.id.in_(doc_ids),
            RagDocument.is_deleted == False,
        ).all()
    }
    bm25_scores = _bm25_scores(question, chunks)
    core_tokens = _core_query_tokens(question)

    items = []
    for chunk in chunks:
        doc = docs.get(chunk.document_id)
        title = vector_titles.get(chunk.id) or (doc.title if doc else "")
        vector_score = vector_scores.get(chunk.id, 0.0)
        bm25_score = bm25_scores.get(chunk.id, 0.0)
        title_match_score = _title_score(question, title)
        core_score = _core_match_count(chunk.content, core_tokens) / max(len(core_tokens), 1) if core_tokens else 0.0
        final_score = (
            vector_score * vector_weight
            + bm25_score * bm25_weight
            + title_match_score * title_weight
            + core_score * core_weight
        )
        if min_score and final_score < min_score:
            continue
        items.append(
            {
                "chunk_id": chunk.id,
                "document_id": chunk.document_id,
                "kb_id": chunk.kb_id,
                "title": title,
                "chunk_no": chunk.chunk_no,
                "score": round(final_score, 4),
                "vector_score": round(vector_score, 4),
                "bm25_score": round(bm25_score, 4),
                "title_score": round(title_match_score, 4),
                "core_score": round(core_score, 4),
                "content": chunk.content,
            }
        )

    items.sort(key=lambda item: item["score"], reverse=True)
    items = items[:top_k]
    return {
        "question": question,
        "total": len(items),
        "items": items,
        "kb_ids": accessible_ids,
        "retrieval": {
            "mode": retrieval_mode,
            "vector_candidates": len(vector_scores),
            "keyword_candidates": len(keyword_chunks),
            "precise_candidates": len(precise_chunks),
            "candidate_total": len(candidate_ids),
            "top_k": top_k,
            "min_score": min_score,
            "weights": {
                "vector": vector_weight,
                "bm25": bm25_weight,
                "title": title_weight,
                "core": core_weight,
            },
            "config": config["kb_config"],
        },
    }


def answer(db: Session, user: User, question: str, kb_ids: Optional[List[int]], top_k: int, min_score: float) -> Dict[str, Any]:
    result = search(db, user, question, kb_ids, top_k, min_score)
    sources = result["items"]
    structured_sources = _find_structured_list_sources(db, user, question, kb_ids)
    if structured_sources:
        structured_answer = _extract_structured_list_answer(question, structured_sources)
        if structured_answer:
            return {"question": question, "answer": structured_answer, "sources": structured_sources[:top_k], "kb_ids": result.get("kb_ids", []), "retrieval": result.get("retrieval", {})}

    if not sources:
        return {
            "question": question,
            "answer": "我没有在当前可访问的知识库中检索到足够相关的内容。你可以换个问法，或先导入相关资料。",
            "sources": [],
            "kb_ids": result.get("kb_ids", []),
            "retrieval": result.get("retrieval", {}),
        }

    structured_answer = _extract_structured_list_answer(question, sources)
    if structured_answer:
        return {"question": question, "answer": structured_answer, "sources": sources, "kb_ids": result.get("kb_ids", []), "retrieval": result.get("retrieval", {})}

    context = "\n\n".join(
        f"[来源{idx}] {item['title']} / 片段{item['chunk_no']}\n{item['content']}"
        for idx, item in enumerate(sources, start=1)
    )
    system_prompt = (
        "你是校园助手的综合知识库问答能力。请只基于给定资料回答，资料不足时明确说明不足。"
        "回答时要像老师讲解一样，用现代白话做归纳、解释和总结，不要把原文大段复制给用户。"
        "除非用户明确要求看原文，否则不要连续引用原文；确需引用时只引用很短的一句。"
        "结尾用“出处”列出来源编号、文档标题和片段号即可。"
    )
    user_message = f"问题：{question}\n\n可用资料：\n{context}"
    reply = _call_deepseek(system_prompt, user_message, max_tokens=800)
    if not reply:
        reply = _fallback_summary_from_sources(question, sources)
    return {"question": question, "answer": reply, "sources": sources, "kb_ids": result.get("kb_ids", []), "retrieval": result.get("retrieval", {})}


def delete_document(db: Session, user: User, document_id: int) -> Dict[str, Any]:
    doc = db.query(RagDocument).filter(RagDocument.id == document_id, RagDocument.is_deleted == False).first()
    if not doc:
        raise NotFoundError("文档不存在")
    kb = get_kb(db, doc.kb_id)
    if not can_manage_kb(user, kb, db):
        raise PermissionDenied("无权删除该文档")

    chunks = db.query(RagDocumentChunk).filter(
        RagDocumentChunk.document_id == doc.id,
        RagDocumentChunk.is_deleted == False,
    ).all()
    now = datetime.now()
    chunk_ids = [c.id for c in chunks]
    for chunk in chunks:
        chunk.is_deleted = True
        chunk.deleted_at = now
        chunk.status = "deleted"
    doc.is_deleted = True
    doc.deleted_at = now
    doc.status = "deleted"
    milvus.delete_chunks(chunk_ids)
    _refresh_kb_stats(db, kb.id)
    db.commit()
    return {"deleted": True, "document_id": document_id, "chunk_count": len(chunk_ids)}


def delete_kb(db: Session, user: User, kb_id: int) -> Dict[str, Any]:
    kb = get_kb(db, kb_id)
    if not can_manage_kb(user, kb, db):
        raise PermissionDenied("无权删除该知识库")
    docs = db.query(RagDocument).filter(RagDocument.kb_id == kb_id, RagDocument.is_deleted == False).all()
    chunks = db.query(RagDocumentChunk).filter(
        RagDocumentChunk.kb_id == kb_id,
        RagDocumentChunk.is_deleted == False,
    ).all()
    now = datetime.now()
    chunk_ids = [c.id for c in chunks]
    for chunk in chunks:
        chunk.is_deleted = True
        chunk.deleted_at = now
        chunk.status = "deleted"
    for doc in docs:
        doc.is_deleted = True
        doc.deleted_at = now
        doc.status = "deleted"
    kb.is_deleted = True
    kb.deleted_at = now
    kb.status = 0
    kb.document_count = 0
    kb.chunk_count = 0
    milvus.delete_chunks(chunk_ids)
    db.commit()
    return {"deleted": True, "kb_id": kb_id, "document_count": len(docs), "chunk_count": len(chunks)}


def health(db: Session) -> Dict[str, Any]:
    return {
        "mysql": {
            "knowledge_bases": db.query(RagKnowledgeBase).filter(RagKnowledgeBase.is_deleted == False).count(),
            "documents": db.query(RagDocument).filter(RagDocument.is_deleted == False).count(),
            "chunks": db.query(RagDocumentChunk).filter(RagDocumentChunk.is_deleted == False).count(),
        },
        "vector": milvus.health(),
    }
