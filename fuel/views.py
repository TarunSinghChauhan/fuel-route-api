import json
from urllib.parse import urlencode

from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_http_methods

from .errors import APIError
from .services.mapview import render_map
from .services.trip import build_trip


def _params(request):
    if request.method == "POST" and request.content_type == "application/json":
        try:
            body = json.loads(request.body or b"{}")
        except json.JSONDecodeError:
            raise APIError("Request body must be valid JSON.")
        if not isinstance(body, dict):
            raise APIError("Request body must be a JSON object.")
        return body
    return request.POST.dict() if request.method == "POST" else request.GET.dict()


def _number(params, name, default):
    if params.get(name) in (None, ""):
        return default
    try:
        return float(params[name])
    except (TypeError, ValueError):
        raise APIError(f"'{name}' must be a number.")


def _trip(request):
    p = _params(request)
    return build_trip(
        p.get("start"),
        p.get("finish"),
        start_fuel_percent=_number(p, "start_fuel_percent", 100.0),
        corridor_miles=_number(p, "max_detour_miles", None),
    ), p


def _error(exc):
    return JsonResponse({"error": {"code": exc.code, "message": exc.message}}, status=exc.status)


@require_http_methods(["GET", "POST"])
def route_plan(request):
    """POST/GET /api/route/  {"start": "...", "finish": "..."}"""
    try:
        data, p = _trip(request)
    except APIError as exc:
        return _error(exc)
    q = {"start": p["start"] if isinstance(p["start"], str) else f'{p["start"]["lat"]},{p["start"]["lng"]}',
         "finish": p["finish"] if isinstance(p["finish"], str) else f'{p["finish"]["lat"]},{p["finish"]["lng"]}'}
    data["map_url"] = request.build_absolute_uri("/api/route/map/?" + urlencode(q))
    return JsonResponse(data, json_dumps_params={"indent": 2})


@require_http_methods(["GET"])
def route_map(request):
    """GET /api/route/map/?start=...&finish=...  -> interactive HTML map."""
    try:
        data, _ = _trip(request)
    except APIError as exc:
        return _error(exc)
    return HttpResponse(render_map(data), content_type="text/html; charset=utf-8")


@require_http_methods(["GET"])
def health(request):
    return JsonResponse({"status": "ok"})
