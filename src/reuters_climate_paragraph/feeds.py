"""Readers for published Reuters Climate Monitor JSON feeds."""

from __future__ import annotations

import json
import re
import unicodedata
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

    def region_history_row(
        self,
        region_set: str,
        region: str,
        day: str,
    ) -> tuple[dict[str, Any], str]:
        """Read one exact date from a manifest-published regional history feed.

        Args:
            region_set: Published region-set slug.
            region: Exact display label or entity identifier.
            day: UTC date in ``YYYY-MM-DD`` form.

        Returns:
            The matching published row and its feed URL.

        Raises:
            ClimateMonitorError: If the manifest, feed, date, or source label
                is unusable.
        """
        GenerationRequest.validate_region_request(region_set, region)
        template = self._region_history_template(region_set)
        region_slug = self._entity_slug(region)
        url = self._url_builder.region_history_feed_url(template, region_slug)
        row = self.select_exact_row(self._json_fetcher(url), day, region)
        source = row.get("source")
        if not isinstance(source, str) or not source.strip():
            raise ClimateMonitorError(
                f"Reuters history row for {region} on {day} has no source label"
            )
        return row, url

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

    def _region_history_template(self, region_set: str) -> str:
        """Read a region-set history URL template from the public manifest.

        Args:
            region_set: Published region-set slug.

        Returns:
            The manifest's full-history URL template.

        Raises:
            ClimateMonitorError: If the manifest does not publish the
                requested history template.
        """
        manifest_url = self._url_builder.region_manifest_url()
        raw = self._json_fetcher(manifest_url)
        if not isinstance(raw, dict):
            raise ClimateMonitorError(
                f"Reuters region manifest is not an object: {manifest_url}"
            )
        region_sets = raw.get("region_sets")
        if not isinstance(region_sets, list):
            raise ClimateMonitorError(
                f"Reuters region manifest has no region sets: {manifest_url}"
            )
        for item in region_sets:
            if not isinstance(item, dict) or item.get("slug") != region_set:
                continue
            urls = item.get("urls")
            template = (
                urls.get("full_history_by_region") if isinstance(urls, dict) else None
            )
            if isinstance(template, str) and template.strip():
                return template
            raise ClimateMonitorError(
                f"Reuters region set {region_set!r} has no published full-history feed"
            )
        raise ClimateMonitorError(
            f"Reuters manifest does not publish region set {region_set!r}"
        )

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
    def _entity_slug(region: str) -> str:
        """Convert a published entity label to its stable feed slug.

        Args:
            region: Published region label or identifier.

        Returns:
            A lowercase URL-safe entity slug.

        Raises:
            ClimateMonitorError: If the label produces no slug.
        """
        normalized = unicodedata.normalize("NFKD", region)
        ascii_label = normalized.encode("ascii", "ignore").decode("ascii")
        slug = re.sub(r"[^a-zA-Z0-9]+", "-", ascii_label).strip("-").lower()
        if not slug:
            raise ClimateMonitorError(f"Region {region!r} has no published entity slug")
        return slug

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
