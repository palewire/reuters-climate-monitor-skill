"""Readers for published Reuters Climate Monitor JSON feeds."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from collections.abc import Callable
from typing import Any, cast

from .diagnostics import (
    get_logger,
    log_http_failure,
    log_http_response,
    safe_url,
)
from .errors import ClimateMonitorError
from .requests import REGION_SETS, GenerationRequest
from .urls import DEFAULT_URL_BUILDER, ReutersUrlBuilder

JsonFetcher = Callable[[str], object]
LOGGER = get_logger(__name__)


class MonitorFeedClient:
    """Read exact-date global and regional monitor rows.

    Args:
        json_fetcher: Optional function used to fetch JSON fixtures or feeds.
        url_builder: Optional URL builder for published feed locations.

    Example:
        ``MonitorFeedClient().global_row("2026-09-22")``
    """

    def __init__(
        self,
        json_fetcher: JsonFetcher | None = None,
        url_builder: ReutersUrlBuilder | None = None,
    ) -> None:
        self._json_fetcher = json_fetcher or self.fetch_json
        self._url_builder = url_builder or DEFAULT_URL_BUILDER

    def global_row(self, day: str) -> tuple[dict[str, Any], str]:
        """Read the globe's row for one exact UTC date.

        Args:
            day: UTC date in ``YYYY-MM-DD`` form.

        Returns:
            The matching row and the feed URL used to read it.

        Raises:
            ClimateMonitorError: If the feed or date is unusable.
        """
        url = self._url_builder.global_feed_url()
        row = self.select_exact_row(self._json_fetcher(url), day, "global")
        return row, url

    def region_row(
        self,
        region_set: str,
        region: str,
        day: str,
    ) -> tuple[dict[str, Any], str]:
        """Read a named region's row for one exact UTC date.

        Args:
            region_set: Published region-set slug.
            region: Exact display label in that feed.
            day: UTC date in ``YYYY-MM-DD`` form.

        Returns:
            The matching row and the feed URL used to read it.

        Raises:
            ClimateMonitorError: If the region set, region, feed, or date is
                unusable.
        """
        GenerationRequest.validate_region_request(region_set, region)
        url = self._url_builder.region_feed_url(region_set)
        rows = self.as_rows(self._json_fetcher(url), url)
        key = self._label_key(region_set)
        matching = [row for row in rows if row.get(key) == region]
        return self.select_exact_row(matching, day, region), url

    def region_labels(self, region_set: str) -> list[str]:
        """List labels currently published in one region-set feed.

        Args:
            region_set: Published region-set slug.

        Returns:
            Sorted, unique labels from the latest daily-averages feed.

        Raises:
            ClimateMonitorError: If the region set or feed is unusable.
        """
        GenerationRequest.validate_region_set(region_set)
        url = self._url_builder.region_feed_url(region_set)
        rows = self.as_rows(self._json_fetcher(url), url)
        key = self._label_key(region_set)
        labels = {
            value.strip()
            for row in rows
            for value in [row.get(key)]
            if isinstance(value, str) and value.strip()
        }
        if not labels:
            raise ClimateMonitorError(f"Reuters feed {url} has no region labels")
        return sorted(labels)

    def all_region_labels(self) -> dict[str, list[str]]:
        """List labels currently published across every region set.

        Returns:
            Region-set slugs mapped to sorted, unique published labels.

        Raises:
            ClimateMonitorError: If any region-set feed is unusable.
        """
        return {
            region_set: self.region_labels(region_set)
            for region_set in sorted(REGION_SETS)
        }

    @staticmethod
    def _label_key(region_set: str) -> str:
        """Return the geography field used by a region-set feed.

        Args:
            region_set: Published region-set slug.

        Returns:
            The JSON field containing the display label.
        """
        if region_set == "continent":
            return "continent"
        if region_set == "country":
            return "country"
        return "region"

    @staticmethod
    def fetch_json(url: str) -> object:
        """Fetch and decode JSON from a Reuters CDN URL.

        Args:
            url: Absolute Reuters CDN URL.

        Returns:
            The decoded JSON value.

        Raises:
            ClimateMonitorError: If the request or JSON decoding fails.
        """
        request = urllib.request.Request(  # noqa: S310 - Reuters HTTPS URL.
            url,
            headers={
                "Accept": "application/json",
                "User-Agent": "ReutersClimateSkill/0.1",
            },
        )
        LOGGER.debug("GET JSON feed url=%s", safe_url(url))
        try:
            with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310
                log_http_response(
                    LOGGER,
                    "GET JSON feed",
                    url,
                    response.getcode(),
                    response.headers,
                )
                return json.load(response)
        except urllib.error.HTTPError as error:
            log_http_failure(LOGGER, "GET JSON feed", url, error)
            raise ClimateMonitorError(
                f"Could not read Reuters feed {url}: HTTP {error.code} {error.reason}"
            ) from error
        except (OSError, urllib.error.URLError) as error:
            log_http_failure(LOGGER, "GET JSON feed", url, error)
            raise ClimateMonitorError(
                f"Could not read Reuters feed {url}: {error}"
            ) from error
        except json.JSONDecodeError as error:
            LOGGER.debug(
                "GET JSON feed returned invalid JSON url=%s",
                safe_url(url),
                exc_info=True,
            )
            raise ClimateMonitorError(
                f"Could not decode Reuters feed {url}: {error}"
            ) from error

    @staticmethod
    def as_rows(raw: object, source_url: str) -> list[dict[str, Any]]:
        """Validate that a feed response is a list of object rows.

        Args:
            raw: Decoded JSON response.
            source_url: URL used for an error message.

        Returns:
            A list of mapping rows.

        Raises:
            ClimateMonitorError: If the response shape is not supported.
        """
        if not isinstance(raw, list) or not all(isinstance(row, dict) for row in raw):
            raise ClimateMonitorError(f"Reuters feed is not a row array: {source_url}")
        return cast("list[dict[str, Any]]", raw)

    @classmethod
    def select_exact_row(
        cls,
        raw: object,
        day: str,
        label: str,
    ) -> dict[str, Any]:
        """Select one row whose date starts with the requested UTC date.

        Args:
            raw: Decoded feed response.
            day: Exact UTC date.
            label: Scope label used in errors.

        Returns:
            The one matching row.

        Raises:
            ClimateMonitorError: If no exact date is published or multiple
                rows match unexpectedly.
        """
        rows = cls.as_rows(raw, label)
        matches = [row for row in rows if str(row.get("date", "")).startswith(day)]
        if len(matches) != 1:
            raise ClimateMonitorError(
                f"Reuters feed has {len(matches)} rows for {label} on {day}; "
                "refusing to substitute another date"
            )
        return matches[0]


def fetch_json(url: str) -> object:
    """Fetch JSON from a Reuters CDN URL.

    Args:
        url: Absolute Reuters CDN URL.

    Returns:
        The decoded JSON value.

    Raises:
        ClimateMonitorError: If the request or JSON decoding fails.

    Example:
        ``raw = fetch_json("https://example.test/feed.json")``
    """
    return MonitorFeedClient.fetch_json(url)


def as_rows(raw: object, source_url: str) -> list[dict[str, Any]]:
    """Validate that a feed response is a list of object rows.

    Args:
        raw: Decoded JSON response.
        source_url: URL used for an error message.

    Returns:
        A list of mapping rows.

    Raises:
        ClimateMonitorError: If the response shape is not supported.
    """
    return MonitorFeedClient.as_rows(raw, source_url)


def select_exact_row(raw: object, day: str, label: str) -> dict[str, Any]:
    """Select one row whose date starts with the requested UTC date.

    Args:
        raw: Decoded feed response.
        day: Exact UTC date.
        label: Scope label used in errors.

    Returns:
        The one matching row.

    Raises:
        ClimateMonitorError: If no exact date is published or multiple rows
            match unexpectedly.
    """
    return MonitorFeedClient.select_exact_row(raw, day, label)
