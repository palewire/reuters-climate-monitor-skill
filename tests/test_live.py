"""Live checks against the published Reuters Climate Monitor data."""

from __future__ import annotations

import math
from datetime import UTC, datetime

import pytest

from reuters_climate_paragraph.client import ClimateMonitorClient
from reuters_climate_paragraph.rendering import format_observation
from reuters_climate_paragraph.urls import (
    CDN_ROOT,
    ERA5_MAP_ROOT,
    HRES_MAP_ROOT,
    SITE_ROOT,
)

PINNED_DATE = "2026-08-01"
PARIS_LABEL = "Paris"
PARIS_LAT = 48.8566
PARIS_LNG = 2.3522
SWISHER_LABEL = "Swisher, Iowa"


def assert_finite_observation(observation: object) -> None:
    """Check that a live observation contains finite published numbers.

    Args:
        observation: Observation returned by the live Reuters client.

    Returns:
        None.
    """
    for field in ("daily_high_c", "normal_high_c", "anomaly_c"):
        assert math.isfinite(getattr(observation, field))


@pytest.mark.integration
def test_today_global_region_and_location_are_published() -> None:
    """Today's global, regional, and point readings are available live."""
    day = datetime.now(UTC).date().isoformat()
    client = ClimateMonitorClient()

    global_observation = client.global_observation(day)
    europe_observation = client.region_observation("continent", "Europe", day)
    paris_observation = client.location_observation(
        PARIS_LABEL, PARIS_LAT, PARIS_LNG, day
    )

    for observation in (
        global_observation,
        europe_observation,
        paris_observation,
    ):
        assert observation.date == day
        assert_finite_observation(observation)
        formatted = format_observation(observation)
        assert isinstance(formatted["daily_high"], int)
        assert f"({SITE_ROOT})" in formatted["paragraph"]
        assert "degrees Celsius (" in formatted["paragraph"]
        assert "degrees Fahrenheit)," in formatted["paragraph"]
        assert ", which is " in formatted["paragraph"]
        assert f"{abs(observation.anomaly_c):.1f} C (" in formatted["paragraph"]
        assert " F)" in formatted["paragraph"]
        assert formatted["paragraph"]

    assert global_observation.source_urls == (
        f"{CDN_ROOT}/daily-global-averages/latest-daily-averages.json",
    )
    assert europe_observation.source_urls == (
        f"{CDN_ROOT}/region-sets/continent/latest-daily-averages.json",
    )
    assert paris_observation.source_urls == (
        f"{HRES_MAP_ROOT}/{day}/t2m_max_delta_data.pmtiles",
    )
    assert paris_observation.coordinates == (2.25, 48.75)


@pytest.mark.integration
def test_pinned_historical_location_has_stable_published_values() -> None:
    """A fixed historical grid cell keeps its expected published reading."""
    client = ClimateMonitorClient()
    observation = client.location_observation(
        PARIS_LABEL,
        PARIS_LAT,
        PARIS_LNG,
        PINNED_DATE,
    )

    assert observation.date == PINNED_DATE
    assert observation.coordinates == (2.25, 48.75)
    assert observation.land_swapped is False
    assert observation.daily_high_c == pytest.approx(28.2, abs=0.00001)
    assert observation.normal_high_c == pytest.approx(22.9, abs=0.00001)
    assert observation.anomaly_c == pytest.approx(5.3, abs=0.00001)
    assert observation.source_urls == (
        f"{ERA5_MAP_ROOT}/{PINNED_DATE}/t2m_max_delta.pmtiles",
    )
    formatted = format_observation(observation)
    assert (
        "reached 28 degrees Celsius (83 degrees Fahrenheit)" in formatted["paragraph"]
    )
    assert "is forecast to reach" not in formatted["paragraph"]


@pytest.mark.integration
def test_today_swisher_uses_the_default_geocoder() -> None:
    """A named Iowa place is geocoded before its live grid lookup."""
    day = datetime.now(UTC).date().isoformat()
    observation = ClimateMonitorClient().location_observation(
        SWISHER_LABEL,
        None,
        None,
        day,
    )

    assert observation.date == day
    assert_finite_observation(observation)
    assert observation.coordinates == (-91.75, 41.75)
    assert observation.geocoder_url is not None
    assert observation.geocoder_url.startswith("https://www.openstreetmap.org/")
    assert "place=Swisher%2C+Iowa" in observation.site_url
