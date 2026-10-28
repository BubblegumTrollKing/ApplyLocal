import json
import threading

import pytest

from applylocal.domain import Answer, Option, Question
from applylocal.engine import Engine
from applylocal.storage import Profile, Settings
from applylocal.workstyle import agreement_scale, judge_statement, workstyle_answer
from test_engine import run_engine

LABELS = ('Strongly agree', 'Moderately agree', 'Agree', 'Neither agree nor disagree',
          'Disagree', 'Moderately disagree', 'Strongly disagree')


def q(prompt, labels=LABELS):
    return Question('q', prompt, 'radio', tuple(Option(str(i), label) for i, label in enumerate(labels)))


EXAMPLES = [
    ('You enjoy exploring unfamiliar ideas and viewpoints.', 1),
    ('You are not easily swayed by emotional arguments.', 1),
    ('You struggle with deadlines.', -1),
    ('I do not struggle with deadlines.', 1),
    ('I struggle with time management.', -1),
    ('I miss deadlines.', -1),
    ('I rarely miss deadlines.', 1),
    ('I never miss deadlines.', 1),
    ('I always meet deadlines.', 1),
    ('I rarely meet deadlines.', -1),
    ('I keep my commitments.', 1),
    ('I never keep my promises.', -1),
    ('I finish my work on time.', 1),
    ('I put off important tasks.', -1),
    ('I am disorganized.', -1),
    ('I am not disorganized.', 1),
    ('I plan ahead.', 1),
    ('I leave work until the last minute.', -1),
    ('I pay close attention to detail.', 1),
    ('I overlook important details.', -1),
    ('I check my work.', 1),
    ('I am careless.', -1),
    ('I am not careless.', 1),
    ('I welcome new approaches.', 1),
    ('I avoid new ideas.', -1),
    ('I am easily swayed by emotional arguments.', -1),
    ('I consider evidence.', 1),
    ('I rely entirely on gut feelings.', -1),
    ('I regularly make new friends.', 1),
    ('I enjoy meeting new people.', 1),
    ('I do not enjoy teamwork.', -1),
    ('I do not dislike teamwork.', 1),
    ('I like collaborating.', 1),
    ('I help my coworkers.', 1),
    ('I treat customers with respect.', 1),
    ('I am rude.', -1),
    ('I am never rude.', 1),
    ('I blame others.', -1),
    ('I am honest.', 1),
    ('I am dishonest.', -1),
    ('I never lie.', 1),
    ('I take responsibility.', 1),
    ('I stay calm under pressure.', 1),
    ('I lose my temper.', -1),
    ('I never lose my temper.', 1),
    ('I welcome feedback.', 1),
    ('I reject criticism.', -1),
    ('I never ignore criticism.', 1),
    ('I follow safety procedures.', 1),
    ('I ignore safety procedures.', -1),
    ('I never ignore safety procedures.', 1),
    ('I cut corners.', -1),
    ('I do not cut corners.', 1),
]


@pytest.mark.parametrize('prompt,direction', EXAMPLES)
def test_distinct_workstyle_meanings_choose_the_requested_professional_direction(prompt, direction):
    item = q(prompt)
    answer = workstyle_answer(item)
    assert answer is not None, prompt
    assert agreement_scale(item)[answer.option_ids[0]] * direction > 0, prompt


def test_exact_reported_page_does_not_repeat_the_same_response():
    answers = [workstyle_answer(q(prompt)) for prompt, _ in EXAMPLES[:3]]
    assert [a.option_ids for a in answers] == [('1',), ('1',), ('6',)]
    assert {a.source for a in answers} == {'workstyle'}


@pytest.mark.parametrize('labels', [LABELS, tuple(reversed(LABELS)),
    ('Strongly disagree', 'Disagree', 'Neutral', 'Agree', 'Strongly agree'),
    ('Strongly disagree', 'Disagree', 'Somewhat disagree', 'Neutral', 'Somewhat agree', 'Agree', 'Strongly agree')])
def test_scale_direction_and_strength_are_independent_of_option_position(labels):
    item = q('You struggle with deadlines.', labels)
    answer = workstyle_answer(item)
    assert item.options[int(answer.option_ids[0])].label == 'Strongly disagree'


def test_ambiguous_clauses_and_unfamiliar_meanings_go_to_model():
    assert judge_statement('I meet deadlines but lie about mistakes.') is None
    assert workstyle_answer(q('I prefer abstract paintings to photographs.')) is None


def test_unknown_statement_does_not_default_to_agreement():
    from applylocal.decisions import fallback_answer
    item = q('I prefer abstract paintings to photographs.')
    answer = fallback_answer(item)
    assert item.options[int(answer.option_ids[0])].label == 'Neither agree nor disagree'


def test_common_statements_make_no_model_calls():
    class NoModel:
        def decide(self, *args, **kwargs):
            pytest.fail('Clear work-style decisions must not wait on the model')
    engine = Engine(None, NoModel(), Settings(), Profile(), threading.Event(), lambda e: None, lambda r: None)
    for text, _ in EXAMPLES:
        assert engine.choose(q(text)).source == 'workstyle'


def test_legacy_blanket_agreement_memory_is_reset_but_facts_and_explicit_answers_survive(tmp_path):
    p = Profile({'email': 'actual@example.test'})
    wrong = q('You struggle with deadlines.')
    availability = q('Are you available weekends?', ('Yes', 'No'))
    manual = q('I prefer abstract paintings to photographs.')
    p.remember(wrong, Answer(('1',), source='fallback'))
    p.remember(availability, Answer(('1',), source='user'))
    p.remember(manual, Answer(('4',), source='user'))
    raw = {'facts': p.facts, 'answers': p.answers, 'answer_sources': p.answer_sources}
    path = tmp_path/'profile.json'
    path.write_text(json.dumps(raw))
    loaded = Profile.load(path)
    assert loaded.lookup(wrong) is None
    assert loaded.lookup(availability).option_ids == ('1',)
    assert loaded.lookup(manual).option_ids == ('4',)
    assert loaded.facts == p.facts
    loaded.save(path)
    assert json.loads(path.read_text())['decision_version'] == 3


@pytest.mark.browser
def test_existing_bad_deadline_selection_is_corrected_without_asking(browser):
    browser.page.set_content('''<fieldset><legend>You struggle with deadlines.</legend>
    <label><input type=radio name=q checked>Agree</label><label><input type=radio name=q>Disagree</label></fieldset>
    <button onclick="window.finalChoice=document.querySelectorAll('input')[1].checked;document.body.innerHTML='<h1>Assessment complete</h1>'">Submit</button>''')
    assert run_engine(browser)[0] == 'complete'
    assert browser.page.evaluate('window.finalChoice') is True


@pytest.mark.browser
def test_sixty_different_workstyle_items_require_no_model_or_user_review(browser):
    statements = [text for text, _ in EXAMPLES] + ['I do not procrastinate.', 'I never cheat.',
        'I am approachable.', 'I am truthful.', 'I stay patient with customers.',
        'I ignore rules.', 'I value suggestions.']
    assert len(statements) == 60
    browser.page.set_content('<main id=content></main>')
    browser.page.evaluate('''data=>{
        const [statements,labels]=data;let page=0;window.results=[];
        function render(){
            if(page===20){content.innerHTML='<h1>Assessment complete</h1>';return;}
            content.innerHTML=statements.slice(page*3,page*3+3).map((text,j)=>
                '<fieldset><legend>'+text+'</legend>'+labels.map((label,i)=>
                '<label><input type="radio" name="q'+j+'" value="'+i+'">'+label+'</label>').join('')+'</fieldset>').join('')+
                '<button>'+(page===19?'Submit':'Next')+'</button>';
            content.querySelector('button').onclick=()=>{content.querySelectorAll('fieldset').forEach(f=>window.results.push(Number(f.querySelector('input:checked').value)));page++;render();};
        }render();
    }''', [statements, LABELS])
    class NoModel:
        def decide(self, *args, **kwargs):
            pytest.fail('No inference should be needed for these common statements')
    result, events = run_engine(browser, ai=NoModel())
    assert result == 'complete'
    selected = browser.page.evaluate('window.results')
    assert len(selected) == 60
    assert len(set(selected)) >= 4
    assert selected[2] == 6  # Reported deadlines item.
    assert not any(e['code'] == 'paused' for e in events)


@pytest.mark.parametrize('prompt,direction', [
    ('I fail to meet deadlines.',-1), ('I never fail to meet deadlines.',1),
    ('I have trouble staying organized.',-1), ('I do not have trouble staying organized.',1),
    ('I struggle to meet deadlines.',-1), ('I never struggle to meet deadlines.',1),
    ('I rarely fail to meet deadlines.',1), ('I have trouble not lying.',-1),
])
def test_adverse_phrases_and_double_negation_are_not_blanket_positive(prompt,direction):
    item=q(prompt)
    answer=workstyle_answer(item)
    assert answer is not None
    assert agreement_scale(item)[answer.option_ids[0]]*direction>0


@pytest.mark.parametrize('prompt', ['I wish I were more organized.',
    'I prefer chaos over an organized desk.', 'I like routine rather than unfamiliar ideas.'])
def test_comparisons_and_wishes_need_actual_reasoning(prompt):
    assert judge_statement(prompt) is None


def test_legacy_migration_keeps_an_original_local_backup(tmp_path):
    item=q('You struggle with deadlines.')
    old={'facts':{'email':'actual@example.test'},'answers':{Profile.key(item):['Moderately agree']}}
    path=tmp_path/'profile.json'
    path.write_text(json.dumps(old))
    Profile.load(path)
    assert json.loads((tmp_path/'profile-before-workstyle-v3.json').read_text()) == old


@pytest.mark.parametrize('prompt,direction',[('I am organized.',1),('I am not organized.',-1),
    ('I dislike making friends.',-1),('I refuse to ignore safety procedures.',1)])
def test_self_state_and_attitude_polarity(prompt,direction):
    item=q(prompt)
    answer=workstyle_answer(item)
    assert answer is not None
    assert agreement_scale(item)[answer.option_ids[0]]*direction>0


def test_unrelated_organized_noun_is_not_a_positive_personality_claim():
    assert judge_statement('An investigation into organized crime.') is None
