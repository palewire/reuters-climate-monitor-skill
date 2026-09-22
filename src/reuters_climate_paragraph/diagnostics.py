"""Logging helpers for the Reuters Climate Monitor sidecar."""

from __future__ import annotations

import logging
import sys
from typing import TYPE_CHECKING
from urllib.parse import urlsplit

if TYPE_CHECKING:
    from collections.abc import Mapping

PACKAGE_LOGGER_NAME = "reuters_climate_paragraph"
_RESPONSE_HEADERS = (
    "content-type",
    "content-length",
    "date",
    "server",
    "via",
    "x-cache",
    "x-amz-cf-pop",
    "x-amz-cf-id",
)


def get_logger(module_name: str) -> logging.Logger:
    """Return a logger in the package namespace.

    Args:
        module_name: Module name passed by ``__name__``.

    Returns:
        A namespaced standard-library logger.
    """
    return logging.getLogger(f"{PACKAGE_LOGGER_NAME}.{module_name.rsplit('.', 1)[-1]}")


def configure_logging(verbose: bool) -> None:
    """Configure human-readable diagnostics for the CLI.

    Args:
        verbose: Whether to emit debug-level network diagnostics.

    Returns:
        None.
    """
    logger = logging.getLogger(PACKAGE_LOGGER_NAME)
    for handler in logger.handlers:
        handler.close()
    logger.handlers.clear()
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG if verbose else logging.CRITICAL)
    logger.propagate = False


def safe_url(url: str) -> str:
    """Remove query strings before writing a URL to logs.

    Args:
        url: URL that may contain user-provided query text.

    Returns:
        URL with its query and fragment removed.
    """
    parsed = urlsplit(url)
    return parsed._replace(query="", fragment="").geturl()


def log_http_response(
    logger: logging.Logger,
    operation: str,
    url: str,
    status: int | None,
    headers: Mapping[str, str] | None,
) -> None:
    """Log safe response metadata for a completed HTTP request.

    Args:
        logger: Logger receiving the diagnostic.
        operation: Human-readable operation such as ``GET JSON feed``.
        url: Request URL.
        status: HTTP response status, when available.
        headers: Response headers, when available.

    Returns:
        None.
    """
    logger.debug(
        "%s response url=%s status=%s headers=%s",
        operation,
        safe_url(url),
        status,
        _safe_headers(headers),
    )


def log_http_failure(
    logger: logging.Logger,
    operation: str,
    url: str,
    error: BaseException,
) -> None:
    """Log the root details of an HTTP or URL failure.

    Args:
        logger: Logger receiving the diagnostic.
        operation: Human-readable operation such as ``GET JSON feed``.
        url: Request URL.
        error: The exception raised by ``urllib``.

    Returns:
        None.
    """
    status = getattr(error, "code", None)
    reason = getattr(error, "reason", str(error))
    headers = getattr(error, "headers", None)
    logger.debug(
        "%s failed url=%s status=%s reason=%s headers=%s",
        operation,
        safe_url(url),
        status,
        reason,
        _safe_headers(headers),
    )


def _safe_headers(headers: Mapping[str, str] | None) -> dict[str, str]:
    """Select response headers useful for diagnosing network failures.

    Args:
        headers: Response headers, when available.

    Returns:
        A mapping containing non-sensitive CDN and HTTP metadata.
    """
    if headers is None:
        return {}
    return {
        name: str(value)
        for name in _RESPONSE_HEADERS
        if (value := headers.get(name)) is not None
    }
