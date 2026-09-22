"""Published Reuters Climate Monitor and verification URLs."""

from __future__ import annotations

import urllib.parse
from dataclasses import dataclass
from datetime import UTC, date, datetime

from .errors import ClimateMonitorError

CDN_ROOT = "https://graphics.thomsonreuters.com/newsapps_climate-forecast"
HRES_MAP_ROOT = (
    "https://graphics.thomsonreuters.com/"
    "newsapps_reuters-climate-monitor/daily-anomalies-map/hres"
)
ERA5_MAP_ROOT = (
    "https://graphics.thomsonreuters.com/"
    "newsapps_reuters-climate-monitor/daily-anomalies-map/era5"
)
MAP_ROOT = HRES_MAP_ROOT
SITE_ROOT = "https://www.reuters.com/graphics/CLIMATE-AUTOMATED/MONITOR/akpeykqqapr/"
OPENSTREETMAP_ROOT = "https://www.openstreetmap.org/"


@dataclass(frozen=True)
class ReutersUrlBuilder:
    """Build URLs for published monitor data and verification pages.

    Args:
        cdn_root: Root URL for published JSON feeds.
        hres_map_root: Root URL for current and future HRES map data.
        era5_map_root: Root URL for historical ERA5 map data.
        site_root: Reuters Climate Monitor page URL.
        openstreetmap_root: OpenStreetMap verification URL.

    Example:
        ``ReutersUrlBuilder().region_feed_url("continent")``
    """

    cdn_root: str = CDN_ROOT
    hres_map_root: str = HRES_MAP_ROOT
    era5_map_root: str = ERA5_MAP_ROOT
    site_root: str = SITE_ROOT
    openstreetmap_root: str = OPENSTREETMAP_ROOT

    def global_feed_url(self) -> str:
        """Build the published global daily-average feed URL.

        Returns:
            The global feed URL.
        """
        return f"{self.cdn_root}/daily-global-averages/latest-daily-averages.json"

    def region_feed_url(self, region_set: str) -> str:
        """Build a published region-set daily-average feed URL.

        Args:
            region_set: Published region-set slug.

        Returns:
            The region-set feed URL.
        """
        return f"{self.cdn_root}/region-sets/{region_set}/latest-daily-averages.json"

    def anomaly_map_url(self, day: str, *, today: date | None = None) -> str:
        """Build the published anomaly map URL for a UTC date.

        Args:
            day: UTC date in ``YYYY-MM-DD`` form.
            today: Optional current UTC date used by tests.

        Returns:
            The HRES URL for today or a future date, or the ERA5 URL for a
            published past date.

        Raises:
            ClimateMonitorError: If ``day`` is not an ISO date.
        """
        try:
            parsed_day = date.fromisoformat(day)
        except ValueError as error:
            raise ClimateMonitorError(f"Invalid UTC date {day!r}") from error
        current_date = today or datetime.now(UTC).date()
        if parsed_day < current_date:
            return f"{self.era5_map_root}/{day}/t2m_max_delta.pmtiles"
        return f"{self.hres_map_root}/{day}/t2m_max_delta_data.pmtiles"

    def site_url(self, lat: float, lng: float, label: str) -> str:
        """Build a shareable Reuters Climate Monitor location URL.

        Args:
            lat: User-requested latitude.
            lng: User-requested longitude.
            label: Human-readable place label.

        Returns:
            A URL that reopens the monitor at the requested location.
        """
        query = urllib.parse.urlencode(
            {"lat": round(lat, 4), "lng": round(lng, 4), "zoom": 6, "place": label}
        )
        return f"{self.site_root}?{query}"

    def geocoder_point_url(self, lat: float, lng: float) -> str:
        """Build an OpenStreetMap link for a geocoded point.

        Args:
            lat: Geocoded latitude.
            lng: Geocoded longitude.

        Returns:
            A URL centered on the geocoded point.
        """
        query = urllib.parse.urlencode({"mlat": round(lat, 6), "mlon": round(lng, 6)})
        return f"{self.openstreetmap_root}?{query}#map=12/{lat:.6f}/{lng:.6f}"


DEFAULT_URL_BUILDER = ReutersUrlBuilder()


def anomaly_map_url(day: str, *, today: date | None = None) -> str:
    """Build an anomaly map URL with the default URL builder.

    Args:
        day: UTC date in ``YYYY-MM-DD`` form.
        today: Optional current UTC date used by tests.

    Returns:
        The published anomaly map URL.

    Raises:
        ClimateMonitorError: If ``day`` is not an ISO date.
    """
    return DEFAULT_URL_BUILDER.anomaly_map_url(day, today=today)


def build_site_url(lat: float, lng: float, label: str) -> str:
    """Build a Reuters Climate Monitor location URL.

    Args:
        lat: User-requested latitude.
        lng: User-requested longitude.
        label: Human-readable place label.

    Returns:
        A shareable Reuters Climate Monitor URL.
    """
    return DEFAULT_URL_BUILDER.site_url(lat, lng, label)


def build_geocoder_point_url(lat: float, lng: float) -> str:
    """Build an OpenStreetMap verification URL.

    Args:
        lat: Geocoded latitude.
        lng: Geocoded longitude.

    Returns:
        An OpenStreetMap URL centered on the point.
    """
    return DEFAULT_URL_BUILDER.geocoder_point_url(lat, lng)
