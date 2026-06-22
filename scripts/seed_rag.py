"""
RAG 四大名著知识库初始化脚本
用法:
    python -m scripts.seed_rag            # 追加写入 (不删已有)
    python -m scripts.seed_rag --reset    # 删除后重新写入
"""
import argparse
import time
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("rag_seed")

from pymilvus import MilvusClient

# ---- 允许独立运行脚本 ----
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from app.database import SessionLocal
from app.models.rag import RagBook, RagSection
from scripts._four_books_data import DATA, BOOKS


COL_NAME = "sic_rag_four_books_v1"
VECTOR_DIM = 768
MILVUS_URI = "http://127.0.0.1:19530"


# ======================================================================
# 建表
# ======================================================================
def _ensure_tables():
    """确保 MySQL 表存在"""
    from app.database import engine
    from sqlalchemy import inspect
    insp = inspect(engine)
    existing = insp.get_table_names()
    for table_name in ("rag_book", "rag_section"):
        if table_name not in existing:
            logger.warning(f"[MySQL] 表 {table_name} 不存在，请先运行 alembic upgrade head")
        else:
            logger.info(f"[MySQL] 表 {table_name} 已存在")


# ======================================================================
# seed MySQL
# ======================================================================
def seed_mysql(db, reset=False):
    """把四大名著基础数据写入 MySQL。返回 records 供 milvus 使用
    records 格式: [(mysql_rag_section_id, text), ...]
    """
    if reset:
        logger.info("[MySQL] 清空旧数据 ...")
        try:
            db.execute(text("DELETE FROM rag_section WHERE 1=1"))
            db.execute(text("DELETE FROM rag_book WHERE 1=1"))
            db.commit()
        except Exception as e:
            db.rollback()
            logger.error(f"[MySQL] 清空失败: {e}")
            raise

    # 写入 book
    book_map = {}  # code -> id
    for code, info in BOOKS.items():
        book = db.query(RagBook).filter(RagBook.code == code).first()
        if book is None:
            book = RagBook(
                code=code,
                name=info["name"],
                author=info.get("author"),
                dynasty=info.get("dynasty"),
                summary=info.get("summary"),
                total_chapters=info.get("total_chapters", 0),
                total_sections=0,
                status=1,
            )
            db.add(book)
            db.flush()
        book_map[code] = book.id

    # 写入 section
    records = []
    for item in DATA:
        (code, chapter_no, chapter_title, section_no, text_content, keywords) = item
        section = db.query(RagSection).filter(
            RagSection.book_id == book_map[code],
            RagSection.chapter_no == int(chapter_no),
            RagSection.section_no == int(section_no),
        ).first()
        if section is None:
            section = RagSection(
                book_id=book_map[code],
                chapter_no=int(chapter_no),
                chapter_title=str(chapter_title),
                section_no=int(section_no),
                text=text_content,
                keywords=str(keywords) if keywords else None,
                status=1,
            )
            db.add(section)
            db.flush()
        # 为 milvus 准备 (id, text)
        records.append((section.id, text_content))

    # 更新每本书的段落数
    for code, bid in book_map.items():
        cnt = db.query(RagSection).filter(RagSection.book_id == bid).count()
        b = db.get(RagBook, bid)
        if b:
            b.total_sections = cnt

    db.commit()
    logger.info(f"[MySQL] 写入 {len(book_map)} 本书 / {len(records)} 段")
    return records


# ======================================================================
# seed Milvus
# ======================================================================
def seed_milvus(records, reset=False):
    """把记录写入 milvus 向量库"""
    uri = MILVUS_URI
    col_name = COL_NAME
    logging.info(f"[Milvus] 连接: {uri}")
    mc = MilvusClient(uri=uri)

    # 生成向量 - 直接用 transformers（避免 Windows symlink 问题）
    logging.info("[Milvus] 加载 embedding 模型 (shibing624/text2vec-base-chinese) ...")
    import numpy as np
    import torch
    import torch.nn.functional as F
    from transformers import AutoTokenizer, AutoModel

    tokenizer = AutoTokenizer.from_pretrained("shibing624/text2vec-base-chinese")
    model = AutoModel.from_pretrained("shibing624/text2vec-base-chinese")
    model.eval()

    texts = [r[1] for r in records]
    logging.info(f"[Milvus] 生成 {len(texts)} 段文本向量 ...")
    t0 = time.time()
    BATCH = 32
    vectors = []
    for i in range(0, len(texts), BATCH):
        batch = texts[i:i + BATCH]
        enc = tokenizer(batch, padding=True, truncation=True, return_tensors="pt", max_length=256)
        with torch.no_grad():
            out = model(**enc)
        vec = out.last_hidden_state[:, 0, :]  # CLS token
        vec = F.normalize(vec, p=2, dim=1)
        vectors.append(vec.numpy())
        logging.info(f"  -> 已生成 {min(i + BATCH, len(texts))}/{len(texts)}")
    vectors = np.vstack(vectors)
    logging.info(f"[Milvus] 向量生成完成 ({time.time() - t0:.1f}s, dim={vectors.shape[1]})")

    if reset and mc.has_collection(col_name):
        logging.info(f"[Milvus] 删除旧集合 {col_name}")
        mc.drop_collection(col_name)

    if not mc.has_collection(col_name):
        logging.info(f"[Milvus] 创建集合 {col_name} (dim={VECTOR_DIM})")
        mc.create_collection(
            collection_name=col_name,
            dimension=VECTOR_DIM,
            metric_type="COSINE",
            id_type="int",
            auto_id=False,
            primary_field_name="id",
            vector_field_name="embedding",
        )

    # 准备数据
    milvus_data = []
    for (sec_id, _), vec in zip(records, vectors):
        milvus_data.append({"id": int(sec_id), "embedding": vec.tolist()})

    # 批量插入
    logging.info(f"[Milvus] 插入 {len(milvus_data)} 条向量 ...")
    t0 = time.time()
    batch_size = 100
    for i in range(0, len(milvus_data), batch_size):
        batch = milvus_data[i:i + batch_size]
        mc.insert(collection_name=col_name, data=batch)
        logging.info(f"  -> 已插入 {min(i + batch_size, len(milvus_data))}/{len(milvus_data)}")
    logging.info(f"[Milvus] 插入完成 ({time.time() - t0:.1f}s)")

    # 建索引
    try:
        mc.create_index(
            collection_name=col_name,
            vector_field_name="embedding",
            index_params={
                "metric_type": "COSINE",
                "index_type": "AUTOINDEX",
                "params": {},
            },
        )
        mc.load_collection(col_name)
        logging.info("[Milvus] 索引已建立 & 集合已加载")
    except Exception as e:
        logging.warning(f"[Milvus] 索引建立提示 (非致命): {e}")


# ======================================================================
# 主入口
# ======================================================================
def main():
    parser = argparse.ArgumentParser(description="RAG 四大名著知识库初始化")
    parser.add_argument("--reset", action="store_true", help="删除旧数据后重新写入")
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("开始写入 RAG 四大名著知识库 ...")
    logger.info("=" * 60)

    _ensure_tables()

    db = SessionLocal()
    try:
        records = seed_mysql(db, reset=args.reset)
        seed_milvus(records, reset=args.reset)
    except Exception as e:
        logger.exception(f"[FATAL] 写入失败: {e}")
        raise
    finally:
        db.close()

    logger.info("=" * 60)
    logger.info("✅ RAG 四大名著知识库初始化完成!")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
