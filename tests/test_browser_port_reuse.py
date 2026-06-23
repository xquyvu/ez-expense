#!/usr/bin/env python3
"""Tests for reusing an already-running debug browser on the preferred port."""

import json
import urllib.request

import config
from browser import BROWSER_CONFIG


class _FakeResponse:
    def __init__(self, payload: dict):
        self._payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self) -> bytes:
        return json.dumps(self._payload).encode()


def test_matching_debug_browser_is_detected(monkeypatch):
    """A debug browser whose CDP token matches the configured browser is reused."""
    token = BROWSER_CONFIG[config.BROWSER].cdp_token
    monkeypatch.setattr(
        urllib.request,
        "urlopen",
        lambda *a, **k: _FakeResponse({"Browser": f"{token}120.0.0"}),
    )

    assert config._has_matching_debug_browser(9222) is True


def test_non_matching_browser_is_ignored(monkeypatch):
    """A debug endpoint for a different browser type is not reused."""
    monkeypatch.setattr(
        urllib.request,
        "urlopen",
        lambda *a, **k: _FakeResponse({"Browser": "HeadlessSomethingElse/1.0"}),
    )

    assert config._has_matching_debug_browser(9222) is False


def test_no_endpoint_returns_false(monkeypatch):
    """When nothing is listening, the helper reports no reusable browser."""

    def _refuse(*_args, **_kwargs):
        raise OSError("connection refused")

    monkeypatch.setattr(urllib.request, "urlopen", _refuse)

    assert config._has_matching_debug_browser(9222) is False
