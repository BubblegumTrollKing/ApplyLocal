import pytest

from applylocal.domain import Answer, AssistanceRequired
from applylocal.engine import Engine
from applylocal.storage import Profile, Settings

pytestmark = pytest.mark.browser


class NoAI:
    def decide(self, *args):
        raise AssertionError("A model must not supply personal or attestation answers")


def test_manual_attestation_is_rechecked_without_confirmation_button(browser):
    browser.page.set_content('''<label><input type=checkbox>I certify these answers are true</label>
    <button onclick="document.body.innerHTML='<h1>Assessment complete</h1>'">Submit</button>''')
    browser.page.evaluate("setTimeout(()=>document.querySelector('input').checked=true,300)")
    engine = Engine(browser, NoAI(), Settings(), Profile(), browser.stop, lambda e: None,
                    lambda r: pytest.fail("A browser-side manual action must be detected automatically"))
    assert engine.run() == "complete"


def test_human_only_restriction_stops_without_a_manual_recheck_dialog(browser):
    browser.page.set_content('<p>Do not use AI tools</p>')
    def emit(event):
        if event['code'] == 'restricted':
            browser.page.set_content('<label>Email address<input></label><button>Next</button>')
    engine = Engine(browser, NoAI(), Settings(), Profile({"email": "real@example.test"}), browser.stop,
                    emit, lambda r: pytest.fail("Human-only work should stop, not ask for a recheck"))
    assert engine.run() == "human_only"
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
