"""
对话管理服务
提供对话历史的存储、查询和管理功能
"""
import uuid
from typing import Optional, List, Dict
from sqlalchemy.orm import Session
from app.models.conversation import Conversation
from app.services import rag_service as rag
from datetime import datetime, timedelta

logger = rag.logger  # 复用 RAG 的日志


def create_session() -> str:
    """
    创建新会话 ID
    """
    return str(uuid.uuid4())


def get_conversation(db: Session, session_id: str) -> Optional[Conversation]:
    """
    获取会话记录
    """
    return db.query(Conversation).filter(
        Conversation.session_id == session_id
    ).first()


def create_conversation(db: Session, session_id: str, user_id: Optional[int] = None) -> Conversation:
    """
    创建新对话记录
    """
    conv = Conversation(
        session_id=session_id,
        user_id=user_id,
        messages=[],
        book_codes=[],
    )
    db.add(conv)
    db.commit()
    db.refresh(conv)
    return conv


def update_conversation(db: Session, session_id: str, messages: List[Dict], book_codes: Optional[List[str]] = None):
    """
    更新对话记录
    """
    conv = get_conversation(db, session_id)
    if conv:
        conv.messages = messages
        if book_codes is not None:
            conv.book_codes = book_codes
        db.commit()
        db.refresh(conv)
        return conv
    return None


def delete_conversation(db: Session, session_id: str):
    """
    删除对话记录
    """
    conv = get_conversation(db, session_id)
    if conv:
        db.delete(conv)
        db.commit()
        return True
    return False


def list_conversations(db: Session, user_id: Optional[int] = None, limit: int = 20) -> List[Conversation]:
    """
    获取对话列表
    """
    query = db.query(Conversation)
    if user_id is not None:
        query = query.filter(Conversation.user_id == user_id)
    return query.order_by(Conversation.updated_at.desc()).limit(limit).all()


def ask_with_memory(db: Session, session_id: str, question: str,
                    book_codes: Optional[List[str]] = None, top_k: int = 0) -> Dict:
    """
    带记忆的问答接口
    """
    # 获取或创建会话
    conv = get_conversation(db, session_id)
    if not conv:
        conv = create_conversation(db, session_id)
    
    # 获取历史消息（只保留最近的几条，避免 token 过多）
    max_history = 5  # 最多保留5轮对话历史
    history_messages = conv.messages[-max_history:]
    
    # 调用 RAG 服务（带历史）
    result = rag.ask_question_with_history(
        db=db,
        question=question,
        history=history_messages,
        book_codes=book_codes or conv.book_codes,
        top_k=top_k
    )
    
    # 更新对话历史
    new_messages = history_messages + [
        {"role": "user", "content": question, "timestamp": datetime.now().isoformat()},
        {"role": "assistant", "content": result.get("answer", ""), "timestamp": datetime.now().isoformat()}
    ]
    
    update_conversation(db, session_id, new_messages, book_codes)
    
    return result


def get_conversation_history(db: Session, session_id: str) -> List[Dict]:
    """
    获取对话历史
    """
    conv = get_conversation(db, session_id)
    return conv.messages if conv else []


def clear_conversation(db: Session, session_id: str):
    """
    清空对话历史（保留会话）
    """
    conv = get_conversation(db, session_id)
    if conv:
        conv.messages = []
        db.commit()
        db.refresh(conv)
        return True
    return False


def cleanup_old_conversations(db: Session, days: int = 30):
    """
    清理过期对话（默认保留30天）
    """
    cutoff_date = datetime.now() - timedelta(days=days)
    count = db.query(Conversation).filter(
        Conversation.updated_at < cutoff_date
    ).delete()
    db.commit()
    logger.info(f"[Conversation] 清理过期对话 {count} 条")
    return count