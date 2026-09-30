import numpy as np

EARTH_RADIUS_MILES = 3958.8


def haversine_miles(lat1, lng1, lat2, lng2):
    lat1, lng1, lat2, lng2 = map(np.radians, (lat1, lng1, lat2, lng2))
    a = (
        np.sin((lat2 - lat1) / 2) ** 2
        + np.cos(lat1) * np.cos(lat2) * np.sin((lng2 - lng1) / 2) ** 2
    )
    return 2 * EARTH_RADIUS_MILES * np.arcsin(np.sqrt(a))


def to_xyz(lat, lng):
    """Points on a sphere (miles). Euclidean distance ~ great-circle distance
    for short ranges, which lets us use a KD-tree with no projection distortion."""
    lat = np.radians(np.asarray(lat, dtype=float))
    lng = np.radians(np.asarray(lng, dtype=float))
    return EARTH_RADIUS_MILES * np.column_stack(
        (np.cos(lat) * np.cos(lng), np.cos(lat) * np.sin(lng), np.sin(lat))
    )


def in_contiguous_usa(lat, lng):
    return 24.3 <= lat <= 49.5 and -125.1 <= lng <= -66.8
