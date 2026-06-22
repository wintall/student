"""
通用接口：枚举字典、健康检查、天气查询
"""
from fastapi import APIRouter, Request
from app.core.enums import ENUM_DICT
from app.utils.response import success
from app.utils.weather import get_weather, get_weather_by_ip

router = APIRouter(tags=["通用接口"])


@router.get("/enums")
def get_enums():
    """获取所有枚举字典"""
    return success(data=ENUM_DICT)


@router.get("/health")
def health_check():
    """健康检查"""
    return success(data={"status": "ok"})


@router.get("/weather")
def weather(city: str = None, request: Request = None):
    """
    查询天气
    - 指定 city：查询该城市天气
    - 不指定 city：根据请求 IP 自动定位城市后查天气
    """
    if city:
        data = get_weather(city.strip())
    else:
        ip = request.client.host if request and request.client else None
        data = get_weather_by_ip(ip)

    if not data:
        return success(data=None, message="暂无法获取天气信息")
    return success(data=data)
