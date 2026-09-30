"""One call to an OSRM-compatible routing API (default: the free public server)."""
import requests
from django.conf import settings

from ..errors import NoRoute, RoutingError


def fetch_route(start, finish, counter):
    """Return {'coords': [[lng, lat], ...], 'distance_m': float, 'duration_s': float}."""
    counter["routing"] += 1
    url = (
        f"{settings.ROUTING_BASE_URL}/route/v1/driving/"
        f"{start.lng:.6f},{start.lat:.6f};{finish.lng:.6f},{finish.lat:.6f}"
    )
    params = {
        "overview": "simplified",  # much smaller payload than 'full'
        "geometries": "geojson",
        "steps": "false",
        "alternatives": "false",
    }
    try:
        resp = requests.get(
            url,
            params=params,
            headers={"User-Agent": settings.HTTP_USER_AGENT},
            timeout=settings.HTTP_TIMEOUT_SECONDS,
        )
        data = resp.json()
    except (requests.RequestException, ValueError) as exc:
        raise RoutingError(f"Routing service unavailable: {exc}")

    code = data.get("code")
    if code == "NoRoute":
        raise NoRoute("No drivable route found between those locations.")
    if code != "Ok" or not data.get("routes"):
        raise RoutingError(f"Routing service error: {data.get('message') or code}")

    route = data["routes"][0]
    return {
        "coords": route["geometry"]["coordinates"],
        "distance_m": route["distance"],
        "duration_s": route["duration"],
    }
