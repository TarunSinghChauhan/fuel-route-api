from django.apps import AppConfig


class FuelConfig(AppConfig):
    name = "fuel"

    def ready(self):
        # Warm the in-memory station index so the first request is fast.
        from .services.stations import get_stations

        try:
            get_stations()
        except FileNotFoundError:
            # Run `python manage.py geocode_stations` to generate the data file.
            pass
