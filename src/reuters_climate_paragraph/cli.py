"""Fetch Reuters Climate Monitor data and render newsroom-ready copy."""

from __future__ import annotations

import gzip
import json
import math
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any, cast

import click
import mapbox_vector_tile
from pmtiles.reader import Reader

from .errors import ClimateMonitorError
from .geocoder import NominatimGeocoder, validate_coordinates
from .temperature import DEFAULT_TEMPERATURE_FORMATTER

CDN_ROOT = "https://graphics.thomsonreuters.com/newsapps_climate-forecast"
HRES_MAP_ROOT = (
    "https://graphics.thomsonreuters.com/"
    "newsapps_reuters-climate-monitor/daily-anomalies-map/hres"
)
ERA5_MAP_ROOT = (
    "https://graphics.thomsonreuters.com/"
    "newsapps_reuters-climate-monitor/daily-anomalies-map/era5"
)
# Kept as the current/future map root for callers that import this constant.
MAP_ROOT = HRES_MAP_ROOT
SITE_ROOT = "https://www.reuters.com/graphics/CLIMATE-AUTOMATED/MONITOR/akpeykqqapr/"
OPENSTREETMAP_ROOT = "https://www.openstreetmap.org/"
CAUTION = (
    "Verify the date, place, and figures against the linked Reuters Climate "
    "Monitor before publication."
)
GRID_SIZE = 0.25
ZOOM = 8
MAX_LAND_SWAP_DISTANCE = GRID_SIZE * 2
CONTINENT_LABELS = {
    "Africa",
    "Asia",
    "Australia",
    "Europe",
    "North America",
    "South America",
}
REGION_SETS = {
    "continent",
    "western-europe",
    "us-contiguous",
    "ncei-climate",
    "country",
}

JsonFetcher = Callable[[str], object]
Geocoder = Callable[[str], tuple[float, float]]


def format_absolute_temperature(value: float, unit_name: str) -> str:
    """Format an absolute temperature through the shared formatter.

    Args:
        value: Absolute temperature in the selected display unit.
        unit_name: Full unit name, either ``Celsius`` or ``Fahrenheit``.

    Returns:
        A Reuters-style whole-degree temperature.
    """
    return DEFAULT_TEMPERATURE_FORMATTER.format_absolute(value, unit_name)


def format_anomaly_temperature(value: float, unit_abbreviation: str) -> str:
    """Format an anomaly through the shared formatter.

    Args:
        value: Anomaly temperature in the selected display unit.
        unit_abbreviation: Unit abbreviation, either ``C`` or ``F``.

    Returns:
        A Reuters-style one-decimal anomaly.
    """
    return DEFAULT_TEMPERATURE_FORMATTER.format_anomaly(value, unit_abbreviation)


def format_temperature_pair(value_c: float, *, anomaly: bool = False) -> str:
    """Format a Celsius/Fahrenheit pair through the shared formatter.

    Args:
        value_c: Temperature in degrees Celsius.
        anomaly: Whether to format the value as a one-decimal anomaly.

    Returns:
        A Reuters-style Celsius-first temperature pair.
    """
    return DEFAULT_TEMPERATURE_FORMATTER.format_pair(value_c, anomaly=anomaly)


def anomaly_map_url(day: str, *, today: date | None = None) -> str:
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
        return f"{ERA5_MAP_ROOT}/{day}/t2m_max_delta.pmtiles"
    return f"{HRES_MAP_ROOT}/{day}/t2m_max_delta_data.pmtiles"


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

    def to_payload(self, *, today: date | None = None) -> dict[str, Any]:
        """Return the reading, paragraph, and verification URLs as JSON data.

        Args:
            today: Optional UTC date used when rendering today's date in tests.

        Returns:
            A JSON-serializable dictionary with source values and copy.
        """
        output = format_observation(self, today=today)
        return {
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


class ClimateMonitorClient:
    """Read and validate Reuters Climate Monitor feeds and map tiles.

    Args:
        json_fetcher: Optional function used to fetch JSON. Tests inject a
            deterministic fixture reader.
        range_source_factory: Optional factory for PMTiles byte readers.

    Example:
        ``client = ClimateMonitorClient()``
    """

    def __init__(
        self,
        json_fetcher: JsonFetcher | None = None,
        range_source_factory: Callable[[str], Callable[[int, int], bytes]]
        | None = None,
        geocoder: Geocoder | None = None,
    ) -> None:
        self._json_fetcher = json_fetcher or fetch_json
        self._range_source_factory = range_source_factory or http_range_source
        self._geocoder = geocoder or NominatimGeocoder()

    def global_observation(self, day: str) -> Observation:
        """Fetch the globe's reading for an exact UTC date.

        Args:
            day: UTC date in ``YYYY-MM-DD`` form.

        Returns:
            A validated global observation.

        Raises:
            ClimateMonitorError: If the feed or date is unusable.
        """
        url = f"{CDN_ROOT}/daily-global-averages/latest-daily-averages.json"
        row = select_exact_row(self._json_fetcher(url), day, "global")
        return observation_from_row("global", "the globe", day, row, (url,))

    def region_observation(self, region_set: str, region: str, day: str) -> Observation:
        """Fetch a named region's reading for an exact UTC date.

        Args:
            region_set: Published region-set slug.
            region: Exact display label in that feed.
            day: UTC date in ``YYYY-MM-DD`` form.

        Returns:
            A validated regional observation.

        Raises:
            ClimateMonitorError: If the region set, region, feed, or date is
                unusable.
        """
        validate_region_request(region_set, region)
        url = f"{CDN_ROOT}/region-sets/{region_set}/latest-daily-averages.json"
        rows = as_rows(self._json_fetcher(url), url)
        key = "continent" if region_set == "continent" else "region"
        matching = [row for row in rows if row.get(key) == region]
        row = select_exact_row(matching, day, region)
        return observation_from_row("region", region, day, row, (url,))

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
            ClimateMonitorError: If the coordinates, tile, or feature is
                unusable.
        """
        if (lat is None) != (lng is None):
            raise ClimateMonitorError("Location requests need both --lat and --lng")
        geocoder_url = None
        if lat is None or lng is None:
            lat, lng = self._geocoder(label)
            geocoder_url = build_geocoder_point_url(lat, lng)
        validate_coordinates(lat, lng)
        url = anomaly_map_url(day)
        reader = Reader(self._range_source_factory(url))
        header = reader.header()
        tile_x, tile_y = tile_coordinates(lng, lat)
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
        feature = choose_feature(
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
        properties = feature["properties"]
        resolved = feature["coordinates"]
        site_url = build_site_url(lat, lng, label)
        return observation_from_row(
            "location",
            label,
            day,
            properties,
            (url,),
            coordinates=resolved,
            site_url=site_url,
            land_swapped=feature["land_swapped"],
            geocoder_url=geocoder_url,
        )


def fetch_json(url: str) -> object:
    """Fetch JSON from a Reuters CDN URL.

    Args:
        url: Absolute Reuters CDN URL.

    Returns:
        The decoded JSON value.

    Raises:
        ClimateMonitorError: If the request or JSON decoding fails.

    Example:
        ``raw = fetch_json("https://example.test/feed.json")``
    """
    request = urllib.request.Request(  # noqa: S310 - Reuters HTTPS URL.
        url,
        headers={"Accept": "application/json", "User-Agent": "ReutersClimateSkill/0.1"},
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310
            return json.load(response)
    except (OSError, urllib.error.URLError, json.JSONDecodeError) as error:
        raise ClimateMonitorError(
            f"Could not read Reuters feed {url}: {error}"
        ) from error


def geocode_place(label: str) -> tuple[float, float]:
    """Resolve a place name with the default Nominatim geocoder.

    Args:
        label: Place name or unambiguous place query.

    Returns:
        A latitude and longitude in decimal degrees.

    Raises:
        ClimateMonitorError: If the lookup, response, or cache is unusable.
    """
    return NominatimGeocoder()(label)


def http_range_source(url: str) -> Callable[[int, int], bytes]:
    """Create a PMTiles byte reader backed by HTTP Range requests.

    Args:
        url: Absolute PMTiles URL.

    Returns:
        A callable accepting an inclusive byte offset and byte length.

    Example:
        ``get_bytes = http_range_source(url); header = get_bytes(0, 127)``
    """

    def get_bytes(offset: int, length: int) -> bytes:
        """Read a byte range from the PMTiles object.

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
        try:
            with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310
                data = response.read()
        except (OSError, urllib.error.URLError) as error:
            raise ClimateMonitorError(
                f"Could not read Reuters tile {url}: {error}"
            ) from error
        if len(data) != length:
            raise ClimateMonitorError(
                f"Reuters tile returned {len(data)} bytes; expected {length}"
            )
        return data

    return get_bytes


def as_rows(raw: object, source_url: str) -> list[dict[str, Any]]:
    """Validate that a feed response is a list of object rows.

    Args:
        raw: Decoded JSON response.
        source_url: URL used for an error message.

    Returns:
        A list of mapping rows.

    Raises:
        ClimateMonitorError: If the response shape is not supported.
    """
    if not isinstance(raw, list) or not all(isinstance(row, dict) for row in raw):
        raise ClimateMonitorError(f"Reuters feed is not a row array: {source_url}")
    return cast("list[dict[str, Any]]", raw)


def select_exact_row(raw: object, day: str, label: str) -> dict[str, Any]:
    """Select one row whose date starts with the requested UTC date.

    Args:
        raw: Decoded feed response.
        day: Exact UTC date.
        label: Scope label used in errors.

    Returns:
        The one matching row.

    Raises:
        ClimateMonitorError: If no exact date is published or multiple rows
            match unexpectedly.
    """
    rows = as_rows(raw, label)
    matches = [row for row in rows if str(row.get("date", "")).startswith(day)]
    if len(matches) != 1:
        raise ClimateMonitorError(
            f"Reuters feed has {len(matches)} rows for {label} on {day}; "
            "refusing to substitute another date"
        )
    return matches[0]


def observation_from_row(
    scope: str,
    label: str,
    day: str,
    row: dict[str, Any],
    source_urls: tuple[str, ...],
    *,
    coordinates: tuple[float, float] | None = None,
    site_url: str | None = None,
    land_swapped: bool = False,
    geocoder_url: str | None = None,
) -> Observation:
    """Build an observation after validating its three published temperatures.

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

    Returns:
        A validated observation.

    Raises:
        ClimateMonitorError: If any required value is non-numeric.
    """
    values = {}
    for name in ("t2m_max_daily", "t2m_max_normal", "t2m_max_delta"):
        value = row.get(name)
        if not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ClimateMonitorError(f"Reuters row has no finite {name}")
        values[name] = float(value)
    return Observation(
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
    )


def validate_region_request(region_set: str, region: str) -> None:
    """Reject unsupported region-set and region combinations.

    Args:
        region_set: Published region-set slug.
        region: Exact display label.

    Returns:
        None.

    Raises:
        ClimateMonitorError: If the request is unsupported.
    """
    if region_set not in REGION_SETS:
        raise ClimateMonitorError(
            f"Unknown region set {region_set!r}; choose from {sorted(REGION_SETS)}"
        )
    if not region.strip():
        raise ClimateMonitorError("Region must not be empty")
    if region_set == "continent" and region not in CONTINENT_LABELS:
        raise ClimateMonitorError(f"Unknown continent {region!r}")


def snap_to_grid(value: float) -> float:
    """Match JavaScript ``Math.round`` snapping to the 0.25-degree grid.

    Args:
        value: Decimal-degree coordinate.

    Returns:
        The nearest grid center.

    Example:
        ``snap_to_grid(48.8566) == 48.75``
    """
    return math.floor(value / GRID_SIZE + 0.5) * GRID_SIZE


def tile_coordinates(lng: float, lat: float) -> tuple[int, int]:
    """Calculate the zoom-eight Web Mercator tile containing a coordinate.

    Args:
        lng: Longitude.
        lat: Latitude.

    Returns:
        A ``(x, y)`` tile coordinate tuple.
    """
    grid_lng = snap_to_grid(lng)
    grid_lat = snap_to_grid(lat)
    tile_x = math.floor(((grid_lng + 180) / 360) * 2**ZOOM)
    tile_y = math.floor(
        (
            1
            - math.log(
                math.tan(math.radians(grid_lat)) + 1 / math.cos(math.radians(grid_lat))
            )
            / math.pi
        )
        / 2
        * 2**ZOOM
    )
    return tile_x, tile_y


def choose_feature(
    features: Iterable[dict[str, Any]],
    tile_x: int,
    tile_y: int,
    lat: float,
    lng: float,
    zoom: int,
    extent: int = 4096,
) -> dict[str, Any] | None:
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
        A feature copy with resolved coordinates and ``land_swapped``, or
        ``None`` when no point feature is present.
    """
    reference_lat = snap_to_grid(lat)
    reference_lng = snap_to_grid(lng)
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
            feature_lat = math.degrees(math.atan(0.5 * (math.exp(n) - math.exp(-n))))
        distance = math.hypot(feature_lng - reference_lng, feature_lat - reference_lat)
        points.append(
            {
                "properties": properties,
                "distance": distance,
                "coordinates": (snap_to_grid(feature_lng), snap_to_grid(feature_lat)),
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
    return {
        "properties": chosen["properties"],
        "coordinates": chosen["coordinates"],
        "land_swapped": chosen is not nearest,
    }


def format_observation(
    observation: Observation,
    *,
    today: date | None = None,
) -> dict[str, Any]:
    """Format an observation and render the fixed newsroom paragraph.

    Args:
        observation: Validated monitor observation.
        today: Optional UTC date used when rendering today's date in tests.

    Returns:
        A dictionary with display values, paragraph, and verification URL.
    """
    direction = (
        "above"
        if observation.anomaly_c > 0
        else "below"
        if observation.anomaly_c < 0
        else "at"
    )
    parsed_date = date.fromisoformat(observation.date)
    current_date = today or datetime.now(UTC).date()
    date_label = (
        parsed_date.strftime("%A")
        if parsed_date == current_date
        else f"{parsed_date.strftime('%B')} {parsed_date.day}, {parsed_date.year}"
    )
    reading_verb = "reached" if parsed_date < current_date else "is forecast to reach"
    if observation.scope == "global":
        subject = "the global average high"
    elif observation.scope == "region":
        subject = f"the average high in {observation.label}"
    else:
        subject = f"the high in {observation.label}"
    paragraph = (
        f"On {date_label}, {subject} {reading_verb} "
        f"{format_temperature_pair(observation.daily_high_c)}, which is "
        f"{format_temperature_pair(observation.anomaly_c, anomaly=True)} {direction} "
        "the 1961–1990 average, "
        f"according to the [Reuters Climate Monitor]({SITE_ROOT})."
    )
    return {
        "daily_high": round(observation.daily_high_c),
        "normal_high": round(observation.normal_high_c),
        "anomaly": round(observation.anomaly_c, 1),
        "anomaly_direction": direction,
        "caution": CAUTION,
        "paragraph": paragraph,
    }


def build_site_url(lat: float, lng: float, label: str) -> str:
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
    return f"{SITE_ROOT}?{query}"


def build_geocoder_point_url(lat: float, lng: float) -> str:
    """Build an OpenStreetMap link for a geocoded point.

    Args:
        lat: Geocoded latitude.
        lng: Geocoded longitude.

    Returns:
        A URL centered on the geocoded point.
    """
    query = urllib.parse.urlencode({"mlat": round(lat, 6), "mlon": round(lng, 6)})
    return f"{OPENSTREETMAP_ROOT}?{query}#map=12/{lat:.6f}/{lng:.6f}"


def run_generation(
    client: ClimateMonitorClient,
    scope: str,
    day: str,
    *,
    region_set: str | None = None,
    region: str | None = None,
    label: str | None = None,
    lat: float | None = None,
    lng: float | None = None,
    today: date | None = None,
) -> dict[str, Any]:
    """Fetch one requested scope and return the JSON payload.

    Args:
        client: Climate Monitor client.
        scope: ``global``, ``region``, or ``location``.
        day: Exact UTC date.
        region_set: Region-set slug for a regional request.
        region: Display label for a regional request.
        label: Place label for a location request.
        lat: Location latitude.
        lng: Location longitude.
        today: Optional UTC date used when rendering today's date in tests.

    Returns:
        A serializable paragraph payload.

    Raises:
        ClimateMonitorError: If the request arguments are incomplete.
    """
    try:
        date.fromisoformat(day)
    except ValueError as error:
        raise ClimateMonitorError("Date must use YYYY-MM-DD") from error
    if scope == "global":
        observation = client.global_observation(day)
    elif scope == "region":
        if region_set is None or region is None:
            raise ClimateMonitorError("Region requests need --region-set and --region")
        observation = client.region_observation(region_set, region, day)
    elif scope == "location":
        if label is None:
            raise ClimateMonitorError("Location requests need --label")
        if (lat is None) != (lng is None):
            raise ClimateMonitorError("Location requests need both --lat and --lng")
        observation = client.location_observation(label, lat, lng, day)
    else:
        raise ClimateMonitorError("Scope must be global, region, or location")
    return observation.to_payload(today=today)


@click.group()
def cli() -> None:
    """Generate Reuters Climate Monitor newsroom copy."""


@cli.command()
@click.option(
    "--scope",
    type=click.Choice(["global", "region", "location"]),
    required=True,
)
@click.option("--date", "day", required=True, help="UTC date in YYYY-MM-DD form.")
@click.option("--region-set", default=None)
@click.option("--region", default=None)
@click.option("--label", default=None)
@click.option("--lat", type=float, default=None, help="Optional latitude override.")
@click.option("--lng", type=float, default=None, help="Optional longitude override.")
def generate(
    scope: str,
    day: str,
    region_set: str | None,
    region: str | None,
    label: str | None,
    lat: float | None,
    lng: float | None,
) -> None:
    """Fetch data and print a deterministic JSON result."""
    try:
        payload = run_generation(
            ClimateMonitorClient(),
            scope,
            day,
            region_set=region_set,
            region=region,
            label=label,
            lat=lat,
            lng=lng,
        )
    except ClimateMonitorError as error:
        raise click.ClickException(str(error)) from error
    click.echo(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    cli()
