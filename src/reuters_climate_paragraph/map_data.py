"""Readers and coordinate helpers for published anomaly map tiles."""

from __future__ import annotations

import gzip
import math
import urllib.error
import urllib.request
from collections.abc import Callable, Iterable
from typing import Any

import mapbox_vector_tile
from pmtiles.reader import Reader

from .diagnostics import (
    get_logger,
    log_http_failure,
    log_http_response,
    safe_url,
)
from .errors import ClimateMonitorError
from .models import ResolvedMapFeature
from .urls import DEFAULT_URL_BUILDER, ReutersUrlBuilder

GRID_SIZE = 0.25
ZOOM = 8
MAX_LAND_SWAP_DISTANCE = GRID_SIZE * 2
RangeReader = Callable[[int, int], bytes]
RangeSourceFactory = Callable[[str], RangeReader]
TileReaderFactory = Callable[[RangeReader], Any]
LOGGER = get_logger(__name__)


class PointDataReader:
    """Read the nearest published anomaly grid cell for a coordinate.

    Args:
        range_source_factory: Optional factory for PMTiles byte readers.
        reader_factory: Optional PMTiles reader constructor for tests.
        url_builder: Optional URL builder for anomaly map locations.

    Example:
        ``PointDataReader().read("2026-09-22", 48.8, 2.3, "Paris")``
    """

    def __init__(
        self,
        range_source_factory: RangeSourceFactory | None = None,
        reader_factory: TileReaderFactory | None = None,
        url_builder: ReutersUrlBuilder | None = None,
    ) -> None:
        self._range_source_factory = range_source_factory or self.http_range_source
        self._reader_factory = reader_factory or Reader
        self._url_builder = url_builder or DEFAULT_URL_BUILDER

    def read(
        self,
        day: str,
        lat: float,
        lng: float,
        label: str,
    ) -> ResolvedMapFeature:
        """Read the nearest grid feature for a point.

        Args:
            day: Exact UTC date.
            lat: Latitude in decimal degrees.
            lng: Longitude in decimal degrees.
            label: Human-readable label used in errors.

        Returns:
            The selected published feature and its resolved coordinates.

        Raises:
            ClimateMonitorError: If the tile or feature is unavailable.
        """
        url = self._url_builder.anomaly_map_url(day)
        reader = self._reader_factory(self._range_source_factory(url))
        header = reader.header()
        tile_x, tile_y = self.tile_coordinates(lng, lat)
        tile = reader.get(ZOOM, tile_x, tile_y)
        if tile is None:
            raise ClimateMonitorError(
                f"No Reuters Climate Monitor tile for {label} at {day}"
            )
        compression = header["tile_compression"]
        if getattr(compression, "value", compression) == 2:
            tile = gzip.decompress(tile)
        decoded = mapbox_vector_tile.decode(tile)
        layer = decoded.get("data", {})
        features = layer.get("features", [])
        feature = self.resolve_feature(
            features,
            tile_x,
            tile_y,
            lat,
            lng,
            ZOOM,
            extent=layer.get("extent", 4096),
        )
        if feature is None:
            raise ClimateMonitorError(
                f"No Reuters Climate Monitor grid cell near {label}"
            )
        return feature

    @staticmethod
    def http_range_source(url: str) -> RangeReader:
        """Create a PMTiles byte reader backed by HTTP Range requests.

        Args:
            url: Absolute PMTiles URL.

        Returns:
            A callable accepting an inclusive byte offset and byte length.

        Example:
            ``get_bytes = PointDataReader.http_range_source(url)``
        """

        def get_bytes(offset: int, length: int) -> bytes:
            """Read one byte range from the PMTiles object.

            Args:
                offset: First byte to read.
                length: Number of bytes to read.

            Returns:
                Exactly the requested bytes.

            Raises:
                ClimateMonitorError: If the CDN returns an incomplete range.
            """
            end = offset + length - 1
            request = urllib.request.Request(  # noqa: S310 - Reuters HTTPS URL.
                url,
                headers={
                    "Range": f"bytes={offset}-{end}",
                    "User-Agent": "ReutersClimateSkill/0.1",
                },
            )
            LOGGER.debug(
                "GET PMTiles range url=%s range=bytes=%s-%s",
                safe_url(url),
                offset,
                end,
            )
            try:
                with urllib.request.urlopen(  # noqa: S310
                    request, timeout=30
                ) as response:
                    log_http_response(
                        LOGGER,
                        "GET PMTiles range",
                        url,
                        response.getcode(),
                        response.headers,
                    )
                    data = response.read()
            except urllib.error.HTTPError as error:
                log_http_failure(LOGGER, "GET PMTiles range", url, error)
                raise ClimateMonitorError(
                    f"Could not read Reuters tile {url}: HTTP {error.code} {error.reason}"
                ) from error
            except (OSError, urllib.error.URLError) as error:
                log_http_failure(LOGGER, "GET PMTiles range", url, error)
                raise ClimateMonitorError(
                    f"Could not read Reuters tile {url}: {error}"
                ) from error
            if len(data) != length:
                raise ClimateMonitorError(
                    f"Reuters tile returned {len(data)} bytes; expected {length}"
                )
            return data

        return get_bytes

    @staticmethod
    def snap_to_grid(value: float) -> float:
        """Match JavaScript ``Math.round`` snapping to the 0.25-degree grid.

        Args:
            value: Decimal-degree coordinate.

        Returns:
            The nearest grid center.
        """
        return math.floor(value / GRID_SIZE + 0.5) * GRID_SIZE

    @classmethod
    def tile_coordinates(cls, lng: float, lat: float) -> tuple[int, int]:
        """Calculate the zoom-eight tile containing a coordinate.

        Args:
            lng: Longitude.
            lat: Latitude.

        Returns:
            A ``(x, y)`` tile coordinate tuple.
        """
        grid_lng = cls.snap_to_grid(lng)
        grid_lat = cls.snap_to_grid(lat)
        tile_x = math.floor(((grid_lng + 180) / 360) * 2**ZOOM)
        tile_y = math.floor(
            (
                1
                - math.log(
                    math.tan(math.radians(grid_lat))
                    + 1 / math.cos(math.radians(grid_lat))
                )
                / math.pi
            )
            / 2
            * 2**ZOOM
        )
        return tile_x, tile_y

    @classmethod
    def resolve_feature(
        cls,
        features: Iterable[dict[str, Any]],
        tile_x: int,
        tile_y: int,
        lat: float,
        lng: float,
        zoom: int,
        extent: int = 4096,
    ) -> ResolvedMapFeature | None:
        """Choose the nearest usable feature and prefer nearby land.

        Args:
            features: Decoded Mapbox Vector Tile point features.
            tile_x: Tile x coordinate.
            tile_y: Tile y coordinate.
            lat: Requested latitude.
            lng: Requested longitude.
            zoom: Tile zoom.
            extent: Vector-tile coordinate extent.

        Returns:
            A resolved feature, or ``None`` when no point feature exists.
        """
        reference_lat = cls.snap_to_grid(lat)
        reference_lng = cls.snap_to_grid(lng)
        points: list[dict[str, Any]] = []
        for feature in features:
            geometry = feature.get("geometry", {})
            coords = geometry.get("coordinates", [])
            if geometry.get("type") != "Point" or len(coords) != 2:
                continue
            properties = feature.get("properties", {})
            property_lng = properties.get("longitude")
            property_lat = properties.get("latitude")
            if (
                isinstance(property_lng, (int, float))
                and math.isfinite(property_lng)
                and isinstance(property_lat, (int, float))
                and math.isfinite(property_lat)
            ):
                feature_lng = float(property_lng)
                feature_lat = float(property_lat)
            else:
                feature_lng = ((tile_x + coords[0] / extent) / 2**zoom) * 360 - 180
                n = math.pi - (2 * math.pi * (tile_y + coords[1] / extent)) / 2**zoom
                feature_lat = math.degrees(
                    math.atan(0.5 * (math.exp(n) - math.exp(-n)))
                )
            distance = math.hypot(
                feature_lng - reference_lng, feature_lat - reference_lat
            )
            points.append(
                {
                    "properties": properties,
                    "distance": distance,
                    "coordinates": (
                        cls.snap_to_grid(feature_lng),
                        cls.snap_to_grid(feature_lat),
                    ),
                }
            )
        if not points:
            return None
        points.sort(key=lambda point: point["distance"])
        nearest = points[0]
        chosen = nearest
        if nearest["properties"].get("is_land") is False:
            land = next(
                (
                    point
                    for point in points
                    if point["properties"].get("is_land") is True
                    and point["distance"] <= MAX_LAND_SWAP_DISTANCE
                ),
                None,
            )
            if land is not None:
                chosen = land
        return ResolvedMapFeature(
            properties=chosen["properties"],
            coordinates=chosen["coordinates"],
            land_swapped=chosen is not nearest,
        )

    @classmethod
    def choose_feature(
        cls,
        features: Iterable[dict[str, Any]],
        tile_x: int,
        tile_y: int,
        lat: float,
        lng: float,
        zoom: int,
        extent: int = 4096,
    ) -> dict[str, Any] | None:
        """Return a legacy mapping for a resolved feature.

        Args:
            features: Decoded Mapbox Vector Tile point features.
            tile_x: Tile x coordinate.
            tile_y: Tile y coordinate.
            lat: Requested latitude.
            lng: Requested longitude.
            zoom: Tile zoom.
            extent: Vector-tile coordinate extent.

        Returns:
            A feature mapping for legacy callers, or ``None``.
        """
        feature = cls.resolve_feature(
            features,
            tile_x,
            tile_y,
            lat,
            lng,
            zoom,
            extent,
        )
        if feature is None:
            return None
        return {
            "properties": feature.properties,
            "coordinates": feature.coordinates,
            "land_swapped": feature.land_swapped,
        }


def http_range_source(url: str) -> RangeReader:
    """Create a PMTiles byte reader backed by HTTP Range requests.

    Args:
        url: Absolute PMTiles URL.

    Returns:
        A callable accepting an inclusive byte offset and byte length.

    Example:
        ``get_bytes = http_range_source(url); header = get_bytes(0, 127)``
    """

    return PointDataReader.http_range_source(url)


def snap_to_grid(value: float) -> float:
    """Match JavaScript ``Math.round`` snapping to the 0.25-degree grid.

    Args:
        value: Decimal-degree coordinate.

    Returns:
        The nearest grid center.

    Example:
        ``snap_to_grid(48.8566) == 48.75``
    """
    return PointDataReader.snap_to_grid(value)


def tile_coordinates(lng: float, lat: float) -> tuple[int, int]:
    """Calculate the zoom-eight Web Mercator tile containing a coordinate.

    Args:
        lng: Longitude.
        lat: Latitude.

    Returns:
        A ``(x, y)`` tile coordinate tuple.
    """
    return PointDataReader.tile_coordinates(lng, lat)


def resolve_feature(
    features: Iterable[dict[str, Any]],
    tile_x: int,
    tile_y: int,
    lat: float,
    lng: float,
    zoom: int,
    extent: int = 4096,
) -> ResolvedMapFeature | None:
    """Choose the nearest usable feature and prefer nearby land.

    Args:
        features: Decoded Mapbox Vector Tile point features.
        tile_x: Tile x coordinate.
        tile_y: Tile y coordinate.
        lat: Requested latitude.
        lng: Requested longitude.
        zoom: Tile zoom.
        extent: Vector-tile coordinate extent.

    Returns:
        A resolved feature, or ``None`` when no point feature is present.
    """
    return PointDataReader.resolve_feature(
        features,
        tile_x,
        tile_y,
        lat,
        lng,
        zoom,
        extent,
    )


def choose_feature(
    features: Iterable[dict[str, Any]],
    tile_x: int,
    tile_y: int,
    lat: float,
    lng: float,
    zoom: int,
    extent: int = 4096,
) -> dict[str, Any] | None:
    """Choose a feature through the object-based resolver.

    Args:
        features: Decoded Mapbox Vector Tile point features.
        tile_x: Tile x coordinate.
        tile_y: Tile y coordinate.
        lat: Requested latitude.
        lng: Requested longitude.
        zoom: Tile zoom.
        extent: Vector-tile coordinate extent.

    Returns:
        The legacy feature mapping, or ``None`` when no point feature exists.
    """
    return PointDataReader.choose_feature(
        features,
        tile_x,
        tile_y,
        lat,
        lng,
        zoom,
        extent,
    )
