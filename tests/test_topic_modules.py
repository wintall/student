from app.services.campus_agent.data_analysis_tools import should_use_data_analysis
from app.services.campus_agent.topic_qa_tools import (
    _authoritative_worldcup_reply,
    _topic_search_query,
    should_use_ai_knowledge,
    should_use_worldcup,
)
from app.services.campus_agent.web_search_tools import build_fresh_search_query
from datetime import date


def test_data_analysis_intent_words():
    assert should_use_data_analysis("分析一下学生成绩趋势和挂科情况")
    assert should_use_data_analysis("系统还有哪些高危异常")


def test_ai_knowledge_intent_words():
    assert should_use_ai_knowledge("LangGraph 和 LangChain 有什么区别")
    assert should_use_ai_knowledge("FastAPI 常见面试题")


def test_worldcup_intent_words():
    assert should_use_worldcup("世界杯小组赛规则是什么")
    assert should_use_worldcup("世界杯射手王是谁")


def test_worldcup_all_time_scorer_uses_latest_search_query():
    query = _topic_search_query("worldcup", "世界杯射手王是谁")

    assert "FIFA World Cup all-time leading scorers" in query
    assert "latest" in query


def test_manual_search_mode_adds_freshness_to_query():
    query = build_fresh_search_query("世界杯射手王", today=date(2026, 7, 1))

    assert "世界杯射手王" in query
    assert "最新" in query
    assert "2026-07-01" in query
    assert "权威" in query


def test_manual_search_mode_does_not_duplicate_freshness_words():
    query = build_fresh_search_query("世界杯射手王 最新", today=date(2026, 7, 1))

    assert query == "世界杯射手王 最新"


def test_worldcup_all_time_scorer_prefers_search_over_stale_memory():
    reply = _authoritative_worldcup_reply("世界杯射手王是谁", [
        {
            "title": "Messi becomes FIFA World Cup all-time leading scorer",
            "snippet": "Lionel Messi has overtaken Miroslav Klose and is now the all-time leading scorer with 18 goals.",
            "source": "fifa.com",
            "url": "https://www.fifa.com/",
        }
    ])

    assert reply is not None
    assert "梅西" in reply
    assert "18" in reply
    assert "克洛泽" in reply
    assert "以前的纪录保持者" in reply


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
