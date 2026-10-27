import pytest

pytestmark = pytest.mark.browser


@pytest.mark.parametrize("message", ["Assessment complete", "Your application has been submitted.", "Thank you for completing the questionnaire."])
def test_explicit_completion(browser, message):
    browser.page.set_content(f"<h1>{message}</h1>")
    assert browser.snapshot().complete


@pytest.mark.parametrize("message", ["When the assessment is complete, click Next.", "After your responses have been submitted, you will see a confirmation.", "The screen will say: Assessment complete."])
def test_instruction_mentioning_completion_is_not_success(browser, message):
    browser.page.set_content(f"<p>{message}</p><button>Next</button>")
    snap = browser.snapshot()
    assert not snap.complete
    assert snap.visual  # No exposed controls: cannot silently skip an unknown question.
