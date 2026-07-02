"""Small LLM client helpers shared by assistant modules."""
from __future__ import annotations

import json
import logging
import urllib.request
from urllib.error import HTTPError, URLError

from app.config import settings

logger = logging.getLogger("app")


def chat_completions_url(url: str | None = None) -> str:
    base = (url or settings.DEEPSEEK_API_URL or "https://api.deepseek.com/v1/chat/completions").rstrip("/")
    if base.endswith("/chat/completions"):
        return base
    return f"{base}/chat/completions"


def call_deepseek(
    *,
    system_prompt: str,
    user_message: str,
    temperature: float = 0.4,
    max_tokens: int = 1000,
) -> str | None:
    if not settings.DEEPSEEK_API_KEY:
        return None

    payload = {
        "model": settings.DEEPSEEK_MODEL or "deepseek-chat",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    req = urllib.request.Request(
        chat_completions_url(),
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {settings.DEEPSEEK_API_KEY}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        return content.strip() if isinstance(content, str) and content.strip() else None
    except Exception as exc:
        logger.warning("DeepSeek assistant module call failed: %s", exc)
        return None


def ollama_chat_url(url: str | None = None) -> str:
    base = (url or settings.OLLAMA_BASE_URL or "http://127.0.0.1:11434").rstrip("/")
    if base.endswith("/api/chat"):
        return base
    return f"{base}/api/chat"


def normalize_ollama_model(model: str | None = None) -> str:
    value = (model or "").strip()
    if not value or value.lower() in {"ollama", "local"}:
        return settings.OLLAMA_MODEL or "qwen:7b-chat"
    return value


def call_ollama(
    *,
    system_prompt: str,
    user_message: str,
    model: str | None = None,
    temperature: float = 0.4,
    max_tokens: int = 1000,
) -> str | None:
    payload = {
        "model": normalize_ollama_model(model),
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        "stream": False,
        "options": {
            "temperature": temperature,
            "num_predict": max_tokens,
        },
    }
    req = urllib.request.Request(
        ollama_chat_url(),
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=settings.OLLAMA_TIMEOUT_SECONDS) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        content = data.get("message", {}).get("content", "")
        return content.strip() if isinstance(content, str) and content.strip() else None
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="ignore") if hasattr(exc, "read") else ""
        logger.warning("Ollama assistant module HTTP failed: %s %s", exc, body[:300])
        return None
    except URLError as exc:
        logger.warning("Ollama assistant module unavailable: %s", exc)
        return None
    except Exception as exc:
        logger.warning("Ollama assistant module call failed: %s", exc)
        return None


def call_selected_llm(
    *,
    system_prompt: str,
    user_message: str,
    llm_provider: str | None = None,
    llm_model: str | None = None,
    temperature: float = 0.4,
    max_tokens: int = 1000,
) -> str | None:
    provider = (llm_provider or "system").strip().lower()
    if provider in {"local", "ollama"}:
        return call_ollama(
            system_prompt=system_prompt,
            user_message=user_message,
            model=llm_model,
            temperature=temperature,
            max_tokens=max_tokens,
        )
    return call_deepseek(
        system_prompt=system_prompt,
        user_message=user_message,
        temperature=temperature,
        max_tokens=max_tokens,
    )
