import threading
from concurrent.futures import ThreadPoolExecutor
import socket

import pytest

from applylocal.browser import BrowserSession
from applylocal.domain import Answer


@pytest.mark.browser
def test_real_cdp_attach_select_and_disconnect(tmp_path, chromium):
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    owner = chromium.browser_type.launch(headless=True, args=[f"--remote-debugging-port={port}"])
    owner.new_page().set_content('<label>Email address<input></label>')
    try:
        def attach(first):
            session = BrowserSession(threading.Event())
            try:
                session.connect(f"http://127.0.0.1:{port}")
                session.select(session.tabs()[0]["id"])
                if first:
                    session.page.set_content('<title>CDP fixture</title><label>Email address<input></label>')
                    snap = session.snapshot()
                    session.apply(snap, snap.questions[0], Answer(value="real@example.test"))
                else:
                    assert session.snapshot().questions[0].value == "real@example.test"
                    session.browser.close()  # Only the test-owned browser.
            finally:
                session.close()
        # The production GUI also owns Playwright exclusively inside a worker thread.
        with ThreadPoolExecutor(max_workers=1) as executor:
            executor.submit(attach, True).result(timeout=15)
            assert owner.is_connected()  # Disconnect leaves the browser running.
            executor.submit(attach, False).result(timeout=15)
    finally:
        owner.close()
