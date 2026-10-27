import threading

import pytest

from applylocal.decisions import fallback_answer, normalize_model_answer
from applylocal.domain import Answer, AssistanceRequired, Option, Question, validate_answer
from applylocal.engine import Engine
from applylocal.local_ai import LocalAI
from applylocal.storage import Profile, Settings
from test_engine import run_engine


def spill():
    return Question('q', 'Which action is safest when you notice a spill on a shop floor?', 'radio', (
        Option('f0:c1', 'Ignore it'), Option('f0:c2', 'Secure the area and follow the spill procedure'),
        Option('f0:c3', 'Run through it')))


@pytest.mark.parametrize('raw', [
    Answer(('f0:c2',), 'Secure the area and follow the spill procedure'),
    Answer(('Secure the area and follow the spill procedure',)),
    Answer((), 'Secure the area and follow the spill procedure'),
    Answer(('1',)), Answer(('f0:c2', 'f0:c2')), Answer(('madeup', 'f0:c2')),
])
def test_reported_mismatched_choice_format_is_repaired(raw):
    answer = normalize_model_answer(spill(), raw)
    assert answer.option_ids == ('f0:c2',)
    assert answer.value is None
    validate_answer(spill(), answer)


@pytest.mark.parametrize('raw', [None, {}, {'choice_indices': []}, {'choice_indices': [400]},
                                {'option_ids': ['invented'], 'value': 'bad output'}])
def test_malformed_output_falls_back_to_sensible_available_choice(raw, monkeypatch):
    ai = LocalAI('http://127.0.0.1:11434', threading.Event())
    calls = []
    def structured(*args):
        calls.append(1)
        return raw
    monkeypatch.setattr(ai, 'structured', structured)
    answer = ai.decide('test:local', spill(), 0.99)
    assert answer.option_ids == ('f0:c2',)
    assert len(calls) == 1


def test_imperfect_choices_never_require_a_review():
    q = Question('q', 'Choose the best imperfect option', 'radio',
                 (Option('a', 'An imperfect option'), Option('b', 'Another imperfect option')))
    assert fallback_answer(q).option_ids in {('a',), ('b',)}


def test_disabled_choices_and_empty_enabled_list_are_not_clicked():
    q = Question('q', spill().prompt, 'radio', (Option('a', 'Secure area', disabled=True), Option('b', 'Report it')))
    assert fallback_answer(q).option_ids == ('b',)
    with pytest.raises(AssistanceRequired):
        fallback_answer(Question('q', 'Waiting', 'radio', (Option('x', 'Unavailable', disabled=True),)))


@pytest.mark.parametrize('prompt,expected', [('You regularly make new friends.', 'b'),
                                         ('I ignore safety procedures.', 'f'),
                                         ('I never ignore safety procedures.', 'b')])
def test_personality_fallback_including_reported_friends_question(prompt, expected):
    labels = ['I strongly agree', 'I moderately agree', 'I agree', 'I am not sure',
              'I disagree', 'I moderately disagree', 'I strongly disagree']
    q = Question('q', 'Question 1 of 60: '+prompt, 'radio',
                 tuple(Option(chr(97+i), label) for i, label in enumerate(labels)))
    assert fallback_answer(q).option_ids == (expected,)


@pytest.mark.browser
def test_bad_answer_from_ai_never_opens_manual_dialog(browser):
    browser.page.set_content('''<fieldset><legend>Which action is safest when you notice a spill on a shop floor?</legend>
    <label><input type=radio name=q>Ignore it</label><label><input type=radio name=q>Secure the area and follow the spill procedure</label>
    <label><input type=radio name=q>Run through it</label></fieldset>
    <button onclick="document.body.innerHTML='<h1>Assessment complete</h1>'">Submit</button>''')
    class BrokenFormat:
        def decide(self, *args, **kwargs):
            return Answer(('wrong-id',), 'Secure the area and follow the spill procedure')
    profile = Profile()
    result, events = run_engine(browser, profile=profile, ai=BrokenFormat())
    assert result == 'complete'
    assert list(profile.answers.values()) == [['Secure the area and follow the spill procedure']]
    assert not any(e['code'] == 'paused' for e in events)


@pytest.mark.browser
def test_empty_error_container_and_stale_aria_invalid_are_not_real_errors(browser):
    browser.page.set_content('''<div class=error style="height:20px"></div><div role=alert style="height:20px"></div>
    <label>Email address<input type=email value="real@example.test" aria-invalid=true required></label>''')
    snapshot = browser.snapshot()
    assert snapshot.errors == []
    assert not snapshot.questions[0].invalid


@pytest.mark.browser
def test_validation_on_new_page_does_not_stop_automatic_completion(browser):
    browser.page.set_content('<label>First name<input required></label><button>Next</button>')
    browser.page.evaluate('''html=>document.querySelector('button').onclick=()=>{
        document.body.innerHTML=html;
        document.querySelector('button').onclick=()=>document.body.innerHTML='<h1>Assessment complete</h1>';
    }''', '<p role=alert>Please fill in the required field</p><label>Email address<input type=email required aria-invalid=true></label><button>Submit</button>')
    result, events = run_engine(browser, Profile({'first_name': 'Actual', 'email': 'real@example.test'}))
    assert result == 'complete'
    assert not any(e['code'] == 'paused' for e in events)


@pytest.mark.browser
def test_real_practice_page_with_non_null_model_value_finishes_without_asking(browser):
    from applylocal.browser import resource_text
    browser.page.set_content(resource_text('practice.html'))
    profile = Profile({'email': 'real@example.test'})
    weekend = Question('x', 'Are you available to work weekends?', 'radio',
                       (Option('a', 'Yes'), Option('b', 'No')), context=browser.snapshot().questions[0].context)
    profile.remember(weekend, Answer(('b',), source='user'))
    class VerboseModel:
        def decide(self, model, q, threshold, **kwargs):
            return Answer((q.options[1].id,), q.options[1].label)
    result, events = run_engine(browser, profile=profile, ai=VerboseModel())
    assert result == 'complete'
    assert not any(e['code'] == 'paused' for e in events)


@pytest.mark.browser
def test_generic_validation_warning_does_not_block_valid_form(browser):
    browser.page.set_content('''<p class=error>A stale validation warning</p>
    <label>Email address<input type=email required></label>
    <button onclick="document.body.innerHTML='<h1>Assessment complete</h1>'">Submit</button>''')
    result, events = run_engine(browser, Profile({'email': 'real@example.test'}))
    assert result == 'complete'
    assert not any(e['code'] == 'paused' for e in events)


@pytest.mark.browser
def test_missing_fact_is_detected_in_browser_without_recheck_click(browser):
    browser.page.set_content('''<label>Email address<input type=email required></label>
    <button onclick="document.body.innerHTML='<h1>Assessment complete</h1>'">Submit</button>''')
    asks = []
    def ask(request):
        asks.append(request)
        if len(asks) == 2:
            browser.page.locator('input').fill('actual@example.test')
        return None  # Poll timeout: nobody pressed a UI button.
    engine = Engine(browser, None, Settings(), Profile(), browser.stop, lambda e: None, ask)
    assert engine.run() == 'complete'
    assert asks
    assert all(r['poll_seconds'] for r in asks)


@pytest.mark.browser
def test_retryable_error_after_eight_attempts_still_never_asks_user(browser, monkeypatch):
    from applylocal.domain import RecheckRequired
    browser.page.set_content('''<label>Email address<input></label>
    <button onclick="document.body.innerHTML='<h1>Assessment complete</h1>'">Submit</button>''')
    original = browser.snapshot
    calls = []
    def snapshot():
        calls.append(1)
        if len(calls) < 10:
            raise RecheckRequired('Transient page state')
        return original()
    monkeypatch.setattr(browser, 'snapshot', snapshot)
    assert run_engine(browser, Profile({'email': 'real@example.test'}))[0] == 'complete'
    assert len(calls) > 8


def test_question_numbers_do_not_defeat_fast_answer_reuse():
    labels = (Option('a', 'Yes'), Option('b', 'No'))
    profile = Profile()
    q = Question('q', 'Question 1 of 60: You regularly make new friends.', 'radio', labels)
    profile.remember(q, Answer(('a',)))
    other = Question('new', 'Question 42 of 60: You regularly make new friends.', 'radio', labels)
    assert profile.recall(other).option_ids == ('a',)
    assert profile.recall(other).source == 'memory'


@pytest.mark.browser
def test_sixty_question_run_with_bad_model_output_and_error_banners_never_asks(browser):
    browser.page.set_content('''<main id=q></main><script>
    let step=1;window.clicks=0;
    function render(){
      if(step>60){q.innerHTML='<h1>Assessment complete</h1>';return;}
      q.innerHTML='<p class="error">A stale validation message</p><fieldset><legend>Question '+step+' of 60: You regularly make new friends.</legend><label><input type="radio" name="choice" required>I agree</label><label><input type="radio" name="choice">I disagree</label></fieldset><button>'+(step===60?'Submit':'Next')+'</button>';
      q.querySelector('button').onclick=()=>{window.clicks++;step++;render();};
    }render();</script>''')
    class BadModel:
        calls = 0
        def decide(self, *args, **kwargs):
            self.calls += 1
            return Answer(('not-a-real-id',), 'extra answer text')
    ai = BadModel()
    result, events = run_engine(browser, ai=ai)
    assert result == 'complete'
    assert browser.page.evaluate('window.clicks') == 60
    assert ai.calls == 1  # Numbered paraphrases use automatic saved memory.
    assert not any(e['code'] == 'paused' for e in events)


@pytest.mark.browser
def test_stale_aria_invalid_on_selected_custom_radio_does_not_stop_navigation(browser):
    browser.page.set_content('''<div role=radiogroup aria-label="I enjoy teamwork">
    <div role=radio aria-checked=true aria-invalid=true>Agree</div>
    <div role=radio aria-checked=false aria-invalid=true>Disagree</div></div>
    <button onclick="document.body.innerHTML='<h1>Assessment complete</h1>'">Submit</button>''')
    assert not browser.snapshot().questions[0].invalid
    assert run_engine(browser)[0] == 'complete'
