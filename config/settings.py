import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-only-insecure-key")
DEBUG = os.environ.get("DJANGO_DEBUG", "1") == "1"
ALLOWED_HOSTS = os.environ.get(
    "DJANGO_ALLOWED_HOSTS", "*" if DEBUG else "localhost,127.0.0.1"
).split(",")

INSTALLED_APPS = ["fuel"]
MIDDLEWARE = ["django.middleware.common.CommonMiddleware"]
ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# The API is stateless; no DB tables are used, but Django wants a default entry.
DATABASES = {
    "default": {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "db.sqlite3"}
}

CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}

USE_TZ = True
TIME_ZONE = "UTC"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---- Fuel planner settings -------------------------------------------------
FUEL_MAX_RANGE_MILES = 500
FUEL_MPG = 10
# Stations further than this from the route line are ignored (miles).
FUEL_CORRIDOR_MILES = float(os.environ.get("FUEL_CORRIDOR_MILES", 10))
# Skip top-offs smaller than this when the tank already covers the next leg.
FUEL_MIN_FILL_MILES = 50
# Route sampling resolution used for station matching (miles).
FUEL_SAMPLE_STEP_MILES = 1.0
ROUTE_CACHE_SECONDS = 60 * 60

# ---- External services -----------------------------------------------------
ROUTING_BASE_URL = os.environ.get("ROUTING_BASE_URL", "https://router.project-osrm.org")
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
HTTP_USER_AGENT = "spotter-fuel-route-assessment/1.0"
HTTP_TIMEOUT_SECONDS = 10
