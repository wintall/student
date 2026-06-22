"""
天气查询工具 - 百度地图 IP 定位 + wttr.in 天气数据
"""
import json
import logging
import urllib.parse
import urllib.request
import urllib.error
from typing import Optional

from app.config import settings
from app.redis import redis_get, redis_set

logger = logging.getLogger("app")

# 天气缓存 30 分钟
WEATHER_CACHE_TTL = 1800


def _http_get(url: str, timeout: int = 10) -> Optional[dict]:
    """HTTP GET 请求，失败返回 None"""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "StudentSystem/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = resp.read().decode("utf-8")
            return json.loads(data)
    except Exception as e:
        logger.warning(f"HTTP 请求失败: {url} -> {e}")
        return None


def get_city_by_ip(ip: str = None) -> str:
    """
    通过 IP 获取城市名（使用百度地图 API）
    :param ip: 客户端 IP，为空则使用请求方 IP
    :return: 城市名（如"北京市"），失败返回空字符串
    """
    if not settings.BAIDU_MAP_KEY:
        logger.warning("百度地图 Key 未配置")
        return ""

    cache_key = f"ip_city:{ip or 'auto'}"
    try:
        cached = redis_get(cache_key)
        if cached:
            return cached
    except Exception:
        pass

    params = {"ak": settings.BAIDU_MAP_KEY, "coor": "bd09ll"}
    if ip:
        params["ip"] = ip
    url = f"{settings.BAIDU_MAP_IP_URL}?{urllib.parse.urlencode(params)}"

    data = _http_get(url)
    if not data:
        return ""

    city = ""
    try:
        if data.get("status") == 0:
            content = data.get("content", {})
            address_detail = content.get("address_detail", {})
            city = address_detail.get("city", "")
            if not city:
                address = content.get("address", "")
                if "|" in address:
                    city = address.split("|")[-1]
    except Exception as e:
        logger.warning(f"解析百度地图返回失败: {e}")

    city = city.replace("市", "")  # wttr.in 用的城市名不带"市"

    # 缓存 1 小时
    if city:
        try:
            redis_set(cache_key, city, ex=3600)
        except Exception:
            pass

    return city


def _translate_wttr_weather(data: dict) -> dict:
    """将 wttr.in 的英文描述映射为常用中文名/图标"""
    try:
        current = data.get("current_condition", [{}])[0]
    except (IndexError, TypeError):
        current = {}

    try:
        lang_zh = current.get("lang_zh", [{}])[0]
        desc_cn = lang_zh.get("value", "") if isinstance(lang_zh, dict) else ""
    except (IndexError, TypeError):
        desc_cn = ""

    desc_en = current.get("weatherDesc", [{}])[0].get("value", "") if current.get("weatherDesc") else ""
    if not desc_cn:
        desc_cn = desc_en

    # 天气图标映射（基于常见描述）
    icon_map = {
        "晴": "☀️", "Sunny": "☀️", "Clear": "🌤️",
        "多云": "⛅", "Partly cloudy": "⛅", "Partly Cloudy": "⛅",
        "阴": "☁️", "Cloudy": "☁️", "Overcast": "☁️",
        "小雨": "🌦️", "Light rain": "🌦️", "Patchy rain": "🌦️",
        "中雨": "🌧️", "Moderate rain": "🌧️", "雨": "🌧️", "Rain": "🌧️",
        "大雨": "⛈️", "Heavy rain": "⛈️", "Thundery": "⛈️",
        "小雪": "🌨️", "Light snow": "🌨️", "雪": "❄️", "Snow": "❄️",
        "雾": "🌫️", "Fog": "🌫️", "Mist": "🌫️", "Haze": "🌫️",
    }

    icon = "🌈"
    for k, v in icon_map.items():
        if k in desc_cn or k in desc_en:
            icon = v
            break

    return {
        "description": desc_cn or desc_en,
        "icon": icon,
    }


def get_weather(city: str) -> Optional[dict]:
    """
    查询指定城市的天气
    :param city: 城市名，如 "北京" "Shanghai"
    :return: 当前天气 + 未来 3 天，失败返回 None
    """
    if not city:
        return None

    cache_key = f"weather:{city.lower()}"
    try:
        cached = redis_get(cache_key)
        if cached:
            return json.loads(cached)
    except Exception:
        pass

    # wttr.in 支持中文城市名，使用 format=j1 返回 JSON
    encoded_city = urllib.parse.quote(city)
    url = f"https://wttr.in/{encoded_city}?format=j1"

    data = _http_get(url, timeout=15)
    if not data:
        return None

    try:
        # 当前天气
        current = data.get("current_condition", [{}])[0]
        weather_info = _translate_wttr_weather(data)

        current_result = {
            "city": city,
            "temperature": current.get("temp_C", ""),
            "feels_like": current.get("FeelsLikeC", ""),
            "humidity": current.get("humidity", ""),
            "wind_speed": current.get("windspeedKmph", ""),
            "description": weather_info["description"],
            "icon": weather_info["icon"],
        }

        # 未来 3 天
        forecast_days = data.get("weather", [])[:3]
        forecast = []
        for day in forecast_days:
            hourly = day.get("hourly", [])
            # 取中午的数据作为代表 (hour=12)
            noon = hourly[4] if len(hourly) > 4 else (hourly[0] if hourly else {})
            desc = ""
            icon = "🌈"
            if noon.get("lang_zh"):
                desc = noon["lang_zh"][0].get("value", "")
            if not desc and noon.get("weatherDesc"):
                desc = noon["weatherDesc"][0].get("value", "")

            # 图标
            for k, v in {"晴": "☀️", "多云": "⛅", "阴": "☁️", "雨": "🌧️", "雪": "❄️"}.items():
                if k in desc:
                    icon = v
                    break

            forecast.append({
                "date": day.get("date", ""),
                "max_temp": day.get("maxtempC", ""),
                "min_temp": day.get("mintempC", ""),
                "description": desc,
                "icon": icon,
            })

        result = {
            "current": current_result,
            "forecast": forecast,
        }

        # 缓存
        try:
            redis_set(cache_key, json.dumps(result, ensure_ascii=False), ex=WEATHER_CACHE_TTL)
        except Exception:
            pass

        return result
    except Exception as e:
        logger.error(f"解析天气数据失败: {e}")
        return None


def get_weather_by_ip(ip: str = None) -> Optional[dict]:
    """
    通过 IP 获取城市，再查天气
    :param ip: 客户端 IP
    :return: 天气信息 dict，失败返回 None
    """
    city = get_city_by_ip(ip)
    if not city:
        # 默认 fallback 到北京
        city = "北京"
    return get_weather(city)
