"""Paragraph generation handlers for each supported request type."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .rendering import ParagraphRenderer
from .requests import (
    GenerationRequest,
    GlobalRequest,
    LocationRequest,
    RegionRequest,
)

if TYPE_CHECKING:
    from datetime import date

    from .client import ClimateMonitorClient
    from .models import Observation


class GlobalRequestHandler:
    """Fetch the observation for a global request."""

    def observe(
        self,
        client: ClimateMonitorClient,
        request: GlobalRequest,
    ) -> Observation:
        """Fetch one global observation.

        Args:
            client: Client for published Reuters data.
            request: Validated global request.

        Returns:
            The requested global observation.
        """
        return client.global_observation(request.day)


class RegionRequestHandler:
    """Fetch the observation for a regional request."""

    def observe(
        self,
        client: ClimateMonitorClient,
        request: RegionRequest,
    ) -> Observation:
        """Fetch one regional observation.

        Args:
            client: Client for published Reuters data.
            request: Validated regional request.

        Returns:
            The requested regional observation.
        """
        return client.region_observation(
            request.region_set,
            request.region,
            request.day,
            today=request.today,
        )


class LocationRequestHandler:
    """Fetch the observation for a location request."""

    def observe(
        self,
        client: ClimateMonitorClient,
        request: LocationRequest,
    ) -> Observation:
        """Fetch one location observation.

        Args:
            client: Client for published Reuters data.
            request: Validated location request.

        Returns:
            The requested location observation.
        """
        return client.location_observation(
            request.label,
            request.lat,
            request.lng,
            request.day,
        )


class ParagraphGenerator:
    """Coordinate typed request handlers and deterministic rendering.

    Args:
        client: Client for published Reuters data.
        renderer: Optional paragraph renderer for dependency injection.

    Example:
        ``ParagraphGenerator(client).generate(GlobalRequest("2026-09-22"))``
    """

    def __init__(
        self,
        client: ClimateMonitorClient,
        renderer: ParagraphRenderer | None = None,
        global_handler: GlobalRequestHandler | None = None,
        region_handler: RegionRequestHandler | None = None,
        location_handler: LocationRequestHandler | None = None,
    ) -> None:
        self._client = client
        self._renderer = renderer or ParagraphRenderer()
        self._global_handler = global_handler or GlobalRequestHandler()
        self._region_handler = region_handler or RegionRequestHandler()
        self._location_handler = location_handler or LocationRequestHandler()

    def generate(self, request: GenerationRequest) -> dict[str, object]:
        """Fetch a typed request and return the JSON payload.

        Args:
            request: One of the supported typed request subclasses.

        Returns:
            A serializable paragraph payload.

        Raises:
            TypeError: If ``request`` is the untyped base class.
        """
        observation = self._observation_for(request)
        return observation.to_payload(
            today=request.today,
            renderer=self._renderer,
        )

    def generate_global(
        self,
        day: str,
        *,
        today: date | None = None,
    ) -> dict[str, object]:
        """Generate a paragraph for the global daily average.

        Args:
            day: Exact UTC date.
            today: Optional current date used by deterministic tests.

        Returns:
            A serializable paragraph payload.
        """
        return self.generate(GlobalRequest(day=day, today=today))

    def generate_region(
        self,
        region_set: str,
        region: str,
        day: str,
        *,
        today: date | None = None,
    ) -> dict[str, object]:
        """Generate a paragraph for one named region.

        Args:
            region_set: Published region-set slug.
            region: Exact display label.
            day: Exact UTC date.
            today: Optional current date used by deterministic tests.

        Returns:
            A serializable paragraph payload.
        """
        return self.generate(
            RegionRequest(
                day=day,
                region_set=region_set,
                region=region,
                today=today,
            )
        )

    def generate_location(
        self,
        label: str,
        day: str,
        *,
        lat: float | None = None,
        lng: float | None = None,
        today: date | None = None,
    ) -> dict[str, object]:
        """Generate a paragraph for a named or coordinate location.

        Args:
            label: Human-readable place label.
            day: Exact UTC date.
            lat: Latitude override, or ``None`` when geocoding.
            lng: Longitude override, or ``None`` when geocoding.
            today: Optional current date used by deterministic tests.

        Returns:
            A serializable paragraph payload.
        """
        return self.generate(
            LocationRequest(
                day=day,
                label=label,
                lat=lat,
                lng=lng,
                today=today,
            )
        )

    def _observation_for(self, request: GenerationRequest) -> Observation:
        """Dispatch a typed request to its dedicated handler.

        Args:
            request: One of the supported typed request subclasses.

        Returns:
            The requested published observation.

        Raises:
            TypeError: If ``request`` is the untyped base class.
        """
        if isinstance(request, GlobalRequest):
            return self._global_handler.observe(self._client, request)
        if isinstance(request, RegionRequest):
            return self._region_handler.observe(self._client, request)
        if isinstance(request, LocationRequest):
            return self._location_handler.observe(self._client, request)
        raise TypeError(f"Unsupported request type: {type(request).__name__}")
