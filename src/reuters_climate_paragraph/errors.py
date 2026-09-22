"""Shared errors for the Reuters Climate Monitor sidecar."""

from __future__ import annotations


class ClimateMonitorError(RuntimeError):
    """Raised when a Reuters Climate Monitor response cannot be used."""
