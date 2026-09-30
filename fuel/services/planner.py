"""Route sampling, corridor station matching, and the cost-optimal refuelling plan."""
from dataclasses import dataclass

import numpy as np
from scipy.spatial import cKDTree

from ..errors import InfeasibleTrip
from .geo import haversine_miles, to_xyz

EPS = 1e-6


# ---------------------------------------------------------------- route sampling
def sample_route(coords_lng_lat, total_miles, step_miles):
    """Return (positions_miles, lats, lngs) sampled every ~step_miles along the route.

    Positions are scaled so the final position equals the routing engine's own
    distance figure (the simplified geometry is a little shorter than the road).
    """
    pts = np.asarray(coords_lng_lat, dtype=float)
    lngs, lats = pts[:, 0], pts[:, 1]
    seg = haversine_miles(lats[:-1], lngs[:-1], lats[1:], lngs[1:])
    cum = np.concatenate(([0.0], np.cumsum(seg)))
    if cum[-1] <= 0:
        return np.array([0.0, total_miles]), lats[[0, -1]], lngs[[0, -1]]
    cum *= total_miles / cum[-1]
    positions = np.unique(np.append(np.arange(0.0, total_miles, step_miles), total_miles))
    return positions, np.interp(positions, cum, lats), np.interp(positions, cum, lngs)


def stations_along_route(index, positions, lats, lngs, corridor_miles):
    """Stations within `corridor_miles` of the route, with their mile marker."""
    tree = cKDTree(to_xyz(lats, lngs))
    dist, nearest = tree.query(index.xyz, distance_upper_bound=corridor_miles)
    mask = np.isfinite(dist)
    st_idx = np.nonzero(mask)[0]
    return st_idx, positions[nearest[mask]], dist[mask]


# ---------------------------------------------------------------- planning
@dataclass
class Purchase:
    node: int          # index into the nodes list (station rows)
    miles_bought: float
    gallons: float
    price: float
    cost: float
    fuel_on_arrival_miles: float


def plan_fuel_stops(positions, prices, total_miles, range_miles, mpg, start_fuel_miles,
                    min_fill_miles=0.0):
    """Cost-optimal refuelling for the classic 'gas station' problem.

    positions/prices describe candidate stations (same length). Greedy rule that
    is optimal for this problem: at each stop, if a cheaper stop (or the
    destination) is reachable on a full tank, buy only enough to reach the first
    such stop; otherwise fill the tank and drive to the cheapest reachable stop.

    `min_fill_miles` (default 0 = exact optimum) skips pointless top-offs: when
    the tank already covers the next leg, a fill-up smaller than this is not
    made. This trades at most a few cents per gallon on a small volume for
    far fewer stops. Trips always stay feasible.

    Returns (purchases, total_cost). `Purchase.node` indexes the input arrays.
    """
    order = np.argsort(positions, kind="stable")
    pos = [0.0] + [float(positions[k]) for k in order] + [float(total_miles)]
    price = [float("inf")] + [float(prices[k]) for k in order] + [0.0]
    # node -> original station index (None for start / destination)
    orig = [None] + [int(k) for k in order] + [None]
    n = len(pos)

    i, fuel = 0, min(start_fuel_miles, range_miles)
    purchases = []

    while i < n - 1:
        cur = pos[i]
        cheaper = cheapest = None
        j = i + 1
        while j < n and pos[j] - cur <= range_miles + EPS:
            if price[j] < price[i]:
                cheaper = j
                break
            if cheapest is None or price[j] <= price[cheapest]:
                cheapest = j
            j += 1

        target = cheaper if cheaper is not None else cheapest
        if target is None:
            raise InfeasibleTrip(
                f"No fuel station within {range_miles:.0f} miles after mile {cur:.0f}; "
                "the vehicle cannot complete this trip."
            )
        dist = pos[target] - cur
        if cheaper is not None:
            buy = max(0.0, dist - fuel)
        else:
            buy = max(0.0, range_miles - fuel)
            if buy < min_fill_miles and fuel >= dist:
                buy = 0.0

        if buy > EPS:
            if orig[i] is None:
                raise InfeasibleTrip(
                    "The starting fuel level cannot reach the first fuel station."
                )
            gallons = buy / mpg
            purchases.append(
                Purchase(orig[i], buy, gallons, price[i], gallons * price[i], fuel)
            )
        fuel = max(0.0, fuel + buy - dist)
        i = target

    return purchases, sum(p.cost for p in purchases)
