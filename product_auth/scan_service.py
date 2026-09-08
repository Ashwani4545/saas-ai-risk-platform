"""Scan tracking and fraud-signal feature computation.

Two concrete fraud signals this computes, both standard in anti-counterfeit
systems:
  - duplicate scans: the same serial scanned an unusually high number of
    times is a signal that a counterfeit product has copied a legitimate
    QR code and is being sold/scanned in many places
  - location anomaly ("impossible travel"): two consecutive scans of the
    same serial that are far apart in distance but close together in time
    imply the product (or a cloned QR) exists in two places at once -
    physically impossible for one item, and a strong counterfeit signal
"""
import math
from datetime import datetime, timezone
from typing import Dict, List

from core import db

EARTH_RADIUS_KM = 6371.0


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two lat/lon points, in kilometers."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def _parse_ts(ts: str) -> datetime:
    return datetime.fromisoformat(ts)


def compute_scan_features(serial: str, tenant_id: str) -> Dict[str, float]:
    """Features describing this product's scan history so far, in the same
    style as feature_store/feature_service.py - a dict of named numeric
    features that both the fraud model and the RAG explainer consume."""
    history: List[dict] = db.get_scan_history(serial, tenant_id, limit=200)
    history = list(reversed(history))  # oldest first

    scan_count = len(history)
    if scan_count == 0:
        return {
            "scan_count": 0,
            "unique_locations": 0,
            "max_travel_speed_kmh": 0.0,
            "min_seconds_between_scans": 0.0,
            "scans_last_hour": 0,
        }

    unique_locations = len({(round(h["latitude"], 2), round(h["longitude"], 2)) for h in history})

    max_speed = 0.0
    min_gap_seconds = float("inf")
    for prev, curr in zip(history, history[1:]):
        t1, t2 = _parse_ts(prev["scanned_at"]), _parse_ts(curr["scanned_at"])
        seconds = max((t2 - t1).total_seconds(), 1.0)
        distance = haversine_km(prev["latitude"], prev["longitude"], curr["latitude"], curr["longitude"])
        speed_kmh = distance / (seconds / 3600)
        max_speed = max(max_speed, speed_kmh)
        min_gap_seconds = min(min_gap_seconds, seconds)

    if min_gap_seconds == float("inf"):
        min_gap_seconds = 0.0

    now = datetime.now(timezone.utc)
    scans_last_hour = sum(1 for h in history if (now - _parse_ts(h["scanned_at"])).total_seconds() <= 3600)

    return {
        "scan_count": float(scan_count),
        "unique_locations": float(unique_locations),
        "max_travel_speed_kmh": round(max_speed, 2),
        "min_seconds_between_scans": round(min_gap_seconds, 2),
        "scans_last_hour": float(scans_last_hour),
    }
