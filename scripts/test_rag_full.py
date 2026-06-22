"""测试 rag_service 完整流程"""
import sys
sys.path.insert(0, ".")

from app.services import rag_service
from app.database import SessionLocal

db = SessionLocal()
result = rag_service.ask_question(
    db,
    "孙悟空三打白骨精是哪一回？",
    book_codes=["xiyouji"],
    top_k=5,
)
print("回答:\n" + result["answer"])
print(f"\n共 {len(result['sources'])} 个参考段落")
for s in result['sources']:
    print(f"  - 《{s['book_name']}》第{s['chapter_no']}回 {s['chapter_title']} score={s['score']:.2f}")

db.close()
