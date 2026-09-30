import random
from unittest import mock

import numpy as np
from django.core.cache import cache
from django.test import SimpleTestCase, TestCase

from .errors import InfeasibleTrip
from .services import geocode, planner
from .services.geo import haversine_miles


def dp_min_cost(pos, price, total, rng, mpg, start_fuel):
    """Brute-force reference: integer-mile DP over (station, fuel) states."""
    pts = sorted(zip(pos, price)) + [(total, 0.0)]
    INF = float("inf")
    best = {(0.0, start_fuel): 0.0}  # (position, fuel) -> cost, processed in order
    nodes = [(0.0, INF)] + pts
    cost = [[INF] * (rng + 1) for _ in nodes]
    cost[0][start_fuel] = 0.0
    for a, (pa, pra) in enumerate(nodes):
        for f in range(rng + 1):
            c = cost[a][f]
            if c == INF:
                continue
            # buy 0..(rng-f) miles of fuel here (not at the start node)
            for buy in range(0, rng - f + 1):
                if a == 0 and buy:
                    break
                c2, f2 = c + buy / mpg * pra if a else c, f + buy
                for b in range(a + 1, len(nodes)):
                    d = int(nodes[b][0] - pa)
                    if d > f2:
                        break
                    cost[b][f2 - d] = min(cost[b][f2 - d], c2)
    return min(cost[-1])


class PlannerTests(SimpleTestCase):
    def test_short_trip_needs_no_stops(self):
        purchases, total = planner.plan_fuel_stops(
            np.array([100.0]), np.array([3.0]), 300, 500, 10, 500
        )
        self.assertEqual(purchases, [])
        self.assertEqual(total, 0)

    def test_buys_only_enough_before_cheaper_station(self):
        # start full; station A (pos 400, $4) then B (pos 700, $3), dest 900.
        p, total = planner.plan_fuel_stops(
            np.array([400.0, 700.0]), np.array([4.0, 3.0]), 900, 500, 10, 500
        )
        self.assertEqual(len(p), 2)
        self.assertAlmostEqual(p[0].miles_bought, 200)   # just enough to reach B
        self.assertAlmostEqual(p[1].miles_bought, 200)   # just enough to finish
        self.assertAlmostEqual(total, 20 * 4.0 + 20 * 3.0)

    def test_infeasible_gap(self):
        with self.assertRaises(InfeasibleTrip):
            planner.plan_fuel_stops(np.array([100.0]), np.array([3.0]), 1000, 500, 10, 500)

    def test_matches_bruteforce_on_random_instances(self):
        rnd = random.Random(7)
        for _ in range(40):
            rng, mpg = 30, 1
            total = rnd.randint(40, 120)
            n = rnd.randint(3, 12)
            pos = sorted(rnd.sample(range(1, total), n))
            price = [rnd.choice([1.0, 1.5, 2.0, 2.5, 3.0]) for _ in pos]
            start = rnd.randint(rng // 2, rng)
            try:
                want = dp_min_cost(pos, price, total, rng, mpg, start)
            except Exception:
                continue
            try:
                _, got = planner.plan_fuel_stops(
                    np.array(pos, float), np.array(price), total, rng, mpg, start
                )
            except InfeasibleTrip:
                self.assertEqual(want, float("inf"))
                continue
            self.assertAlmostEqual(got, want, places=6, msg=(pos, price, total, start))


class GeocodeTests(SimpleTestCase):
    def test_offline_city_lookup(self):
        c = {"routing": 0, "geocoding": 0}
        for text in ("Chicago, IL", "chicago, illinois", "Chicago IL", "Chicago, IL, USA"):
            p = geocode.resolve_location(text, c)
            self.assertEqual(p.source, "city_table")
            self.assertAlmostEqual(p.lat, 41.85, delta=0.5)
        self.assertEqual(c["geocoding"], 0)

    def test_lat_lng_and_bounds(self):
        c = {"routing": 0, "geocoding": 0}
        self.assertEqual(geocode.resolve_location("40.7,-74.0", c).source, "coordinates")
        from .errors import InvalidLocation
        with self.assertRaises(InvalidLocation):
            geocode.resolve_location("51.5,-0.12", c)  # London


def fake_route(start, finish, counter):
    counter["routing"] += 1
    t = np.linspace(0, 1, 80)
    lat = start.lat + (finish.lat - start.lat) * t
    lng = start.lng + (finish.lng - start.lng) * t
    miles = haversine_miles(lat[:-1], lng[:-1], lat[1:], lng[1:]).sum() * 1.15
    return {"coords": np.column_stack((lng, lat)).tolist(),
            "distance_m": miles * 1609.344, "duration_s": miles / 62 * 3600}


class EndpointTests(TestCase):
    def setUp(self):
        cache.clear()

    @mock.patch("fuel.services.routing.fetch_route", side_effect=fake_route)
    def test_cross_country(self, m):
        r = self.client.post("/api/route/", {"start": "New York, NY", "finish": "Los Angeles, CA"},
                             content_type="application/json")
        self.assertEqual(r.status_code, 200, r.content)
        d = r.json()
        self.assertEqual(m.call_count, 1)
        self.assertEqual(d["meta"]["routing_api_calls"], 1)
        self.assertEqual(d["meta"]["geocoding_api_calls"], 0)
        self.assertGreater(len(d["fuel_stops"]), 2)
        self.assertAlmostEqual(
            sum(s["cost"] for s in d["fuel_stops"]), d["summary"]["total_fuel_cost"], delta=0.05
        )
        self.assertEqual(d["route"]["geometry"]["geometry"]["type"], "LineString")
        # never more than one tank between stops
        marks = [0] + [s["mile_marker"] for s in d["fuel_stops"]] + [d["route"]["distance_miles"]]
        self.assertTrue(all(b - a <= 500.5 for a, b in zip(marks, marks[1:])))
        # second identical request is served from cache with no routing call
        r2 = self.client.post("/api/route/", {"start": "New York, NY", "finish": "Los Angeles, CA"},
                              content_type="application/json").json()
        self.assertTrue(r2["meta"]["cached"])
        self.assertEqual(m.call_count, 1)

    def test_validation_errors(self):
        r = self.client.post("/api/route/", {"start": "Chicago, IL"}, content_type="application/json")
        self.assertEqual(r.status_code, 400)
        r = self.client.get("/api/route/", {"start": "51.5,-0.12", "finish": "Dallas, TX"})
        self.assertEqual(r.status_code, 400)

    @mock.patch("fuel.services.routing.fetch_route", side_effect=fake_route)
    def test_map_page(self, m):
        r = self.client.get("/api/route/map/", {"start": "Dallas, TX", "finish": "Chicago, IL"})
        self.assertEqual(r.status_code, 200)
        self.assertIn(b"leaflet", r.content)
