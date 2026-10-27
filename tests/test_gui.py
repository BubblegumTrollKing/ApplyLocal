import os
import sys

import pytest

from applylocal.domain import Option, Question

pytestmark = pytest.mark.skipif(sys.platform != "win32" and not os.environ.get("DISPLAY"),
                                reason="GUI tests need Windows desktop or an X display")


@pytest.fixture(scope="session")
def gui_root(tmp_path_factory):
    # A real desktop process owns one Tk interpreter. Repeatedly creating and
    # destroying interpreters before starting worker threads can let CPython
    # collect a dead Tcl interpreter on the wrong thread.
    patch = pytest.MonkeyPatch()
    patch.setenv("LOCALAPPDATA", str(tmp_path_factory.mktemp("gui-data")))
    from applylocal.gui import Application
    instance = Application()
    instance.update()
    yield instance
    instance.shutdown()
    patch.undo()


@pytest.fixture
def app(gui_root):
    import threading
    import gc
    gui_root.stop_event = threading.Event()
    gui_root.busy(False)
    gui_root.request = None
    for child in gui_root.answer_frame.winfo_children():
        child.destroy()
    gc.collect()  # Release any prior handoff's Tk variables on their owner thread.
    gui_root.update()
    return gui_root


def test_gui_renders_and_stop_remains_available(app):
    assert app.start_button.winfo_ismapped()
    app.busy(True)
    assert str(app.start_button["state"]) == "disabled"
    app.stop()
    assert app.stop_event.is_set()


def test_personal_handoff_sends_only_selected_option(app):
    from tkinter import ttk
    q = Question("q", "Are you available on weekends?", "radio", (Option("yes", "Yes"), Option("no", "No")))
    app.show_request({"message": "Your own answer is required.", "question": q, "submit": False})
    app.update()
    def descendants(widget):
        for child in widget.winfo_children():
            yield child
            yield from descendants(child)
    radios = [w for w in descendants(app.answer_frame) if isinstance(w, ttk.Radiobutton)]
    radios[1].invoke()
    send = next(w for w in descendants(app.answer_frame) if isinstance(w, ttk.Button) and str(w["text"]).startswith("Use this"))
    send.invoke()
    assert app.replies.get_nowait().answer.option_ids == ("no",)
    assert app.request is None


def test_manual_only_handoff_has_no_answer_input(app):
    from tkinter import ttk
    app.show_request({"message": "Complete identity verification manually.", "question": None, "submit": False})
    assert len(app.answer_frame.winfo_children()) == 1
    button = app.answer_frame.winfo_children()[0]
    assert isinstance(button, ttk.Button)
    assert "recheck" in button["text"]


def test_final_review_requires_explicit_submit_button(app):
    app.show_request({"message": "Review before submission", "question": None, "submit": True})
    button = next(w for w in app.answer_frame.winfo_children() if w["text"] == "Submit this questionnaire")
    button.invoke()
    assert app.replies.get_nowait().proceed


def test_gui_worker_fills_and_submits_over_real_cdp(app, chromium):
    import socket
    import time
    from applylocal.storage import Profile
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    owner = chromium.browser_type.launch(headless=True, args=[f"--remote-debugging-port={port}"])
    page = owner.new_page()
    page.set_content('''<title>Worker integration</title><label>Email address<input></label>
    <button onclick="document.body.innerHTML=\'<h1>Assessment complete</h1>\'">Submit</button>''')
    app.settings.endpoint = f"http://127.0.0.1:{port}"
    app.profile = Profile({"email": "real@example.test"})
    app.auto_submit.set(True)
    def until(condition):
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            app.update()
            if condition():
                app.update()
                return
            time.sleep(0.02)
        raise AssertionError("GUI worker timed out: " + app.status.get())
    try:
        app.refresh_tabs()
        until(lambda: bool(app.tabs) and not app.worker.is_alive() and app.messages.empty())
        app.start()
        until(lambda: not app.worker.is_alive() and "questionnaire is complete" in app.status.get())
        assert "questionnaire is complete" in app.status.get()
        assert page.locator("h1").inner_text() == "Assessment complete"
        assert page.context.browser.is_connected()  # Worker left the browser open.
    finally:
        app.stop_event.set()
        owner.close()
