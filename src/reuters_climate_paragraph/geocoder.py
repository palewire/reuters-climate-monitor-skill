"""OpenStreetMap Nominatim geocoding with a local cache."""

from __future__ import annotations

import json
import math
import os
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .diagnostics import (
    get_logger,
    log_http_failure,
    log_http_response,
    safe_url,
)
from .errors import ClimateMonitorError

NOMINATIM_ROOT = "https://nominatim.openstreetmap.org/search"
NOMINATIM_USER_AGENT = (
    "ReutersClimateParagraph/0.1 "
    "(https://github.com/palewire/reuters-climate-paragraph)"
)
NominatimFetcher = Callable[[str], object]
LOGGER = get_logger(__name__)


class NominatimGeocoder:
    """Resolve place names with cached OpenStreetMap Nominatim lookups.

    Args:
        cache_path: Optional JSON path for cached coordinates. When omitted,
            the path under ``$XDG_CACHE_HOME`` is used.
        fetcher: Optional function that fetches and decodes a Nominatim URL.
            The default performs the network request.

    Example:
        ``geocoder = NominatimGeocoder(); geocoder("Paris")``
    """

    def __init__(
        self,
        *,
        cache_path: Path | None = None,
        fetcher: NominatimFetcher | None = None,
    ) -> None:
        self._cache_path = cache_path or self.default_cache_path()
        self._fetcher = fetcher or self.fetch_nominatim_json

    def __call__(self, label: str) -> tuple[float, float]:
        """Resolve a place name when the geocoder is used as a callable.

        Args:
            label: Place name or unambiguous place query.

        Returns:
            A latitude and longitude in decimal degrees.

        Raises:
            ClimateMonitorError: If the lookup, response, or cache is unusable.
        """
        return self.geocode(label)

    def geocode(self, label: str) -> tuple[float, float]:
        """Resolve a place name using the cache before querying Nominatim.

        Args:
            label: Place name or unambiguous place query.

        Returns:
            A latitude and longitude in decimal degrees.

        Raises:
            ClimateMonitorError: If the label, lookup, response, or cache is
                unusable.

        Example:
            ``NominatimGeocoder().geocode("Paris")``
        """
        query = label.strip()
        if not query:
            raise ClimateMonitorError("Location label must not be empty")

        cache = self._read_cache()
        cache_key = query.casefold()
        cached = cache.get(cache_key)
        if cached is not None:
            return self.parse_coordinates(cached, query)

        url = (
            f"{NOMINATIM_ROOT}?"
            f"{urllib.parse.urlencode({'q': query, 'format': 'jsonv2', 'limit': 1})}"
        )
        raw = self._fetcher(url)
        if not isinstance(raw, list) or not raw or not isinstance(raw[0], dict):
            raise ClimateMonitorError(f"Nominatim found no result for {query!r}")

        coordinates = self.parse_coordinates(raw[0], query)
        cache[cache_key] = {"lat": coordinates[0], "lng": coordinates[1]}
        self._write_cache(cache)
        return coordinates

    @staticmethod
    def default_cache_path() -> Path:
        """Return the default local cache path.

        Returns:
            A JSON path under ``$XDG_CACHE_HOME`` or the user's cache directory.

        Example:
            ``NominatimGeocoder.default_cache_path().name == "nominatim.json"``
        """
        cache_root = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
        return cache_root / "reuters-climate-paragraph" / "nominatim.json"

    @staticmethod
    def parse_coordinates(result: dict[str, Any], query: str) -> tuple[float, float]:
        """Parse and validate coordinates from a Nominatim result or cache entry.

        Args:
            result: Nominatim result mapping.
            query: Original place query used in the error message.

        Returns:
            A latitude and longitude in decimal degrees.

        Raises:
            ClimateMonitorError: If the result does not contain valid
                coordinates.
        """
        try:
            lat = float(result["lat"])
            lng = float(result["lon"] if "lon" in result else result["lng"])
        except (KeyError, TypeError, ValueError) as error:
            raise ClimateMonitorError(
                f"Nominatim returned no valid coordinates for {query!r}"
            ) from error

        NominatimGeocoder.validate_coordinates(lat, lng)
        return lat, lng

    @staticmethod
    def fetch_nominatim_json(url: str) -> object:
        """Fetch and decode a Nominatim response.

        Args:
            url: Absolute Nominatim search URL.

        Returns:
            The decoded JSON response.

        Raises:
            ClimateMonitorError: If the request or response is unusable.
        """
        request = urllib.request.Request(  # noqa: S310 - Nominatim HTTPS URL.
            url,
            headers={
                "Accept": "application/json",
                "User-Agent": NOMINATIM_USER_AGENT,
            },
        )
        LOGGER.debug("GET Nominatim response url=%s", safe_url(url))
        try:
            with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310
                log_http_response(
                    LOGGER,
                    "GET Nominatim response",
                    url,
                    response.getcode(),
                    response.headers,
                )
                return json.load(response)
        except urllib.error.HTTPError as error:
            log_http_failure(LOGGER, "GET Nominatim response", url, error)
            raise ClimateMonitorError(
                f"Could not read Nominatim response for {url}: "
                f"HTTP {error.code} {error.reason}"
            ) from error
        except (OSError, urllib.error.URLError) as error:
            log_http_failure(LOGGER, "GET Nominatim response", url, error)
            raise ClimateMonitorError(
                f"Could not read Nominatim response for {url}: {error}"
            ) from error
        except json.JSONDecodeError as error:
            LOGGER.debug(
                "GET Nominatim response returned invalid JSON url=%s",
                safe_url(url),
                exc_info=True,
            )
            raise ClimateMonitorError(
                f"Could not decode Nominatim response for {url}: {error}"
            ) from error

    @staticmethod
    def validate_coordinates(lat: float, lng: float) -> None:
        """Validate decimal-degree coordinates.

        Args:
            lat: Latitude in decimal degrees.
            lng: Longitude in decimal degrees.

        Returns:
            None.

        Raises:
            ClimateMonitorError: If either coordinate is out of range or
                non-finite.
        """
        if not math.isfinite(lat) or not -90 <= lat <= 90:
            raise ClimateMonitorError("Latitude must be between -90 and 90")
        if not math.isfinite(lng) or not -180 <= lng <= 180:
            raise ClimateMonitorError("Longitude must be between -180 and 180")

    def _read_cache(self) -> dict[str, dict[str, float]]:
        """Read this geocoder's cached coordinates.

        Returns:
            Cached place coordinates, or an empty mapping when no cache exists.

        Raises:
            ClimateMonitorError: If an existing cache cannot be decoded.
        """
        try:
            raw = json.loads(self._cache_path.read_text())
        except FileNotFoundError:
            return {}
        except (OSError, json.JSONDecodeError) as error:
            raise ClimateMonitorError(
                f"Could not read geocoder cache {self._cache_path}: {error}"
            ) from error
        if not isinstance(raw, dict):
            raise ClimateMonitorError(
                f"Geocoder cache is not an object: {self._cache_path}"
            )
        return raw

    def _write_cache(self, cache: dict[str, dict[str, float]]) -> None:
        """Write cached coordinates for this geocoder.

        Args:
            cache: Place coordinates to save.

        Returns:
            None.

        Raises:
            ClimateMonitorError: If the cache cannot be written.
        """
        try:
            self._cache_path.parent.mkdir(parents=True, exist_ok=True)
            self._cache_path.write_text(
                json.dumps(cache, indent=2, sort_keys=True) + "\n"
            )
        except OSError as error:
            raise ClimateMonitorError(
                f"Could not write geocoder cache {self._cache_path}: {error}"
            ) from error


def fetch_nominatim_json(url: str) -> object:
    """Fetch and decode a Nominatim response.

    Args:
        url: Absolute Nominatim search URL.

    Returns:
        The decoded JSON response.

    Raises:
        ClimateMonitorError: If the request or response is unusable.

    Example:
        ``raw = fetch_nominatim_json("https://example.test/search")``
    """
    return NominatimGeocoder.fetch_nominatim_json(url)


def validate_coordinates(lat: float, lng: float) -> None:
    """Validate decimal-degree coordinates.

    Args:
        lat: Latitude in decimal degrees.
        lng: Longitude in decimal degrees.

    Returns:
        None.

    Raises:
        ClimateMonitorError: If either coordinate is out of range or non-finite.
    """
    NominatimGeocoder.validate_coordinates(lat, lng)


def geocode_place(label: str) -> tuple[float, float]:
    """Resolve a place name with the default Nominatim geocoder.

    Args:
        label: Place name or unambiguous place query.

    Returns:
        A latitude and longitude in decimal degrees.

    Raises:
        ClimateMonitorError: If the lookup, response, or cache is unusable.
    """
    return NominatimGeocoder()(label)
