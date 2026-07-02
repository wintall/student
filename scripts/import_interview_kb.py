from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.database import SessionLocal
from app.models.rag_knowledge import RagDocument, RagKnowledgeBase
from app.models.user import User
from app.schemas.rag_knowledge import KnowledgeBaseCreate
from app.services import rag_knowledge_service as rag_service


KB_NAME = "AI面试问题知识库"
DOC_TITLE = "面试问题总结_v.11"


def read_interview_file() -> str:
    desktop = Path.home() / "Desktop"
    candidates = list(desktop.glob("*v.11.md")) + list(desktop.glob("*面试问题*.md"))
    if not candidates:
        raise FileNotFoundError("未在桌面找到 面试问题总结_v.11.md")
    path = candidates[0]
    for encoding in ("utf-8", "utf-8-sig", "gbk"):
        try:
            return path.read_text(encoding=encoding), path
        except UnicodeDecodeError:
            continue
    raise UnicodeDecodeError("unknown", b"", 0, 1, f"无法识别文件编码：{path}")


def main():
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == "admin", User.is_deleted == False).first()
        if not user:
            raise RuntimeError("未找到 admin 用户")

        for kb in db.query(RagKnowledgeBase).filter(
            RagKnowledgeBase.owner_id == user.id,
            RagKnowledgeBase.is_deleted == False,
            RagKnowledgeBase.document_count == 0,
            RagKnowledgeBase.chunk_count == 0,
        ).all():
            if "AI" in (kb.name or "") and kb.name != KB_NAME:
                kb.soft_delete()
        db.commit()

        kb = db.query(RagKnowledgeBase).filter(
            RagKnowledgeBase.name == KB_NAME,
            RagKnowledgeBase.is_deleted == False,
        ).first()
        if not kb:
            kb = rag_service.create_kb(
                db,
                user,
                KnowledgeBaseCreate(
                    name=KB_NAME,
                    description="AI、大模型应用开发、RAG、Agent、Milvus 等面试知识整理，可用于学习辅导和知识问答。",
                    scope_type="public",
                    chunk_strategy="paragraph",
                    chunk_size=700,
                    chunk_overlap=100,
                    retrieval_mode="hybrid",
                    default_top_k=5,
                    default_min_score=45,
                    vector_weight=62,
                    bm25_weight=28,
                    title_weight=10,
                    core_weight=35,
                ),
            )

        existing = db.query(RagDocument).filter(
            RagDocument.kb_id == kb.id,
            RagDocument.title == DOC_TITLE,
            RagDocument.is_deleted == False,
        ).first()
        if existing:
            print({
                "status": "exists",
                "kb_id": kb.id,
                "kb_name": kb.name,
                "doc_id": existing.id,
                "chunks": existing.chunk_count,
                "chars": existing.char_count,
            })
            return

        text, path = read_interview_file()
        doc = rag_service.import_text(db, user, kb.id, DOC_TITLE, text)
        print({
            "status": "imported",
            "source_path": str(path),
            "kb_id": kb.id,
            "kb_name": kb.name,
            "doc_id": doc.id,
            "doc_status": doc.status,
            "chunks": doc.chunk_count,
            "chars": doc.char_count,
        })
    finally:
        db.close()


if __name__ == "__main__":
    main()
