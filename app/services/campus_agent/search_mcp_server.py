"""MCP server for the campus assistant search tools.

Run with:
    python -m app.services.campus_agent.search_mcp_server

The assistant currently calls the search provider in-process for speed. This
server exposes the same capability as MCP tools so later modules or external
agents can reuse it without coupling to the web UI.
"""
from __future__ import annotations

from app.services.campus_agent.web_search_tools import answer_web_search, search_web

try:
    from mcp.server.fastmcp import FastMCP
except Exception as exc:  # pragma: no cover - dependency hint for local setup
    FastMCP = None
    MCP_IMPORT_ERROR = exc
else:
    MCP_IMPORT_ERROR = None


if FastMCP:
    mcp = FastMCP("campus-search")

    @mcp.tool()
    def web_search(query: str, limit: int = 6, fresh: bool = False) -> dict:
        """Search the web and return structured results with source links."""
        return search_web(query, limit=limit, fresh=fresh)

    @mcp.tool()
    def web_search_answer(query: str, limit: int = 6, fresh: bool = True) -> dict:
        """Search the web and return an assistant-ready answer plus references."""
        result = search_web(query, limit=limit, fresh=fresh)
        results = result.get("results") or []
        if not result.get("ok"):
            return {
                "ok": False,
                "query": query,
                "answer": result.get("error") or "联网搜索暂时不可用。",
                "references": [],
                "provider": result.get("provider"),
            }
        answer, data, references = answer_web_search(query)
        return {
            "ok": True,
            "query": query,
            "answer": answer,
            "references": references,
            "provider": data.get("provider"),
            "results": results,
        }


def main() -> None:
    if not FastMCP:
        raise RuntimeError(f"mcp is not installed or cannot be imported: {MCP_IMPORT_ERROR}")
    mcp.run()


if __name__ == "__main__":
    main()
