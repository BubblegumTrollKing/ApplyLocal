from __future__ import annotations

from dataclasses import dataclass
import threading
import time
from typing import Callable

from .browser import BrowserSession
from .domain import (Answer, AssistanceRequired, NavigationUnconfirmed, Question,
                     RecheckRequired, Stopped, check_stop, validate_answer)
from .local_ai import LocalAI
from .policy import (can_reason_autonomously, page_restriction, question_restriction,
                     requires_personal_answer)
from .storage import Profile, Settings
from .vision import VisionFallback


@dataclass
class UserReply:
    answer: Answer | None = None
    remember: bool = True
    proceed: bool = False


class Engine:
    def __init__(self, browser: BrowserSession, ai: LocalAI, settings: Settings,
                 profile: Profile, stop: threading.Event, emit: Callable,
                 ask: Callable, save_profile: Callable = lambda: None):
        self.browser, self.ai, self.settings, self.profile = browser, ai, settings, profile
        self.stop, self.emit, self.ask, self.save_profile = stop, emit, ask, save_profile
        self.answered = 0
        self.pages = 1
        self.actions = 0
        self.manual_acknowledgements = set()
        self.verified_states = {}
        self.inflight = Profile()
        self.answer_recoveries = {}
        self.navigation_recovery_seconds = 120

    @staticmethod
    def answer_state(q):
        return (q.value, tuple(o.id for o in q.options if o.selected))

    def event(self, code: str, message: str):
        self.emit({"code": code, "message": message, "answered": self.answered, "pages": self.pages})

    def pause(self, message: str, question: Question | None = None, *, submit=False):
        self.event("paused", message)
        response = self.ask({"message": message, "question": question, "submit": submit})
        check_stop(self.stop)
        return response

    def choose(self, q: Question) -> Answer:
        answer = self.inflight.lookup(q) or self.profile.recall(q)
        if answer:
            self.event("remembered", "Reusing a saved answer without another model call.")
            return answer
        if q.prompt == "Unlabeled question" or not q.prompt.strip():
            raise AssistanceRequired("The question has no dependable accessible label.")
        if q.kind == "combobox" and not q.options:
            raise AssistanceRequired("This dropdown exposes no options. Complete it in the browser.")
        if requires_personal_answer(q):
            raise AssistanceRequired("This question needs an actual personal fact that is not saved yet.")
        if not can_reason_autonomously(q):
            raise AssistanceRequired("This prompt needs your answer; it is not clearly a general question.")
        self.event("reasoning", "Choosing an answer using local AI…")
        return self.ai.decide(self.settings.text_model, q, self.settings.confidence,
                              memories=self.profile.related(q))

    def remember(self, q, answer):
        key = self.profile.key(q)
        previous = self.profile.answers.get(key)
        self.profile.remember(q, answer)
        if self.profile.answers.get(key) != previous:
            self.save_profile()

    def answer_question(self, snapshot, q):
        restriction = question_restriction(q)
        if restriction:
            if q.signature not in self.manual_acknowledgements or not q.answered:
                self.pause(restriction)
                self.manual_acknowledgements.add(q.signature)
                return False
            self.verified_states[q.signature] = self.answer_state(q)
            return True
        if q.answered and self.inflight.lookup(q) is None:
            existing = Answer(tuple(o.id for o in q.options if o.selected),
                              None if q.options else q.value, source="browser")
            self.remember(q, existing)
            self.verified_states[q.signature] = self.answer_state(q)
            return True
        try:
            answer = self.choose(q)
        except AssistanceRequired as exc:
            reply = self.pause(str(exc), q)
            if not reply or reply.answer is None:
                return False
            answer = reply.answer
            validate_answer(q, answer)
        check_stop(self.stop)
        self.event("applying", "Applying and checking an answer…")
        self.inflight.remember(q, answer)
        observed = self.browser.apply(snapshot, q, answer)
        current = next(item for item in observed.questions if item.signature == q.signature)
        self.verified_states[q.signature] = self.answer_state(current)
        self.remember(current, answer)
        self.inflight.answers.pop(self.profile.key(q), None)
        self.actions += 1
        self.answered += 1
        self.event("verified", "Answer verified in the browser.")
        return True

    def run(self):
        seen = set()
        finished_on_page = set()
        navigation_started = None
        navigation_recheck = None
        human_only = False
        rechecks = 0
        try:
            self.event("started", "Reading the selected questionnaire tab…")
            while self.pages <= self.settings.max_pages and self.actions < 1000:
                check_stop(self.stop)
                try:
                    if navigation_started is not None:
                        snapshot = navigation_recheck()
                        if snapshot is None:
                            if time.monotonic() - navigation_started > self.navigation_recovery_seconds:
                                self.event("stalled", "Navigation made no confirmed progress after automatic recovery. Stopped with the browser left open.")
                                return "stalled"
                            continue
                        navigation_started = None
                        self.pages += 1
                        finished_on_page.clear()
                        self.verified_states.clear()
                        rechecks = 0
                        self.event("recovered", "The page transition was detected automatically. Continuing…")
                    else:
                        snapshot = self.browser.snapshot()
                    human_only |= bool(page_restriction(snapshot.text))
                    if human_only:
                        self.pause("This assessment requires human completion. Stop the agent and complete all remaining pages yourself.")
                        continue
                    if snapshot.blocked:
                        self.pause(snapshot.blocked)
                        continue
                    if snapshot.complete:
                        self.event("complete", "The page confirms that the questionnaire is complete.")
                        return "complete"
                    if snapshot.busy:
                        raise RecheckRequired("Waiting for the page to finish loading; rechecking automatically.")
                    changed = [q for q in snapshot.questions if q.signature in finished_on_page
                               and q.signature in self.verified_states
                               and self.answer_state(q) != self.verified_states[q.signature]]
                    if changed:
                        for q in changed:
                            key = self.profile.key(q)
                            self.answer_recoveries[key] = self.answer_recoveries.get(key, 0) + 1
                            if self.answer_recoveries[key] > 2:
                                self.pause("A previously verified answer keeps changing after automatic recovery. Inspect the browser.")
                                self.answer_recoveries[key] = 0
                            answer = self.profile.lookup(q)
                            if answer:
                                self.inflight.remember(q, answer)
                            finished_on_page.discard(q.signature)
                        self.event("rechecking", "Restoring a previously verified answer that the page changed.")
                        continue
                    # A re-render may create new IDs; remembered answers still require re-verification.
                    pending = [q for q in snapshot.questions if q.signature not in finished_on_page]
                    if pending:
                        q = pending[0]
                        if self.answer_question(snapshot, q):
                            finished_on_page.add(q.signature)
                            rechecks = 0
                        continue
                    visual_read = None
                    if snapshot.questions and snapshot.visual:
                        self.pause("This page also contains visual content that may include questions. Check it and navigate manually, then recheck.")
                        finished_on_page.clear()
                        self.verified_states.clear()
                        continue
                    if not snapshot.questions and snapshot.visual:
                        if not self.settings.vision:
                            self.pause("This page needs visual interpretation. Enable local vision or complete it manually.")
                            continue
                        self.event("vision", "Reading the current browser viewport with local vision…")
                        visual = VisionFallback(self.ai, self.settings.vision_model, self.stop,
                                                self.settings.confidence)
                        visual_read = visual.read(self.browser)
                        q = visual_read.question
                        # Selected visual state still must be independently verified if modified.
                        if not q.answered or self.inflight.lookup(q) is not None:
                            try:
                                answer = self.choose(q)
                            except AssistanceRequired as exc:
                                reply = self.pause(str(exc), q)
                                if not reply or reply.answer is None:
                                    continue
                                answer = reply.answer
                                validate_answer(q, answer)
                            self.inflight.remember(q, answer)
                            visual.apply(self.browser, visual_read, answer)
                            self.remember(q, answer)
                            self.inflight.answers.pop(self.profile.key(q), None)
                            self.actions += 1
                            self.answered += 1
                            self.event("verified", "Visual selection verified by a second image read.")
                            # Keep a hash of the selected screen for navigation verification.
                            visual_read = visual.read(self.browser)
                    if snapshot.errors:
                        self.pause("The page reports validation errors. Correct them in the browser, then recheck.")
                        finished_on_page.clear()
                        continue
                    button, final = self.browser.navigation(snapshot)
                    if button is None:
                        raise RecheckRequired("Waiting for a Next or Submit control; rechecking automatically.")
                    if final and not self.settings.auto_submit:
                        reply = self.pause("Answers are filled. Review the browser before submitting.", submit=True)
                        if not reply or not reply.proceed:
                            continue
                    self.event("navigating", "Submitting the page…" if final else "Opening the next page…")
                    before = snapshot.structure
                    try:
                        if visual_read:
                            def navigation_recheck(original=snapshot, reader=visual, read=visual_read):
                                return reader.observe_navigation(self.browser, original, read, timeout=2)
                            after = visual.navigate(self.browser, snapshot, button, visual_read)
                        else:
                            def navigation_recheck():
                                return self.browser.recheck_navigation(timeout=2)
                            after = self.browser.navigate(snapshot, button)
                    except NavigationUnconfirmed:
                        navigation_started = time.monotonic()
                        self.actions += 1
                        self.event("rechecking", "Navigation is taking longer. Rechecking automatically and recovering when safe…")
                        continue
                    self.actions += 1
                    if after.complete:
                        self.event("complete", "The page confirms that the questionnaire is complete.")
                        return "complete"
                    if after.structure in seen and after.structure != before:
                        self.pause("The questionnaire returned to a previous page. Inspect it before continuing.")
                        seen.clear()
                    seen.add(before)
                    self.pages += 1
                    finished_on_page.clear()
                    self.verified_states.clear()
                    rechecks = 0
                except RecheckRequired as exc:
                    rechecks += 1
                    if rechecks <= 8:
                        self.event("rechecking", str(exc))
                        if self.stop.wait(min(0.25 * rechecks, 1)):
                            raise Stopped()
                    else:
                        self.pause("Automatic recovery could not resolve the page: " + str(exc))
                        rechecks = 0
                    finished_on_page.clear()
                except AssistanceRequired as exc:
                    self.pause(str(exc))
                    finished_on_page.clear()
            self.event("limit", "The page/action limit was reached. Inspect the browser before starting again.")
            return "limit"
        except Stopped:
            self.event("stopped", "Stopped. No further browser actions will be started.")
            return "stopped"
