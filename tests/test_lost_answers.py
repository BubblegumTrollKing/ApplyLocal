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
    def ask(request):
        assert "also contains visual content" in request["message"]
        browser.stop.set()
        return UserReply()
    engine = Engine(browser, None, Settings(), Profile({"email": "real@example.test"}),
                    browser.stop, lambda e: None, ask)
    assert engine.run() == "stopped"
    assert browser.page.evaluate("!!window.clicked") is False
