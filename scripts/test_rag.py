import sys
sys.path.insert(0, ".")
from app.services.rag_service import retrieve
from app.database import SessionLocal

db = SessionLocal()

for question in [
    "孙悟空三打白骨精是哪一回？",
    "关羽过五关斩六将",
    "林黛玉焚稿",
    "武松打虎",
]:
    print(f"\n问题: {question}")
    results = retrieve(db, question, top_k=3)
    for i, r in enumerate(results, 1):
        print(f"  [{i}] 《{r['book_name']}》第{r['chapter_no']}回 {r['chapter_title']} (score={r['score']:.3f})")
        print(f"       内容: {r['text'][:60]}...")
db.close()
