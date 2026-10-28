import pytest

from applylocal.decisions import normalize_model_answer
from applylocal.workstyle import workstyle_answer
from test_engine import run_engine

pytestmark = pytest.mark.browser


def numeric_scale(browser, *, reversed_scale=False):
    start, end = ('Disagree', 'Agree') if reversed_scale else ('Agree', 'Disagree')
    browser.page.set_content(f'''<style>.scale{{display:flex;align-items:center;gap:18px}}label{{display:block;width:32px;height:32px;border:2px solid gray;border-radius:50%}}input{{display:none}}</style>
    <div class=question><div class=statement>You struggle with deadlines.</div>
    <div class=scale><span>{start}</span>{''.join(f'<label><input type=radio name=q value={i}></label>' for i in range(7))}<span>{end}</span></div></div>
    <button onclick="window.selected=Number(document.querySelector('input:checked').value);document.body.innerHTML='<h1>Assessment complete</h1>'">Submit</button>''')


def test_statement_caption_and_bare_numeric_scale_have_actual_meaning(browser):
    numeric_scale(browser)
    question = browser.snapshot().questions[0]
    assert question.prompt == 'You struggle with deadlines.'
    assert question.options[0].label == 'Strongly agree'
    assert question.options[-1].label == 'Strongly disagree'
    answer = workstyle_answer(question)
    assert answer.option_ids == (question.options[-1].id,)
    assert normalize_model_answer(question, answer) == answer


@pytest.mark.parametrize('reversed_scale,expected', [(False, 6), (True, 0)])
def test_hidden_radios_use_visible_circle_labels_and_correct_scale_direction(browser, reversed_scale, expected):
    numeric_scale(browser, reversed_scale=reversed_scale)
    assert run_engine(browser)[0] == 'complete'
    assert browser.page.evaluate('window.selected') == expected


def test_no_scale_direction_is_invented_without_visible_anchors(browser):
    browser.page.set_content('''<div class=question><div class=statement>You struggle with deadlines.</div>
    <label><input type=radio name=q value=1></label><label><input type=radio name=q value=2></label><label><input type=radio name=q value=3></label></div>''')
    question = browser.snapshot().questions[0]
    assert [o.label for o in question.options] == ['1','2','3']
    assert workstyle_answer(question) is None


def test_numeric_accessible_suffixes_do_not_hide_an_explicit_visual_scale(browser):
    numeric_scale(browser)
    browser.page.locator('input').evaluate_all("els=>els.forEach((el,i)=>el.setAttribute('aria-label','Agree position '+i))")
    question=browser.snapshot().questions[0]
    assert question.options[-1].label=='Strongly disagree'
    assert workstyle_answer(question).option_ids==(question.options[-1].id,)
