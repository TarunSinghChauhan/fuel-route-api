"""Orchestrates one API request: locations -> route -> stations -> plan -> response."""
import hashlib
import json
import time
from urllib.parse import urlencode

from django.conf import settings
from django.core.cache import cache

from ..errors import InvalidLocation
from . import geocode, planner, routing
from .stations import get_stations

M_PER_MILE = 1609.344


def _r(x, n=2):
    return round(float(x), n)


def build_trip(start_in, finish_in, *, start_fuel_percent=100.0, corridor_miles=None):
    t0 = time.perf_counter()
    counter = {"routing": 0, "geocoding": 0}
    range_mi, mpg = settings.FUEL_MAX_RANGE_MILES, settings.FUEL_MPG
    corridor = corridor_miles or settings.FUEL_CORRIDOR_MILES

    if not (0 <= start_fuel_percent <= 100):
        raise InvalidLocation("start_fuel_percent must be between 0 and 100.", code="bad_request")

    start = geocode.resolve_location(start_in, counter)
    finish = geocode.resolve_location(finish_in, counter)

    key = "trip:" + hashlib.sha1(
        json.dumps([round(start.lat, 4), round(start.lng, 4), round(finish.lat, 4),
                    round(finish.lng, 4), start_fuel_percent, corridor]).encode()
    ).hexdigest()
    if (hit := cache.get(key)) is not None:
        hit = json.loads(json.dumps(hit))
        hit["meta"] = {"elapsed_ms": _r((time.perf_counter() - t0) * 1000, 1),
                       "routing_api_calls": 0, "geocoding_api_calls": counter["geocoding"],
                       "cached": True}
        return hit

    route = routing.fetch_route(start, finish, counter)
    total_mi = route["distance_m"] / M_PER_MILE

    positions, lats, lngs = planner.sample_route(
        route["coords"], total_mi, settings.FUEL_SAMPLE_STEP_MILES
    )
    index = get_stations()
    st_idx, st_pos, st_off = planner.stations_along_route(
        index, positions, lats, lngs, corridor
    )

    start_fuel = range_mi * start_fuel_percent / 100.0
    purchases, total_cost = planner.plan_fuel_stops(
        st_pos, index.prices[st_idx], total_mi, range_mi, mpg, start_fuel,
        min_fill_miles=settings.FUEL_MIN_FILL_MILES,
    )

    stops, cum = [], 0.0
    for order, p in enumerate(purchases, 1):
        s = st_idx[p.node]
        cum += p.cost
        stops.append({
            "order": order,
            "station_id": index.ids[s],
            "name": index.names[s],
            "address": index.addresses[s],
            "city": index.cities[s],
            "state": index.states[s],
            "lat": _r(index.lats[s], 5),
            "lng": _r(index.lngs[s], 5),
            "mile_marker": _r(st_pos[p.node], 1),
            "off_route_miles": _r(st_off[p.node], 1),
            "price_per_gallon": _r(index.prices[s], 3),
            "gallons": _r(p.gallons),
            "cost": _r(p.cost),
            "cumulative_cost": _r(cum),
            "fuel_on_arrival_gallons": _r(p.fuel_on_arrival_miles / mpg),
        })

    # Client-facing geometry: the routing engine's simplified line.
    geometry = {"type": "Feature", "properties": {},
                "geometry": {"type": "LineString", "coordinates": route["coords"]}}
    gallons_bought = sum(p.gallons for p in purchases)
    payload = {
        "start": {"query": start.query, "label": start.label, "lat": _r(start.lat, 5),
                  "lng": _r(start.lng, 5), "resolved_via": start.source},
        "finish": {"query": finish.query, "label": finish.label, "lat": _r(finish.lat, 5),
                   "lng": _r(finish.lng, 5), "resolved_via": finish.source},
        "route": {"distance_miles": _r(total_mi, 1),
                  "duration_hours": _r(route["duration_s"] / 3600, 2),
                  "geometry": geometry},
        "fuel_stops": stops,
        "summary": {
            "total_fuel_cost": _r(total_cost),
            "currency": "USD",
            "fuel_stop_count": len(stops),
            "total_gallons_purchased": _r(gallons_bought),
            "trip_gallons_required": _r(total_mi / mpg),
            "average_price_paid": _r(total_cost / gallons_bought, 3) if gallons_bought else None,
            "vehicle": {"max_range_miles": range_mi, "mpg": mpg,
                        "tank_gallons": range_mi / mpg,
                        "start_fuel_percent": start_fuel_percent},
        },
        "assumptions": [
            "Vehicle starts with a tank filled to start_fuel_percent (default 100%); "
            "that starting fuel is not counted as money spent on this trip.",
            "Fuel is only bought when needed to reach a cheaper stop or the destination; "
            "the vehicle is assumed to arrive at the destination with an empty tank. "
            f"Top-offs under {settings.FUEL_MIN_FILL_MILES / mpg:g} gallons are skipped when "
            "the tank already covers the next leg.",
            f"Only stations within {corridor:g} miles of the route are considered; detour "
            "distance is not added to trip length. Station positions are city-level.",
        ],
    }
    cache.set(key, payload, settings.ROUTE_CACHE_SECONDS)

    out = json.loads(json.dumps(payload))
    out["meta"] = {"elapsed_ms": _r((time.perf_counter() - t0) * 1000, 1),
                   "routing_api_calls": counter["routing"],
                   "geocoding_api_calls": counter["geocoding"], "cached": False}
    return out
