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


def test_manual_only_status_has_no_recheck_button(app):
    from tkinter import ttk
    app.show_request({"message": "Complete identity verification manually.", "question": None, "submit": False})
    assert len(app.answer_frame.winfo_children()) == 1
    button = app.answer_frame.winfo_children()[0]
    assert isinstance(button, ttk.Label)
    assert "automatically" in button["text"]


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


def test_fact_prompt_poll_does_not_rebuild_widgets_or_require_recheck_button(app):
    import queue
    import threading
    import time
    from applylocal.engine import UserReply
    app.messages = queue.Queue()
    app.replies = queue.Queue()
    app._worker_request_id = None
    q = Question('q', 'Email address', 'text')
    request = {'message': 'An actual email is needed', 'question': q, 'submit': False,
               'request_id': q.signature, 'poll_seconds': 0.08}
    def call():
        assert app.ask(request) is None
        assert app.ask(request) is None
    thread = threading.Thread(target=call)
    thread.start()
    while thread.is_alive():
        app.update()
        time.sleep(0.01)
    thread.join()
    assert app.request['request_id'] == q.signature
    app.reply(UserReply())
    assert app.replies.get_nowait().request_id == q.signature


def test_gui_exposes_browser_selection_and_existing_session_mode(app):
    assert 'Google Chrome' in app.browser_picker['values']
    app.browser_name.set('Google Chrome')
    app.connection_mode.set('existing')
    app.persist_settings()
    assert app.settings.browser_name == 'Google Chrome'
    assert app.settings.connection_mode == 'existing'
    app.connection_mode.set('companion')
    app.browser_name.set('Automatic')
    app.persist_settings()


def test_entire_window_scrolls_at_small_size_and_stop_stays_visible(app):
    from types import SimpleNamespace
    app.geometry('660x440')
    app.update()
    canvas = app.scroll_host.canvas
    canvas.yview_moveto(0)
    app.update()
    assert canvas.yview()[1] < 1
    app.scroll_host._wheel(SimpleNamespace(widget=app.scroll_host.content, delta=-1200, num=None))
    app.update()
    assert canvas.yview()[0] > 0
    canvas.yview_moveto(1)
    app.update()
    assert canvas.yview()[1] >= 0.99
    top = app.scroll_host.winfo_rooty()
    bottom = top + app.scroll_host.winfo_height()
    assert top <= app.data_button.winfo_rooty() < bottom
    assert app.stop_button.winfo_ismapped()
    assert app.stop_button.winfo_rooty() + app.stop_button.winfo_height() <= app.winfo_rooty()+app.winfo_height()
    assert app.start_button.winfo_ismapped()
    app.scroll_host._edge(SimpleNamespace(widget=app), 0)
    app.geometry('1000x800')
    app.update()


def test_large_text_and_long_fact_question_remain_scrollable(app):
    import tkinter.font as tkfont
    default = tkfont.nametofont('TkDefaultFont')
    original = default.cget('size')
    try:
        default.configure(size=16)
        app.geometry('700x480')
        question = Question('q', 'A long required factual question. '*12, 'text')
        app.show_request({'message':'A real fact is needed', 'question':question, 'submit':False})
        app.update()
        canvas = app.scroll_host.canvas
        canvas.yview_moveto(1)
        app.update()
        assert canvas.yview()[1] >= 0.99
        assert app.stop_button.winfo_ismapped()
        assert app.stop_button.winfo_rooty()+app.stop_button.winfo_height() <= app.winfo_rooty()+app.winfo_height()
    finally:
        default.configure(size=original)
        app.geometry('1000x800')
        app.update()


def test_wheel_over_empty_log_scrolls_the_window(app):
    from types import SimpleNamespace
    app.geometry('660x440')
    app.log.configure(state='normal')
    app.log.delete('1.0','end')
    app.log.configure(state='disabled')
    app.update()
    canvas=app.scroll_host.canvas
    canvas.yview_moveto(0)
    app.scroll_host._wheel(SimpleNamespace(widget=app.log,delta=-120,num=None))
    app.update()
    assert canvas.yview()[0]>0
    canvas.yview_moveto(0)
    app.geometry('1000x800')
    app.update()


@pytest.mark.parametrize('opener',['edit_profile','advanced'])
def test_profile_and_settings_dialogs_scroll_with_save_always_reachable(app,opener):
    import tkinter as tk
    from tkinter import ttk
    getattr(app,opener)()
    dialog=next(w for w in app.winfo_children() if isinstance(w,tk.Toplevel))
    try:
        dialog.geometry('520x340')
        app.update()
        def descendants(widget):
            for child in widget.winfo_children():
                yield child
                yield from descendants(child)
        save=next(w for w in descendants(dialog) if isinstance(w,ttk.Button) and w['text']=='Save')
        assert save.winfo_rooty()+save.winfo_height()<=dialog.winfo_rooty()+dialog.winfo_height()
        canvas=dialog.scroll_host.canvas
        canvas.yview_moveto(1)
        app.update()
        assert canvas.yview()[1]>=0.99
    finally:
        dialog.destroy()
        app.update()
    assert len(app._applylocal_scroll_surfaces)==1
