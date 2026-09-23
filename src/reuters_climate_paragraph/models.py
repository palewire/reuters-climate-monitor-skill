"""Validated data models used by the paragraph generator."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from .errors import ClimateMonitorError
from .urls import SITE_ROOT

if TYPE_CHECKING:
    from collections.abc import Mapping
    from datetime import date

    from .rendering import ParagraphRenderer


@dataclass(frozen=True)
class Observation:
    """A validated monitor reading and its verification links.

    Args:
        scope: One of ``global``, ``region``, or ``location``.
        label: Human-readable geography label.
        date: Exact UTC date represented by the reading.
        daily_high_c: Published daily high in Celsius.
        normal_high_c: Published 1961-1990 normal in Celsius.
        anomaly_c: Published daily-high anomaly in Celsius.
        source_urls: Direct Reuters CDN URLs used for the lookup.
        site_url: Reuters Climate Monitor page URL for visual verification.
        coordinates: Resolved grid-cell coordinates for a point, if applicable.
        land_swapped: Whether an ocean click was resolved to nearby land.
        geocoder_url: Review URL for coordinates resolved by a geocoder.
        source: Published source label for history rows, if present.

    Example:
        ``Observation(...).to_payload()["scope"] == "global"``
    """

    scope: str
    label: str
    date: str
    daily_high_c: float
    normal_high_c: float
    anomaly_c: float
    source_urls: tuple[str, ...]
    site_url: str
    coordinates: tuple[float, float] | None = None
    land_swapped: bool = False
    geocoder_url: str | None = None
    source: str | None = None

    @classmethod
    def from_row(
        cls,
        scope: str,
        label: str,
        day: str,
        row: Mapping[str, Any],
        source_urls: tuple[str, ...],
        *,
        coordinates: tuple[float, float] | None = None,
        site_url: str | None = None,
        land_swapped: bool = False,
        geocoder_url: str | None = None,
        source: str | None = None,
    ) -> Observation:
        """Build an observation from published row fields.

        Args:
            scope: Observation scope.
            label: Human-readable geography label.
            day: Exact UTC date.
            row: Feed or tile properties.
            source_urls: Direct source URLs.
            coordinates: Resolved point coordinates, if any.
            site_url: Optional prebuilt page URL.
            land_swapped: Whether the point used nearby land.
            geocoder_url: Review URL for coordinates resolved by a geocoder.
            source: Published source label, if the feed provides one.

        Returns:
            A validated observation.

        Raises:
            ClimateMonitorError: If any required value is non-numeric.
        """
        values: dict[str, float] = {}
        for name in ("t2m_max_daily", "t2m_max_normal", "t2m_max_delta"):
            value = row.get(name)
            if not isinstance(value, (int, float)) or not math.isfinite(value):
                raise ClimateMonitorError(f"Reuters row has no finite {name}")
            values[name] = float(value)
        return cls(
            scope=scope,
            label=label,
            date=day,
            daily_high_c=values["t2m_max_daily"],
            normal_high_c=values["t2m_max_normal"],
            anomaly_c=values["t2m_max_delta"],
            source_urls=source_urls,
            site_url=site_url or SITE_ROOT,
            coordinates=coordinates,
            land_swapped=land_swapped,
            geocoder_url=geocoder_url,
            source=source if isinstance(source, str) else None,
        )

    def to_payload(
        self,
        *,
        today: date | None = None,
        renderer: ParagraphRenderer | None = None,
    ) -> dict[str, Any]:
        """Return the reading, paragraph, and verification URLs as JSON data.

        Args:
            today: Optional UTC date used when rendering today's date in tests.
            renderer: Optional paragraph renderer for dependency injection.

        Returns:
            A JSON-serializable dictionary with source values and copy.
        """
        if renderer is None:
            from .rendering import ParagraphRenderer

            renderer = ParagraphRenderer()
        output = renderer.render(self, today=today)
        payload = {
            "scope": self.scope,
            "label": self.label,
            "date": self.date,
            "daily_high_c": self.daily_high_c,
            "normal_high_c": self.normal_high_c,
            "anomaly_c": self.anomaly_c,
            "site_url": self.site_url,
            "coordinates": list(self.coordinates) if self.coordinates else None,
            "land_swapped": self.land_swapped,
            "geocoder_url": self.geocoder_url,
            **output,
        }
        if self.source is not None:
            payload["source"] = self.source
        return payload


@dataclass(frozen=True)
class ResolvedMapFeature:
    """A selected grid feature and its resolved coordinates.

    Args:
        properties: Published properties from the PMTiles feature.
        coordinates: Snapped longitude and latitude of the selected cell.
        land_swapped: Whether a nearby land feature replaced an ocean feature.
    """

    properties: dict[str, Any]
    coordinates: tuple[float, float]
    land_swapped: bool


def observation_from_row(
    scope: str,
    label: str,
    day: str,
    row: Mapping[str, Any],
    source_urls: tuple[str, ...],
    *,
    coordinates: tuple[float, float] | None = None,
    site_url: str | None = None,
    land_swapped: bool = False,
    geocoder_url: str | None = None,
    source: str | None = None,
) -> Observation:
    """Build an observation through the model factory.

    Args:
        scope: Observation scope.
        label: Human-readable geography label.
        day: Exact UTC date.
        row: Feed or tile properties.
        source_urls: Direct source URLs.
        coordinates: Resolved point coordinates, if any.
        site_url: Optional prebuilt page URL.
        land_swapped: Whether the point used nearby land.
        geocoder_url: Review URL for coordinates resolved by a geocoder.
        source: Published source label, if the feed provides one.

    Returns:
        A validated observation.
    """
    return Observation.from_row(
        scope,
        label,
        day,
        row,
        source_urls,
        coordinates=coordinates,
        site_url=site_url,
        land_swapped=land_swapped,
        geocoder_url=geocoder_url,
        source=source,
    )
