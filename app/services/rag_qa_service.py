"""
RAG 问答对服务
- CRUD 管理问答对
- 快速问答对匹配（关键词+语义匹配）
- 集成到 RAG 检索流程（优先匹配问答对，节省 LLM 调用
"""

import logging
from typing import Dict, List, Optional

from sqlalchemy import or_, and_
from sqlalchemy.orm import Session

from app.models.rag_qa import RagQaPair

logger = logging.getLogger("app")


# ============ 管理类 ============

def create_qa_pair(db: Session, data) -> RagQaPair:
    """创建问答对"""
    qa = RagQaPair(
        category=data.category,
        question=data.question.strip(),
        question_variants=data.question_variants,
        answer=data.answer.strip(),
        keywords=data.keywords,
        source=data.source,
        status=1,
        hit_count=0,
    )
    db.add(qa)
    db.commit()
    db.refresh(qa)
    return qa


def get_qa_pair(db: Session, qa_id: int) -> Optional[RagQaPair]:
    """获取单个问答对"""
    return db.query(RagQaPair).filter(RagQaPair.id == qa_id).first()


def update_qa_pair(db: Session, qa_id: int, data) -> Optional[RagQaPair]:
    """更新问答对"""
    qa = get_qa_pair(db, qa_id)
    if not qa:
        return None
    if data.category is not None:
        qa.category = data.category
    if data.question is not None:
        qa.question = data.question.strip()
    if data.question_variants is not None:
        qa.question_variants = data.question_variants
    if data.answer is not None:
        qa.answer = data.answer.strip()
    if data.keywords is not None:
        qa.keywords = data.keywords
    if data.source is not None:
        qa.source = data.source
    if data.status is not None:
        qa.status = data.status
    db.commit()
    db.refresh(qa)
    return qa


def delete_qa_pair(db: Session, qa_id: int) -> bool:
    """删除问答对（软删除，这里直接删除，或用status=0禁用）"""
    qa = get_qa_pair(db, qa_id)
    if not qa:
        return False
    db.delete(qa)
    db.commit()
    return True


def list_qa_pairs(db: Session, keyword: Optional[str] = None,
                   category: Optional[str] = None,
                   status: Optional[int] = None,
                   offset: int = 0, limit: int = 20) -> List[RagQaPair]:
    """列表查询"""
    q = db.query(RagQaPair)
    filters = []
    if status is not None:
        filters.append(RagQaPair.status == status)
    if category:
        filters.append(RagQaPair.category == category)
    if keyword:
        kw = f"%{keyword}%"
        filters.append(or_(
            RagQaPair.question.like(kw),
            RagQaPair.question_variants.like(kw),
            RagQaPair.answer.like(kw),
            RagQaPair.keywords.like(kw),
        ))
    if filters:
        q = q.filter(and_(*filters))
    return q.order_by(RagQaPair.id.desc()).offset(offset).limit(limit).all()


def count_qa_pairs(db: Session, keyword: Optional[str] = None,
                    category: Optional[str] = None,
                    status: Optional[int] = None) -> int:
    """统计数量"""
    q = db.query(RagQaPair)
    filters = []
    if status is not None:
        filters.append(RagQaPair.status == status)
    if category:
        filters.append(RagQaPair.category == category)
    if keyword:
        kw = f"%{keyword}%"
        filters.append(or_(
            RagQaPair.question.like(kw),
            RagQaPair.question_variants.like(kw),
            RagQaPair.answer.like(kw),
            RagQaPair.keywords.like(kw),
        ))
    if filters:
        q = q.filter(and_(*filters))
    return q.count()


# ============ 匹配问答对（用于 RAG 快速回答） ============

def _calc_keyword_match_score(question: str, qa: RagQaPair) -> float:
    """计算问题与问答对的关键词匹配度（0~1）"""
    # 清洗问题文本
    q_text = question.strip()
    if not q_text:
        return 0.0

    # 精确匹配（问题文本
    all_questions = [qa.question]
    if qa.question_variants:
        all_questions += [v.strip() for v in qa.question_variants.split(";") if v.strip()]

    # 直接完全匹配给高分
    for variant in all_questions:
        if not variant:
            continue
        if q_text == variant:
            return 1.0
        # 关键词标签也匹配
        if q_text in variant or variant in q_text:
            return 0.9

    # 关键词匹配（从问答对关键词标签
    if qa.keywords:
        kws = [k.strip() for k in qa.keywords.replace(",", "，").split(",") if k.strip()]
        match_count = sum(1 for kw in kws if kw and kw in q_text)
        if match_count and kws:
            return 0.6 + 0.3 * (match_count / len(kws))

    # 文本包含匹配
    if q_text in qa.question or qa.question in q_text:
        return 0.7

    return 0.0


def match_qa_pairs(db: Session, question: str,
                   top_n: int = 3,
                   category: Optional[str] = None,
                   min_score: float = 0.6) -> List[Dict]:
    """匹配问答对（关键词+文本相似度混合匹配）

    返回匹配到的问答对列表（按分数排序）
    """
    if not question or not question.strip():
        return []

    # 查询所有启用的问答对
    q = db.query(RagQaPair).filter(RagQaPair.status == 1)
    if category:
        q = q.filter(RagQaPair.category == category)
    all_qas = q.all()
    if not all_qas:
        return []

    # 计算每个问答对的匹配分数
    scored = []
    for qa in all_qas:
        # 关键词/文本匹配分数
        score = _calc_keyword_match_score(question, qa)
        if score >= min_score:
            scored.append((qa, score))

    # 按分数排序，取 top_n
    scored.sort(key=lambda x: x[1], reverse=True)

    results = []
    for qa, score in scored[:top_n]:
        results.append({
            "id": qa.id,
            "question": qa.question,
            "answer": qa.answer,
            "source": qa.source or "",
            "score": score,
            "category": qa.category or "",
        })
    return results


def try_answer_from_qa_pairs(db: Session, question: str,
                             category: Optional[str] = None) -> Optional[Dict]:
    """尝试从问答对中获取答案，如果命中则返回答案，否则返回 None

    返回格式: {answer, source, matched_from_qa, score}
    """
    matches = match_qa_pairs(db, question, top_n=1, category=category, min_score=0.85)
    if not matches:
        return None

    match = matches[0]
    qa_id = match["id"]

    # 更新命中次数
    qa = get_qa_pair(db, qa_id)
    if qa:
        qa.hit_count = (qa.hit_count or 0) + 1
        db.commit()

    return {
        "answer": match["answer"],
        "source": match["source"] or "",
        "matched_from_qa": True,
        "score": match["score"],
        "qa_question": match["question"],
    }
