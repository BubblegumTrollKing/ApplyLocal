from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
import re
import shutil
import subprocess
import sys
import threading
import time
from importlib.resources import files

from playwright.sync_api import Error as PlaywrightError, sync_playwright

from .domain import (Answer, AssistanceRequired, Button, NavigationUnconfirmed, Option,
                     Question, RecheckRequired, Snapshot, check_stop, validate_answer)
from .domain import digest
from .browser_choice import local_browser_endpoint
from .policy import page_restriction


NEXT = re.compile(r"^(?:next(?:\s+(?:page|question|step))?|continue|save\s*(?:&|and)\s*continue|proceed|start(?: assessment| questionnaire)?)(?:\s*[›»→>])?$", re.I)
FINAL = re.compile(r"^(?:submit(?:\s+(?:application|assessment|answers|responses|questionnaire))?|finish|complete(?: assessment| questionnaire)?|done)(?:\s*[›»→>])?$", re.I)
COMPLETE = re.compile(r"(?:your (?:application|assessment|responses|answers) (?:has|have) been (?:successfully )?submitted|"
                      r"(?:assessment|questionnaire) (?:is )?complete|"
                      r"thank you for (?:completing|submitting)(?: (?:the |your )?(?:application|assessment|questionnaire|responses|answers))?|"
                      r"submission (?:was )?(?:successful|received))[.!]?", re.I)


def resource_text(name: str) -> str:
    return files("applylocal").joinpath("resources", name).read_text(encoding="utf-8")


@dataclass
class NavigationWatch:
    before: Snapshot
    button: Button
    network_seen: bool = False
    retried: bool = False
    candidate: str = ""
    stable_since: float = 0


def find_browser() -> str:
    candidates = []
    if sys.platform == "win32":
        for key in ("PROGRAMFILES(X86)", "PROGRAMFILES", "LOCALAPPDATA"):
            if os.environ.get(key):
                root = Path(os.environ[key])
                candidates.extend([root / "Microsoft/Edge/Application/msedge.exe",
                                   root / "Google/Chrome/Application/chrome.exe"])
    else:
        for name in ("microsoft-edge", "google-chrome", "chromium", "chromium-browser"):
            if path := shutil.which(name):
                candidates.append(Path(path))
    for path in candidates:
        if path.is_file():
            return str(path)
    raise AssistanceRequired("Install Microsoft Edge or Google Chrome, then select Open browser again.")


def launch_browser(profile: Path, port: int = 9222, executable: str | None = None,
                   headless: bool = False) -> subprocess.Popen:
    profile.mkdir(parents=True, exist_ok=True)
    args = [executable or find_browser(), f"--remote-debugging-port={port}",
            "--remote-debugging-address=127.0.0.1", f"--user-data-dir={profile.resolve()}",
            "--no-first-run", "--no-default-browser-check"]
    if headless:
        args += ["--headless=new"]
    args += ["about:blank"]
    return subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)


class BrowserSession:
    """One thread owns every Playwright object. Closing disconnects, leaves tabs open."""

    def __init__(self, stop: threading.Event):
        self.stop = stop
        self.playwright = None
        self.browser = None
        self.page = None
        self._targets = {}
        self._navigation_watch = None
        self._request_listener = None
        self._navigation_attempts = {}

    def connect(self, endpoint: str) -> None:
        check_stop(self.stop)
        self.playwright = sync_playwright().start()
        try:
            self.browser = self.playwright.chromium.connect_over_cdp(local_browser_endpoint(endpoint), timeout=30000)
        except Exception:
            self.close()
            raise AssistanceRequired("Cannot connect. For an existing browser, enable remote debugging and allow its connection prompt; otherwise use Open browser.")

    def close(self) -> None:
        self._end_navigation_watch()
        if self.playwright:
            self.playwright.stop()
            self.playwright = None

    def tabs(self) -> list[dict]:
        tabs = []
        for context in self.browser.contexts:
            for page in context.pages:
                if not page.url.startswith(("https://", "http://", "file://", "about:blank")):
                    continue
                session = context.new_cdp_session(page)
                try:
                    target = session.send("Target.getTargetInfo")["targetInfo"]
                    tabs.append({"id": target["targetId"], "url": page.url, "title": page.title()})
                finally:
                    session.detach()
        return tabs

    def select(self, target_id: str) -> None:
        for context in self.browser.contexts:
            for page in context.pages:
                session = context.new_cdp_session(page)
                try:
                    match = session.send("Target.getTargetInfo")["targetInfo"]["targetId"] == target_id
                finally:
                    session.detach()
                if match:
                    self.page = page
                    page.set_default_timeout(2000)
                    page.set_default_navigation_timeout(5000)
                    return
        raise AssistanceRequired("The selected tab was closed. Refresh tabs and select it again.")

    def _node(self, target: str):
        try:
            frame, local = self._targets[target]
            handle = frame.evaluate_handle("id => window.__applylocal_state?.nodes.get(id) || null", local)
            element = handle.as_element()
            if element is None or not element.evaluate("el => el.isConnected"):
                raise RecheckRequired("The page changed; reading its current controls again.")
            return element
        except (KeyError, PlaywrightError) as exc:
            raise RecheckRequired("The page changed; reading its current controls again.") from exc

    def snapshot(self) -> Snapshot:
        check_stop(self.stop)
        if not self.page or self.page.is_closed():
            raise AssistanceRequired("The assessment tab was closed.")
        self._targets = {}
        questions, buttons, errors, texts, completion_candidates = [], [], [], [], []
        blocked, visual, busy = "", False, False
        markers = []
        for index, frame in enumerate(self.page.frames):
            if frame != self.page.main_frame:
                try:
                    if not frame.frame_element().is_visible():
                        continue
                except PlaywrightError:
                    continue
            try:
                raw = frame.evaluate(resource_text("extract.js"))
            except PlaywrightError as exc:
                raise RecheckRequired("The page is still loading; rechecking automatically.") from exc
            prefix = f"f{index}:"

            def target(local):
                key = prefix + local
                self._targets[key] = (frame, local)
                return key

            texts.append(raw["text"])
            markers.append(raw.get("page_marker", ""))
            busy |= raw.get("busy", False)
            completion_candidates.extend(raw.get("completion_candidates", []))
            for q in raw["questions"]:
                options = tuple(Option(target(o["id"]), o["label"], o["selected"], o["disabled"])
                                for o in q["options"])
                questions.append(Question(target(q["id"]), q["prompt"], q["kind"], options,
                                          q["value"], q["required"], q["sensitive"], q.get("context", ""),
                                          q.get("invalid", False)))
            buttons.extend(Button(target(b["id"]), b["label"], b["disabled"], b["submit"])
                           for b in raw["buttons"])
            errors.extend(raw["errors"])
            if raw["authentication"]:
                blocked = "Complete sign-in, CAPTCHA, or verification directly in the browser."
            visual |= raw["visual"]
        text = "\n".join(texts)
        blocked = page_restriction(text) or blocked
        # Inaccessible custom widgets may have no canvas or ARIA roles at all.
        # Do not silently skip a questionless Next page with visible content.
        if not questions and text and any(NEXT.fullmatch(b.label.strip()) and not b.label.casefold().startswith("start") for b in buttons):
            visual = True
        return Snapshot(self.page.url, self.page.title(), text, questions, buttons, errors,
                        blocked, bool(not questions and any(COMPLETE.fullmatch(t.strip())
                                      for t in completion_candidates + [text])), visual,
                        " | ".join(m for m in markers if m), busy)

    def apply(self, expected: Snapshot, question: Question, answer: Answer) -> Snapshot:
        validate_answer(question, answer)
        latest = self.snapshot()
        current = next((q for q in latest.questions if q.id == question.id), None)
        if latest.blocked or latest.structure != expected.structure or current is None or current != question:
            raise RecheckRequired("The question or its state changed; re-reading before applying the answer.")
        check_stop(self.stop)
        try:
            node = self._node(question.id)
            tag = node.evaluate("el => el.tagName")
            if tag == "SELECT":
                # Values need not be unique. Use option indexes from the live element.
                indexes = []
                for option_id in answer.option_ids:
                    indexes.append(self._node(option_id).evaluate("el => el.index"))
                check_stop(self.stop)
                node.select_option(index=indexes, timeout=2000)
            elif question.kind == "combobox":
                node.click(timeout=2000, no_wait_after=True)
                check_stop(self.stop)
                self._node(answer.option_ids[0]).click(timeout=2000, no_wait_after=True)
            elif question.options:
                for option in question.options:
                    wanted = option.id in answer.option_ids
                    if option.selected == wanted:
                        continue
                    if question.kind == "radio" and not wanted:
                        continue  # Selecting its peer unchecks a native radio automatically.
                    check_stop(self.stop)
                    el = self._node(option.id)
                    native = el.evaluate("el => el.tagName === 'INPUT'")
                    if native:
                        if el.is_visible():
                            el.set_checked(wanted, timeout=2000, no_wait_after=True)
                        else:
                            label_handle = el.evaluate_handle("el => Array.from(el.labels || []).find(label => {const r=label.getBoundingClientRect();return r.width>0&&r.height>0&&getComputedStyle(label).visibility!=='hidden';}) || null")
                            label_element = label_handle.as_element()
                            if label_element is None:
                                raise RecheckRequired("Waiting for a visible label for this choice.")
                            label_element.click(timeout=2000, no_wait_after=True)
                    elif question.kind == "checkbox" or wanted:
                        el.click(timeout=2000, no_wait_after=True)
            else:
                check_stop(self.stop)
                node.fill(answer.value or "", timeout=2000)
                node.dispatch_event("change")
        except PlaywrightError as exc:
            raise RecheckRequired("The control could not be operated; checking for a replaced or temporarily covered control.") from exc
        # Read back live controls, not the model's claimed success.
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            check_stop(self.stop)
            observed = self.snapshot()
            after = next((q for q in observed.questions if q.id == question.id), None)
            if after and after.signature == question.signature:
                if question.options:
                    selected = {o.id for o in after.options if o.selected}
                    if selected == set(answer.option_ids):
                        return observed
                elif after.value == answer.value:
                    return observed
            self.page.wait_for_timeout(80)
        raise RecheckRequired("The answer did not persist or the page changed; checking and recovering the answer.")

    @staticmethod
    def navigation(snapshot: Snapshot) -> tuple[Button | None, bool]:
        next_buttons = [b for b in snapshot.buttons if NEXT.fullmatch(b.label.strip())]
        final_buttons = [b for b in snapshot.buttons if FINAL.fullmatch(b.label.strip())]
        candidates = next_buttons or final_buttons
        if len(candidates) > 1:
            raise RecheckRequired("Several navigation controls match; rechecking after the page settles.")
        return (candidates[0], not bool(next_buttons)) if candidates else (None, False)

    def navigate(self, expected: Snapshot, button: Button, *, timeout: float = 8) -> Snapshot:
        latest = self.snapshot()
        if latest.blocked or latest.structure != expected.structure or latest.questions != expected.questions:
            raise RecheckRequired("The page changed before navigation; rechecking automatically.")
        if any(q.invalid for q in latest.questions):
            raise RecheckRequired("Rechecking the form's current invalid fields before navigation.")
        if button.disabled or latest.busy:
            raise RecheckRequired("Waiting for the page's navigation control to become ready.")
        attempt_key = digest([latest.content_signature, button.label,
                              [(q.value, [o.label for o in q.options if o.selected]) for q in latest.questions]])
        attempts = self._navigation_attempts.get(attempt_key, 0)
        if attempts >= 2:
            raise RecheckRequired("Watching the current page before sending another navigation action.")
        self._navigation_attempts[attempt_key] = attempts + 1
        self._begin_navigation_watch(latest, button)
        check_stop(self.stop)
        try:
            self._node(button.id).click(timeout=2000, no_wait_after=True)
        except PlaywrightError as exc:
            raise NavigationUnconfirmed("Navigation needs an automatic recheck after an interrupted click.") from exc
        after = self.recheck_navigation(timeout=timeout, allow_retry=False)
        if after is not None:
            return after
        raise NavigationUnconfirmed("Navigation was not confirmed; rechecking automatically.")

    def _begin_navigation_watch(self, before, button):
        self._end_navigation_watch()
        self._navigation_watch = NavigationWatch(before, button)

        def request_seen(request):
            if self._navigation_watch and (request.resource_type in {"document", "xhr", "fetch"}
                                           or request.method != "GET"):
                self._navigation_watch.network_seen = True
        self._request_listener = request_seen
        self.page.on("request", request_seen)

    def _end_navigation_watch(self):
        if self._request_listener and self.page:
            self.page.remove_listener("request", self._request_listener)
        self._request_listener = None
        self._navigation_watch = None

    @staticmethod
    def _same_answers(left, right):
        def states(snapshot):
            return [(q.prompt, q.value, [o.label for o in q.options if o.selected])
                    for q in snapshot.questions]
        return states(left) == states(right)

    def recheck_navigation(self, *, timeout: float = 2, allow_retry: bool = True) -> Snapshot | None:
        """Observe late transitions. Retry a local Next once only if no request was seen.

        A Submit is never repeated. A request (even a failed one) means the server
        might have processed the first click, so recovery stays observational.
        """
        watch = self._navigation_watch
        if watch is None:
            return self.snapshot()
        deadline = time.monotonic() + timeout
        unchanged_since = time.monotonic()
        while time.monotonic() < deadline:
            check_stop(self.stop)
            try:
                after = self.snapshot()
                if after.blocked or after.complete:
                    self._end_navigation_watch()
                    return after
                if (not watch.network_seen and any(q.invalid for q in after.questions)
                        and after.content_signature == watch.before.content_signature):
                    self._end_navigation_watch()
                    return after  # Repair this form from a fresh snapshot, not a manual dialog.
                transitioned = after.content_signature != watch.before.content_signature
                if (FINAL.fullmatch(watch.button.label.strip())
                        and after.question_content_signature == watch.before.question_content_signature):
                    transitioned = False
                if transitioned and not after.busy:
                    # Do not accept a blank/loading interstitial as a finished page.
                    ready = bool(after.questions or any(NEXT.fullmatch(b.label.strip())
                                 or FINAL.fullmatch(b.label.strip()) for b in after.buttons if not b.disabled))
                    if ready and after.content_signature != watch.candidate:
                        watch.candidate = after.content_signature
                        watch.stable_since = time.monotonic()
                    elif ready and time.monotonic() - watch.stable_since >= 0.25:
                        self._end_navigation_watch()
                        return after
                    unchanged_since = time.monotonic()
                else:
                    watch.candidate = ""
                    if (allow_retry and not watch.retried and not watch.network_seen
                            and not FINAL.fullmatch(watch.button.label.strip())
                            and not after.busy and self._same_answers(watch.before, after)
                            and time.monotonic() - unchanged_since >= 0.75):
                        current, final = self.navigation(after)
                        if (current and not final and not current.disabled
                                and current.label == watch.button.label
                                and after.content_signature == watch.before.content_signature):
                            watch.retried = True
                            check_stop(self.stop)
                            self._node(current.id).click(timeout=2000, no_wait_after=True)
            except (PlaywrightError, RecheckRequired):
                unchanged_since = time.monotonic()
            self.page.wait_for_timeout(100)
        return None

    def navigate_visual_click(self, expected: Snapshot, button: Button) -> None:
        latest = self.snapshot()
        if latest.blocked or latest.structure != expected.structure:
            raise RecheckRequired("The page changed before visual navigation; rechecking automatically.")
        if button.disabled or latest.busy:
            raise RecheckRequired("Waiting for the visual page's navigation control to become ready.")
        check_stop(self.stop)
        try:
            self._node(button.id).click(timeout=2000, no_wait_after=True)
        except PlaywrightError as exc:
            raise NavigationUnconfirmed("Visual page navigation needs an automatic recheck.") from exc

    def capture(self) -> tuple[bytes, int, int]:
        check_stop(self.stop)
        size = self.page.evaluate("({width: innerWidth, height: innerHeight})")
        return (self.page.screenshot(type="png", full_page=False, scale="css", timeout=3000),
                size["width"], size["height"])

    def click_point(self, x: float, y: float, width: int, height: int) -> None:
        if not (0 <= x < width and 0 <= y < height):
            raise AssistanceRequired("The visual target is outside the browser viewport.")
        check_stop(self.stop)
        self.page.mouse.click(x, y)
        self.page.wait_for_timeout(150)
