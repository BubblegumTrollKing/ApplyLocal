import pytest

from applylocal.domain import Answer, AssistanceRequired, Stopped

pytestmark = pytest.mark.browser


def test_native_control_extraction_and_readback(browser, fixture_html):
    browser.page.set_content(fixture_html("native.html"))
    snap = browser.snapshot()
    assert [q.kind for q in snap.questions] == ["radio", "text", "select", "checkbox"]
    assert snap.questions[0].prompt == "What should a worker do after spotting a hazard?"
    q = snap.questions[0]
    snap = browser.apply(snap, q, Answer((q.options[1].id,)))
    assert snap.questions[0].options[1].selected
    q = snap.questions[1]
    snap = browser.apply(snap, q, Answer(value="true@example.test"))
    assert snap.questions[1].value == "true@example.test"
    q = snap.questions[2]
    snap = browser.apply(snap, q, Answer((q.options[0].id,)))
    assert browser.page.locator("select").input_value() == "fl"
    q = snap.questions[3]
    snap = browser.apply(snap, q, Answer((q.options[0].id, q.options[2].id)))
    assert [o.label for o in snap.questions[3].options if o.selected] == ["Gloves", "Goggles"]


def test_aria_radio_and_combobox(browser, fixture_html):
    browser.page.set_content(fixture_html("aria.html"))
    snap = browser.snapshot()
    q = snap.questions[0]
    assert q.prompt == "How should a worker respond to a spill?"
    snap = browser.apply(snap, q, Answer((q.options[1].id,)))
    assert snap.questions[0].options[1].selected
    q = snap.questions[1]
    snap = browser.apply(snap, q, Answer((q.options[0].id,)))
    assert snap.questions[1].options[0].selected


def test_open_shadow_dom(browser):
    browser.page.set_content('<div id="host"></div><button>Next</button>')
    browser.page.evaluate("host.attachShadow({mode:'open'}).innerHTML='<label>First name<input></label>'")
    snap = browser.snapshot()
    assert len(snap.questions) == 1
    q = snap.questions[0]
    assert browser.apply(snap, q, Answer(value="Actual name")).questions[0].value == "Actual name"


def test_iframe_controls(browser):
    browser.page.set_content('<iframe srcdoc="&lt;label&gt;Email address&lt;input type=email&gt;&lt;/label&gt;"></iframe>')
    browser.page.wait_for_timeout(150)
    snap = browser.snapshot()
    q = snap.questions[0]
    assert q.id.startswith("f1:")
    assert browser.apply(snap, q, Answer(value="true@example.test")).questions[0].value == "true@example.test"


def test_stale_question_cannot_be_clicked(browser):
    browser.page.set_content('<label>Email address<input></label>')
    snap = browser.snapshot()
    browser.page.locator('label').evaluate("el => el.firstChild.textContent='Password'")
    with pytest.raises(AssistanceRequired, match="changed"):
        browser.apply(snap, snap.questions[0], Answer(value="secret"))
    assert browser.page.locator("input").input_value() == ""


def test_external_edit_is_not_overwritten(browser):
    browser.page.set_content('<label>Email address<input></label>')
    snap = browser.snapshot()
    browser.page.locator('input').fill("useredit@example.test")
    with pytest.raises(AssistanceRequired, match="changed"):
        browser.apply(snap, snap.questions[0], Answer(value="other@example.test"))


def test_rejected_input_detected(browser):
    browser.page.set_content('<label>Email address<input oninput="this.value=\'\'"></label>')
    snap = browser.snapshot()
    with pytest.raises(AssistanceRequired, match="persist"):
        browser.apply(snap, snap.questions[0], Answer(value="true@example.test"))


def test_navigation_timeout_never_reclicks(browser):
    browser.page.set_content('<button onclick="window.clicks=(window.clicks||0)+1">Next</button>')
    snap = browser.snapshot()
    with pytest.raises(AssistanceRequired, match="not confirmed"):
        browser.navigate(snap, snap.buttons[0], timeout=0.3)
    assert browser.page.evaluate("window.clicks") == 1


def test_validation_failure_detected(browser):
    browser.page.set_content('<button onclick="document.body.insertAdjacentHTML(\'beforeend\',\'<p role=alert>Required</p>\')">Next</button>')
    snap = browser.snapshot()
    with pytest.raises(AssistanceRequired, match="validation"):
        browser.navigate(snap, snap.buttons[0], timeout=1)


def test_ambiguous_navigation_pauses(browser):
    browser.page.set_content('<button>Next</button><button>Next</button>')
    with pytest.raises(AssistanceRequired, match="Several"):
        browser.navigation(browser.snapshot())


def test_disabled_options_extracted_and_rejected(browser):
    browser.page.set_content('<fieldset><legend>Choose one</legend><label><input type=radio name=q disabled>Unavailable</label><label><input type=radio name=q>Available</label></fieldset>')
    snap = browser.snapshot()
    # First usable radio still includes its disabled peer, preserving choice semantics.
    q = snap.questions[0]
    assert q.options[0].disabled
    with pytest.raises(AssistanceRequired):
        browser.apply(snap, q, Answer((q.options[0].id,)))


def test_invisible_controls_ignored(browser):
    browser.page.set_content('<label hidden>Trap<input></label><label>Email address<input></label>')
    assert len(browser.snapshot().questions) == 1


def test_page_level_restrictions(browser):
    browser.page.set_content('<p>This is a human-only assessment.</p><label>First name<input></label>')
    assert browser.snapshot().blocked


def test_sign_in_is_not_automated(browser):
    browser.page.set_content('<label>Password<input type="password"></label>')
    assert browser.snapshot().blocked


def test_stop_prevents_mutation(browser):
    browser.page.set_content('<label>Email address<input></label>')
    snap = browser.snapshot()
    browser.stop.set()
    with pytest.raises(Stopped):
        browser.apply(snap, snap.questions[0], Answer(value="never@example.test"))
    assert browser.page.locator("input").input_value() == ""


def test_closed_tab_detected(browser):
    browser.page.close()
    with pytest.raises(AssistanceRequired, match="closed"):
        browser.snapshot()
