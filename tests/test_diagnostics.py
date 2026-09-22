"""Tests for network diagnostics."""

from __future__ import annotations

import io
import urllib.error
import urllib.request

import pytest

from reuters_climate_paragraph.diagnostics import configure_logging, safe_url
from reuters_climate_paragraph.errors import ClimateMonitorError
from reuters_climate_paragraph.feeds import MonitorFeedClient


def test_safe_url_removes_query_and_fragment() -> None:
    """Diagnostic URLs do not expose user-provided query text."""
    assert (
        safe_url("https://example.test/search?q=private-place#result")
        == "https://example.test/search"
    )


def test_verbose_feed_failure_logs_http_status_and_safe_headers(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verbose diagnostics identify CDN rejection details without a body."""

    def raise_forbidden(
        request: urllib.request.Request,
        *,
        timeout: int,
    ) -> object:
        raise urllib.error.HTTPError(
            request.full_url,
            403,
            "Forbidden",
            {
                "server": "AmazonS3",
                "x-cache": "Error from cloudfront",
            },
            io.BytesIO(b"private response body"),
        )

    monkeypatch.setattr(urllib.request, "urlopen", raise_forbidden)
    configure_logging(True)
    try:
        with pytest.raises(ClimateMonitorError, match="HTTP 403 Forbidden"):
            MonitorFeedClient.fetch_json(
                "https://graphics.thomsonreuters.com/private?token=secret"
            )
        stderr = capsys.readouterr().err
    finally:
        configure_logging(False)

    assert "status=403" in stderr
    assert "x-cache" in stderr
    assert "private response body" not in stderr
    assert "token=secret" not in stderr
