"""
天气查询工具 - 高德地图 IP 定位 + 天气查询
"""
import json
import logging
import urllib.error
import urllib.parse
import urllib.request
from typing import Optional

from app.config import settings
from app.redis import redis_get, redis_set

logger = logging.getLogger("app")

WEATHER_CACHE_TTL = 1800
DEFAULT_CITY = "北京"

CITY_ALIASES = {
    "beijing": "北京",
    "peking": "北京",
    "shanghai": "上海",
    "guangzhou": "广州",
    "canton": "广州",
    "shenzhen": "深圳",
    "hangzhou": "杭州",
    "nanjing": "南京",
    "chengdu": "成都",
    "chongqing": "重庆",
    "wuhan": "武汉",
    "xian": "西安",
    "xi'an": "西安",
    "tianjin": "天津",
}

WTTR_DESC_MAP = {
    "sunny": "晴",
    "clear": "晴",
    "partly cloudy": "多云",
    "cloudy": "阴",
    "overcast": "阴",
    "mist": "雾",
    "fog": "雾",
    "haze": "霾",
    "patchy rain": "阵雨",
    "light rain": "小雨",
    "moderate rain": "中雨",
    "heavy rain": "大雨",
    "thundery": "雷阵雨",
    "snow": "雪",
}


def _http_get(url: str, timeout: int = 10) -> Optional[dict]:
    """HTTP GET 请求，失败返回 None。"""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "StudentSystem/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = resp.read().decode("utf-8")
            return json.loads(data)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
        logger.warning("天气 HTTP 请求失败: %s -> %s", url, e)
        return None
    except Exception as e:
        logger.warning("天气 HTTP 请求异常: %s -> %s", url, e)
        return None


def _normalize_city(city: str = None) -> str:
    if not city:
        return ""
    text = str(city).strip()
    if not text:
        return ""
    text = text.replace("　", "").replace(" ", "")
    lower = text.lower()
    if lower in CITY_ALIASES:
        return CITY_ALIASES[lower]
    for suffix in ("市", "地区", "盟", "自治州", "特别行政区"):
        if text.endswith(suffix):
            return text[: -len(suffix)]
    return text


def get_city_by_ip(ip: str = None) -> str:
    """
    通过 IP 获取城市名。
    本地地址或接口失败时返回空字符串，由调用方决定兜底城市。
    """
    if not settings.AMAP_KEY:
        logger.warning("高德地图 Key 未配置")
        return ""

    cache_key = f"ip_city:{ip or 'auto'}"
    try:
        cached = redis_get(cache_key)
        if cached:
            return cached
    except Exception:
        pass

    params = {"key": settings.AMAP_KEY, "ip": ip or ""}
    url = f"{settings.AMAP_IP_LOCATION_URL}?{urllib.parse.urlencode(params)}"

    data = _http_get(url)
    if not data:
        return ""

    city = ""
    try:
        if data.get("status") == "1":
            city = _normalize_city(data.get("city", ""))
    except Exception as e:
        logger.warning("解析高德 IP 定位返回失败: %s", e)

    if city:
        try:
            redis_set(cache_key, city, ex=3600)
        except Exception:
            pass

    return city


def _translate_weather_icon(weather: str) -> str:
    """将天气描述映射为前端展示图标。"""
    icon_map = {
        "晴": "☀️",
        "少云": "🌤️",
        "晴间多云": "🌤️",
        "多云": "⛅",
        "阴": "☁️",
        "阵雨": "🌦️",
        "雷阵雨": "⛈️",
        "小雨": "🌧️",
        "中雨": "🌧️",
        "大雨": "🌧️",
        "暴雨": "🌧️",
        "雪": "❄️",
        "雨夹雪": "🌨️",
        "雾": "🌫️",
        "霾": "🌫️",
        "沙尘": "🌫️",
    }
    weather = weather or ""
    for key, icon in icon_map.items():
        if key in weather:
            return icon
    return "🌡️"


def _amap_weather(city: str, extensions: str) -> Optional[dict]:
    params = {
        "key": settings.AMAP_KEY,
        "city": city,
        "extensions": extensions,
        "output": "JSON",
    }
    url = f"{settings.AMAP_WEATHER_URL}?{urllib.parse.urlencode(params)}"
    data = _http_get(url, timeout=15)
    if not data:
        return None
    if data.get("status") != "1":
        logger.warning("高德天气 API 返回错误: %s", data.get("info"))
        return None
    return data


def _build_current(city: str, live: dict = None, first_cast: dict = None) -> Optional[dict]:
    if live:
        weather = live.get("weather", "")
        return {
            "city": _normalize_city(live.get("city", "")) or city,
            "temperature": live.get("temperature", ""),
            "feels_like": f"{live.get('winddirection', '')}{live.get('windpower', '')}",
            "humidity": live.get("humidity", ""),
            "wind_speed": live.get("windpower", ""),
            "description": weather,
            "icon": _translate_weather_icon(weather),
        }

    if first_cast:
        weather = first_cast.get("dayweather", "")
        return {
            "city": city,
            "temperature": first_cast.get("daytemp", ""),
            "feels_like": f"{first_cast.get('daywind', '')}{first_cast.get('daypower', '')}",
            "humidity": "",
            "wind_speed": first_cast.get("daypower", ""),
            "description": weather,
            "icon": _translate_weather_icon(weather),
        }

    return None


def _pick_wttr_description(item: dict) -> str:
    for field in ("lang_zh", "weatherDesc"):
        values = item.get(field) or []
        if values and isinstance(values[0], dict):
            desc = values[0].get("value", "")
            if desc:
                if field == "weatherDesc":
                    lower = desc.lower()
                    for key, value in WTTR_DESC_MAP.items():
                        if key in lower:
                            return value
                return desc
    return ""


def _wttr_weather(city: str) -> Optional[dict]:
    encoded_city = urllib.parse.quote(city)
    url = f"https://wttr.in/{encoded_city}?format=j1"
    data = _http_get(url, timeout=15)
    if not data:
        return None

    try:
        current = (data.get("current_condition") or [{}])[0]
        description = _pick_wttr_description(current)
        current_result = {
            "city": city,
            "temperature": current.get("temp_C", ""),
            "feels_like": current.get("FeelsLikeC", ""),
            "humidity": current.get("humidity", ""),
            "wind_speed": current.get("windspeedKmph", ""),
            "description": description,
            "icon": _translate_weather_icon(description),
        }

        forecast = []
        for day in (data.get("weather") or [])[:3]:
            hourly = day.get("hourly") or []
            noon = hourly[4] if len(hourly) > 4 else (hourly[0] if hourly else {})
            day_desc = _pick_wttr_description(noon)
            forecast.append({
                "date": day.get("date", ""),
                "max_temp": day.get("maxtempC", ""),
                "min_temp": day.get("mintempC", ""),
                "description": day_desc,
                "icon": _translate_weather_icon(day_desc),
            })

        if not current_result["temperature"] and not forecast:
            return None
        return {"current": current_result, "forecast": forecast}
    except Exception as e:
        logger.warning("解析 wttr.in 天气数据失败: %s", e)
        return None


def get_weather(city: str) -> Optional[dict]:
    """
    查询指定城市的天气。
    高德实时天气和预报是两种 extensions，需要分开请求后组装。
    """
    city = _normalize_city(city)
    if not city:
        return None
    if not settings.AMAP_KEY:
        logger.warning("高德地图 Key 未配置")
        return None

    cache_key = f"weather:{city.lower()}"
    try:
        cached = redis_get(cache_key)
        if cached:
            return json.loads(cached)
    except Exception:
        pass

    live_data = _amap_weather(city, "base")
    forecast_data = _amap_weather(city, "all")

    try:
        live = (live_data or {}).get("lives", [])
        casts = []
        forecasts = (forecast_data or {}).get("forecasts", [])
        if forecasts:
            casts = forecasts[0].get("casts", []) or []

        current = _build_current(city, live[0] if live else None, casts[0] if casts else None)
        if not current:
            result = _wttr_weather(city)
            if result:
                try:
                    redis_set(cache_key, json.dumps(result, ensure_ascii=False), ex=WEATHER_CACHE_TTL)
                except Exception:
                    pass
            return result

        if not casts:
            result = _wttr_weather(city)
            if result:
                casts_forecast = result.get("forecast") or []
                if not live:
                    try:
                        redis_set(cache_key, json.dumps(result, ensure_ascii=False), ex=WEATHER_CACHE_TTL)
                    except Exception:
                        pass
                    return result
                if casts_forecast:
                    result = {"current": current, "forecast": casts_forecast}
                    try:
                        redis_set(cache_key, json.dumps(result, ensure_ascii=False), ex=WEATHER_CACHE_TTL)
                    except Exception:
                        pass
                    return result

        forecast = []
        for day in casts[:3]:
            weather = day.get("dayweather", "")
            forecast.append({
                "date": day.get("date", ""),
                "max_temp": day.get("daytemp", ""),
                "min_temp": day.get("nighttemp", ""),
                "description": weather,
                "icon": _translate_weather_icon(weather),
            })

        result = {
            "current": current,
            "forecast": forecast,
        }

        try:
            redis_set(cache_key, json.dumps(result, ensure_ascii=False), ex=WEATHER_CACHE_TTL)
        except Exception:
            pass

        return result
    except Exception as e:
        logger.error("解析天气数据失败: %s", e)
        return None


def get_weather_by_ip(ip: str = None) -> Optional[dict]:
    """
    通过 IP 获取城市，再查天气。
    本地开发环境多为 127.0.0.1，无法定位时默认查询北京。
    """
    city = get_city_by_ip(ip) or DEFAULT_CITY
    return get_weather(city)
