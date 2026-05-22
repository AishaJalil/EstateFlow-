import math
from typing import Any

MAX_ACTIVE_BOOKINGS = 5
DEFAULT_TOP_N = 6


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _active_bookings(vendor: dict[str, Any]) -> int:
    """`available` column = count of active bookings (vendors at 5+ are at capacity)."""
    raw = vendor.get("available", 0)
    if isinstance(raw, bool):
        return 0 if raw else MAX_ACTIVE_BOOKINGS
    try:
        return max(0, int(raw))
    except (TypeError, ValueError):
        return 0


def _score_vendor(
    vendor: dict[str, Any],
    specialty_norm: str,
    tenant_lat: float | None,
    tenant_lon: float | None,
    radius_km: float,
) -> tuple[float, dict[str, Any]] | None:
    if vendor.get("specialty", "").lower() != specialty_norm:
        return None

    active = _active_bookings(vendor)
    if active >= MAX_ACTIVE_BOOKINGS:
        return None

    score = float(vendor.get("rating") or 0)
    distance = None

    if tenant_lat is not None and tenant_lon is not None:
        vlat, vlon = vendor.get("latitude"), vendor.get("longitude")
        if vlat is not None and vlon is not None:
            distance = haversine_km(tenant_lat, tenant_lon, float(vlat), float(vlon))
            if distance > radius_km:
                return None
            score += max(0, 5 - distance)

    # Prefer vendors with fewer active bookings (0 is best; 4 still eligible)
    capacity_bonus = max(0, MAX_ACTIVE_BOOKINGS - active) * 0.75
    score += capacity_bonus

    return score, {**vendor, "distance_km": distance, "active_bookings": active}


def rank_vendors_top(
    vendors: list[dict[str, Any]],
    specialty: str,
    tenant_lat: float | None,
    tenant_lon: float | None,
    radius_km: float,
    top_n: int = DEFAULT_TOP_N,
) -> list[dict[str, Any]]:
    """Return up to `top_n` vendors sorted by match score (rating, geo, capacity)."""
    specialty_norm = specialty.lower().strip()
    candidates: list[tuple[float, dict]] = []

    for vendor in vendors:
        scored = _score_vendor(vendor, specialty_norm, tenant_lat, tenant_lon, radius_km)
        if scored:
            candidates.append(scored)

    candidates.sort(key=lambda x: x[0], reverse=True)
    return [v for _, v in candidates[:top_n]]


def rank_vendors(
    vendors: list[dict[str, Any]],
    specialty: str,
    tenant_lat: float | None,
    tenant_lon: float | None,
    radius_km: float,
) -> dict[str, Any] | None:
    """Single best vendor (backward compatible)."""
    top = rank_vendors_top(vendors, specialty, tenant_lat, tenant_lon, radius_km, top_n=1)
    return top[0] if top else None
