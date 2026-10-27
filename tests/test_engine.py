import threading

import pytest

from applylocal.domain import Answer, AssistanceRequired, Question, Snapshot, Button
from applylocal.engine import Engine, UserReply
from applylocal.storage import Profile, Settings


class FakeAI:
    def __init__(self):
        self.calls = 0

    def decide(self, model, question, threshold, **kwargs):
        self.calls += 1
        return Answer((question.options[0].id,))


def run_engine(browser, profile=None, ask=None, settings=None, ai=None):
    events = []
    if ask is None:
        def ask(request):
            raise AssertionError("Unexpected pause: " + request["message"])
    engine = Engine(browser, ai or FakeAI(), settings or Settings(auto_submit=True),
                    profile or Profile(), browser.stop, events.append, ask)
    return engine.run(), events


@pytest.mark.browser
def test_full_spa_workflow_with_real_browser_and_stub_ai(browser, fixture_html):
    browser.page.set_content(fixture_html("multipage.html"))
    result, events = run_engine(browser, Profile({"email": "real@example.test"}))
    assert result == "complete"
    assert browser.page.evaluate("window.nextClicks") == 1
    assert browser.page.evaluate("window.submits") == 1
    assert sum(e["code"] == "verified" for e in events) == 2


@pytest.mark.browser
def test_missing_personal_fact_asks_user_and_remembers(browser):
    browser.page.set_content('<fieldset><legend>Are you available on weekends?</legend><label><input type=radio name=q>Yes</label><label><input type=radio name=q>No</label></fieldset><button onclick="document.body.innerHTML=\'<h1>Assessment complete</h1>\'">Submit</button>')
    profile = Profile()
    ai = FakeAI()
    requests = []
    def ask(request):
        requests.append(request)
        return UserReply(Answer((request["question"].options[1].id,), source="user"), True)
    result, _ = run_engine(browser, profile, ask, ai=ai)
    assert result == "complete"
    assert ai.calls == 0
    assert len(profile.answers) == 1
    assert len(requests) == 1


@pytest.mark.browser
def test_final_submission_requires_user_when_disabled(browser):
    browser.page.set_content('<button onclick="document.body.innerHTML=\'<h1>Assessment complete</h1>\'">Submit</button>')
    def ask(request):
        assert request["submit"]
        return UserReply(proceed=True)
    assert run_engine(browser, ask=ask, settings=Settings(auto_submit=False))[0] == "complete"


@pytest.mark.browser
def test_human_only_never_calls_model_or_clicks(browser):
    browser.page.set_content('<p>Do not use AI tools</p><button onclick="window.clicked=true">Next</button>')
    ai = FakeAI()
    def ask(request):
        browser.stop.set()
        return UserReply()
    assert run_engine(browser, ask=ask, ai=ai)[0] == "human_only"
    assert ai.calls == 0
    assert browser.page.evaluate("!!window.clicked") is False


@pytest.mark.browser
def test_attestation_requires_manual_even_with_saved_answer(browser):
    browser.page.set_content('<label><input type=checkbox>I certify these answers are true</label><button>Submit</button>')
    profile = Profile()
    q = browser.snapshot().questions[0]
    profile.remember(q, Answer((q.options[0].id,), source="user"))
    def ask(request):
        assert request["question"] is None
        browser.stop.set()
    timer = threading.Timer(0.3, browser.stop.set)
    timer.start()
    try:
        assert run_engine(browser, profile, ask)[0] == "stopped"
    finally:
        timer.join()
    assert not browser.page.locator('input').is_checked()


@pytest.mark.browser
def test_model_failure_uses_best_effort_choice_without_asking(browser):
    browser.page.set_content('<fieldset><legend>Which action is safest?</legend><label><input type=radio name=q>Secure the area</label><label><input type=radio name=q>Ignore it</label></fieldset><button onclick="document.body.innerHTML=\'<h1>Assessment complete</h1>\'">Submit</button>')
    class BrokenAI:
        def decide(self, *args, **kwargs):
            raise AssistanceRequired("Model unavailable")
    assert run_engine(browser, ai=BrokenAI())[0] == "complete"


def test_uncertain_navigation_is_rechecked_without_user_input():
    from applylocal.domain import NavigationUnconfirmed
    stop = threading.Event()
    snap = Snapshot("http://local", "", "", [], [Button("b", "Next")])
    done = Snapshot("http://local", "", "Assessment complete", [], [], complete=True)
    class Browser:
        def __init__(self):
            self.stop = stop
            self.clicks = 0
            self.rechecks = 0
        def snapshot(self):
            return snap
        def navigation(self, s):
            return snap.buttons[0], False
        def navigate(self, *args):
            self.clicks += 1
            raise NavigationUnconfirmed("Navigation not confirmed")
        def recheck_navigation(self, **kwargs):
            self.rechecks += 1
            return done if self.rechecks == 3 else None
    browser = Browser()
    result, events = run_engine(browser)
    assert result == "complete"
    assert browser.clicks == 1
    assert browser.rechecks == 3
    assert any(e["code"] == "recovered" for e in events)


def test_no_model_for_bare_personal_label():
    ai = FakeAI()
    class Browser:
        stop = threading.Event()
    engine = Engine(Browser(), ai, Settings(), Profile(), Browser.stop, lambda e: None, lambda r: None)
    with pytest.raises(AssistanceRequired):
        engine.choose(Question("q", "Nationality", "text"))
    assert ai.calls == 0
