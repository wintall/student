from app.services.rag_knowledge_service import (
    _core_query_tokens,
    _extract_structured_list_answer,
    _fallback_summary_from_sources,
    _is_list_question,
)


def test_who_question_counts_as_structured_list_question():
    assert _is_list_question("十常侍是谁")


def test_ten_attendants_who_question_returns_direct_answer():
    sources = [
        {
            "title": "三国演义",
            "chunk_no": 13,
            "content": "后张让、赵忠、封谞、段珪、曹节、侯览、蹇硕、程旷、夏恽、郭胜十人号为十常侍。",
        }
    ]

    answer = _extract_structured_list_answer("十常侍是谁", sources)

    assert answer is not None
    assert "张让、赵忠、封谞、段珪、曹节、侯览、蹇硕、程旷、夏恽、郭胜" in answer
    assert "东汉末年" in answer
    assert "出处：三国演义 / 片段13" in answer


def test_fallback_summary_uses_sources_without_internal_failure_message():
    sources = [
        {
            "title": "三国演义",
            "chunk_no": 19,
            "content": "何进谋诛宦官，袁绍建议召外兵入京。十常侍得知消息后，宫中局势更加紧张。",
        },
        {
            "title": "三国演义",
            "chunk_no": 20,
            "content": "董卓后来进入洛阳，朝廷权力格局发生剧烈变化。",
        },
    ]

    answer = _fallback_summary_from_sources("何进为什么召外兵入京", sources)

    assert "当前大模型暂时没有生成总结" not in answer
    assert "何进" in answer
    assert "袁绍" in answer
    assert "出处" in answer


def test_core_query_tokens_keep_story_entities():
    tokens = _core_query_tokens("刘备怎么请到诸葛亮")

    assert "刘备" in tokens
    assert "诸葛亮" in tokens


def test_fallback_refuses_unrelated_story_chunks():
    sources = [
        {
            "title": "三国演义",
            "chunk_no": 420,
            "content": "周瑜顿足曰：子敬又中诸葛亮之计也。吾有一计，使诸葛亮不能出吾算中。",
        }
    ]

    answer = _fallback_summary_from_sources("刘备怎么请到诸葛亮", sources)

    assert "不能据此给出可靠结论" in answer
    assert "周瑜顿足" not in answer


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
