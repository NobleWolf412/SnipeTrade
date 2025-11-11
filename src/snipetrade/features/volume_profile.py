"""Basic helpers for volume profile derived zones."""

from __future__ import annotations

from typing import Iterable, List, Sequence, Tuple


def hvn_lvn_levels(profile: Iterable[Tuple[float, float]], top_n: int = 1) -> Tuple[List[float], List[float]]:
    """Return high-volume and low-volume nodes from a profile."""

    cleaned: List[Tuple[float, float]] = []
    for price, volume in profile:
        try:
            cleaned.append((float(price), float(volume)))
        except (TypeError, ValueError):
            continue

    if not cleaned:
        return [], []

    sorted_profile = sorted(cleaned, key=lambda x: x[1], reverse=True)
    hvn = [price for price, _ in sorted_profile[:top_n]]

    sorted_low = sorted(cleaned, key=lambda x: x[1])
    lvn = [price for price, _ in sorted_low[:top_n]]
    return hvn, lvn
