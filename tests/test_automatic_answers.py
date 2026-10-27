import threading

import pytest

from applylocal.domain import Answer, AssistanceRequired, Option, Question, RecheckRequired
from applylocal.engine import Engine, UserReply
from applylocal.policy import can_reason_autonomously, requires_personal_answer
from applylocal.storage import Profile, Settings
from test_engine import FakeAI, run_engine


def choices(prompt, *labels, context=""):
    return Question("q", prompt, "radio", tuple(Option(str(i), label) for i, label in enumerate(labels)), context=context)


@pytest.mark.parametrize("prompt", [
    "Are you traditional?", "I am always punctual", "Do you enjoy teamwork?",
    "I prefer working as part of a team", "I stay calm under pressure",
    "How often do you get annoyed with customers?", "Describe yourself",
    "Which action is safest when you notice a spill on a shop floor?",
    "What should you do if your certification expires?",
    "Your manager asks you to help a coworker. Choose the best response.",
])
def test_workstyle_and_knowledge_do_not_require_manual_answers(prompt):
    q = choices(prompt, "Yes", "No")
    assert not requires_personal_answer(q)
    assert can_reason_autonomously(q)


@pytest.mark.parametrize("prompt", [
    "What would your salary expectation be?", "How would you describe your education?",
    "Are you available on weekends?", "Have you operated a forklift?",
    "Do you have a degree?", "Work authorization", "How many days were you absent last year?",
    "What is your email address?", "Are you willing to relocate?", "I have 5 years of retail experience",
])
def test_concrete_facts_and_commitments_still_require_real_values(prompt):
    q = choices(prompt, "Yes", "No")
    assert requires_personal_answer(q)
    assert not can_reason_autonomously(q)


def test_saved_paraphrase_reuses_answer_with_reordered_choices(tmp_path):
    profile = Profile()
    original = choices("Do you enjoy teamwork?", "Yes", "No")
    profile.remember(original, Answer(("0",)))
    path = tmp_path / "profile.json"
    profile.save(path)
    restored = Profile.load(path)
    equivalent = choices("I like collaborating", "No", "Yes")
    assert restored.recall(equivalent).option_ids == ("1",)
    assert restored.recall(equivalent).source == "memory"


def test_memory_does_not_copy_into_reversed_question():
    profile = Profile()
    profile.remember(choices("Do you enjoy teamwork?", "Yes", "No"), Answer(("0",)))
    reversed_q = choices("I don't enjoy teamwork", "Yes", "No")
    assert profile.recall(reversed_q) is None
    assert profile.related(reversed_q)[0]["selected"] == ["Yes"]


def test_scenario_context_and_new_fact_are_not_treated_as_equivalent():
    p = Profile()
    first = choices("Which action is safest?", "Stop", "Continue", context="A fire alarm sounds.")
    p.remember(first, Answer(("0",)))
    assert p.recall(choices(first.prompt, "Stop", "Continue", context="A drill is complete.")) is None
    available = choices("Are you available on weekends?", "Yes", "No")
    p.remember(available, Answer(("0",)))
    nights = choices("Are you available for night shifts?", "Yes", "No")
    assert p.recall(nights) is None
    assert p.related(nights) == []


def test_engine_reuses_paraphrase_without_an_ai_call():
    profile = Profile()
    profile.remember(choices("Do you enjoy teamwork?", "Yes", "No"), Answer(("0",)))
    class NoAI:
        def decide(self, *args, **kwargs):
            raise AssertionError("A simple paraphrase must not need inference")
    engine = Engine(None, NoAI(), Settings(), profile, threading.Event(), lambda e: None, lambda r: None)
    assert engine.choose(choices("I like collaborating", "Yes", "No")).option_ids == ("0",)


@pytest.mark.browser
def test_employer_judgment_and_automatic_persistent_memory(browser, tmp_path):
    browser.page.set_content('''<fieldset><legend>Are you traditional?</legend>
    <label><input type=radio name=q>Yes</label><label><input type=radio name=q>No</label></fieldset>
    <button onclick="document.body.innerHTML='<h1>Assessment complete</h1>'">Submit</button>''')
    profile, ai = Profile(), FakeAI()
    path = tmp_path / "profile.json"
    engine = Engine(browser, ai, Settings(), profile, browser.stop, lambda e: None,
                    lambda r: pytest.fail("Personality must not ask the user"), lambda: profile.save(path))
    assert engine.run() == "complete"
    assert ai.calls == 1
    assert Profile.load(path).answers


@pytest.mark.browser
def test_real_user_answer_is_saved_without_remember_checkbox(browser):
    browser.page.set_content('''<label>Email address<input></label>
    <button onclick="document.body.innerHTML='<h1>Assessment complete</h1>'">Submit</button>''')
    profile = Profile()
    def ask(request):
        return UserReply(Answer(value="true@example.test", source="user"), remember=False)
    assert run_engine(browser, profile, ask)[0] == "complete"
    assert profile.lookup(Question("new", "Email address", "text")).value == "true@example.test"


@pytest.mark.browser
def test_stale_dom_automatically_rechecks_and_reuses_inflight_answer(browser, monkeypatch):
    browser.page.set_content('''<fieldset><legend>Which action is safest?</legend>
    <label><input type=radio name=q>Report hazard</label><label><input type=radio name=q>Ignore it</label></fieldset>
    <button onclick="document.body.innerHTML='<h1>Assessment complete</h1>'">Submit</button>''')
    apply = browser.apply
    attempts = []
    def stale_once(*args):
        attempts.append(1)
        if len(attempts) == 1:
            browser.page.locator("fieldset").evaluate("el => el.outerHTML=el.outerHTML")
            raise RecheckRequired("The question changed; rechecking automatically.")
        return apply(*args)
    monkeypatch.setattr(browser, "apply", stale_once)
    ai = FakeAI()
    result, events = run_engine(browser, ai=ai)
    assert result == "complete"
    assert ai.calls == 1
    assert len(attempts) == 2
    assert any(e["code"] == "rechecking" for e in events)


@pytest.mark.browser
def test_other_question_personal_context_does_not_contaminate_safety(browser):
    browser.page.set_content('''<fieldset><legend>Which action is safest?</legend>
    <label><input type=radio name=q>Secure the area</label><label><input type=radio name=q>Ignore it</label></fieldset>
    <fieldset><legend>Availability</legend><p>Tell us about your work history and availability.</p>
    <label><input type=radio name=x>Yes</label><label><input type=radio name=x>No</label></fieldset>''')
    snap = browser.snapshot()
    assert "work history" not in snap.questions[0].context
    assert "work history" in snap.questions[1].context


def test_hands_off_default_and_legacy_settings_upgrade(tmp_path):
    assert Settings().auto_submit
    path = tmp_path / "settings.json"
    path.write_text('{"auto_submit": false}')
    assert Settings.load(path).auto_submit
    Settings(auto_submit=False).save(path)
    assert not Settings.load(path).auto_submit


def test_facts_still_do_not_call_ai():
    ai = FakeAI()
    engine = Engine(None, ai, Settings(), Profile(), threading.Event(), lambda e: None, lambda r: None)
    with pytest.raises(AssistanceRequired):
        engine.choose(choices("Are you available weekends?", "Yes", "No"))
    assert ai.calls == 0


def test_equivalent_weekend_availability_reuses_actual_user_answer():
    profile = Profile()
    profile.remember(choices("Are you available on weekends?", "Yes", "No"), Answer(("1",), source="user"))
    assert profile.recall(choices("Can you work Saturdays and Sundays?", "No", "Yes")).option_ids == ("0",)
    assert profile.recall(choices("Are you willing to work weekends?", "Yes", "No")) is None


def test_related_opposite_workstyle_gets_consistency_hint_without_direct_copy():
    profile = Profile()
    profile.remember(choices("I embrace change", "Agree", "Disagree"), Answer(("0",)))
    target = choices("Are you traditional?", "Yes", "No")
    assert profile.recall(target) is None
    assert profile.related(target)[0]["selected"] == ["Agree"]


def test_contact_fact_paraphrase_uses_profile_without_guessing():
    profile = Profile({"email": "actual@example.test"})
    assert profile.lookup(Question("q", "Please enter your email address", "text")).value == "actual@example.test"
    assert Profile().lookup(Question("q", "Please enter your email address", "text")) is None


def test_known_experience_is_reused_but_years_are_not_invented():
    profile = Profile()
    original = choices("Have you ever worked in retail?", "Yes", "No")
    profile.remember(original, Answer(("0",), source="user"))
    assert profile.recall(choices("Do you have retail experience?", "No", "Yes")).option_ids == ("1",)
    assert profile.recall(choices("Do you have warehouse experience?", "Yes", "No")) is None
    assert profile.recall(choices("How many years of retail experience?", "1", "5")) is None


@pytest.mark.browser
def test_reported_spill_question_recovers_model_misclassification_and_selects_correct_middle_option(browser):
    from applylocal.local_ai import LocalAI
    browser.page.set_content('''<fieldset><legend>Which action is safest when you notice a spill on a shop floor?</legend>
    <label><input type=radio name=q>Ignore it</label>
    <label><input type=radio name=q>Secure the area and follow the spill procedure</label>
    <label><input type=radio name=q>Run through it</label></fieldset>
    <button onclick="document.body.innerHTML='<h1>Assessment complete</h1>'">Submit</button>''')
    class MisclassifiedOnce(LocalAI):
        calls = 0
        def structured(self, model, system, payload, schema, image=None):
            self.calls += 1
            if self.calls == 1:
                return {"kind": "personal", "option_ids": [], "value": None,
                        "confidence": 0.98, "reason": "Misclassification reproduced"}
            return {"kind": "knowledge", "option_ids": [payload["options"][1]["id"]],
                    "value": None, "confidence": 0.98, "reason": "Use the safe spill procedure"}
    ai = MisclassifiedOnce("http://127.0.0.1:11434", browser.stop)
    profile = Profile()
    assert run_engine(browser, profile=profile, ai=ai)[0] == "complete"
    assert ai.calls == 1
    assert list(profile.answers.values()) == [["Secure the area and follow the spill procedure"]]


def test_disabled_old_choice_does_not_force_manual_answer():
    p = Profile()
    original = choices("Which action is safest?", "Stop", "Continue")
    p.remember(original, Answer(("0",)))
    changed = Question("q", original.prompt, "radio", (Option("x", "Stop", disabled=True), Option("y", "Continue")))
    assert p.recall(changed) is None


def test_fast_memory_preserves_comparison_order_and_negation_scope():
    profile = Profile()
    original = choices("I prefer safety over speed", "Agree", "Disagree")
    profile.remember(original, Answer(("0",)))
    assert profile.recall(choices("I prefer speed over safety", "Agree", "Disagree")) is None
    assert profile.recall(choices("I do not prefer safety over speed", "Agree", "Disagree")) is None
    assert profile.related(choices("I prefer speed over safety", "Agree", "Disagree"))
