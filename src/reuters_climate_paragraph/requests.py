"""Validated requests for paragraph generation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Literal

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
    """A complete, validated request for one paragraph.

    Args:
        scope: ``global``, ``region``, or ``location``.
        day: Exact UTC date in ``YYYY-MM-DD`` form.
        region_set: Region-set slug for a regional request.
        region: Display label for a regional request.
        label: Place label for a location request.
        lat: Location latitude, or ``None`` when geocoding.
        lng: Location longitude, or ``None`` when geocoding.
        today: Optional current date used by deterministic tests.

    Example:
        ``GenerationRequest.from_args("global", "2026-09-22")``
    """

    scope: Scope
    day: str
    region_set: str | None = None
    region: str | None = None
    label: str | None = None
    lat: float | None = None
    lng: float | None = None
    today: date | None = None

    @classmethod
    def from_args(
        cls,
        scope: str,
        day: str,
        *,
        region_set: str | None = None,
        region: str | None = None,
        label: str | None = None,
        lat: float | None = None,
        lng: float | None = None,
        today: date | None = None,
    ) -> GenerationRequest:
        """Build and validate a request from CLI-style arguments.

        Args:
            scope: Requested scope.
            day: Exact UTC date.
            region_set: Region-set slug for a regional request.
            region: Display label for a regional request.
            label: Place label for a location request.
            lat: Location latitude.
            lng: Location longitude.
            today: Optional current date used by deterministic tests.

        Returns:
            A validated generation request.

        Raises:
            ClimateMonitorError: If the request is incomplete or malformed.
        """
        try:
            date.fromisoformat(day)
        except ValueError as error:
            raise ClimateMonitorError("Date must use YYYY-MM-DD") from error

        if scope == "global":
            return cls(scope="global", day=day, today=today)
        if scope == "region":
            if region_set is None or region is None:
                raise ClimateMonitorError(
                    "Region requests need --region-set and --region"
                )
            cls.validate_region_request(region_set, region)
            return cls(
                scope="region",
                day=day,
                region_set=region_set,
                region=region,
                today=today,
            )
        if scope == "location":
            if label is None:
                raise ClimateMonitorError("Location requests need --label")
            if (lat is None) != (lng is None):
                raise ClimateMonitorError("Location requests need both --lat and --lng")
            return cls(
                scope="location",
                day=day,
                label=label,
                lat=lat,
                lng=lng,
                today=today,
            )
        raise ClimateMonitorError("Scope must be global, region, or location")

    @staticmethod
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
    GenerationRequest.validate_region_request(region_set, region)
