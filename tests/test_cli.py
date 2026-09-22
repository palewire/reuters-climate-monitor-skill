"""Offline tests for the Reuters Climate Monitor paragraph sidecar."""

from __future__ import annotations

import gzip
from datetime import date
from typing import Any

import mapbox_vector_tile
import pytest

from reuters_climate_paragraph.cli import (
    CDN_ROOT,
    SITE_ROOT,
    ClimateMonitorClient,
    ClimateMonitorError,
    Observation,
    choose_feature,
    format_observation,
    geocode_place,
    run_generation,
    snap_to_grid,
    validate_coordinates,
    validate_region_request,
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


def test_global_generation_uses_exact_date_and_published_delta() -> None:
    """The global output uses the feed anomaly rather than recomputing it."""
    url = f"{CDN_ROOT}/daily-global-averages/latest-daily-averages.json"
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
        "celsius",
        today=date(2026, 9, 22),
    )

    assert payload["daily_high_c"] == 20.04
    assert payload["anomaly_c"] == 1.234
    assert payload["paragraph"] == (
        "On Tuesday, the global average high is forecast to reach 20 degrees "
        "Celsius (68 degrees Fahrenheit), which is 1.2 C (2.2 F) above the "
        "1961–1990 average, "
        "according to the [Reuters Climate "
        f"Monitor]({SITE_ROOT})."
    )
    assert payload["source_urls"] == [url]


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
        "fahrenheit",
        region_set="continent",
        region="Europe",
    )

    assert payload["anomaly"] == 6.3
    assert (
        "20 degrees Celsius (68 degrees Fahrenheit), which is 3.5 C (6.3 F) above"
        in payload["paragraph"]
    )


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

    today_output = format_observation(
        observation,
        "fahrenheit",
        today=date(2026, 9, 22),
    )
    historical_output = format_observation(
        observation,
        "fahrenheit",
        today=date(2026, 9, 23),
    )

    assert today_output["daily_high"] == 68
    assert today_output["normal_high"] == 64
    assert today_output["anomaly"] == 3.6
    assert "On Tuesday," in today_output["paragraph"]
    assert (
        "reach 20 degrees Celsius (68 degrees Fahrenheit), which is 2.0 C (3.6 F) above"
        in today_output["paragraph"]
    )
    assert "On September 22, 2026," in historical_output["paragraph"]


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

    output = format_observation(observation, "celsius", today=date(2026, 9, 22))

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
    output = format_observation(observation, "celsius", today=date(2026, 9, 22))

    assert (
        "reach zero degrees Celsius (32 degrees Fahrenheit), which is zero C (zero F) at"
        in output["paragraph"]
    )


def test_missing_date_is_an_error_instead_of_a_silent_fallback() -> None:
    """The sidecar never substitutes the last available day."""
    client = ClimateMonitorClient(json_fetcher=lambda _: [feed_row("2026-09-21")])

    with pytest.raises(ClimateMonitorError, match="refusing to substitute"):
        run_generation(client, "global", "2026-09-22", "celsius")


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
        range_source_factory=lambda _: lambda _offset, _length: b"",
        geocoder=lambda _label: (0, 0),
    )
    original_reader = __import__("reuters_climate_paragraph.cli", fromlist=["Reader"])
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(original_reader, "Reader", FakeReader)
    try:
        payload = run_generation(
            client,
            "location",
            "2026-09-22",
            "celsius",
            label="Test Coast",
        )
    finally:
        monkeypatch.undo()

    assert payload["land_swapped"] is True
    assert payload["coordinates"] is not None
    assert "the high in Test Coast" in payload["paragraph"]
    assert "lat=0" in payload["site_url"]
    assert payload["source_urls"][0].endswith("/2026-09-22/t2m_max_delta_data.pmtiles")


def test_nominatim_results_are_cached(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Any
) -> None:
    """A place lookup uses the local cache on repeated requests."""
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    calls: list[str] = []

    def fake_fetch(url: str) -> object:
        calls.append(url)
        return [{"lat": "48.8566", "lon": "2.3522"}]

    monkeypatch.setattr(
        "reuters_climate_paragraph.cli.fetch_nominatim_json",
        fake_fetch,
    )

    assert geocode_place("Paris") == (48.8566, 2.3522)
    assert geocode_place(" paris ") == (48.8566, 2.3522)
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


def test_grid_rounding_matches_frontend_boundary_behavior() -> None:
    """Grid snapping follows the frontend's quarter-degree rule."""
    assert snap_to_grid(48.8566) == 48.75
    assert snap_to_grid(-118.7) == -118.75


def test_invalid_requests_are_rejected() -> None:
    """Generation rejects incomplete and malformed request arguments."""
    client = ClimateMonitorClient(json_fetcher=lambda _: [])

    with pytest.raises(ClimateMonitorError, match="Date must use"):
        run_generation(client, "global", "not-a-date", "celsius")
    with pytest.raises(ClimateMonitorError, match="Region requests need"):
        run_generation(client, "region", "2026-09-22", "celsius")
    with pytest.raises(ClimateMonitorError, match="Location requests need"):
        run_generation(client, "location", "2026-09-22", "celsius")
    with pytest.raises(ClimateMonitorError, match="Scope must be"):
        run_generation(client, "other", "2026-09-22", "celsius")


def test_invalid_values_and_geographies_are_rejected() -> None:
    """Formatting and geography validation reject unsupported values."""
    observation = Observation(
        scope="global",
        label="the globe",
        date="2026-09-22",
        daily_high_c=20,
        normal_high_c=18,
        anomaly_c=2,
        source_urls=(),
        site_url="https://example.test",
    )

    with pytest.raises(ClimateMonitorError, match="Unit must be"):
        format_observation(observation, "kelvin")
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
