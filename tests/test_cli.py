"""Offline tests for the Reuters Climate Monitor paragraph sidecar."""

from __future__ import annotations

import gzip
from typing import Any

import mapbox_vector_tile
import pytest

from reuters_climate_paragraph.cli import (
    CDN_ROOT,
    ClimateMonitorClient,
    ClimateMonitorError,
    choose_feature,
    run_generation,
    snap_to_grid,
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

    payload = run_generation(client, "global", "2026-09-22", "celsius")

    assert payload["daily_high_c"] == 20.04
    assert payload["anomaly_c"] == 1.234
    assert payload["paragraph"] == (
        "On September 22, 2026, the global average high is forecast to reach "
        "20.0°C, 1.2°C above the 1961–1990 average, according to the Reuters "
        "Climate Monitor."
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
    assert "6.3°F above" in payload["paragraph"]


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
            lat=0,
            lng=0,
        )
    finally:
        monkeypatch.undo()

    assert payload["land_swapped"] is True
    assert payload["coordinates"] is not None
    assert "nearest monitor grid cell to Test Coast" in payload["paragraph"]
    assert "lat=0" in payload["site_url"]
    assert payload["source_urls"][0].endswith("/2026-09-22/t2m_max_delta_data.pmtiles")


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
