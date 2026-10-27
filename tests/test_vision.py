import threading

import pytest

from applylocal.domain import Answer, AssistanceRequired
from applylocal.vision import VisionFallback, READ_SCHEMA


class ScriptedVision:
    def __init__(self, selected=False, restricted=False, wrong_verify=False):
        self.selected = selected
        self.restricted = restricted
        self.wrong_verify = wrong_verify
        self.calls = []

    def structured(self, model, system, payload, schema, image=None):
        self.calls.append((schema, image))
        if schema == READ_SCHEMA:
            return {"prompt": "Which action is safest?", "options": [
                {"label": "Report it", "x": 80, "y": 110, "selected": self.selected},
                {"label": "Ignore it", "x": 80, "y": 170, "selected": False}],
                "restricted": self.restricted, "single_choice": True, "confidence": 0.99}
        return {"prompt": "Which action is safest?", "selected_labels": [] if self.wrong_verify else ["Report it"],
                "restricted": self.restricted, "confidence": 0.99}


def canvas_page(browser):
    browser.page.set_content('''<canvas id="q" width="600" height="250"></canvas><button>Next</button>
    <script>
    const ctx=q.getContext('2d');
    function draw(selected){ctx.clearRect(0,0,600,250);ctx.font='20px sans-serif';ctx.fillText('Which action is safest?',30,40);
    ctx.strokeRect(60,90,24,24);ctx.strokeRect(60,150,24,24);ctx.fillText('Report it',100,110);ctx.fillText('Ignore it',100,170);
    if(selected)ctx.fillRect(65,95,14,14)}
    draw(false);q.onclick=e=>{window.canvasClicked=true;draw(true)};
    </script>''')


@pytest.mark.browser
def test_canvas_fallback_click_and_independent_readback(browser):
    canvas_page(browser)
    ai = ScriptedVision()
    vision = VisionFallback(ai, "local:vision", browser.stop, 0.9)
    assert browser.snapshot().visual
    read = vision.read(browser)
    vision.apply(browser, read, Answer(("v0",)))
    assert browser.page.evaluate("window.canvasClicked") is True
    assert len(ai.calls) == 2
    assert ai.calls[0][1].startswith(b"\x89PNG")


@pytest.mark.browser
def test_visual_readback_failure_does_not_claim_success(browser):
    canvas_page(browser)
    vision = VisionFallback(ScriptedVision(wrong_verify=True), "local:vision", browser.stop, 0.9)
    read = vision.read(browser)
    with pytest.raises(AssistanceRequired, match="could not be verified"):
        vision.apply(browser, read, Answer(("v0",)))


@pytest.mark.browser
def test_screen_change_cancels_visual_click(browser):
    canvas_page(browser)
    vision = VisionFallback(ScriptedVision(), "local:vision", browser.stop, 0.9)
    read = vision.read(browser)
    browser.page.evaluate("document.body.style.background='red'")
    with pytest.raises(AssistanceRequired, match="screen changed"):
        vision.apply(browser, read, Answer(("v0",)))
    assert browser.page.evaluate("!!window.canvasClicked") is False


@pytest.mark.browser
def test_restricted_visual_page_never_clicked(browser):
    canvas_page(browser)
    vision = VisionFallback(ScriptedVision(restricted=True), "local:vision", browser.stop, 0.9)
    with pytest.raises(AssistanceRequired, match="cannot be read reliably"):
        vision.read(browser)
    assert browser.page.evaluate("!!window.canvasClicked") is False


def test_out_of_viewport_visual_target_rejected():
    class BadVision(ScriptedVision):
        def structured(self, *args, **kwargs):
            raw = super().structured(*args, **kwargs)
            raw["options"][0]["x"] = 2000
            return raw
    class Browser:
        def capture(self):
            return b"image", 1000, 700
    with pytest.raises(AssistanceRequired, match="outside"):
        VisionFallback(BadVision(), "local", threading.Event(), 0.9).read(Browser())
