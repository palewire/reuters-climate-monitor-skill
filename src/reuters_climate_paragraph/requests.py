"""Validated request types for paragraph generation."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import ClassVar, Literal

from .errors import ClimateMonitorError

Scope = Literal["global", "region", "location"]
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


@dataclass(frozen=True)
class GenerationRequest:
    """Base request shared by the three supported generation scopes.

    Args:
        day: Exact UTC date in ``YYYY-MM-DD`` form.
        today: Optional current date used by deterministic tests.

    Example:
        ``GlobalRequest(day="2026-09-22")``
    """

    day: str
    today: date | None = field(default=None, kw_only=True)
    scope: ClassVar[Scope]

    def __post_init__(self) -> None:
        """Validate the shared date field.

        Raises:
            ClimateMonitorError: If ``day`` is not an ISO date.
        """
        try:
            date.fromisoformat(self.day)
        except ValueError as error:
            raise ClimateMonitorError("Date must use YYYY-MM-DD") from error

    @staticmethod
    def validate_region_request(region_set: str, region: str) -> None:
        """Reject unsupported region-set and region combinations.

        Args:
            region_set: Published region-set slug.
            region: Exact display label.

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


@dataclass(frozen=True)
class GlobalRequest(GenerationRequest):
    """Request the global published daily average."""

    scope: ClassVar[Literal["global"]] = "global"


@dataclass(frozen=True)
class RegionRequest(GenerationRequest):
    """Request one named published regional daily average.

    Args:
        day: Exact UTC date in ``YYYY-MM-DD`` form.
        region_set: Published region-set slug.
        region: Exact display label in that feed.
        today: Optional current date used by deterministic tests.
    """

    region_set: str
    region: str
    scope: ClassVar[Literal["region"]] = "region"

    def __post_init__(self) -> None:
        """Validate the date and region fields."""
        super().__post_init__()
        self.validate_region_request(self.region_set, self.region)


@dataclass(frozen=True)
class LocationRequest(GenerationRequest):
    """Request the nearest published map cell for a location.

    Args:
        day: Exact UTC date in ``YYYY-MM-DD`` form.
        label: Human-readable place label.
        lat: Latitude override, or ``None`` when geocoding.
        lng: Longitude override, or ``None`` when geocoding.
        today: Optional current date used by deterministic tests.
    """

    label: str
    lat: float | None = None
    lng: float | None = None
    scope: ClassVar[Literal["location"]] = "location"

    def __post_init__(self) -> None:
        """Validate the label and optional coordinate pair."""
        super().__post_init__()
        if not self.label.strip():
            raise ClimateMonitorError("Location requests need --label")
        if (self.lat is None) != (self.lng is None):
            raise ClimateMonitorError("Location requests need both --lat and --lng")


def validate_region_request(region_set: str, region: str) -> None:
    """Validate a region request for compatibility callers.

    Args:
        region_set: Published region-set slug.
        region: Exact display label.

    Raises:
        ClimateMonitorError: If the request is unsupported.
    """
    GenerationRequest.validate_region_request(region_set, region)
