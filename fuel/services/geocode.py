"""Resolve user-supplied locations to coordinates with as few API calls as possible.

Order of attempts:
  1. "lat,lng" string or {"lat":..,"lng":..} object   -> no lookup at all
  2. "City, ST" / "City, State" (optionally with a street prefix or ", USA")
     resolved from a bundled US cities table          -> no API call
  3. Free-form address -> one Nominatim (OpenStreetMap) call
"""
import csv
import re
from dataclasses import dataclass
from functools import lru_cache

import requests
from django.conf import settings

from ..errors import InvalidLocation
from .geo import in_contiguous_usa
from .stations import DATA_DIR

LATLNG_RE = re.compile(r"^\s*(-?\d+(?:\.\d+)?)\s*[,;\s]\s*(-?\d+(?:\.\d+)?)\s*$")


@dataclass
class Place:
    query: str
    lat: float
    lng: float
    label: str
    source: str  # "coordinates" | "city_table" | "nominatim"


def _norm(text):
    return re.sub(r"\s+", " ", re.sub(r"[.']", "", text)).strip().upper()


@lru_cache(maxsize=1)
def _city_table():
    by_code, by_name, state_codes = {}, {}, {}
    with open(DATA_DIR / "us_cities.csv", newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            code, sname, city = r["STATE_CODE"], r["STATE_NAME"], _norm(r["CITY"])
            state_codes[_norm(sname)] = code
            coords = (float(r["LATITUDE"]), float(r["LONGITUDE"]), r["CITY"], code)
            by_code.setdefault((city, code), coords)
    return by_code, state_codes


def _from_city_table(text):
    by_code, state_codes = _city_table()
    parts = [p.strip() for p in text.split(",") if p.strip()]
    if parts and _norm(parts[-1]) in ("USA", "US", "UNITED STATES"):
        parts = parts[:-1]
    candidates = []
    if len(parts) >= 2:
        candidates.append((parts[-2], parts[-1]))
    elif len(parts) == 1 and " " in parts[0]:
        head, _, tail = parts[0].rpartition(" ")
        candidates.append((head, tail))
    for city, state in candidates:
        # "TX 75201" style: drop trailing zip
        state = re.sub(r"\s*\d{5}(-\d{4})?$", "", state)
        code = state.upper() if len(state) == 2 else state_codes.get(_norm(state))
        if code and (hit := by_code.get((_norm(city), code))):
            lat, lng, name, st = hit
            return lat, lng, f"{name}, {st}"
    return None


def resolve_location(value, counter):
    if isinstance(value, dict):
        try:
            lat, lng = float(value["lat"]), float(value.get("lng", value.get("lon")))
        except (KeyError, TypeError, ValueError):
            raise InvalidLocation("Location objects need numeric 'lat' and 'lng'.")
        return _validated(Place(f"{lat},{lng}", lat, lng, f"{lat:.4f}, {lng:.4f}", "coordinates"))

    if not isinstance(value, str) or not value.strip():
        raise InvalidLocation("Both 'start' and 'finish' are required.")
    text = value.strip()

    if m := LATLNG_RE.match(text):
        lat, lng = float(m.group(1)), float(m.group(2))
        return _validated(Place(text, lat, lng, f"{lat:.4f}, {lng:.4f}", "coordinates"))

    if hit := _from_city_table(text):
        return _validated(Place(text, hit[0], hit[1], hit[2], "city_table"))

    return _validated(_nominatim(text, counter))


def _nominatim(text, counter):
    counter["geocoding"] += 1
    try:
        resp = requests.get(
            settings.NOMINATIM_URL,
            params={"q": text, "format": "jsonv2", "limit": 1, "countrycodes": "us"},
            headers={"User-Agent": settings.HTTP_USER_AGENT},
            timeout=settings.HTTP_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as exc:
        raise InvalidLocation(f"Could not geocode '{text}': {exc}", status=502, code="geocoding_failed")
    if not data:
        raise InvalidLocation(f"Could not find a US location for '{text}'.")
    hit = data[0]
    return Place(text, float(hit["lat"]), float(hit["lon"]), hit.get("display_name", text), "nominatim")


def _validated(place):
    if not (-90 <= place.lat <= 90 and -180 <= place.lng <= 180):
        raise InvalidLocation(f"Invalid coordinates for '{place.query}'.")
    if not in_contiguous_usa(place.lat, place.lng):
        raise InvalidLocation(f"'{place.query}' is not within the contiguous USA.")
    return place
