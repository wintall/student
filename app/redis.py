"""
Redis connection pool and safe helper operations.

Redis is an optional cache in this project. When it is not running, requests
must degrade quickly instead of blocking login, menu loading, or permission
checks until the frontend times out.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Callable, TypeVar

import redis

from app.config import settings

logger = logging.getLogger("app")

_redis_pool: redis.ConnectionPool | None = None
_redis_disabled_until = 0.0

CONNECT_TIMEOUT_SECONDS = 0.3
SOCKET_TIMEOUT_SECONDS = 0.5
DISABLE_AFTER_ERROR_SECONDS = 30

T = TypeVar("T")


def _redis_available() -> bool:
    return time.monotonic() >= _redis_disabled_until


def _mark_redis_unavailable(exc: Exception) -> None:
    global _redis_disabled_until
    _redis_disabled_until = time.monotonic() + DISABLE_AFTER_ERROR_SECONDS
    redis_close()
    logger.warning(
        "Redis unavailable, cache operations are disabled for %s seconds: %s",
        DISABLE_AFTER_ERROR_SECONDS,
        exc,
    )


def get_redis_pool() -> redis.ConnectionPool:
    global _redis_pool
    if _redis_pool is None:
        _redis_pool = redis.ConnectionPool.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            max_connections=20,
            socket_connect_timeout=CONNECT_TIMEOUT_SECONDS,
            socket_timeout=SOCKET_TIMEOUT_SECONDS,
            retry_on_timeout=False,
            health_check_interval=0,
        )
    return _redis_pool


def get_redis() -> redis.Redis:
    return redis.Redis(connection_pool=get_redis_pool())


def _run_redis(operation: Callable[[redis.Redis], T], default: T) -> T:
    if not _redis_available():
        return default

    try:
        return operation(get_redis())
    except redis.RedisError as exc:
        _mark_redis_unavailable(exc)
        return default
    except OSError as exc:
        _mark_redis_unavailable(exc)
        return default


def redis_set(key: str, value: str, ex: int | None = None) -> bool:
    def _set(r: redis.Redis) -> bool:
        return bool(r.set(key, value, ex=ex)) if ex else bool(r.set(key, value))

    return _run_redis(_set, False)


def redis_get(key: str) -> Any:
    return _run_redis(lambda r: r.get(key), None)


def redis_delete(key: str) -> int:
    return _run_redis(lambda r: int(r.delete(key)), 0)


def redis_incr(key: str, ex: int | None = None) -> int:
    def _incr(r: redis.Redis) -> int:
        val = int(r.incr(key))
        if ex and val == 1:
            r.expire(key, ex)
        return val

    return _run_redis(_incr, 1)


def redis_close():
    global _redis_pool
    if _redis_pool:
        _redis_pool.disconnect()
        _redis_pool = None
