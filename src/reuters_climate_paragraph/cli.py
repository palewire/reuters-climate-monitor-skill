"""Fetch Reuters Climate Monitor data and render newsroom-ready copy."""

from __future__ import annotations

import gzip
import json
import math
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Iterable
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from typing import Any, cast

import click
import mapbox_vector_tile
from pmtiles.reader import Reader

CDN_ROOT = "https://graphics.thomsonreuters.com/newsapps_climate-forecast"
MAP_ROOT = (
    "https://graphics.thomsonreuters.com/"
    "newsapps_reuters-climate-monitor/daily-anomalies-map/hres"
)
SITE_ROOT = "https://www.reuters.com/graphics/CLIMATE-AUTOMATED/MONITOR/akpeykqqapr/"
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


class ClimateMonitorError(RuntimeError):
    """Raised when a Reuters Climate Monitor response cannot be used."""


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

    def to_payload(
        self, unit: str = "celsius", *, today: date | None = None
    ) -> dict[str, Any]:
        """Return the reading, paragraph, and verification URLs as JSON data.

        Args:
            unit: Output unit, either ``celsius`` or ``fahrenheit``.
            today: Optional UTC date used when rendering today's date in tests.

        Returns:
            A JSON-serializable dictionary with source values and copy.

        Example:
            ``payload = observation.to_payload("fahrenheit")``
        """
        output = format_observation(self, unit, today=today)
        return {
            **asdict(self),
            "source_urls": list(self.source_urls),
            "coordinates": list(self.coordinates) if self.coordinates else None,
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
    ) -> None:
        self._json_fetcher = json_fetcher or fetch_json
        self._range_source_factory = range_source_factory or http_range_source

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
        self, label: str, lat: float, lng: float, day: str
    ) -> Observation:
        """Fetch the nearest daily anomaly grid cell for a point.

        Args:
            label: Human-readable name supplied by the newsroom user.
            lat: Latitude in decimal degrees.
            lng: Longitude in decimal degrees.
            day: UTC date in ``YYYY-MM-DD`` form.

        Returns:
            A validated point observation, including resolved grid coordinates.

        Raises:
            ClimateMonitorError: If the coordinates, tile, or feature is
                unusable.
        """
        validate_coordinates(lat, lng)
        url = f"{MAP_ROOT}/{day}/t2m_max_delta_data.pmtiles"
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


def validate_coordinates(lat: float, lng: float) -> None:
    """Validate decimal-degree coordinates.

    Args:
        lat: Latitude.
        lng: Longitude.

    Returns:
        None.

    Raises:
        ClimateMonitorError: If either coordinate is out of range or non-finite.
    """
    if not math.isfinite(lat) or not -90 <= lat <= 90:
        raise ClimateMonitorError("Latitude must be between -90 and 90")
    if not math.isfinite(lng) or not -180 <= lng <= 180:
        raise ClimateMonitorError("Longitude must be between -180 and 180")


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
        feature_lng = ((tile_x + coords[0] / extent) / 2**zoom) * 360 - 180
        n = math.pi - (2 * math.pi * (tile_y + coords[1] / extent)) / 2**zoom
        feature_lat = math.degrees(math.atan(0.5 * (math.exp(n) - math.exp(-n))))
        distance = math.hypot(feature_lng - reference_lng, feature_lat - reference_lat)
        points.append(
            {
                "properties": feature.get("properties", {}),
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


def format_absolute_temperature(value: float, unit_name: str) -> str:
    """Format an absolute temperature using Reuters style.

    Args:
        value: Absolute temperature in the selected display unit.
        unit_name: Full unit name, either ``Celsius`` or ``Fahrenheit``.

    Returns:
        A whole-degree temperature with ``degrees`` and a clear minus sign.
    """
    rounded = round(value)
    if rounded == 0:
        number = "zero"
    elif rounded < 0:
        number = f"minus {abs(rounded)}"
    else:
        number = str(rounded)
    return f"{number} degrees {unit_name}"


def format_anomaly_temperature(value: float, unit_abbreviation: str) -> str:
    """Format an anomaly using Reuters style.

    Args:
        value: Anomaly temperature in the selected display unit.
        unit_abbreviation: Unit abbreviation, either ``C`` or ``F``.

    Returns:
        A one-decimal anomaly with a space before its unit abbreviation.
    """
    rounded = round(abs(value), 1)
    number = "zero" if rounded == 0 else f"{rounded:.1f}"
    return f"{number} {unit_abbreviation}"


def format_temperature_pair(value_c: float, *, anomaly: bool = False) -> str:
    """Format Celsius first with the Fahrenheit equivalent in parentheses.

    Args:
        value_c: Temperature in Celsius.
        anomaly: Whether to format the value as a one-decimal anomaly.

    Returns:
        A Reuters-style Celsius/Fahrenheit temperature pair.
    """
    if anomaly:
        celsius = format_anomaly_temperature(value_c, "C")
        fahrenheit = format_anomaly_temperature(value_c * 9 / 5, "F")
    else:
        celsius = format_absolute_temperature(value_c, "Celsius")
        fahrenheit = format_absolute_temperature(value_c * 9 / 5 + 32, "Fahrenheit")
    return f"{celsius} ({fahrenheit})"


def format_observation(
    observation: Observation,
    unit: str,
    *,
    today: date | None = None,
) -> dict[str, Any]:
    """Format an observation and render the fixed newsroom paragraph.

    Args:
        observation: Validated monitor observation.
        unit: ``celsius`` or ``fahrenheit``.
        today: Optional UTC date used when rendering today's date in tests.

    Returns:
        A dictionary with display values, paragraph, and verification URL.

    Raises:
        ClimateMonitorError: If the requested unit is unsupported.
    """
    if unit not in {"celsius", "fahrenheit"}:
        raise ClimateMonitorError("Unit must be celsius or fahrenheit")
    factor = 1 if unit == "celsius" else 9 / 5
    offset = 0 if unit == "celsius" else 32
    daily = observation.daily_high_c * factor + offset
    normal = observation.normal_high_c * factor + offset
    anomaly = observation.anomaly_c * factor
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
    if observation.scope == "global":
        subject = "the global average high"
    elif observation.scope == "region":
        subject = f"the average high in {observation.label}"
    else:
        subject = f"the high in the nearest monitor grid cell to {observation.label}"
    paragraph = (
        f"On {date_label}, {subject} is forecast to reach "
        f"{format_temperature_pair(observation.daily_high_c)}, "
        f"{format_temperature_pair(observation.anomaly_c, anomaly=True)} {direction} "
        "the 1961–1990 average, "
        f"according to the [Reuters Climate Monitor]({SITE_ROOT})."
    )
    return {
        "unit": unit,
        "daily_high": round(daily),
        "normal_high": round(normal),
        "anomaly": round(anomaly, 1),
        "anomaly_direction": direction,
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


def run_generation(
    client: ClimateMonitorClient,
    scope: str,
    day: str,
    unit: str,
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
        unit: ``celsius`` or ``fahrenheit``.
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
        if label is None or lat is None or lng is None:
            raise ClimateMonitorError(
                "Location requests need --label, --lat, and --lng"
            )
        observation = client.location_observation(label, lat, lng, day)
    else:
        raise ClimateMonitorError("Scope must be global, region, or location")
    return observation.to_payload(unit, today=today)


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
@click.option(
    "--unit",
    type=click.Choice(["celsius", "fahrenheit"]),
    default="celsius",
    show_default=True,
)
@click.option("--region-set", default=None)
@click.option("--region", default=None)
@click.option("--label", default=None)
@click.option("--lat", type=float, default=None)
@click.option("--lng", type=float, default=None)
def generate(
    scope: str,
    day: str,
    unit: str,
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
            unit,
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
