"""Client orchestration for published Reuters Climate Monitor data."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, date, datetime

from .errors import ClimateMonitorError
from .feeds import JsonFetcher, MonitorFeedClient
from .geocoder import NominatimGeocoder, validate_coordinates
from .map_data import (
    PointDataReader,
    RangeSourceFactory,
    TileReaderFactory,
)
from .models import Observation
from .urls import DEFAULT_URL_BUILDER, ReutersUrlBuilder

Geocoder = Callable[[str], tuple[float, float]]


class ClimateMonitorClient:
    """Read published monitor feeds and point map data.

    Args:
        json_fetcher: Optional function used to fetch JSON fixtures or feeds.
        range_source_factory: Optional factory for PMTiles byte readers.
        geocoder: Optional callable for named locations.
        feed_client: Optional feed client for full dependency injection.
        point_reader: Optional point reader for full dependency injection.
        url_builder: Optional builder for published URLs.
        reader_factory: Optional PMTiles reader constructor for tests.

    Example:
        ``ClimateMonitorClient().global_observation("2026-09-22")``
    """

    def __init__(
        self,
        json_fetcher: JsonFetcher | None = None,
        range_source_factory: RangeSourceFactory | None = None,
        geocoder: Geocoder | None = None,
        *,
        feed_client: MonitorFeedClient | None = None,
        point_reader: PointDataReader | None = None,
        url_builder: ReutersUrlBuilder | None = None,
        reader_factory: TileReaderFactory | None = None,
    ) -> None:
        builder = url_builder or DEFAULT_URL_BUILDER
        self._feed_client = feed_client or MonitorFeedClient(
            json_fetcher=json_fetcher,
            url_builder=builder,
        )
        self._point_reader = point_reader or PointDataReader(
            range_source_factory=range_source_factory,
            reader_factory=reader_factory,
            url_builder=builder,
        )
        self._geocoder = geocoder or NominatimGeocoder()
        self._url_builder = builder

    def global_observation(self, day: str) -> Observation:
        """Fetch the globe's reading for an exact UTC date.

        Args:
            day: UTC date in ``YYYY-MM-DD`` form.

        Returns:
            A validated global observation.
        """
        row, source_url = self._feed_client.global_row(day)
        return Observation.from_row(
            "global",
            "the globe",
            day,
            row,
            (source_url,),
        )

    def region_observation(
        self,
        region_set: str,
        region: str,
        day: str,
        *,
        today: date | None = None,
    ) -> Observation:
        """Fetch a named region's reading for an exact UTC date.

        Args:
            region_set: Published region-set slug.
            region: Exact display label in that feed.
            day: UTC date in ``YYYY-MM-DD`` form.
            today: Optional current date used to select the current or
                full-history published feed.

        Returns:
            A validated regional observation.
        """
        current_date = today or datetime.now(UTC).date()
        if date.fromisoformat(day) < current_date:
            row, source_url = self._feed_client.region_history_row(
                region_set,
                region,
                day,
            )
        else:
            row, source_url = self._feed_client.region_row(region_set, region, day)
        return Observation.from_row(
            "region",
            region,
            day,
            row,
            (source_url,),
            source=row.get("source"),
        )

    def location_observation(
        self,
        label: str,
        lat: float | None,
        lng: float | None,
        day: str,
    ) -> Observation:
        """Fetch the nearest daily anomaly grid cell for a point.

        Args:
            label: Human-readable name supplied by the newsroom user.
            lat: Latitude in decimal degrees, or ``None`` to geocode ``label``.
            lng: Longitude in decimal degrees, or ``None`` to geocode ``label``.
            day: UTC date in ``YYYY-MM-DD`` form.

        Returns:
            A validated point observation, including resolved grid coordinates.

        Raises:
            ClimateMonitorError: If the coordinates or published tile is
                unusable.
        """
        if (lat is None) != (lng is None):
            raise ClimateMonitorError("Location requests need both --lat and --lng")
        geocoder_url = None
        if lat is None or lng is None:
            resolved_lat, resolved_lng = self._geocoder(label)
            geocoder_url = self._url_builder.geocoder_point_url(
                resolved_lat, resolved_lng
            )
        else:
            resolved_lat, resolved_lng = lat, lng
        validate_coordinates(resolved_lat, resolved_lng)
        feature = self._point_reader.read(
            day,
            resolved_lat,
            resolved_lng,
            label,
        )
        return Observation.from_row(
            "location",
            label,
            day,
            feature.properties,
            (self._url_builder.anomaly_map_url(day),),
            coordinates=feature.coordinates,
            site_url=self._url_builder.site_url(resolved_lat, resolved_lng, label),
            land_swapped=feature.land_swapped,
            geocoder_url=geocoder_url,
        )
