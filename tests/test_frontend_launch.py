#!/usr/bin/env python3
"""Tests for opening the web UI in the dedicated debug browser (not the user's main one)."""

from unittest.mock import AsyncMock, MagicMock

import pytest

import main


@pytest.fixture(autouse=True)
def _fast_and_quiet(monkeypatch):
    """Skip the real server wait and OS-level side effects during these tests."""

    async def _ready(*_args, **_kwargs):
        return True

    monkeypatch.setattr(main, "_wait_for_frontend", _ready)
    monkeypatch.setattr(main, "_raise_dedicated_browser_to_front", lambda: None)
    monkeypatch.setattr(main, "_notify_ready", lambda _url: None)


def _fake_browser_with_page():
    page = MagicMock()
    page.goto = AsyncMock()
    page.bring_to_front = AsyncMock()

    context = MagicMock()
    context.new_page = AsyncMock(return_value=page)

    browser = MagicMock()
    browser.contexts = [context]
    return browser, context, page


@pytest.mark.asyncio
async def test_opens_frontend_in_dedicated_browser(monkeypatch):
    """The web UI is opened as a tab in the dedicated browser, not the default browser."""
    open_new = MagicMock()
    monkeypatch.setattr(main.webbrowser, "open_new", open_new)

    browser, context, page = _fake_browser_with_page()
    url = "http://127.0.0.1:5000"

    await main._open_frontend_when_ready(browser, url)

    context.new_page.assert_awaited_once()
    page.goto.assert_awaited_once_with(url)
    page.bring_to_front.assert_awaited_once()
    open_new.assert_not_called()


@pytest.mark.asyncio
async def test_falls_back_to_default_browser_when_no_dedicated(monkeypatch):
    """When no dedicated browser is available, fall back to the OS default browser."""
    open_new = MagicMock()
    monkeypatch.setattr(main.webbrowser, "open_new", open_new)

    url = "http://127.0.0.1:5000"
    await main._open_frontend_when_ready(None, url)

    open_new.assert_called_once_with(url)


@pytest.mark.asyncio
async def test_falls_back_when_dedicated_browser_errors(monkeypatch):
    """If opening a tab in the dedicated browser fails, fall back to the default browser."""
    open_new = MagicMock()
    monkeypatch.setattr(main.webbrowser, "open_new", open_new)

    browser = MagicMock()
    context = MagicMock()
    context.new_page = AsyncMock(side_effect=RuntimeError("boom"))
    browser.contexts = [context]

    url = "http://127.0.0.1:5000"
    await main._open_frontend_when_ready(browser, url)

    open_new.assert_called_once_with(url)
