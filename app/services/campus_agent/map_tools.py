"""Map planning tools used by the assistant through the MCP-style adapter."""
from __future__ import annotations

import json
import urllib.parse
import urllib.request
from typing import Any

from app.config import settings

AMAP_BASE = "https://restapi.amap.com/v3"
COMMON_CITY_HINTS = [
    "北京",
    "上海",
    "天津",
    "重庆",
    "广州",
    "深圳",
    "杭州",
    "南京",
    "武汉",
    "成都",
    "西安",
    "郑州",
    "青岛",
    "苏州",
    "长沙",
]
GEOCODE_CACHE: dict[tuple[str, str], dict] = {}


def _active_amap_key() -> str:
    return settings.AMAP_WEB_SERVICE_KEY or settings.AMAP_KEY


def _amap_get(path: str, params: dict[str, Any], timeout: int = 15) -> dict | None:
    key = _active_amap_key()
    if not key:
        return None
    payload = {"key": key, "output": "JSON", **params}
    url = f"{AMAP_BASE}{path}?{urllib.parse.urlencode(payload)}"
    for _ in range(2):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "CampusAssistant/1.0"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                if data.get("status") == "0" and data.get("info") in {"INVALID_USER_IP", "DAILY_QUERY_OVER_LIMIT"}:
                    continue
                return data
        except Exception:
            continue
    return None


def _amap_city_param(city: str | None) -> str:
    value = (city or "").strip()
    if value.endswith("市") and len(value) <= 4:
        return value[:-1]
    return value


def _coord_parts(location: str | None) -> tuple[str, str] | None:
    if not location or "," not in location:
        return None
    lon, lat = [item.strip() for item in location.split(",", 1)]
    if not lon or not lat:
        return None
    return lon, lat


def _amap_nav_url(origin: dict | None, destination: dict | None, mode: str = "car") -> str | None:
    origin_coord = _coord_parts((origin or {}).get("location"))
    dest_coord = _coord_parts((destination or {}).get("location"))
    if not origin_coord or not dest_coord:
        return None
    from_text = f"{origin_coord[0]},{origin_coord[1]},{urllib.parse.quote((origin or {}).get('name') or '出发地')}"
    to_text = f"{dest_coord[0]},{dest_coord[1]},{urllib.parse.quote((destination or {}).get('name') or '目的地')}"
    return (
        "https://uri.amap.com/navigation"
        f"?from={from_text}&to={to_text}&mode={mode}&policy=1&coordinate=gaode&callnative=0"
    )


def _amap_marker_url(place: dict | None) -> str | None:
    coord = _coord_parts((place or {}).get("location"))
    if not coord:
        return None
    name = urllib.parse.quote((place or {}).get("name") or "地点")
    return f"https://uri.amap.com/marker?position={coord[0]},{coord[1]}&name={name}&coordinate=gaode&callnative=0"


def _route_summary(result: dict, label: str) -> dict:
    return {
        "label": label,
        "distance_km": round(_meters_to_km(result.get("distance_m")), 1),
        "duration_minutes": _seconds_to_minutes(result.get("duration_s")),
        "walking_m": int(result.get("walking_m") or 0),
        "cost": result.get("cost"),
    }


def _decorate_route_result(result: dict, route_type: str) -> dict:
    if not result.get("ok"):
        return result
    mode = "bus" if route_type == "transit" else "car"
    label = "公共交通" if route_type == "transit" else "自驾"
    result["route_type"] = route_type
    result["summary"] = _route_summary(result, label)
    result["map_links"] = {
        "amap": _amap_nav_url(result.get("origin"), result.get("destination"), mode=mode),
    }
    for idx, seg in enumerate(result.get("segments") or [], 1):
        seg["index"] = idx
        seg["summary"] = {
            "distance_km": round(_meters_to_km(seg.get("distance_m")), 1),
            "duration_minutes": _seconds_to_minutes(seg.get("duration_s")),
        }
    return result


def geocode(address: str, city: str | None = None) -> dict | None:
    city = city or _infer_city(address)
    request_city = _amap_city_param(city)
    cache_key = (_normalize_place_name(address), request_city or "")
    cached = GEOCODE_CACHE.get(cache_key)
    if cached:
        return dict(cached)

    def poi_lookup(limit: int = 1) -> dict | None:
        poi_data = _amap_get(
            "/place/text",
            {
                "keywords": address,
                "city": request_city or "",
                "offset": limit,
                "page": 1,
                "extensions": "base",
            },
        )
        pois = (poi_data or {}).get("pois") or []
        if not pois:
            return None
        poi = pois[0]
        display_name = poi.get("name") or poi.get("address") or address
        return {
            "name": address,
            "formatted_address": display_name,
            "location": poi.get("location"),
            "city": poi.get("cityname") or city,
        }

    if any(word in address for word in ["大学", "学院", "地铁", "车站", "机场", "公园", "商场", "医院", "校区"]):
        poi = poi_lookup()
        if poi and poi.get("location"):
            GEOCODE_CACHE[cache_key] = dict(poi)
            return poi

    data = _amap_get("/geocode/geo", {"address": address, "city": request_city or ""})
    items = (data or {}).get("geocodes") or []
    if items:
        item = items[0]
        result = {
            "name": address,
            "formatted_address": item.get("formatted_address") or address,
            "location": item.get("location"),
            "city": item.get("city") or city,
        }
        if result.get("location"):
            GEOCODE_CACHE[cache_key] = dict(result)
        return result

    poi = poi_lookup()
    if poi and poi.get("location"):
        GEOCODE_CACHE[cache_key] = dict(poi)
    return poi


def _infer_city(*parts: str | None) -> str | None:
    text = " ".join(part or "" for part in parts)
    for city in COMMON_CITY_HINTS:
        if city in text:
            return city
    return None


def _normalize_place_name(name: str | None) -> str:
    value = (name or "").strip()
    for suffix in ["的路线", "的线路", "路线", "线路", "规划一下", "规划"]:
        value = value.replace(suffix, "")
    value = value.strip(" ，,。?？吧呢啊呀")
    if value in {"学校", "校园", "本校", "校内"}:
        return settings.SCHOOL_ADDRESS
    if "人才公寓" in value:
        value = value.replace("人才公寓", "人才公园")
    value = value.strip(" ，,。?？吧呢啊呀")
    return value


def normalize_place_name(name: str | None) -> str:
    return _normalize_place_name(name)


def suggest_places(keyword: str, city: str | None = None, limit: int = 5) -> list[dict]:
    keyword = _normalize_place_name(keyword)
    city = city or _infer_city(keyword)
    request_city = _amap_city_param(city)
    data = _amap_get(
        "/place/text",
        {
            "keywords": keyword,
            "city": request_city or "",
            "offset": max(1, min(limit, 10)),
            "page": 1,
            "extensions": "base",
        },
    )
    result = []
    for item in ((data or {}).get("pois") or [])[:limit]:
        result.append({
            "name": item.get("name"),
            "address": item.get("address"),
            "city": item.get("cityname") or city,
            "location": item.get("location"),
            "type": item.get("type"),
        })
    return result


def search_poi(keyword: str, city: str | None = None, location: str | None = None, radius: int = 3000) -> list[dict]:
    request_city = _amap_city_param(city)
    params = {
        "keywords": keyword,
        "city": request_city or "",
        "offset": 8,
        "page": 1,
        "extensions": "base",
    }
    if location:
        params.update({"location": location, "radius": radius, "sortrule": "distance"})
        path = "/place/around"
    else:
        path = "/place/text"
    data = _amap_get(path, params)
    pois = (data or {}).get("pois") or []
    result = []
    for item in pois[:8]:
        result.append({
            "name": item.get("name"),
            "type": item.get("type"),
            "address": item.get("address"),
            "location": item.get("location"),
            "distance": item.get("distance"),
            "tel": item.get("tel"),
            "map_url": _amap_marker_url({
                "name": item.get("name"),
                "location": item.get("location"),
            }),
        })
    return result


def _seconds_to_minutes(value: int | float | str | None) -> int:
    try:
        seconds = int(float(value or 0))
    except (TypeError, ValueError):
        seconds = 0
    return max(1, round(seconds / 60)) if seconds else 0


def _meters_to_km(value: int | float | str | None) -> float:
    try:
        meters = int(float(value or 0))
    except (TypeError, ValueError):
        meters = 0
    return meters / 1000


def _plan_driving_segment(start: dict, end: dict) -> dict | None:
    data = _amap_get(
        "/direction/driving",
        {
            "origin": start["location"],
            "destination": end["location"],
            "strategy": 10,
            "extensions": "base",
        },
    )
    route = (data or {}).get("route") or {}
    paths = route.get("paths") or []
    if not paths:
        return None
    path = paths[0]
    steps = []
    for step in (path.get("steps") or [])[:6]:
        instruction = step.get("instruction")
        if instruction:
            steps.append(instruction)
    return {
        "from": start["formatted_address"],
        "to": end["formatted_address"],
        "distance_m": int(float(path.get("distance") or 0)),
        "duration_s": int(float(path.get("duration") or 0)),
        "steps": steps,
    }


def _plan_transit_segment(start: dict, end: dict, city: str | None = None) -> dict | None:
    city_name = _amap_city_param(city or start.get("city") or end.get("city") or _infer_city(start.get("formatted_address"), end.get("formatted_address")))
    cityd = _amap_city_param(end.get("city") or city_name)
    data = _amap_get(
        "/direction/transit/integrated",
        {
            "origin": start["location"],
            "destination": end["location"],
            "city": city_name or "",
            "cityd": cityd or "",
            "strategy": 0,
            "nightflag": 0,
            "extensions": "all",
        },
    )
    route = (data or {}).get("route") or {}
    transits = route.get("transits") or []
    if not transits:
        return None
    transit = transits[0]
    lines = []
    for seg in (transit.get("segments") or [])[:8]:
        bus = seg.get("bus") or {}
        buslines = bus.get("buslines") or []
        if buslines:
            line = buslines[0]
            name = line.get("name") or "公交/地铁"
            departure = line.get("departure_stop", {}).get("name")
            arrival = line.get("arrival_stop", {}).get("name")
            via_num = line.get("via_num")
            detail = name
            if departure and arrival:
                detail += f"：{departure} -> {arrival}"
            if via_num:
                detail += f"，约 {via_num} 站"
            lines.append(detail)
            continue
        walking = seg.get("walking") or {}
        if walking.get("distance"):
            lines.append(f"步行约 {int(float(walking.get('distance') or 0))} 米")
    return {
        "from": start["formatted_address"],
        "to": end["formatted_address"],
        "distance_m": int(float(transit.get("distance") or 0)),
        "duration_s": int(float(transit.get("duration") or 0)),
        "walking_m": int(float(transit.get("walking_distance") or 0)),
        "cost": transit.get("cost"),
        "steps": lines,
    }


def plan_route(origin: str, destination: str, waypoint: str | None = None, city: str | None = None) -> dict:
    origin = _normalize_place_name(origin)
    destination = _normalize_place_name(destination)
    waypoint = _normalize_place_name(waypoint) if waypoint else None
    city = city or _infer_city(origin, destination, waypoint)
    origin_geo = geocode(origin, city)
    dest_geo = geocode(destination, city)
    waypoint_geo = geocode(waypoint, city) if waypoint else None
    if not origin_geo or not dest_geo:
        missing = []
        suggestions = {}
        if not origin_geo:
            missing.append("origin")
            suggestions["origin"] = suggest_places(origin, city)
        if not dest_geo:
            missing.append("destination")
            suggestions["destination"] = suggest_places(destination, city)
        return {"ok": False, "message": "没有定位到出发地或目的地，请补充更准确的地点名称。", "missing": missing, "suggestions": suggestions}

    parts = []
    total_distance = 0
    total_duration = 0
    route_points = [origin_geo, waypoint_geo, dest_geo] if waypoint_geo else [origin_geo, dest_geo]
    route_points = [item for item in route_points if item]
    for start, end in zip(route_points, route_points[1:]):
        part = _plan_driving_segment(start, end)
        if not part:
            continue
        total_distance += part["distance_m"]
        total_duration += part["duration_s"]
        parts.append(part)

    if not parts:
        return {"ok": False, "message": "地图服务没有返回可用路线，请换一个更明确的地点。"}
    return _decorate_route_result({
        "ok": True,
        "origin": origin_geo,
        "destination": dest_geo,
        "waypoint": waypoint_geo,
        "distance_m": total_distance,
        "duration_s": total_duration,
        "segments": parts,
    }, "driving")


def plan_transit_route(origin: str, destination: str, waypoint: str | None = None, city: str | None = None) -> dict:
    origin = _normalize_place_name(origin)
    destination = _normalize_place_name(destination)
    waypoint = _normalize_place_name(waypoint) if waypoint else None
    city = city or _infer_city(origin, destination, waypoint)
    origin_geo = geocode(origin, city)
    dest_geo = geocode(destination, city)
    waypoint_geo = geocode(waypoint, city) if waypoint else None
    if not origin_geo or not dest_geo:
        missing = []
        suggestions = {}
        if not origin_geo:
            missing.append("origin")
            suggestions["origin"] = suggest_places(origin, city)
        if not dest_geo:
            missing.append("destination")
            suggestions["destination"] = suggest_places(destination, city)
        return {"ok": False, "message": "没有定位到出发地或目的地，请补充更准确的地点名称。", "missing": missing, "suggestions": suggestions}

    parts = []
    total_distance = 0
    total_duration = 0
    total_walking = 0
    total_cost = 0.0
    route_points = [origin_geo, waypoint_geo, dest_geo] if waypoint_geo else [origin_geo, dest_geo]
    route_points = [item for item in route_points if item]
    for start, end in zip(route_points, route_points[1:]):
        part = _plan_transit_segment(start, end, city)
        if not part:
            continue
        total_distance += part["distance_m"]
        total_duration += part["duration_s"]
        total_walking += part["walking_m"]
        try:
            total_cost += float(part.get("cost") or 0)
        except (TypeError, ValueError):
            pass
        parts.append(part)

    if not parts:
        return {"ok": False, "message": "地图服务没有返回可用公共交通路线，请换一个更明确的地点，或改用驾车方案。"}
    return _decorate_route_result({
        "ok": True,
        "origin": origin_geo,
        "destination": dest_geo,
        "waypoint": waypoint_geo,
        "distance_m": total_distance,
        "duration_s": total_duration,
        "walking_m": total_walking,
        "cost": round(total_cost, 2) if total_cost else None,
        "segments": parts,
    }, "transit")


def plan_multi_mode_route(origin: str, destination: str, waypoint: str | None = None, city: str | None = None) -> dict:
    transit = plan_transit_route(origin, destination, waypoint, city)
    driving = plan_route(origin, destination, waypoint, city)
    destination_geo = None
    if driving.get("ok"):
        destination_geo = driving.get("destination")
    elif transit.get("ok"):
        destination_geo = transit.get("destination")
    nearby = {}
    if destination_geo and destination_geo.get("location"):
        for keyword in ["餐厅", "咖啡", "景点", "商场"]:
            nearby[keyword] = search_poi(keyword, location=destination_geo["location"])[:3]
    visual = {
        "type": "route",
        "title": "路线规划",
        "origin": (driving.get("origin") or transit.get("origin")),
        "destination": (driving.get("destination") or transit.get("destination")),
        "waypoint": (driving.get("waypoint") or transit.get("waypoint")),
        "routes": [item for item in [transit if transit.get("ok") else None, driving if driving.get("ok") else None] if item],
        "nearby": nearby,
        "map_links": {
            "transit": ((transit.get("map_links") or {}).get("amap") if transit.get("ok") else None),
            "driving": ((driving.get("map_links") or {}).get("amap") if driving.get("ok") else None),
        },
    }
    return {
        "ok": bool(transit.get("ok") or driving.get("ok")),
        "transit": transit,
        "driving": driving,
        "nearby": nearby,
        "visual": visual,
    }


def format_route(result: dict) -> str:
    if not result.get("ok"):
        return result.get("message") or "路线规划失败。"
    km = result["distance_m"] / 1000
    minutes = max(1, round(result["duration_s"] / 60))
    lines = [f"路线规划好了：全程约 {km:.1f} 公里，驾车约 {minutes} 分钟。"]
    if result.get("waypoint"):
        lines.append(f"途经：{result['waypoint']['formatted_address']}")
    for idx, seg in enumerate(result.get("segments") or [], 1):
        lines.append(f"{idx}. {seg['from']} -> {seg['to']}，约 {seg['distance_m'] / 1000:.1f} 公里。")
        for step in (seg.get("steps") or [])[:3]:
            lines.append(f"   - {step}")
    lines.append("公共交通/步行方案建议以地图 App 实时结果为准，校园出行我会优先给你安全、少换乘的方案。")
    return "\n".join(lines)


def format_transit_route(result: dict) -> str:
    if not result.get("ok"):
        return result.get("message") or "公共交通路线规划失败。"
    km = _meters_to_km(result.get("distance_m"))
    minutes = _seconds_to_minutes(result.get("duration_s"))
    walking = int(result.get("walking_m") or 0)
    cost = f"，预估票价约 {result['cost']} 元" if result.get("cost") else ""
    lines = [f"公共交通建议：全程约 {km:.1f} 公里，约 {minutes} 分钟，步行约 {walking} 米{cost}。"]
    if result.get("waypoint"):
        lines.append(f"途经：{result['waypoint']['formatted_address']}")
    for idx, seg in enumerate(result.get("segments") or [], 1):
        seg_minutes = _seconds_to_minutes(seg.get("duration_s"))
        lines.append(f"{idx}. {seg['from']} -> {seg['to']}，约 {seg_minutes} 分钟。")
        for step in (seg.get("steps") or [])[:5]:
            lines.append(f"   - {step}")
    return "\n".join(lines)


def _format_place_suggestions(result: dict) -> str:
    suggestions = result.get("suggestions") or {}
    lines = []
    labels = {"origin": "出发地", "destination": "目的地"}
    for key, items in suggestions.items():
        if not items:
            continue
        lines.append(f"{labels.get(key, key)}可能是：")
        for idx, item in enumerate(items[:5], 1):
            address = f"：{item.get('address')}" if item.get("address") else ""
            lines.append(f"{idx}. {item.get('name')}{address}")
    return "\n".join(lines)


def format_multi_mode_route(result: dict) -> str:
    if not result.get("ok"):
        transit_msg = (result.get("transit") or {}).get("message")
        driving_msg = (result.get("driving") or {}).get("message")
        suggestion_text = _format_place_suggestions(result.get("transit") or {}) or _format_place_suggestions(result.get("driving") or {})
        base = transit_msg or driving_msg or "路线规划失败，请补充更明确的地点。"
        return f"{base}\n{suggestion_text}" if suggestion_text else base

    lines = ["我给你按公共交通和自驾各规划一版："]
    lines.append("")
    transit = result.get("transit") or {}
    if transit.get("ok"):
        lines.append(format_transit_route(transit))
    else:
        lines.append(f"公共交通建议：{transit.get('message') or '地图服务暂时没有返回可用公共交通方案。'}")
    lines.append("")
    driving = result.get("driving") or {}
    if driving.get("ok"):
        lines.append(format_route(driving))
    else:
        lines.append(f"自驾建议：{driving.get('message') or '地图服务暂时没有返回可用自驾方案。'}")
    nearby = result.get("nearby") or {}
    if nearby:
        lines.append("")
        lines.append("目的地附近可以顺手看看：")
        for keyword, items in nearby.items():
            if not items:
                continue
            names = "、".join(item.get("name") or "未命名地点" for item in items[:3])
            lines.append(f"- {keyword}：{names}")
    return "\n".join(lines)


def format_pois(pois: list[dict], keyword: str) -> str:
    if not pois:
        return f"附近没有搜索到“{keyword}”，可以换个关键词，比如餐厅、咖啡、超市、景点。"
    lines = [f"附近这些“{keyword}”可以看看："]
    for item in pois:
        distance = f"，约 {item.get('distance')} 米" if item.get("distance") else ""
        tel = f"，电话：{item.get('tel')}" if item.get("tel") else ""
        lines.append(f"- {item.get('name')}：{item.get('address') or '地址暂缺'}{distance}{tel}")
    return "\n".join(lines)
