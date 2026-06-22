"""
Redis 连接池和常用操作封装
"""
import redis
from app.config import settings

# Redis 连接池
_redis_pool = None


def get_redis_pool() -> redis.ConnectionPool:
    global _redis_pool
    if _redis_pool is None:
        _redis_pool = redis.ConnectionPool.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            max_connections=20,
        )
    return _redis_pool


def get_redis() -> redis.Redis:
    """获取 Redis 客户端"""
    return redis.Redis(connection_pool=get_redis_pool())


# ---- 便捷操作 ----

def redis_set(key: str, value: str, ex: int = None):
    """设置键值，ex 为过期时间(秒)"""
    r = get_redis()
    if ex:
        r.set(key, value, ex=ex)
    else:
        r.set(key, value)


def redis_get(key: str):
    """获取值"""
    return get_redis().get(key)


def redis_delete(key: str):
    """删除键"""
    return get_redis().delete(key)


def redis_incr(key: str, ex: int = None) -> int:
    """自增计数器"""
    r = get_redis()
    val = r.incr(key)
    if ex and val == 1:
        r.expire(key, ex)
    return val


def redis_close():
    """关闭连接池"""
    global _redis_pool
    if _redis_pool:
        _redis_pool.disconnect()
        _redis_pool = None
