"""Web search tools for the campus assistant.

The module is intentionally provider-shaped. It uses Tavily first when a key is
configured, then falls back to free providers so the assistant keeps responding
when the external search service is temporarily unavailable.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from html import unescape
from html.parser import HTMLParser
from typing import Any
from urllib.parse import parse_qs, quote_plus, unquote, urljoin, urlparse
import json
import urllib.request
import xml.etree.ElementTree as ET

from app.config import settings
from app.services.campus_agent.llm_client import call_deepseek


USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) CampusAssistant/1.0"

FRESHNESS_WORDS = ("最新", "今天", "现在", "当前", "截至", "实时", "近期", "刚刚", "2026")


def build_fresh_search_query(query: str, *, today: date | None = None) -> str:
    """Make manual Search mode behave like a fresh web search by default."""
    text = " ".join((query or "").split())
    if not text:
        return text
    today = today or date.today()
    if any(word in text for word in FRESHNESS_WORDS):
        return text
    if any(word in text for word in ["世界杯", "欧冠", "NBA", "射手", "积分榜", "排名", "赛程"]):
        return f"{text} 最新 截至 {today.isoformat()} 官方 权威"
    return f"{text} 最新 截至 {today.isoformat()} 权威"


@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str = ""
    source: str = ""
    published_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "url": self.url,
            "snippet": self.snippet,
            "source": self.source,
            "published_at": self.published_at,
        }


class DuckDuckGoLiteParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.results: list[SearchResult] = []
        self._in_link = False
        self._in_snippet = False
        self._current_url = ""
        self._current_title: list[str] = []
        self._current_snippet: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = {key: value or "" for key, value in attrs}
        href = attrs_dict.get("href", "")
        class_name = attrs_dict.get("class", "")
        normalized_href = _normalize_duckduckgo_url(href)
        if tag == "a" and normalized_href:
            self._flush()
            self._in_link = True
            self._current_url = normalized_href
            self._current_title = []
            self._current_snippet = []
        elif class_name and any(name in class_name for name in ["result-snippet", "result__snippet"]):
            self._in_snippet = True

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._in_link:
            self._in_link = False
        if self._in_snippet:
            self._in_snippet = False

    def handle_data(self, data: str) -> None:
        text = " ".join((data or "").split())
        if not text:
            return
        if self._in_link:
            self._current_title.append(text)
        elif self._in_snippet:
            self._current_snippet.append(text)

    def close(self) -> None:
        self._flush()
        super().close()

    def _flush(self) -> None:
        if not self._current_url or not self._current_title:
            return
        title = unescape(" ".join(self._current_title)).strip()
        snippet = unescape(" ".join(self._current_snippet)).strip()
        if not title or title.lower() in {"images", "videos", "news", "maps"}:
            return
        source = urlparse(self._current_url).netloc.replace("www.", "")
        if not any(item.url == self._current_url for item in self.results):
            self.results.append(SearchResult(title=title, url=self._current_url, snippet=snippet, source=source))
        self._current_url = ""
        self._current_title = []
        self._current_snippet = []


def _normalize_duckduckgo_url(href: str) -> str:
    if not href:
        return ""
    href = unescape(href)
    if href.startswith("//"):
        href = f"https:{href}"
    elif href.startswith("/"):
        href = urljoin("https://duckduckgo.com", href)
    parsed = urlparse(href)
    query = parse_qs(parsed.query)
    uddg = query.get("uddg") or query.get("u")
    if uddg:
        return unquote(uddg[0])
    return href if parsed.scheme in {"http", "https"} else ""


def should_use_web_search(message: str) -> bool:
    text = message or ""
    explicit_words = ["搜索", "联网查", "网上查", "帮我查", "查一下", "搜一下", "检索", "给出处", "附链接", "来源"]
    time_words = ["今天", "现在", "最新", "近期", "最近", "刚发布", "新闻", "版本", "价格", "政策", "公告"]
    if any(word in text for word in explicit_words):
        return True
    if any(word in text for word in time_words) and not any(word in text for word in ["我的", "学生", "教师", "课程", "课表", "成绩", "请假", "考勤"]):
        return True
    return False


def search_web(query: str, *, limit: int = 6, fresh: bool = False) -> dict[str, Any]:
    original_query = (query or "").strip()
    query = build_fresh_search_query(original_query) if fresh else original_query
    if not query:
        return {"ok": False, "error": "请先输入要搜索的关键词。", "query": query, "results": []}
    if settings.TAVILY_API_KEY and (settings.SEARCH_PROVIDER or "").lower() in {"tavily", "auto"}:
        tavily_result = search_web_tavily(query, limit=limit)
        if tavily_result.get("ok"):
            tavily_result["original_query"] = original_query
            return tavily_result
    url = f"https://lite.duckduckgo.com/lite/?q={quote_plus(query)}"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
    except Exception as exc:
        return search_web_instant_answer(query, limit=limit, previous_error=str(exc))

    parser = DuckDuckGoLiteParser()
    parser.feed(html)
    parser.close()
    results = [item.to_dict() for item in parser.results[: max(1, min(limit, 10))]]
    if results:
        return {"ok": True, "query": query, "original_query": original_query, "results": results, "provider": "duckduckgo_lite"}
    bing_result = search_web_bing_rss(query, limit=limit)
    if bing_result.get("ok"):
        return bing_result
    baidu_result = search_web_baidu(query, limit=limit)
    if baidu_result.get("ok"):
        return baidu_result
    result = search_web_instant_answer(query, limit=limit)
    result["original_query"] = original_query
    return result


def search_web_tavily(query: str, *, limit: int = 6) -> dict[str, Any]:
    payload = {
        "api_key": settings.TAVILY_API_KEY,
        "query": query,
        "search_depth": "advanced",
        "max_results": max(1, min(limit, 10)),
        "include_answer": False,
        "include_raw_content": False,
    }
    req = urllib.request.Request(
        settings.TAVILY_SEARCH_URL,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "User-Agent": USER_AGENT,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=max(3, int(settings.SEARCH_TIMEOUT_SECONDS))) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="ignore"))
    except Exception as exc:
        return {"ok": False, "error": f"Tavily 搜索暂时不可用：{exc}", "query": query, "results": [], "provider": "tavily"}

    results = []
    for item in data.get("results") or []:
        url = item.get("url") or ""
        title = item.get("title") or url
        if not url or not title:
            continue
        results.append(SearchResult(
            title=title,
            url=url,
            snippet=item.get("content") or "",
            source=urlparse(url).netloc.replace("www.", ""),
            published_at=item.get("published_date"),
        ).to_dict())
    return {
        "ok": bool(results),
        "query": query,
        "results": results[: max(1, min(limit, 10))],
        "provider": "tavily",
        "response_time": data.get("response_time"),
    }


class BaiduResultParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.results: list[SearchResult] = []
        self._in_title = False
        self._in_snippet = False
        self._current_url = ""
        self._current_title: list[str] = []
        self._current_snippet: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = {key: value or "" for key, value in attrs}
        class_name = attrs_dict.get("class", "")
        if tag == "h3":
            self._flush()
            self._in_title = True
            self._current_title = []
            self._current_snippet = []
            self._current_url = ""
        elif self._in_title and tag == "a" and attrs_dict.get("href"):
            self._current_url = attrs_dict.get("href", "")
        elif class_name and any(name in class_name for name in ["c-abstract", "content-right_8Zs40"]):
            self._in_snippet = True

    def handle_endtag(self, tag: str) -> None:
        if tag == "h3":
            self._in_title = False
        if self._in_snippet and tag in {"div", "span"}:
            self._in_snippet = False

    def handle_data(self, data: str) -> None:
        text = " ".join((data or "").split())
        if not text:
            return
        if self._in_title:
            self._current_title.append(text)
        elif self._in_snippet:
            self._current_snippet.append(text)

    def close(self) -> None:
        self._flush()
        super().close()

    def _flush(self) -> None:
        title = unescape(" ".join(self._current_title)).strip()
        if not title or not self._current_url:
            return
        snippet = unescape(" ".join(self._current_snippet)).strip()
        self.results.append(SearchResult(
            title=title,
            url=self._current_url,
            snippet=snippet,
            source=urlparse(self._current_url).netloc.replace("www.", "") or "baidu",
        ))
        self._current_url = ""
        self._current_title = []
        self._current_snippet = []


def search_web_baidu(query: str, *, limit: int = 6) -> dict[str, Any]:
    url = f"https://www.baidu.com/s?wd={quote_plus(query)}"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
    except Exception as exc:
        return {"ok": False, "error": str(exc), "query": query, "results": [], "provider": "baidu_html"}
    parser = BaiduResultParser()
    parser.feed(html)
    parser.close()
    results = [item.to_dict() for item in parser.results[: max(1, min(limit, 10))]]
    return {"ok": bool(results), "query": query, "results": results, "provider": "baidu_html"}


def search_web_bing_rss(query: str, *, limit: int = 6) -> dict[str, Any]:
    url = f"https://www.bing.com/search?q={quote_plus(query)}&format=rss"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            xml_text = resp.read().decode("utf-8", errors="ignore")
    except Exception as exc:
        return {"ok": False, "error": str(exc), "query": query, "results": [], "provider": "bing_rss"}
    try:
        root = ET.fromstring(xml_text)
    except Exception as exc:
        return {"ok": False, "error": str(exc), "query": query, "results": [], "provider": "bing_rss"}

    results: list[dict[str, Any]] = []
    for item in root.findall(".//item"):
        if len(results) >= limit:
            break
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        description = (item.findtext("description") or "").strip()
        pub_date = (item.findtext("pubDate") or "").strip() or None
        if not title or not link:
            continue
        results.append(SearchResult(
            title=title,
            url=link,
            snippet=description,
            source=urlparse(link).netloc.replace("www.", ""),
            published_at=pub_date,
        ).to_dict())
    return {"ok": bool(results), "query": query, "results": results, "provider": "bing_rss"}


def _flatten_related_topics(items: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for item in items:
        if len(results) >= limit:
            break
        nested = item.get("Topics")
        if isinstance(nested, list):
            results.extend(_flatten_related_topics(nested, limit - len(results)))
            continue
        text = item.get("Text") or ""
        url = item.get("FirstURL") or ""
        if not text or not url:
            continue
        title = text.split(" - ", 1)[0][:120]
        results.append(SearchResult(
            title=title,
            url=url,
            snippet=text,
            source=urlparse(url).netloc.replace("www.", ""),
        ).to_dict())
    return results[:limit]


def search_web_instant_answer(query: str, *, limit: int = 6, previous_error: str | None = None) -> dict[str, Any]:
    url = f"https://api.duckduckgo.com/?q={quote_plus(query)}&format=json&no_html=1&no_redirect=1"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="ignore"))
    except Exception as exc:
        error = f"联网搜索暂时不可用：{previous_error or exc}"
        return {"ok": False, "error": error, "query": query, "results": [], "provider": "duckduckgo_instant"}

    results: list[dict[str, Any]] = []
    abstract = data.get("AbstractText") or data.get("Abstract")
    abstract_url = data.get("AbstractURL")
    heading = data.get("Heading") or query
    if abstract and abstract_url:
        results.append(SearchResult(
            title=heading,
            url=abstract_url,
            snippet=abstract,
            source=urlparse(abstract_url).netloc.replace("www.", ""),
        ).to_dict())
    results.extend(_flatten_related_topics(data.get("RelatedTopics") or [], max(1, min(limit, 10)) - len(results)))
    return {"ok": bool(results), "query": query, "results": results[:limit], "provider": "duckduckgo_instant"}


def _references(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    refs = []
    for idx, item in enumerate(results, 1):
        refs.append({
            "id": idx,
            "title": item.get("title") or item.get("source") or f"搜索结果 {idx}",
            "content": item.get("snippet") or item.get("url") or "",
            "score": 1,
            "metadata": {
                "url": item.get("url"),
                "source": item.get("source"),
                "published_at": item.get("published_at"),
            },
        })
    return refs


def _fallback_answer(query: str, results: list[dict[str, Any]]) -> str:
    if not results:
        return "我这次没有检索到可用结果。你可以换一个更具体的关键词，或者加上地点、时间、官网等限定。"
    lines = [f"我按最新公开资料帮你联网搜索了“{query}”，先整理出这些相关信息：", ""]
    for idx, item in enumerate(results[:6], 1):
        snippet = item.get("snippet") or "暂无摘要"
        lines.append(f"{idx}. {item.get('title') or item.get('source')}")
        lines.append(f"   {snippet}")
    lines.append("")
    lines.append("这些是搜索结果摘要，不等同于最终事实结论；重要信息建议结合权威渠道核对。")
    return "\n".join(lines)


def summarize_search_results(query: str, results: list[dict[str, Any]]) -> str:
    if not results:
        return _fallback_answer(query, results)
    source_text = "\n".join(
        f"{idx}. 标题：{item.get('title')}\n来源：{item.get('url')}\n摘要：{item.get('snippet')}"
        for idx, item in enumerate(results[:6], 1)
    )
    prompt = (
        f"你是校园助手的搜索引擎模块，当前日期是 {date.today().isoformat()}。请基于搜索结果回答用户，要求："
        "1. 先给出简明综合结论；2. 再列出关键依据；3. 用自然语言说明信息时效性或不确定性；"
        "4. 不要在正文列出 URL、来源链接或参考文献清单；5. 不要编造搜索结果里没有的信息；"
        "6. 如果检索到的资料日期早于当前日期，要明确说“目前检索到的较新公开资料截至某日期/某报道”；"
        "7. 如果信息不够权威，要提醒用户可进一步核验。"
    )
    reply = call_deepseek(
        system_prompt=prompt,
        user_message=f"用户问题：{query}\n\n搜索结果：\n{source_text}",
        temperature=0.25,
        max_tokens=1200,
    )
    return reply or _fallback_answer(query, results)


def answer_web_search(message: str, *, previous_results: list[dict[str, Any]] | None = None) -> tuple[str, dict[str, Any], list[dict[str, Any]]]:
    text = (message or "").strip()
    followup_markers = ["第二条", "第2条", "第一条", "第1条", "第三条", "第3条", "详细说说", "展开", "总结成表格"]
    if previous_results and any(marker in text for marker in followup_markers):
        query = f"基于上一轮搜索结果追问：{text}"
        reply = summarize_search_results(query, previous_results)
        return reply, {"query": query, "results": previous_results, "provider": "memory"}, _references(previous_results)

    result = search_web(text)
    results = result.get("results") or []
    if not result.get("ok"):
        reply = result.get("error") or "联网搜索暂时不可用。"
        return reply, result, []
    reply = summarize_search_results(text, results)
    data = {"query": text, "results": results, "provider": result.get("provider")}
    return reply, data, _references(results)
