import pytest

from applylocal.domain import Answer, AssistanceRequired
from applylocal.engine import Engine, UserReply
from applylocal.storage import Profile, Settings

pytestmark = pytest.mark.browser


class NoAI:
    def decide(self, *args):
        raise AssertionError("A model must not supply personal or attestation answers")


def test_manual_attestation_can_resume_after_user_checks(browser):
    browser.page.set_content('<label><input type=checkbox>I certify these answers are true</label><button onclick="document.body.innerHTML=\'<h1>Assessment complete</h1>\'">Submit</button>')
    asks = []
    def ask(request):
        asks.append(request)
        assert request["question"] is None
        browser.page.locator("input").check()  # Explicit manual user action.
        return UserReply()
    engine = Engine(browser, NoAI(), Settings(auto_submit=True), Profile(), browser.stop, lambda e: None, ask)
    assert engine.run() == "complete"
    assert len(asks) == 1


def test_human_only_restriction_survives_page_change(browser):
    browser.page.set_content('<p>Do not use AI tools</p>')
    asks = []
    def ask(request):
        asks.append(request)
        if len(asks) == 1:
            browser.page.set_content('<label>Email address<input></label><button>Next</button>')
        else:
            browser.stop.set()
        return UserReply()
    engine = Engine(browser, NoAI(), Settings(), Profile({"email": "real@example.test"}), browser.stop, lambda e: None, ask)
    assert engine.run() == "stopped"
    assert len(asks) == 2
    assert browser.page.locator("input").input_value() == ""


def test_scenario_context_is_captured_and_bound_to_answer(browser):
    browser.page.set_content('<fieldset><legend>Which action is safest?</legend><p>A coworker is injured.</p><label><input type=radio name=q>Get help</label><label><input type=radio name=q>Ignore it</label></fieldset>')
    snap = browser.snapshot()
    q = snap.questions[0]
    assert q.context == "A coworker is injured."
    browser.page.locator("p").evaluate("el => el.textContent='The alarm is a drill.'")
    with pytest.raises(AssistanceRequired, match="changed"):
        browser.apply(snap, q, Answer((q.options[0].id,)))


def test_scenario_outside_fieldset_is_not_omitted(browser):
    browser.page.set_content('<p>A customer reports smoke in the stockroom.</p><fieldset><legend>Which action is safest?</legend><label><input type=radio name=q>Follow the emergency procedure</label><label><input type=radio name=q>Ignore it</label></fieldset>')
    assert "smoke in the stockroom" in browser.snapshot().questions[0].context
