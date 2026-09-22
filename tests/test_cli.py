"""Offline tests for the Reuters Climate Monitor paragraph sidecar."""

from __future__ import annotations

import gzip
import json
from datetime import date
from typing import Any

import mapbox_vector_tile
import pytest
from click.testing import CliRunner

import reuters_climate_paragraph.cli as cli_module
from reuters_climate_paragraph.cli import run_generation
from reuters_climate_paragraph.client import ClimateMonitorClient
from reuters_climate_paragraph.errors import ClimateMonitorError
from reuters_climate_paragraph.feeds import MonitorFeedClient
from reuters_climate_paragraph.geocoder import NominatimGeocoder, validate_coordinates
from reuters_climate_paragraph.map_data import (
    PointDataReader,
    choose_feature,
    snap_to_grid,
)
from reuters_climate_paragraph.models import Observation
from reuters_climate_paragraph.rendering import format_observation
from reuters_climate_paragraph.requests import validate_region_request
from reuters_climate_paragraph.urls import (
    ERA5_MAP_ROOT,
    HRES_MAP_ROOT,
    SITE_ROOT,
    anomaly_map_url,
)


def feed_row(day: str, **extra: Any) -> dict[str, Any]:
    """Create a valid synthetic daily-average row for tests.

    Args:
        day: Row date.
        extra: Optional geography fields.

    Returns:
        A valid feed row.
    """
    return {
        "date": day,
        "t2m_max_daily": 20.0,
        "t2m_max_normal": 18.0,
        "t2m_max_delta": 2.0,
        **extra,
    }


def test_anomaly_map_url_selects_published_source_by_date() -> None:
    """Past point readings use ERA5 while current readings use HRES."""
    assert (
        anomaly_map_url("2026-09-21", today=date(2026, 9, 22))
        == f"{ERA5_MAP_ROOT}/2026-09-21/t2m_max_delta.pmtiles"
    )
    assert (
        anomaly_map_url("2026-09-22", today=date(2026, 9, 22))
        == f"{HRES_MAP_ROOT}/2026-09-22/t2m_max_delta_data.pmtiles"
    )


def test_global_generation_uses_exact_date_and_published_delta() -> None:
    """The global output uses the feed anomaly rather than recomputing it."""
    client = ClimateMonitorClient(
        json_fetcher=lambda requested: [
            feed_row("2026-09-21"),
            feed_row(
                "2026-09-22",
                t2m_max_daily=20.04,
                t2m_max_normal=18.99,
                t2m_max_delta=1.234,
            ),
        ]
    )

    payload = run_generation(
        client,
        "global",
        "2026-09-22",
        today=date(2026, 9, 22),
    )

    assert payload["daily_high_c"] == 20.04
    assert payload["anomaly_c"] == 1.234
    assert payload["caution"].startswith("Verify the date")
    assert payload["paragraph"] == (
        "On Tuesday, the global average high is forecast to reach 20 degrees "
        "Celsius (68 degrees Fahrenheit), which is 1.2 C (2.2 F) above the "
        "1961–1990 average, "
        "according to the [Reuters Climate "
        f"Monitor]({SITE_ROOT})."
    )
    assert payload["site_url"] == SITE_ROOT
    assert "source_urls" not in payload


def test_region_generation_filters_the_requested_region() -> None:
    """A regional request selects the named entity on the requested date."""
    client = ClimateMonitorClient(
        json_fetcher=lambda _: [
            feed_row("2026-09-22", continent="Africa", t2m_max_delta=-1.0),
            feed_row("2026-09-22", continent="Europe", t2m_max_delta=3.5),
        ]
    )

    payload = run_generation(
        client,
        "region",
        "2026-09-22",
        region_set="continent",
        region="Europe",
    )

    assert payload["anomaly"] == 3.5
    assert (
        "20 degrees Celsius (68 degrees Fahrenheit), which is 3.5 C (6.3 F) above"
        in payload["paragraph"]
    )


def test_country_feed_uses_country_labels() -> None:
    """Country feed rows use the country field for region selection."""
    client = MonitorFeedClient(
        json_fetcher=lambda _: [
            feed_row("2026-09-22", country="France"),
            feed_row("2026-09-22", country="Germany"),
        ]
    )

    row, _ = client.region_row("country", "France", "2026-09-22")

    assert row["country"] == "France"
    assert client.region_labels("country") == ["France", "Germany"]


def test_regions_command_lists_published_labels(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The regions command prints the current region-set and label map."""

    class FakeFeedClient:
        def all_region_labels(self) -> dict[str, list[str]]:
            return {
                "continent": ["Africa", "Europe"],
                "country": ["France", "Germany"],
            }

    monkeypatch.setattr(cli_module, "_MonitorFeedClient", FakeFeedClient)

    result = CliRunner().invoke(cli_module.cli, ["regions"])

    assert result.exit_code == 0
    assert json.loads(result.output) == {
        "continent": ["Africa", "Europe"],
        "country": ["France", "Germany"],
    }


def test_cli_help_documents_verbose_diagnostics() -> None:
    """The CLI exposes the network diagnostic switch."""
    result = CliRunner().invoke(cli_module.cli, ["--help"])

    assert result.exit_code == 0
    assert "--verbose" in result.output


def test_formatting_uses_weekday_today_and_whole_degree_absolute_values() -> None:
    """Today's copy uses a weekday and rounds absolute values to degrees."""
    observation = Observation(
        scope="global",
        label="the globe",
        date="2026-09-22",
        daily_high_c=20,
        normal_high_c=18,
        anomaly_c=2,
        source_urls=(),
        site_url=SITE_ROOT,
    )

    today_output = format_observation(observation, today=date(2026, 9, 22))
    historical_output = format_observation(observation, today=date(2026, 9, 23))

    assert today_output["daily_high"] == 20
    assert today_output["normal_high"] == 18
    assert today_output["anomaly"] == 2
    assert "On Tuesday," in today_output["paragraph"]
    assert (
        "reach 20 degrees Celsius (68 degrees Fahrenheit), which is 2.0 C (3.6 F) above"
        in today_output["paragraph"]
    )
    assert "On September 22, 2026," in historical_output["paragraph"]
    assert (
        "reached 20 degrees Celsius (68 degrees Fahrenheit)"
        in historical_output["paragraph"]
    )
    assert "is forecast to reach" not in historical_output["paragraph"]


def test_formatting_spells_out_zero_and_minus() -> None:
    """Absolute temperatures use zero and minus instead of symbols."""
    observation = Observation(
        scope="global",
        label="the globe",
        date="2026-09-22",
        daily_high_c=-10.4,
        normal_high_c=-8.2,
        anomaly_c=-2,
        source_urls=(),
        site_url=SITE_ROOT,
    )

    output = format_observation(observation, today=date(2026, 9, 22))

    assert (
        "reach minus 10 degrees Celsius (13 degrees Fahrenheit), which is "
        "2.0 C (3.6 F) below"
    ) in output["paragraph"]

    observation = Observation(
        scope="global",
        label="the globe",
        date="2026-09-22",
        daily_high_c=0.2,
        normal_high_c=0.1,
        anomaly_c=0,
        source_urls=(),
        site_url=SITE_ROOT,
    )
    output = format_observation(observation, today=date(2026, 9, 22))

    assert (
        "reach zero degrees Celsius (32 degrees Fahrenheit), which is zero C (zero F) at"
        in output["paragraph"]
    )


def test_missing_date_is_an_error_instead_of_a_silent_fallback() -> None:
    """The sidecar never substitutes the last available day."""
    client = ClimateMonitorClient(json_fetcher=lambda _: [feed_row("2026-09-21")])

    with pytest.raises(ClimateMonitorError, match="refusing to substitute"):
        run_generation(client, "global", "2026-09-22")


def test_location_land_fallback_and_verification_url() -> None:
    """A nearby land cell is selected and the output links to the map."""
    feature_tile = gzip.compress(
        mapbox_vector_tile.encode(
            {
                "name": "data",
                "features": [
                    {
                        "geometry": {"type": "Point", "coordinates": [100, 100]},
                        "properties": {
                            "t2m_max_daily": 20,
                            "t2m_max_normal": 18,
                            "t2m_max_delta": 2,
                            "is_land": False,
                        },
                    },
                    {
                        "geometry": {"type": "Point", "coordinates": [110, 100]},
                        "properties": {
                            "t2m_max_daily": 21,
                            "t2m_max_normal": 18,
                            "t2m_max_delta": 3,
                            "is_land": True,
                        },
                    },
                ],
            }
        )
    )

    class FakeReader:
        """Minimal PMTiles reader used to exercise the client path."""

        def __init__(self, _: Any) -> None:
            pass

        def header(self) -> dict[str, int]:
            """Return a gzip-compressed synthetic tile header."""
            return {"tile_compression": 2}

        def get(self, _z: int, _x: int, _y: int) -> bytes:
            """Return the synthetic vector tile."""
            return feature_tile

    client = ClimateMonitorClient(
        point_reader=PointDataReader(
            range_source_factory=lambda _: lambda _offset, _length: b"",
            reader_factory=FakeReader,
        ),
        geocoder=lambda _label: (0, 0),
    )
    payload = run_generation(
        client,
        "location",
        "2026-09-22",
        label="Test Coast",
    )

    assert payload["land_swapped"] is True
    assert payload["coordinates"] is not None
    assert "the high in Test Coast" in payload["paragraph"]
    assert "lat=0" in payload["site_url"]
    assert payload["geocoder_url"].startswith("https://www.openstreetmap.org/")
    assert "source_urls" not in payload


def test_nominatim_geocoder_caches_results(
    tmp_path: Any,
) -> None:
    """A geocoder instance uses its local cache on repeated requests."""
    calls: list[str] = []

    def fake_fetch(url: str) -> object:
        calls.append(url)
        return [{"lat": "48.8566", "lon": "2.3522"}]

    geocoder = NominatimGeocoder(
        cache_path=tmp_path / "nominatim.json",
        fetcher=fake_fetch,
    )

    assert geocoder("Paris") == (48.8566, 2.3522)
    assert geocoder(" paris ") == (48.8566, 2.3522)
    assert len(calls) == 1


def test_choose_feature_ignores_non_point_features() -> None:
    """Only point features in the data layer can provide a grid reading."""
    assert (
        choose_feature(
            [{"geometry": {"type": "Polygon", "coordinates": []}, "properties": {}}],
            0,
            0,
            0,
            0,
            8,
        )
        is None
    )


def test_choose_feature_prefers_published_grid_coordinates() -> None:
    """ERA5 properties prevent MVT coordinate quantization from shifting cells."""
    chosen = choose_feature(
        [
            {
                "geometry": {"type": "Point", "coordinates": [0, 0]},
                "properties": {"longitude": 2.25, "latitude": 48.75},
            }
        ],
        129,
        88,
        48.8566,
        2.3522,
        8,
    )

    assert chosen is not None
    assert chosen["coordinates"] == (2.25, 48.75)


def test_grid_rounding_matches_frontend_boundary_behavior() -> None:
    """Grid snapping follows the frontend's quarter-degree rule."""
    assert snap_to_grid(48.8566) == 48.75
    assert snap_to_grid(-118.7) == -118.75


def test_invalid_requests_are_rejected() -> None:
    """Generation rejects incomplete and malformed request arguments."""
    client = ClimateMonitorClient(json_fetcher=lambda _: [])

    with pytest.raises(ClimateMonitorError, match="Date must use"):
        run_generation(client, "global", "not-a-date")
    with pytest.raises(ClimateMonitorError, match="Region requests need"):
        run_generation(client, "region", "2026-09-22")
    with pytest.raises(ClimateMonitorError, match="Location requests need"):
        run_generation(client, "location", "2026-09-22")
    with pytest.raises(ClimateMonitorError, match="Scope must be"):
        run_generation(client, "other", "2026-09-22")


def test_invalid_values_and_geographies_are_rejected() -> None:
    """Geography validation rejects unsupported values."""
    with pytest.raises(ClimateMonitorError, match="Latitude"):
        validate_coordinates(91, 0)
    with pytest.raises(ClimateMonitorError, match="Longitude"):
        validate_coordinates(0, 181)
    with pytest.raises(ClimateMonitorError, match="Unknown region set"):
        validate_region_request("unknown", "Europe")
    with pytest.raises(ClimateMonitorError, match="must not be empty"):
        validate_region_request("continent", "")
    with pytest.raises(ClimateMonitorError, match="Unknown continent"):
        validate_region_request("continent", "Atlantis")
