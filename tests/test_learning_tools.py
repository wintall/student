from app.services.campus_agent.learning_tools import (
    _filter_sources_for_intent,
    _poetry_reference_keywords,
    detect_learning_intent,
    should_use_learning,
)
from app.services.campus_agent.orchestrator import detect_auto_mode, detect_capability_override


def test_poetry_appreciation_by_title():
    message = "赏析一下《静夜思》"

    assert should_use_learning(message)
    assert detect_learning_intent(message) == "poetry_appreciation"
    assert detect_auto_mode(message) == "study"


def test_poetry_appreciation_without_book_title_marks():
    message = "赏析一下将进酒吧"

    assert should_use_learning(message)
    assert detect_learning_intent(message) == "poetry_appreciation"
    assert detect_auto_mode(message) == "study"
    assert "将进酒" in _poetry_reference_keywords(message)


def test_poetry_appreciation_filters_unrelated_rag_sources():
    sources = [
        {"title": "三国演义", "content": "刘备关羽张飞桃园结义。", "score": 0.66, "chunk_id": 1},
        {"title": "唐诗资料", "content": "李白《将进酒》气势奔放，表达及时行乐与怀才不遇。", "score": 0.54, "chunk_id": 2},
    ]

    filtered = _filter_sources_for_intent("poetry_appreciation", "赏析一下将进酒吧", sources)

    assert len(filtered) == 1
    assert filtered[0]["chunk_id"] == 2


def test_poetry_appreciation_drops_all_unrelated_rag_sources():
    sources = [
        {"title": "三国演义", "content": "十常侍与黄巾起义相关内容。", "score": 0.66, "chunk_id": 1},
        {"title": "三国演义", "content": "曹操、刘备、孙权三方势力。", "score": 0.59, "chunk_id": 2},
    ]

    filtered = _filter_sources_for_intent("poetry_appreciation", "赏析一下将进酒吧", sources)

    assert filtered == []


def test_concept_tutoring_filters_unrelated_rag_sources():
    sources = [
        {"title": "三国演义", "content": "刘备关羽张飞桃园结义。", "score": 0.66, "chunk_id": 1},
        {"title": "物理基础", "content": "牛顿第二定律说明物体加速度与所受合外力成正比。", "score": 0.61, "chunk_id": 2},
    ]

    filtered = _filter_sources_for_intent("concept_tutoring", "讲解一下牛顿第二定律", sources)

    assert len(filtered) == 1
    assert filtered[0]["chunk_id"] == 2


def test_concept_tutoring_drops_all_unrelated_rag_sources():
    sources = [
        {"title": "三国演义", "content": "刘备关羽张飞桃园结义。", "score": 0.66, "chunk_id": 1},
        {"title": "三国演义", "content": "曹操与袁绍在官渡交战。", "score": 0.59, "chunk_id": 2},
    ]

    filtered = _filter_sources_for_intent("concept_tutoring", "讲解一下牛顿第二定律", sources)

    assert filtered == []


def test_learning_overrides_stale_academic_ops_mode():
    message = "鉴赏一下登高"

    assert detect_capability_override(message, "academic_ops") == "study"


def test_academic_data_query_does_not_become_learning():
    message = "吴磊岗位是什么"

    assert not should_use_learning(message)
    assert detect_auto_mode(message) == "academic_ops"


def test_poetry_appreciation_by_text():
    message = "床前明月光，疑是地上霜。\n举头望明月，低头思故乡。"

    assert should_use_learning(message)
    assert detect_learning_intent(message) == "poetry_appreciation"


def test_study_plan_intent():
    message = "帮我制定一周英语复习计划"

    assert should_use_learning(message)
    assert detect_learning_intent(message) == "study_plan"
    assert detect_auto_mode(message) == "study"


def test_problem_solving_intent():
    message = "这道题怎么做，能给出解题步骤吗"

    assert should_use_learning(message)
    assert detect_learning_intent(message) == "problem_solving"


def test_concept_tutoring_intent():
    message = "数据库事务隔离级别怎么理解"

    assert should_use_learning(message)
    assert detect_learning_intent(message) == "concept_tutoring"


if __name__ == "__main__":
    import traceback

    failed = 0
    current = globals()
    for name in sorted(key for key in current if key.startswith("test_")):
        try:
            current[name]()
            print(f"PASS {name}")
        except Exception:
            failed += 1
            print(f"FAIL {name}")
            traceback.print_exc()
    raise SystemExit(1 if failed else 0)
