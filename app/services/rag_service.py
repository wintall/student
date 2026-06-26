"""RAG 检索主服务 - 基于四大名著知识库的问答
- 向量检索：用户问题 → embedding → Milvus 搜索 → 返回最相关段落
- 答案生成：检索到的段落 + 用户问题 → DeepSeek Chat 生成自然语言回答
- 降级机制：Milvus 不可用时，自动降级为 MySQL LIKE 关键词召回
- 性能优化：并行检索、超时控制、结果缓存
"""

import json
import logging
import time
import urllib.request
from typing import Dict, List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import lru_cache

from sqlalchemy.orm import Session

from app.config import settings
from app.models.rag import RagBook, RagSection
from app.services import rag_qa_service

logger = logging.getLogger("app")

# ====== 性能配置 ======
RAG_TIMEOUT = int(getattr(settings, "RAG_TIMEOUT", 30))  # 总超时时间（秒）
VECTOR_SEARCH_TIMEOUT = int(getattr(settings, "RAG_VECTOR_TIMEOUT", 15))  # 向量检索超时
KEYWORD_SEARCH_TIMEOUT = int(getattr(settings, "RAG_KEYWORD_TIMEOUT", 10))  # 关键词检索超时
LLM_TIMEOUT = int(getattr(settings, "RAG_LLM_TIMEOUT", 30))  # LLM调用超时
CACHE_SIZE = int(getattr(settings, "RAG_CACHE_SIZE", 100))  # 缓存大小

# ====== 嵌入模型配置 ======
_tokenizer = None
_model = None
_embedding_model_name = "maidalun1020/bce-embedding-base_v1"  # 更适合中文的模型

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
    """文本向量化，带超时控制"""
    try:
        import torch
        tokenizer, model, _ = _get_embedding_model()
        # 针对古典文学优化：截断到512token，保留更多上下文
        enc = tokenizer([text], padding=True, truncation=True, return_tensors="pt", max_length=512)
        with torch.no_grad():
            out = model(**enc)
        # 使用 CLS token 表示 + 平均池化，增强语义表示
        cls_vec = out.last_hidden_state[:, 0, :]
        mean_vec = out.last_hidden_state.mean(dim=1)
        vec = torch.cat([cls_vec, mean_vec], dim=1)
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
        # 检查返回值是否为 None
        if hits is None:
            logger.warning("[RAG] Milvus 返回 None，跳过向量检索")
            return []
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


# ====== MySQL 关键词召回（优化版） ======

# 停用词列表（四大名著场景常见停用词）
STOPWORDS = {
    '的', '了', '和', '是', '就', '都', '而', '及', '与', '着', '或', '一个',
    '没有', '我们', '你们', '他们', '它们', '这个', '那个', '这些', '那些',
    '什么', '怎么', '为什么', '如何', '哪里', '何时', '多少', '一些', '许多',
    '可以', '可能', '应该', '必须', '需要', '会', '能', '要', '想', '知道',
    '说', '看', '听', '做', '有', '在', '到', '去', '来', '上', '下', '进', '出',
    '过', '起', '开', '关', '走', '跑', '跳', '飞', '吃', '喝', '睡', '死', '生',
    '打', '杀', '骂', '笑', '哭', '爱', '恨', '情', '仇', '恩', '怨', '功', '过',
    # 四大名著专属停用词
    '曰', '道', '云', '言', '谓', '答', '问', '应', '诺', '拜', '谢', '辞',
    '进', '退', '战', '守', '攻', '防', '胜', '败', '亡', '存', '兴', '衰',
}

def _extract_keywords(question: str) -> list:
    """
    使用 jieba 分词提取关键词，只保留名词类词汇
    返回按重要性排序的关键词列表
    """
    try:
        import jieba
        import jieba.posseg as pseg
    except ImportError:
        logger.warning("[RAG] jieba 未安装，使用简单分词")
        return _simple_tokenize(question)
    
    # 清理文本，只保留中文和字母数字
    cleaned = "".join(ch for ch in question if ch.isalnum() or "\u4e00" <= ch <= "\u9fff")
    
    # 使用 jieba 分词并标注词性
    words = pseg.cut(cleaned)
    
    keywords = []
    for word, flag in words:
        # 只保留名词类词汇（n 开头的词性）
        # n: 名词, nr: 人名, ns: 地名, nt: 机构名, nz: 其他专名, nl: 名词性惯用语, ng: 名词性语素
        if flag.startswith('n') and len(word) >= 2 and word not in STOPWORDS:
            keywords.append(word)
    
    return list(set(keywords))  # 去重

def _simple_tokenize(question: str) -> list:
    """
    简单分词回退方案（当 jieba 不可用时）
    """
    cleaned = "".join(ch for ch in question if ch.isalnum() or "\u4e00" <= ch <= "\u9fff")
    
    # 四大名著常见角色名和关键词（优先级最高）
    famous_entities = [
        # 三国演义
        '刘备', '关羽', '张飞', '诸葛亮', '曹操', '孙权', '周瑜', '赵云', '马超', '黄忠',
        '吕布', '董卓', '袁绍', '袁术', '刘表', '刘璋', '刘禅', '司马懿', '司马昭', '司马炎',
        # 水浒传
        '宋江', '卢俊义', '吴用', '公孙胜', '林冲', '花荣', '鲁智深', '武松', '李逵', '燕青',
        '晁盖', '杨志', '柴进', '阮小二', '阮小五', '阮小七', '张顺', '戴宗', '秦明', '呼延灼',
        # 西游记
        '唐僧', '孙悟空', '猪八戒', '沙僧', '如来', '观音', '玉帝', '牛魔王', '铁扇公主',
        '红孩儿', '白骨精', '蜘蛛精', '玉兔精', '太上老君', '太白金星', '二郎神', '哪吒',
        # 红楼梦
        '贾宝玉', '林黛玉', '薛宝钗', '王熙凤', '贾母', '贾政', '王夫人', '探春', '迎春',
        '惜春', '史湘云', '妙玉', '袭人', '晴雯', '香菱', '刘姥姥', '贾珍', '贾琏', '薛蟠',
        # 地名
        '桃园', '赤壁', '华容道', '荆州', '益州', '建业', '长安', '洛阳', '梁山水泊',
        '花果山', '水帘洞', '火焰山', '盘丝洞', '大观园', '荣国府', '宁国府',
        # 书名
        '三国演义', '水浒传', '西游记', '红楼梦', '三国志', '水浒', '西游', '红楼'
    ]
    
    keywords = []
    
    # 优先匹配名著实体
    for entity in famous_entities:
        if entity in cleaned and entity not in keywords:
            keywords.append(entity)
    
    # 补充 2-3 字词汇
    for size in (3, 2):
        for j in range(0, len(cleaned) - size + 1):
            w = cleaned[j:j + size]
            if w and w not in keywords and w not in STOPWORDS:
                keywords.append(w)
            if len(keywords) >= 15:
                break
        if len(keywords) >= 15:
            break
    
    return keywords

def _retrieve_by_keyword(db: Session, question: str,
                         book_codes: Optional[List[str]], top_k: int) -> List[Dict]:
    logger.info("[RAG] 关键词检索（优化版）")
    from sqlalchemy import or_

    # 使用优化的关键词提取策略
    kws = _extract_keywords(question)
    
    # 如果没有提取到关键词，使用原始问题
    if not kws:
        cleaned = "".join(ch for ch in question if ch.isalnum() or "\u4e00" <= ch <= "\u9fff")
        kws = [cleaned]
    
    logger.debug(f"[RAG] 提取关键词: {kws}")
    
    query = db.query(RagSection).join(RagBook, RagSection.book_id == RagBook.id).filter(
        RagSection.status == 1, RagBook.status == 1
    )
    if book_codes:
        query = query.filter(RagBook.code.in_(book_codes))
    if kws:
        # 构建更精确的查询条件
        conditions = []
        for w in kws:
            # 对短词（2-3字）使用精确匹配，对长词使用模糊匹配
            if len(w) <= 3:
                conditions.append(RagSection.text.like(f"%{w}%"))
                conditions.append(RagSection.chapter_title.like(f"%{w}%"))
            else:
                # 长词使用更精确的匹配
                conditions.append(RagSection.text.contains(w))
        
        if conditions:
            query = query.filter(or_(*conditions))

    items = query.limit(top_k * 3).all()
    scored = []
    for it in items:
        text = (it.text or "").lower()
        title = (it.chapter_title or "").lower()
        hit = 0
        for w in kws:
            w_lower = w.lower()
            if w_lower in text:
                hit += 1
            if w_lower in title:
                hit += 2  # 标题匹配权重更高
        if hit > 0:
            scored.append({
                "id": it.id,
                "book_code": it.book.code,
                "book_name": it.book.name,
                "chapter_no": it.chapter_no or 0,
                "chapter_title": it.chapter_title or "",
                "section_no": it.section_no or 0,
                "text": it.text or "",
                "keywords": ", ".join(kws),
                "score": float(hit) / max(1, len(kws)),
            })
    # 按分数排序，分数相同则按章节号排序
    scored.sort(key=lambda r: (r["score"], r["chapter_no"]), reverse=True)
    return scored[:top_k]


# ====== 统一入口（并行版本） ======

def _timeout_wrapper(func, timeout, *args, **kwargs):
    """带超时的函数包装器"""
    import threading
    result = [None]
    exception = [None]
    event = threading.Event()
    
    def worker():
        try:
            result[0] = func(*args, **kwargs)
        except Exception as e:
            exception[0] = e
        event.set()
    
    thread = threading.Thread(target=worker)
    thread.daemon = True
    thread.start()
    event.wait(timeout=timeout)
    
    if exception[0]:
        raise exception[0]
    
    # 超时情况下返回空列表，避免 None 迭代错误
    if result[0] is None:
        raise TimeoutError(f"Function {func.__name__} timed out after {timeout}s")
    
    return result[0]

def retrieve(db: Session, question: str,
             book_codes: Optional[List[str]] = None, top_k: int = 0) -> List[Dict]:
    if not question or not question.strip():
        return []
    top_k = top_k or int(getattr(settings, "RAG_TOP_K", 5))

    t0 = time.time()
    
    vec_results = []
    kw_results = []
    
    # 并行执行向量检索和关键词检索
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = {}
        
        # 提交向量检索任务（带超时）
        vec_future = executor.submit(
            _timeout_wrapper,
            _retrieve_by_vector, VECTOR_SEARCH_TIMEOUT,
            question, book_codes, top_k
        )
        futures[vec_future] = "vector"
        
        # 提交关键词检索任务（带超时）
        kw_future = executor.submit(
            _timeout_wrapper,
            _retrieve_by_keyword, KEYWORD_SEARCH_TIMEOUT,
            db, question, book_codes, top_k
        )
        futures[kw_future] = "keyword"
        
        # 收集结果（不等待超时任务）
        for future in as_completed(futures, timeout=RAG_TIMEOUT):
            task_name = futures[future]
            try:
                result = future.result()
                # 检查结果是否为 None
                if result is None:
                    logger.warning(f"[RAG] {task_name} 检索返回 None")
                    continue
                if task_name == "vector":
                    vec_results = result
                else:
                    kw_results = result
            except TimeoutError:
                logger.warning(f"[RAG] {task_name} 检索超时")
            except Exception as e:
                logger.warning(f"[RAG] {task_name} 检索失败: {e}")
    
    # 融合结果：去重并按分数排序
    seen_ids = set()
    merged = []
    
    # 先添加向量检索结果（通常更相关）
    for r in vec_results:
        if r["id"] not in seen_ids:
            seen_ids.add(r["id"])
            merged.append(r)
    
    # 添加关键词检索中未出现的结果作为补充
    for r in kw_results:
        if r["id"] not in seen_ids:
            seen_ids.add(r["id"])
            r["score"] = r["score"] * 0.7
            merged.append(r)
    
    # 按分数排序，取前 top_k
    merged.sort(key=lambda x: x["score"], reverse=True)
    final_results = merged[:top_k]
    
    logger.info(f"[RAG] 检索完成 ({time.time()-t0:.2f}s) 向量命中 {len(vec_results)} 段, 关键词命中 {len(kw_results)} 段, 融合后 {len(final_results)} 段")
    return final_results


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
        "max_tokens": 1000,  # 增加回答长度
        "temperature": 0.3,  # 降低随机性，更严谨
        "top_p": 0.9,
    }
    try:
        req = urllib.request.Request(
            url, data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json",
                     "Authorization": f"Bearer {settings.DEEPSEEK_API_KEY}"},
            method="POST",
        )
        # 使用配置的超时时间
        with urllib.request.urlopen(req, timeout=LLM_TIMEOUT) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        choice = data.get("choices", [{}])[0] if data.get("choices") else {}
        msg = choice.get("message", {}) if isinstance(choice, dict) else {}
        reply = msg.get("content", "") if isinstance(msg, dict) else ""
        return reply.strip() if isinstance(reply, str) and reply.strip() else None
    except Exception as e:
        logger.error(f"[RAG] 调用 DeepSeek 失败: {e}")
        return None

def _classify_question(question: str) -> str:
    """问题类型分类"""
    question = question.lower()
    
    # 人物相关问题
    person_keywords = ['是谁', '何人', '谁', '人物', '生平', '出身', '结局']
    if any(k in question for k in person_keywords):
        return "character"
    
    # 情节相关问题
    plot_keywords = ['情节', '故事', '经过', '过程', '起因', '结果', '如何', '为什么', '缘由']
    if any(k in question for k in plot_keywords):
        return "plot"
    
    # 地点相关问题
    location_keywords = ['哪里', '何处', '地方', '位置', '地点']
    if any(k in question for k in location_keywords):
        return "location"
    
    # 评价分析问题
    analysis_keywords = ['评价', '分析', '观点', '看法', '意义', '价值', '形象']
    if any(k in question for k in analysis_keywords):
        return "analysis"
    
    # 关系问题
    relation_keywords = ['关系', '与', '和', '之间', '朋友', '敌人', '亲属']
    if any(k in question for k in relation_keywords):
        return "relation"
    
    # 细节问题
    detail_keywords = ['第几', '何时', '多少', '什么', '哪', '几']
    if any(k in question for k in detail_keywords):
        return "detail"
    
    return "general"

def answer_by_llm(question: str, sources: List[Dict], history: Optional[List[Dict]] = None) -> str:
    """
    LLM 答案生成（支持历史消息）
    """
    if not sources:
        return "知识库中没有找到相关内容。可以换一个关键词再试试，或者提供更多上下文信息。"

    # 问题分类
    question_type = _classify_question(question)
    
    # 构建对话历史（如果有）
    history_str = ""
    if history and isinstance(history, list) and len(history) > 0:
        history_lines = []
        for msg in history:
            role = msg.get("role", "")
            content = msg.get("content", "")
            if role and content:
                role_cn = "用户" if role == "user" else "助手"
                history_lines.append(f"{role_cn}：{content}")
        if history_lines:
            history_str = "\n".join(history_lines) + "\n\n"
    
    # 构建更有效的系统提示词
    system_prompt = f"""
你是一位精通中国古典文学的学者，尤其熟悉四大名著（《三国演义》《水浒传》《西游记》《红楼梦》）。

## 核心指令
1. **严格基于提供的知识库片段回答**：你的回答必须完全基于用户提供的检索结果，不得引用任何外部知识或虚构内容。
2. **明确标注来源**：在回答中适当位置引用出处（如：《三国演义》第XX回）。
3. **答案结构清晰**：使用分点、分段等方式组织回答，提高可读性。
4. **处理信息缺失**：如果知识库中没有足够信息回答问题，明确说明"根据现有知识库，无法回答此问题"。
5. **保持语言风格**：使用正式、文雅的中文表达，符合古典文学讨论的语境。
6. **理解上下文**：注意结合对话历史理解当前问题，特别是代词指代（如"他"、"这个"、"之前提到的"等）。

## 当前问题类型：{question_type}
- **character（人物类）**：详细介绍人物身份、性格、主要事迹和结局
- **plot（情节类）**：清晰叙述事件的起因、经过和结果
- **location（地点类）**：描述地点的背景、特点和相关情节
- **analysis（分析类）**：基于文本进行合理分析和评价
- **relation（关系类）**：分析人物之间的关系和互动
- **detail（细节类）**：准确回答具体细节问题

## 输出格式要求
- 开头直接给出答案
- 关键信息用加粗表示
- 引用内容使用书名号《》
- 分段清晰，逻辑连贯

请务必遵守以上规则，不要生成与知识库无关的内容。
"""
    
    # 构建用户消息，优化片段展示方式
    parts = []
    max_sources = 3  # 限制参考资料数量，减少 LLM 调用时间
    for i, s in enumerate(sources[:max_sources]):
        book_info = f"《{s['book_name']}》"
        if s.get("chapter_title"):
            book_info += f" · {s['chapter_title']}"
        elif s.get("chapter_no"):
            book_info += f" · 第{s['chapter_no']}回"
        
        # 对长文本进行截断处理
        text = s["text"]
        if len(text) > 300:  # 进一步缩短文本长度
            text = text[:300] + "..."
        
        parts.append(f"【参考资料{i+1}】{book_info}\n{s['text']}")
    
    user_message = f"""
{history_str}用户问题：{question.strip()}

参考资料：
{"\\n".join(parts)}

请根据以上参考资料回答用户问题。
"""

    reply = _call_deepseek_chat(system_prompt, user_message)
    if reply:
        return reply

    # 降级：直接拼接片段原文
    fallback = ["以下是知识库检索到的相关片段（LLM 不可用）：\n"]
    for s in sources[:max_sources]:
        loc = f"《{s['book_name']}》"
        if s.get("chapter_title"):
            loc += f"（{s['chapter_title']}）"
        elif s.get("chapter_no"):
            loc += f"（第{s['chapter_no']}回）"
        fallback.append(f"● {loc}\n{s['text']}\n")
    return "\n".join(fallback)


# ====== 对外主入口 ======

@lru_cache(maxsize=CACHE_SIZE)
def _cached_retrieve(question_hash: str, book_codes_str: str, top_k: int) -> str:
    """检索结果缓存（使用问题哈希作为key）"""
    # 实际缓存逻辑在调用层处理
    return ""

def ask_question(db: Session, question: str,
                 book_codes: Optional[List[str]] = None, top_k: int = 0) -> Dict:
    """
    RAG 问答主入口（无历史版本）
    """
    return ask_question_with_history(db, question, None, book_codes, top_k)


def ask_question_with_history(db: Session, question: str,
                              history: Optional[List[Dict]] = None,
                              book_codes: Optional[List[str]] = None,
                              top_k: int = 0) -> Dict:
    """
    RAG 问答主入口（支持历史消息 + 问答对快速匹配）
    
    Args:
        db: 数据库会话
        question: 用户问题
        history: 对话历史 [{role, content, timestamp}, ...]
        book_codes: 书籍筛选列表
        top_k: 返回结果数量
    """
    question = (question or "").strip()
    if not question:
        return {"answer": "请先输入问题。", "sources": [],
                "question": "", "book_filter": [], "error": None}

    logger.info(f"[RAG] 新问题: {question} (book_codes={book_codes}, history_len={len(history) if history else 0})")
    t0 = time.time()
    
    # 步骤 1: 尝试从问答对直接匹配（快速回答，节省 LLM 调用）
    try:
        qa_match = rag_qa_service.try_answer_from_qa_pairs(
            db, question, category=book_codes[0] if book_codes and len(book_codes) == 1 else None
        )
        if qa_match:
            answer = qa_match["answer"]
            source = qa_match.get("source", "")
            elapsed = time.time() - t0
            logger.info(f"[RAG] 问答对命中 ({elapsed:.2f}s): {qa_match.get('qa_question', '')}")
            return {
                "answer": answer,
                "sources": [{
                    "id": qa_match.get("id", 0),
                    "book_code": "qa_pair",
                    "book_name": source or "常见问答",
                    "chapter_no": 0,
                    "chapter_title": "",
                    "section_no": 0,
                    "text": answer,
                    "keywords": "",
                    "score": qa_match.get("score", 0.9),
                }],
                "question": question,
                "book_filter": book_codes or [],
                "time": round(elapsed, 2),
                "error": None,
                "matched_from_qa": True,
            }
    except Exception as e:
        logger.warning(f"[RAG] 问答对匹配失败，继续走向量检索: {e}")
    
    # 步骤 2: 传统 RAG 流程（向量检索 + LLM 回答）
    try:
        def _inner_task():
            sources = retrieve(db, question, book_codes=book_codes, top_k=top_k)
            answer = answer_by_llm(question, sources, history)
            return answer, sources
        
        answer, sources = _timeout_wrapper(_inner_task, RAG_TIMEOUT)
        
        elapsed = time.time() - t0
        logger.info(f"[RAG] 回答生成完成 ({elapsed:.2f}s)")
        return {"answer": answer, "sources": sources,
                "question": question, "book_filter": book_codes or [],
                "time": round(elapsed, 2), "error": None}
    
    except TimeoutError:
        logger.error(f"[RAG] 回答超时 ({time.time()-t0:.2f}s)")
        return {
            "answer": "请求超时，请稍后重试或简化问题。",
            "sources": [],
            "question": question,
            "book_filter": book_codes or [],
            "time": round(time.time() - t0, 2),
            "error": "timeout"
        }
    except Exception as e:
        logger.error(f"[RAG] 处理异常: {e}")
        return {
            "answer": f"系统繁忙，请稍后重试。错误信息：{str(e)[:50]}",
            "sources": [],
            "question": question,
            "book_filter": book_codes or [],
            "time": round(time.time() - t0, 2),
            "error": str(e)[:50]
        }


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
