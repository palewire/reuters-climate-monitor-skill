"""Live checks against the published Reuters Climate Monitor data."""

from __future__ import annotations

import math
from datetime import UTC, datetime

import pytest

from reuters_climate_paragraph.cli import (
    CDN_ROOT,
    MAP_ROOT,
    SITE_ROOT,
    ClimateMonitorClient,
    format_observation,
)

PINNED_DATE = "2026-08-01"
PARIS_LABEL = "Paris"
PARIS_LAT = 48.8566
PARIS_LNG = 2.3522


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
        formatted = format_observation(observation, "celsius")
        assert isinstance(formatted["daily_high"], int)
        assert f"({SITE_ROOT})" in formatted["paragraph"]
        assert f"{abs(observation.anomaly_c):.1f} C" in formatted["paragraph"]
        assert formatted["paragraph"]

    assert global_observation.source_urls == (
        f"{CDN_ROOT}/daily-global-averages/latest-daily-averages.json",
    )
    assert europe_observation.source_urls == (
        f"{CDN_ROOT}/region-sets/continent/latest-daily-averages.json",
    )
    assert paris_observation.source_urls == (
        f"{MAP_ROOT}/{day}/t2m_max_delta_data.pmtiles",
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
    assert observation.daily_high_c == pytest.approx(27.2, abs=0.00001)
    assert observation.normal_high_c == pytest.approx(23.6, abs=0.00001)
    assert observation.anomaly_c == pytest.approx(4.1, abs=0.00001)
    assert observation.source_urls == (
        f"{MAP_ROOT}/{PINNED_DATE}/t2m_max_delta_data.pmtiles",
    )
