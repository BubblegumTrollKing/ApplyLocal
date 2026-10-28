from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import tempfile
import threading
import time


def self_test(gui: bool = False, browser: bool = False) -> dict:
    import tkinter
    from playwright._impl._driver import compute_driver_executable
    from .browser import BrowserSession, launch_browser, resource_text
    from .storage import Profile
    assert "questions" in resource_text("extract.js")
    assert "Practice questionnaire" in resource_text("practice.html")
    assert tkinter.Tcl().eval("expr {2 + 2}") == "4"
    driver, cli = compute_driver_executable()
    assert Path(driver).is_file() and Path(cli).is_file()
    assert not Profile().facts
    from .domain import Option, Question
    from .workstyle import workstyle_answer
    labels = ('Strongly agree', 'Moderately agree', 'Agree', 'Neither agree nor disagree',
              'Disagree', 'Moderately disagree', 'Strongly disagree')
    prompts = ('You enjoy exploring unfamiliar ideas and viewpoints.',
               'You are not easily swayed by emotional arguments.', 'You struggle with deadlines.')
    selections = [workstyle_answer(Question('q', prompt, 'radio',
                  tuple(Option(str(i), text) for i, text in enumerate(labels)))).option_ids
                  for prompt in prompts]
    assert selections == [('1',), ('1',), ('6',)]
    result = {"status": "passed", "python": sys.version.split()[0],
              "resources": True, "tkinter_tcl": True, "playwright_driver": True,
              "workstyle_polarity": True}
    if gui:
        from .gui import Application
        app = Application()
        app.update()
        assert app.start_button.winfo_exists()
        app.geometry('660x440')
        app.update()
        app.scroll_host.canvas.yview_moveto(1)
        app.update()
        assert app.scroll_host.canvas.yview()[1] >= 0.99
        assert app.stop_button.winfo_ismapped()
        assert app.stop_button.winfo_rooty()+app.stop_button.winfo_height() <= app.winfo_rooty()+app.winfo_height()
        result['window_scroll'] = True
        result['stop_button_visible'] = True
        app.after(100, app.shutdown)
        app.mainloop()
        result["gui_window"] = True
    if browser:
        import socket
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        with tempfile.TemporaryDirectory(prefix="applylocal-smoke-") as directory:
            proc = launch_browser(Path(directory), port, headless=True)
            session = BrowserSession(threading.Event())
            try:
                deadline = time.monotonic() + 15
                while time.monotonic() < deadline:
                    try:
                        session.connect(f"http://127.0.0.1:{port}")
                        break
                    except Exception:
                        time.sleep(0.3)
                else:
                    raise RuntimeError("Browser did not start")
                tabs = session.tabs()
                assert tabs
                session.select(tabs[0]["id"])
                session.page.set_content('<label>Email<input type="email"></label>')
                assert session.snapshot().questions[0].prompt == "Email"
                # This browser was created solely for the smoke test.
                session.browser.close()
                result["chromium_cdp"] = True
            finally:
                session.close()
                if proc.poll() is None:
                    proc.terminate()
                proc.wait(timeout=5)
    return result


def main():
    parser = argparse.ArgumentParser(description="ApplyLocal local questionnaire assistant")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--gui-smoke", action="store_true")
    parser.add_argument("--smoke-browser", action="store_true")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    if args.self_test or args.gui_smoke or args.smoke_browser:
        try:
            result = self_test(args.gui_smoke, args.smoke_browser)
            exit_code = 0
        except Exception as exc:
            result = {"status": "failed", "error": str(exc), "type": type(exc).__name__}
            exit_code = 1
        if args.report:
            args.report.write_text(json.dumps(result, indent=2), encoding="utf-8")
        if sys.stdout:
            print(json.dumps(result))
        raise SystemExit(exit_code)
    from .gui import Application
    Application().mainloop()


if __name__ == "__main__":
    main()
