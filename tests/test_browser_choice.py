import threading

import pytest

from applylocal.browser import BrowserSession
from applylocal.browser_choice import connection_endpoint, discover_existing, local_browser_endpoint
from applylocal.engine import Engine
from applylocal.storage import Profile, Settings


def test_existing_endpoint_descriptor_is_read_without_profile_data(tmp_path):
    (tmp_path / 'DevToolsActivePort').write_text('9229\n/devtools/browser/example-token\n')
    (tmp_path / 'Cookies').write_text('not accessed')
    endpoint = discover_existing(profile=str(tmp_path))
    assert endpoint == 'ws://127.0.0.1:9229/devtools/browser/example-token'
    settings = Settings(connection_mode='existing', browser_profile=str(tmp_path))
    assert connection_endpoint(settings) == endpoint
    assert (tmp_path / 'Cookies').read_text() == 'not accessed'


@pytest.mark.parametrize('text', ['notaport\n/devtools/browser/x', '0\n/devtools/browser/x',
                                 '9222\nhttps://external.invalid', '9222\n/other/path'])
def test_invalid_descriptor_is_ignored(tmp_path, text):
    (tmp_path / 'DevToolsActivePort').write_text(text)
    assert discover_existing(profile=str(tmp_path)) is None


@pytest.mark.parametrize('value', ['ws://evil.test:9222/devtools/browser/x',
                                  'ws://user:pass@127.0.0.1:9222/devtools/browser/x',
                                  'wss://127.0.0.1:9222/devtools/browser/x',
                                  'ws://127.0.0.1:9222/arbitrary',
                                  'ws://127.0.0.1:9222/devtools/browser/x#fragment'])
def test_browser_socket_must_be_local(value):
    with pytest.raises(ValueError):
        local_browser_endpoint(value)


def test_existing_mode_retains_manual_local_debugging_address(tmp_path):
    settings = Settings(connection_mode='existing', browser_profile=str(tmp_path), endpoint='http://localhost:9333')
    assert connection_endpoint(settings) == 'http://127.0.0.1:9333'


@pytest.mark.browser
def test_attach_to_already_running_browser_and_preserve_its_tab(chromium, tmp_path):
    context = chromium.browser_type.launch_persistent_context(str(tmp_path), headless=True,
        args=['--remote-debugging-port=0', '--disable-dev-shm-usage'])
    page = context.pages[0]
    page.set_content('''<title>Existing browser</title><label>Email address<input></label>
    <button onclick="document.body.innerHTML='<h1>Assessment complete</h1>'">Submit</button>''')
    settings = Settings(connection_mode='existing', browser_profile=str(tmp_path))
    stop = threading.Event()
    result = []
    def worker():
        session = BrowserSession(stop)
        try:
            endpoint = connection_endpoint(settings)
            assert endpoint.startswith('ws://127.0.0.1:')
            session.connect(endpoint)
            tabs = session.tabs()
            assert len(tabs) == 1
            session.select(tabs[0]['id'])
            engine = Engine(session, None, settings, Profile({'email': 'real@example.test'}),
                            stop, lambda e: None, lambda r: pytest.fail('No manual steps'))
            result.append(engine.run())
        except Exception as exc:
            result.append(exc)
        finally:
            session.close()
    thread = threading.Thread(target=worker)
    try:
        thread.start()
        thread.join(timeout=10)
        assert not thread.is_alive()
        assert result == ['complete']
        assert not page.is_closed()
        assert page.locator('h1').inner_text() == 'Assessment complete'
        assert len(context.pages) == 1
    finally:
        stop.set()
        thread.join(timeout=5)
        context.close()
