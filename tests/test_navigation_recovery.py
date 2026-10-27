import threading

import pytest

from applylocal.domain import NavigationUnconfirmed, Snapshot, Button
from applylocal.engine import Engine
from applylocal.storage import Profile, Settings

pytestmark = pytest.mark.browser


def unconfirmed_click(browser, timeout=0.15):
    snap = browser.snapshot()
    with pytest.raises(NavigationUnconfirmed):
        browser.navigate(snap, snap.buttons[0], timeout=timeout)


def test_late_page_change_is_detected_without_a_second_click(browser):
    browser.page.set_content('''<button onclick="window.clicks=(window.clicks||0)+1;
    setTimeout(()=>document.body.innerHTML='<h1>Assessment complete</h1>',450)">Next</button>''')
    unconfirmed_click(browser)
    assert browser.recheck_navigation(timeout=2).complete
    assert browser.page.evaluate("window.clicks") == 1


def test_no_effect_next_is_retried_once_and_recovers(browser):
    browser.page.set_content('''<button onclick="window.clicks=(window.clicks||0)+1;
    if(window.clicks===2)document.body.innerHTML='<h1>Assessment complete</h1>'">Next</button>''')
    unconfirmed_click(browser)
    assert browser.recheck_navigation(timeout=2).complete
    assert browser.page.evaluate("window.clicks") == 2


def test_no_effect_next_retry_is_bounded(browser):
    browser.page.set_content('<button onclick="window.clicks=(window.clicks||0)+1">Next</button>')
    unconfirmed_click(browser)
    assert browser.recheck_navigation(timeout=1.1) is None
    assert browser.recheck_navigation(timeout=1.1) is None
    assert browser.page.evaluate("window.clicks") == 2


def test_submit_is_never_repeated_even_when_it_has_no_visible_effect(browser):
    browser.page.set_content('<button onclick="window.clicks=(window.clicks||0)+1">Submit</button>')
    unconfirmed_click(browser)
    assert browser.recheck_navigation(timeout=1.1) is None
    assert browser.page.evaluate("window.clicks") == 1


def test_sent_request_prevents_duplicate_next(browser):
    browser.page.route("**/assessment", lambda route: route.fulfill(
        content_type="text/html", body='''<button onclick="window.clicks=(window.clicks||0)+1;fetch('/save',{method:'POST'})">Next</button>'''))
    browser.page.route("**/save", lambda route: route.fulfill(body="ok"))
    browser.page.goto("http://assessment.test/assessment")
    unconfirmed_click(browser)
    assert browser._navigation_watch.network_seen
    assert browser.recheck_navigation(timeout=1.1) is None
    assert browser.page.evaluate("window.clicks") == 1


def test_dom_replacement_with_same_questions_is_not_a_new_page(browser):
    browser.page.set_content('''<label>Email address<input value="true@example.test"></label>
    <button onclick="document.body.innerHTML=document.body.innerHTML">Next</button>''')
    unconfirmed_click(browser)
    assert browser.recheck_navigation(timeout=0.4, allow_retry=False) is None


def test_blank_interstitial_is_not_a_finished_transition(browser):
    browser.page.set_content('''<button onclick="document.body.innerHTML='';
    setTimeout(()=>document.body.innerHTML='<label>Email address<input></label><button>Next</button>',450)">Next</button>''')
    unconfirmed_click(browser)
    after = browser.recheck_navigation(timeout=2)
    assert after.questions[0].prompt == "Email address"


def test_stop_interrupts_automatic_navigation_rechecking(browser):
    from applylocal.domain import Stopped
    browser.page.set_content('<button>Next</button>')
    unconfirmed_click(browser)
    timer = threading.Timer(0.1, browser.stop.set)
    timer.start()
    try:
        with pytest.raises(Stopped):
            browser.recheck_navigation(timeout=10)
    finally:
        timer.join()


def test_unresolved_navigation_stops_after_bounded_observation():
    snap = Snapshot("http://test", "", "", [], [Button("b", "Next")])
    class Browser:
        stop = threading.Event()
        def snapshot(self):
            return snap
        def navigation(self, snapshot):
            return snapshot.buttons[0], False
        def navigate(self, *args):
            raise NavigationUnconfirmed()
        def recheck_navigation(self, **kwargs):
            return None
    browser = Browser()
    engine = Engine(browser, None, Settings(), Profile(), browser.stop, lambda e: None,
                    lambda r: pytest.fail("Recovery must not require a recheck button"))
    engine.navigation_recovery_seconds = 0
    assert engine.run() == "stalled"
