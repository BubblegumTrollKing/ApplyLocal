from pathlib import Path
import threading

import pytest
from playwright.sync_api import sync_playwright

from applylocal.browser import BrowserSession


@pytest.fixture(scope="session")
def chromium():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--disable-dev-shm-usage"])
        yield browser
        browser.close()


@pytest.fixture
def browser(chromium):
    context = chromium.new_context(viewport={"width": 1000, "height": 750}, device_scale_factor=1)
    page = context.new_page()
    session = BrowserSession(threading.Event())
    session.browser = chromium
    session.page = page
    page.set_default_timeout(2000)
    yield session
    context.close()


@pytest.fixture
def fixture_html():
    return lambda name: (Path(__file__).parent / "fixtures" / name).read_text(encoding="utf-8")
