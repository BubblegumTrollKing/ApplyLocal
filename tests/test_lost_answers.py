import pytest

from applylocal.engine import Engine, UserReply
from applylocal.storage import Profile, Settings

pytestmark = pytest.mark.browser


def test_answer_erased_by_later_field_is_restored_automatically(browser):
    browser.page.set_content('''<label>Email address<input id="email"></label>
    <label>First name<input onchange="email.value=''"></label>
    <button onclick="window.clicked=true;document.body.innerHTML=\'<h1>Assessment complete</h1>\'">Submit</button>''')
    reasons = []
    def ask(request):
        reasons.append(request["message"])
        browser.stop.set()
        return UserReply()
    engine = Engine(browser, None, Settings(), Profile({"email": "real@example.test", "first_name": "Real"}),
                    browser.stop, lambda e: None, ask)
    assert engine.run() == "complete"
    assert reasons == []
    assert browser.page.evaluate("!!window.clicked") is True


def test_mixed_visual_question_is_not_silently_skipped(browser):
    browser.page.set_content('''<label>Email address<input></label><canvas width=400 height=200></canvas>
    <button onclick="window.clicked=true">Next</button>''')
    import threading
    events = []
    timer = threading.Timer(0.5, browser.stop.set)
    timer.start()
    engine = Engine(browser, None, Settings(), Profile({"email": "real@example.test"}),
                    browser.stop, events.append, lambda r: pytest.fail("No operational recheck dialog"))
    try:
        assert engine.run() == "stopped"
    finally:
        timer.join()
    assert any("visual content" in e["message"] for e in events)
    assert browser.page.evaluate("!!window.clicked") is False
