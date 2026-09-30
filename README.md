# Fuel Route API (Django)

Given a start and finish inside the USA, returns the driving route (GeoJSON + an
interactive map), the cost-optimal fuel stops along it, and total fuel spend for a
vehicle with a 500-mile range at 10 MPG.

## Run

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python manage.py runserver
python manage.py test
```

`fuel/data/stations_geocoded.csv` is committed. To regenerate it from the raw
price file: `python manage.py geocode_stations`.

## API

`POST /api/route/` (or `GET` with query params)

```json
{"start": "New York, NY", "finish": "Los Angeles, CA"}
```

`start` / `finish` accept `"City, ST"`, `"lat,lng"`, `{"lat":..,"lng":..}`, or a
free-form address. Optional: `start_fuel_percent` (default 100), `max_detour_miles`
(default 10).

Response: `route` (distance, duration, GeoJSON), `fuel_stops` (station, price, mile
marker, gallons, cost), `summary.total_fuel_cost`, `map_url`, `assumptions`, and
`meta` (elapsed ms, external API call counts).

`GET /api/route/map/?start=...&finish=...` renders the route and stops on a Leaflet map.

## Design

- **Routing calls:** exactly one OSRM request per uncached trip (`overview=simplified`
  keeps the payload small). Results are cached for an hour.
- **Geocoding calls:** none for `City, ST` or coordinates (bundled US cities table).
  Only free-form addresses trigger one Nominatim call each.
- **Stations:** the raw CSV has no coordinates, so `geocode_stations` assigns
  city-level coordinates once, offline. Canadian rows are dropped and duplicate
  station IDs keep the lowest price. Everything is held in memory as numpy arrays.
- **Station matching:** the route is sampled every mile, a KD-tree finds stations
  within the corridor, and each gets a mile marker. A request takes a few ms after
  the routing call.
- **Optimiser:** the classic gas-station greedy. If a cheaper stop (or the
  destination) is within a full tank, buy just enough to reach it; otherwise fill up
  and go to the cheapest reachable stop. It is verified against a brute-force DP in
  the tests. Top-offs under 5 gallons are skipped when the tank already covers the
  next leg (`FUEL_MIN_FILL_MILES`).

## Assumptions and limits

- The vehicle starts full and that fuel is not counted as spent; it arrives empty.
  Use `start_fuel_percent` to change this.
- Station locations are city centroids, so real exits can be several miles off.
- Detour distance to a station is not added to trip length.
- Contiguous USA only. The public OSRM server is for light use; set
  `ROUTING_BASE_URL` to a self-hosted OSRM for production.
- City coordinates come from kelvins/US-Cities-Database.
