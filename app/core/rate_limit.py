"""
登录限流模块
- 基于 Redis 计数器
- 同 IP / 同账号：5分钟内最多10次
- Redis 不可用时跳过限流
"""
from app.redis import redis_incr


# 限流配置
RATE_LIMIT_WINDOW = 300   # 5分钟(秒)
RATE_LIMIT_MAX = 10       # 最多10次


def check_login_rate_limit(account: str, ip: str) -> tuple[bool, str]:
    """
    检查登录限流
    :param account: 登录账号
    :param ip: 请求IP
    :return: (是否允许, 提示信息)
    """
    try:
        # 按账号限流
        account_key = f"rate_limit:login:account:{account}"
        account_count = redis_incr(account_key, ex=RATE_LIMIT_WINDOW)
        if account_count > RATE_LIMIT_MAX:
            return False, f"该账号登录次数过于频繁，请{RATE_LIMIT_WINDOW // 60}分钟后再试"

        # 按IP限流
        ip_key = f"rate_limit:login:ip:{ip}"
        ip_count = redis_incr(ip_key, ex=RATE_LIMIT_WINDOW)
        if ip_count > RATE_LIMIT_MAX:
            return False, f"该IP登录次数过于频繁，请{RATE_LIMIT_WINDOW // 60}分钟后再试"
    except Exception:
        # Redis 不可用时跳过限流
        pass

    return True, ""
