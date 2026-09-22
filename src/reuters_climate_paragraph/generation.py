"""Paragraph generation orchestration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .rendering import ParagraphRenderer
from .requests import GenerationRequest

if TYPE_CHECKING:
    from datetime import date

    from .client import ClimateMonitorClient
    from .models import Observation


class ParagraphGenerator:
    """Coordinate data lookup and deterministic paragraph rendering.

    Args:
        client: Client for published Reuters data.
        renderer: Optional paragraph renderer for dependency injection.

    Example:
        ``ParagraphGenerator(client).generate(request)``
    """

    def __init__(
        self,
        client: ClimateMonitorClient,
        renderer: ParagraphRenderer | None = None,
    ) -> None:
        self._client = client
        self._renderer = renderer or ParagraphRenderer()

    def generate(self, request: GenerationRequest) -> dict[str, object]:
        """Fetch one requested scope and return the JSON payload.

        Args:
            request: Validated generation request.

        Returns:
            A serializable paragraph payload.
        """
        observation = self._observation_for(request)
        return observation.to_payload(
            today=request.today,
            renderer=self._renderer,
        )

    @classmethod
    def generate_args(
        cls,
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
    ) -> dict[str, object]:
        """Validate CLI-style arguments and generate one paragraph payload.

        Args:
            client: Client for published Reuters data.
            scope: ``global``, ``region``, or ``location``.
            day: Exact UTC date.
            region_set: Region-set slug for a regional request.
            region: Display label for a regional request.
            label: Place label for a location request.
            lat: Location latitude.
            lng: Location longitude.
            today: Optional UTC date used by deterministic tests.

        Returns:
            A serializable paragraph payload.
        """
        request = GenerationRequest.from_args(
            scope,
            day,
            region_set=region_set,
            region=region,
            label=label,
            lat=lat,
            lng=lng,
            today=today,
        )
        return cls(client).generate(request)

    def _observation_for(self, request: GenerationRequest) -> Observation:
        """Fetch the observation described by a validated request.

        Args:
            request: Validated generation request.

        Returns:
            The requested published observation.
        """
        if request.scope == "global":
            return self._client.global_observation(request.day)
        if request.scope == "region":
            return self._client.region_observation(
                request.region_set or "",
                request.region or "",
                request.day,
            )
        return self._client.location_observation(
            request.label or "",
            request.lat,
            request.lng,
            request.day,
        )
