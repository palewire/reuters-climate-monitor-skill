"""Command-line adapter for Reuters Climate Monitor paragraph generation."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import click

if TYPE_CHECKING:
    from datetime import date

from .client import ClimateMonitorClient
from .errors import ClimateMonitorError
from .feeds import JsonFetcher, as_rows, fetch_json, select_exact_row
from .generation import ParagraphGenerator
from .geocoder import geocode_place, validate_coordinates
from .map_data import (
    GRID_SIZE,
    MAX_LAND_SWAP_DISTANCE,
    ZOOM,
    choose_feature,
    http_range_source,
    snap_to_grid,
    tile_coordinates,
)
from .models import Observation, observation_from_row
from .rendering import CAUTION, ParagraphRenderer, format_observation
from .requests import (
    CONTINENT_LABELS,
    REGION_SETS,
    validate_region_request,
)
from .temperature import (
    format_absolute_temperature,
    format_anomaly_temperature,
    format_temperature_pair,
)
from .urls import (
    CDN_ROOT,
    ERA5_MAP_ROOT,
    HRES_MAP_ROOT,
    MAP_ROOT,
    OPENSTREETMAP_ROOT,
    SITE_ROOT,
    anomaly_map_url,
    build_geocoder_point_url,
    build_site_url,
)

__all__ = [
    "CAUTION",
    "CDN_ROOT",
    "CONTINENT_LABELS",
    "ERA5_MAP_ROOT",
    "GRID_SIZE",
    "HRES_MAP_ROOT",
    "MAP_ROOT",
    "MAX_LAND_SWAP_DISTANCE",
    "OPENSTREETMAP_ROOT",
    "REGION_SETS",
    "SITE_ROOT",
    "ZOOM",
    "ClimateMonitorClient",
    "ClimateMonitorError",
    "JsonFetcher",
    "Observation",
    "ParagraphRenderer",
    "anomaly_map_url",
    "as_rows",
    "build_geocoder_point_url",
    "build_site_url",
    "choose_feature",
    "cli",
    "fetch_json",
    "format_absolute_temperature",
    "format_anomaly_temperature",
    "format_observation",
    "format_temperature_pair",
    "generate",
    "geocode_place",
    "http_range_source",
    "observation_from_row",
    "run_generation",
    "select_exact_row",
    "snap_to_grid",
    "tile_coordinates",
    "validate_coordinates",
    "validate_region_request",
]


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
    """Fetch one requested scope and return its JSON payload.

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
    generator = ParagraphGenerator(client)
    if scope == "global":
        return generator.generate_global(day, today=today)
    if scope == "region":
        if region_set is None or region is None:
            raise ClimateMonitorError("Region requests need --region-set and --region")
        return generator.generate_region(region_set, region, day, today=today)
    if scope == "location":
        if label is None:
            raise ClimateMonitorError("Location requests need --label")
        return generator.generate_location(
            label,
            day,
            lat=lat,
            lng=lng,
            today=today,
        )
    raise ClimateMonitorError("Scope must be global, region, or location")


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
