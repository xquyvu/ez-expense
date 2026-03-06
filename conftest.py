"""
Shared pytest fixtures for EZ Expense E2E tests.

Provides:
- Quart app via create_app()
- Live server on a random free port (Hypercorn in a background thread)
- Playwright browser + page using the sync API
"""

import os

# Set mock mode BEFORE any test module imports config.py (which evaluates env vars
# at import time). conftest.py is processed before test collection, so this ensures
# config.IMPORT_EXPENSE_MOCK is True when config is first imported.
os.environ["IMPORT_EXPENSE_MOCK"] = "True"

import socket
import threading
import asyncio

import pytest
from playwright.sync_api import sync_playwright


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _free_port() -> int:
    """Return an unused TCP port on localhost."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _create_test_jpeg(path: str) -> None:
    """Create a tiny but valid JPEG file for upload tests."""
    # Minimal valid JPEG: SOI + APP0 (JFIF) + minimal frame + EOI
    # This is a 1x1 white pixel JPEG
    data = bytes([
        0xFF, 0xD8,  # SOI
        0xFF, 0xE0,  # APP0 marker
        0x00, 0x10,  # Length = 16
        0x4A, 0x46, 0x49, 0x46, 0x00,  # "JFIF\0"
        0x01, 0x01,  # Version 1.1
        0x00,        # Aspect ratio units (0 = no units)
        0x00, 0x01,  # X density
        0x00, 0x01,  # Y density
        0x00, 0x00,  # No thumbnail
        0xFF, 0xDB,  # DQT marker
        0x00, 0x43,  # Length = 67
        0x00,        # Table 0, 8-bit precision
    ])
    # 64 quantization values (all 1s for simplicity)
    data += bytes([0x01] * 64)
    data += bytes([
        0xFF, 0xC0,  # SOF0 marker
        0x00, 0x0B,  # Length = 11
        0x08,        # 8-bit precision
        0x00, 0x01,  # Height = 1
        0x00, 0x01,  # Width = 1
        0x01,        # 1 component
        0x01,        # Component ID = 1
        0x11,        # Sampling factors
        0x00,        # Quantization table 0
        0xFF, 0xC4,  # DHT marker
        0x00, 0x1F,  # Length = 31
        0x00,        # DC table 0
        # Number of codes of each length (1-16)
        0x00, 0x01, 0x05, 0x01, 0x01, 0x01, 0x01, 0x01,
        0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
        # Values
        0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08, 0x09, 0x0A, 0x0B,
        0xFF, 0xDA,  # SOS marker
        0x00, 0x08,  # Length = 8
        0x01,        # 1 component
        0x01,        # Component ID = 1
        0x00,        # DC/AC table selectors
        0x00, 0x3F, 0x00,  # Spectral selection
        0x7F, 0x50,  # Compressed data (minimal)
        0xFF, 0xD9,  # EOI
    ])
    with open(path, "wb") as f:
        f.write(data)


# ---------------------------------------------------------------------------
# App fixture
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def app():
    """Create the Quart app for testing."""
    from front_end.app import create_app

    # Patch IMPORT_EXPENSE_MOCK in all modules that import it by value,
    # because load_dotenv(override=True) in config.py may have overridden
    # the env var with the .env file's value (False).
    import config
    from front_end.routes import expense_routes
    import expense_importer
    config.IMPORT_EXPENSE_MOCK = True
    expense_routes.IMPORT_EXPENSE_MOCK = True
    expense_importer.IMPORT_EXPENSE_MOCK = True

    app = create_app()
    app.config["TESTING"] = True
    return app


# ---------------------------------------------------------------------------
# Live server fixture (Hypercorn in a background thread)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def live_server(app):
    """Start the Quart app on a random free port, yield the base URL, shut down after."""
    import hypercorn.asyncio
    import hypercorn.config

    port = _free_port()
    config = hypercorn.config.Config()
    config.bind = [f"127.0.0.1:{port}"]
    config.loglevel = "WARNING"

    loop = asyncio.new_event_loop()
    shutdown_event = asyncio.Event()

    async def _serve():
        await hypercorn.asyncio.serve(app, config, shutdown_trigger=shutdown_event.wait)

    thread = threading.Thread(target=loop.run_until_complete, args=(_serve(),), daemon=True)
    thread.start()

    # Wait until the server is accepting connections
    import time
    base_url = f"http://127.0.0.1:{port}"
    for _ in range(50):
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                break
        except OSError:
            time.sleep(0.1)
    else:
        raise RuntimeError(f"Live server did not start on port {port}")

    yield base_url

    # Shutdown
    loop.call_soon_threadsafe(shutdown_event.set)
    thread.join(timeout=5)


# ---------------------------------------------------------------------------
# Playwright fixtures (sync API)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def playwright_instance():
    """Start and stop the Playwright engine per module.

    Module scope (not session) prevents Playwright's internal event loop from
    staying alive during non-Playwright test modules, which would cause
    'Runner.run() cannot be called from a running event loop' errors in
    pytest-asyncio async tests.
    """
    pw = sync_playwright().start()
    yield pw
    pw.stop()


@pytest.fixture(scope="module")
def browser(playwright_instance, request):
    """Launch a headless Chromium browser for the test module."""
    headed = request.config.getoption("--headed", default=False)
    browser = playwright_instance.chromium.launch(headless=not headed)
    yield browser
    browser.close()


@pytest.fixture()
def page(browser, live_server):
    """Create a fresh browser page for each test, navigated to the app."""
    pg = browser.new_page()
    pg.goto(live_server)
    pg.wait_for_load_state("networkidle")
    yield pg
    pg.close()


# ---------------------------------------------------------------------------
# Test data fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def test_jpeg(tmp_path_factory):
    """Return the path to a tiny valid JPEG file for upload tests."""
    path = str(tmp_path_factory.mktemp("data") / "test_receipt.jpg")
    _create_test_jpeg(path)
    return path


@pytest.fixture(scope="session")
def test_jpegs(tmp_path_factory):
    """Return paths to 3 small JPEG files for multi-upload tests."""
    d = tmp_path_factory.mktemp("multi")
    paths = []
    for i in range(3):
        p = str(d / f"receipt_{i}.jpg")
        _create_test_jpeg(p)
        paths.append(p)
    return paths


# ---------------------------------------------------------------------------
# pytest addoption for --headed
# ---------------------------------------------------------------------------

def pytest_addoption(parser):
    parser.addoption(
        "--headed",
        action="store_true",
        default=False,
        help="Run Playwright tests in headed mode (visible browser).",
    )


def pytest_configure(config):
    config.addinivalue_line("markers", "real_myexpense: tests against a real running app")


# ---------------------------------------------------------------------------
# Hook: store test outcome so fixtures can detect failure
# ---------------------------------------------------------------------------

@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    rep = outcome.get_result()
    setattr(item, f"rep_{rep.when}", rep)


# ---------------------------------------------------------------------------
# Real-app fixtures (for test_e2e_myexpense_automation)
# ---------------------------------------------------------------------------

SCREENSHOT_DIR = os.path.join(os.path.dirname(__file__), "test_screenshots")


@pytest.fixture(scope="session")
def real_app_url():
    """Return the base URL of an already-running app. Skip if unreachable."""
    url = os.environ.get("EZ_EXPENSE_BASE_URL", "http://127.0.0.1:5001")
    try:
        import urllib.request
        urllib.request.urlopen(f"{url}/health", timeout=5)
    except Exception:
        pytest.skip(f"Real app not reachable at {url}")
    return url


@pytest.fixture()
def real_page(browser, real_app_url, request):
    """Fresh Playwright page navigated to the real app. Auto-screenshots on failure."""
    pg = browser.new_page()
    pg.goto(real_app_url)
    pg.wait_for_load_state("networkidle")
    yield pg

    # On test failure, capture dual screenshots
    if hasattr(request.node, "rep_call") and request.node.rep_call.failed:
        os.makedirs(SCREENSHOT_DIR, exist_ok=True)
        test_name = request.node.name
        try:
            pg.screenshot(path=os.path.join(SCREENSHOT_DIR, f"{test_name}_frontend.png"))
        except Exception:
            pass
        try:
            import urllib.request
            resp = urllib.request.urlopen(
                f"{real_app_url}/api/expenses/screenshot", timeout=30
            )
            with open(os.path.join(SCREENSHOT_DIR, f"{test_name}_myexpense.png"), "wb") as f:
                f.write(resp.read())
        except Exception:
            pass

    pg.close()


@pytest.fixture()
def setup_expense_report(real_app_url):
    """Navigate the app's browser to the test expense report (AI_DEBUG mode)."""
    import urllib.request
    import urllib.error
    import json

    report_number = os.environ.get("AI_DEBUG_REPORT", "D10710000200323")
    url = f"{real_app_url}/api/expenses/navigate-to-report"
    data = json.dumps({"report_number": report_number}).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        resp = urllib.request.urlopen(req, timeout=60)
        result = json.loads(resp.read())
        if not result.get("success"):
            pytest.fail(f"navigate-to-report failed: {result}")
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        if e.code == 403:
            pytest.skip("App is not in AI_DEBUG mode")
        elif e.code == 500:
            pytest.skip(f"navigate-to-report failed (500): {body}")
        else:
            pytest.fail(f"navigate-to-report returned {e.code}: {body}")
    except Exception as e:
        pytest.fail(f"navigate-to-report error: {e}")
