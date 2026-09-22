"""Command-line adapter for Reuters Climate Monitor paragraph generation."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import click

if TYPE_CHECKING:
    from datetime import date

from .client import ClimateMonitorClient as _ClimateMonitorClient
from .errors import ClimateMonitorError as _ClimateMonitorError
from .generation import ParagraphGenerator as _ParagraphGenerator


def run_generation(
    client: _ClimateMonitorClient,
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
    generator = _ParagraphGenerator(client)
    if scope == "global":
        return generator.generate_global(day, today=today)
    if scope == "region":
        if region_set is None or region is None:
            raise _ClimateMonitorError("Region requests need --region-set and --region")
        return generator.generate_region(region_set, region, day, today=today)
    if scope == "location":
        if label is None:
            raise _ClimateMonitorError("Location requests need --label")
        return generator.generate_location(
            label,
            day,
            lat=lat,
            lng=lng,
            today=today,
        )
    raise _ClimateMonitorError("Scope must be global, region, or location")


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
            _ClimateMonitorClient(),
            scope,
            day,
            region_set=region_set,
            region=region,
            label=label,
            lat=lat,
            lng=lng,
        )
    except _ClimateMonitorError as error:
        raise click.ClickException(str(error)) from error
    click.echo(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    cli()
