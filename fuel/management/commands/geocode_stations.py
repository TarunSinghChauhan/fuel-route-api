"""Build fuel/data/stations_geocoded.csv from the raw OPIS price file.

The raw file only has city/state, so each station gets its city's coordinates
from the bundled US cities table (done once, offline). Canadian rows are
dropped (assignment is US-only), and duplicate station IDs keep the lowest price.
"""
import csv

from django.core.management.base import BaseCommand

from fuel.services.stations import DATA_DIR

US_STATES = set(
    "AL AK AZ AR CA CO CT DE DC FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH "
    "NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY".split()
)


def norm(s):
    return " ".join(s.replace(".", "").replace("'", "").upper().split())


class Command(BaseCommand):
    help = "Geocode the raw fuel price CSV to city-level coordinates."

    def handle(self, *args, **opts):
        cities = {}
        with open(DATA_DIR / "us_cities.csv", newline="", encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                cities.setdefault((norm(r["CITY"]), r["STATE_CODE"]),
                                  (r["LATITUDE"], r["LONGITUDE"]))

        best, skipped_non_us, unmatched = {}, 0, 0
        with open(DATA_DIR / "fuel_prices_raw.csv", newline="", encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                if r["State"] not in US_STATES:
                    skipped_non_us += 1
                    continue
                coords = cities.get((norm(r["City"]), r["State"]))
                if not coords:
                    unmatched += 1
                    continue
                sid, price = r["OPIS Truckstop ID"], float(r["Retail Price"])
                if sid in best and best[sid]["price"] <= price:
                    continue
                best[sid] = {
                    "id": sid, "name": r["Truckstop Name"].strip(),
                    "address": r["Address"].strip(), "city": r["City"].strip(),
                    "state": r["State"], "price": price,
                    "lat": coords[0], "lng": coords[1],
                }

        out = DATA_DIR / "stations_geocoded.csv"
        with open(out, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=["id", "name", "address", "city", "state",
                                               "price", "lat", "lng"])
            w.writeheader()
            w.writerows(best.values())
        self.stdout.write(self.style.SUCCESS(
            f"Wrote {len(best)} stations to {out} "
            f"(skipped {skipped_non_us} non-US rows, {unmatched} unmatched cities)"))
