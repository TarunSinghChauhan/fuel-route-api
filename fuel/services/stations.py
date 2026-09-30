"""In-memory station index built from the pre-geocoded CSV.

The raw fuel file has no coordinates, so `manage.py geocode_stations` resolves
each station's city/state to coordinates once, offline. At request time there
are zero geocoding calls for stations.
"""
import csv
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import numpy as np

from .geo import to_xyz

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
GEOCODED_CSV = DATA_DIR / "stations_geocoded.csv"


@dataclass(frozen=True)
class StationIndex:
    ids: list
    names: list
    addresses: list
    cities: list
    states: list
    prices: np.ndarray
    lats: np.ndarray
    lngs: np.ndarray
    xyz: np.ndarray

    def __len__(self):
        return len(self.ids)


@lru_cache(maxsize=1)
def get_stations(path=None):
    path = Path(path) if path else GEOCODED_CSV
    rows = []
    with open(path, newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    lats = np.array([float(r["lat"]) for r in rows])
    lngs = np.array([float(r["lng"]) for r in rows])
    return StationIndex(
        ids=[r["id"] for r in rows],
        names=[r["name"] for r in rows],
        addresses=[r["address"] for r in rows],
        cities=[r["city"] for r in rows],
        states=[r["state"] for r in rows],
        prices=np.array([float(r["price"]) for r in rows]),
        lats=lats,
        lngs=lngs,
        xyz=to_xyz(lats, lngs),
    )
