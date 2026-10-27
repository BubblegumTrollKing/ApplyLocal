import pytest

pytestmark = pytest.mark.browser


def test_loading_button_is_not_mistaken_for_a_new_page(browser):
    browser.page.set_content('''<button onclick="this.textContent='Loading…';setTimeout(()=>{document.body.innerHTML='<label>Email address<input></label><button>Next</button>'},500)">Next</button>''')
    snap = browser.snapshot()
    after = browser.navigate(snap, snap.buttons[0], timeout=2)
    assert len(after.questions) == 1
    assert after.questions[0].prompt == "Email address"
