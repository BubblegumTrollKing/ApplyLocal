from __future__ import annotations

from dataclasses import dataclass
import threading
import time
from typing import Callable

from .browser import BrowserSession
from .decisions import fallback_answer, normalize_model_answer
from .domain import (Answer, AssistanceRequired, NavigationUnconfirmed, PersonalFactRequired,
                     Question, RecheckRequired, Stopped, check_stop, validate_answer)
from .local_ai import LocalAI
from .policy import (can_reason_autonomously, page_restriction, question_restriction,
                     requires_personal_answer)
from .storage import Profile, Settings
from .vision import VisionFallback
from .workstyle import contradicts_workstyle, workstyle_answer


@dataclass
class UserReply:
    answer: Answer | None = None
    remember: bool = True
    proceed: bool = False
    request_id: str = ""


class Engine:
    def __init__(self, browser: BrowserSession, ai: LocalAI, settings: Settings,
                 profile: Profile, stop: threading.Event, emit: Callable,
                 ask: Callable, save_profile: Callable = lambda: None):
        self.browser, self.ai, self.settings, self.profile = browser, ai, settings, profile
        self.stop, self.emit, self.ask, self.save_profile = stop, emit, ask, save_profile
        self.answered, self.pages, self.actions = 0, 1, 0
        self.manual_states = {}
        self.manual_acknowledgements = set()
        self.verified_states = {}
        self.inflight = Profile()
        self.answer_recoveries = {}
        self.wait_key, self.wait_time = "", 0.0
        self.request_id = ""

    @staticmethod
    def answer_state(q):
        return (q.value, tuple(o.id for o in q.options if o.selected))

    def event(self, code: str, message: str, **details):
        self.emit({"code": code, "message": message, "answered": self.answered,
                   "pages": self.pages, **details})

    def wait(self, message: str, key: str = "", delay: float = 0.25):
        key = key or message
        now = time.monotonic()
        if key != self.wait_key or now - self.wait_time >= 5:
            self.event("rechecking", message)
            self.wait_key, self.wait_time = key, now
        if self.stop.wait(delay):
            raise Stopped()

    def pause(self, message: str, question: Question | None = None, *, submit=False):
        # Reserved for a real missing fact or an explicitly enabled final review.
        # A short polling request lets the worker keep observing the browser.
        request_id = question.signature if question else "final-review"
        if self.request_id != request_id:
            self.request_id = request_id
            self.event("paused", message + " The browser is still being rechecked automatically.")
        response = self.ask({"message": message, "question": question, "submit": submit,
                             "request_id": request_id, "poll_seconds": 0.35})
        check_stop(self.stop)
        return response

    def dismiss_request(self):
        if self.request_id:
            self.event("input_resolved", "Continuing automatically…", request_id=self.request_id)
            self.request_id = ""

    def choose(self, q: Question) -> Answer:
        immediate = workstyle_answer(q)
        if immediate:
            self.event("workstyle", "Choosing a professional work-style response immediately.")
            return immediate
        try:
            answer = self.inflight.lookup(q)
        except AssistanceRequired:
            answer = None
            self.inflight.answers.pop(self.profile.key(q), None)
        answer = answer or self.profile.recall(q)
        if answer:
            self.event("remembered", "Reusing a saved answer without another model call.")
            return answer
        if requires_personal_answer(q):
            raise PersonalFactRequired("This question needs an actual personal fact that is not saved yet.")
        if q.prompt == "Unlabeled question" or not q.prompt.strip():
            raise RecheckRequired("Reading the question label again automatically.")
        if not can_reason_autonomously(q):
            raise RecheckRequired("Rechecking the question for enough context to answer.")
        self.event("reasoning", "Choosing the best available answer using local AI…")
        try:
            answer = self.ai.decide(self.settings.text_model, q, self.settings.confidence,
                                    memories=self.profile.related(q))
            answer = normalize_model_answer(q, answer)
        except AssistanceRequired:
            if not q.options:
                raise RecheckRequired("Local text reasoning needs another automatic attempt.") from None
            answer = fallback_answer(q)
        if answer.source == "fallback":
            self.event("fallback", "Using an enabled best-effort choice; no user review is needed.")
        return answer

    def remember(self, q, answer):
        key = self.profile.key(q)
        previous = self.profile.answers.get(key)
        previous_source = self.profile.answer_sources.get(key)
        self.profile.remember(q, answer)
        if self.profile.answers.get(key) != previous or self.profile.answer_sources.get(key) != previous_source:
            try:
                self.save_profile()
            except OSError:
                self.event("memory", "Answers remain available for this run; the local data file could not be written.")

    def answer_question(self, snapshot, q):
        restriction = question_restriction(q)
        if restriction:
            previous = self.manual_states.get(q.signature)
            self.manual_states[q.signature] = q.answered
            if q.signature not in self.manual_acknowledgements:
                if q.answered and previous is False:
                    self.manual_acknowledgements.add(q.signature)
                else:
                    self.wait(restriction + " The agent will detect your browser changes automatically.")
                    return False
            self.verified_states[q.signature] = self.answer_state(q)
            return True
        correction = contradicts_workstyle(q)
        if correction:
            self.event("correcting", "Correcting a work-style response that points against the requested candidate profile.")
        if q.answered and not q.invalid and not correction and self.inflight.lookup(q) is None:
            existing = Answer(tuple(o.id for o in q.options if o.selected),
                              None if q.options else q.value, source="browser")
            self.remember(q, existing)
            self.verified_states[q.signature] = self.answer_state(q)
            self.dismiss_request()
            return True
        try:
            answer = self.choose(q)
        except PersonalFactRequired as exc:
            reply = self.pause(str(exc), q)
            if not reply or reply.answer is None:
                return False
            answer = reply.answer
            validate_answer(q, answer)
        if q.invalid:
            repair_key = (self.profile.key(q), self.answer_state(q))
            tries = self.answer_recoveries.get(repair_key, 0)
            if tries >= 2:
                self.wait("The field still reports a problem. Watching for the browser to accept or update it automatically.")
                return False
            self.answer_recoveries[repair_key] = tries + 1
        check_stop(self.stop)
        self.event("applying", "Applying and checking an answer…")
        self.inflight.remember(q, answer)
        self.actions += 1
        observed = self.browser.apply(snapshot, q, answer)
        current = next(item for item in observed.questions if item.signature == q.signature)
        self.verified_states[q.signature] = self.answer_state(current)
        self.remember(current, answer)
        self.inflight.answers.pop(self.profile.key(q), None)
        self.dismiss_request()
        self.answered += 1
        self.event("verified", "Answer verified in the browser.")
        return True

    def prepare_page(self, pending):
        if not hasattr(self.ai, "decide_many"):
            return
        unknown = [q for q in pending if not q.answered and q.options
                   and not question_restriction(q) and not requires_personal_answer(q)
                   and can_reason_autonomously(q) and workstyle_answer(q) is None
                   and self.profile.recall(q) is None and self.inflight.recall(q) is None][:8]
        if len(unknown) < 2:
            return
        self.event("reasoning", f"Choosing {len(unknown)} unfamiliar responses in one local AI call…")
        answers = self.ai.decide_many(self.settings.text_model, unknown, self.settings.confidence,
                                     memories={q.signature: self.profile.related(q) for q in unknown})
        for q in unknown:
            if q.signature in answers:
                self.inflight.remember(q, normalize_model_answer(q, answers[q.signature]))

    def run(self):
        finished_on_page = set()
        navigation_recheck = None
        navigation_before = None
        human_only = False
        try:
            self.event("started", "Reading the selected questionnaire tab…")
            while self.pages <= self.settings.max_pages and self.actions < 1000:
                check_stop(self.stop)
                try:
                    if navigation_recheck is not None:
                        snapshot = navigation_recheck()
                        if snapshot is None:
                            self.wait("Waiting for navigation; rechecking automatically. Stop remains available.",
                                      "navigation", delay=0.1)
                            continue
                        if snapshot.content_signature != navigation_before.content_signature:
                            self.pages += 1
                        navigation_recheck = None
                        finished_on_page.clear()
                        self.verified_states.clear()
                        self.event("recovered", "The current page was detected automatically. Continuing…")
                    else:
                        snapshot = self.browser.snapshot()
                    if self.request_id and not any(q.signature == self.request_id and not q.answered
                                                   for q in snapshot.questions) and self.request_id != "final-review":
                        self.dismiss_request()
                    human_only |= bool(page_restriction(snapshot.text))
                    if human_only:
                        self.event("restricted", "This assessment requires human completion. The agent has stopped without answering it.")
                        return "human_only"
                    if snapshot.blocked:
                        self.wait(snapshot.blocked + " Changes will be detected automatically.")
                        continue
                    if snapshot.complete:
                        self.dismiss_request()
                        self.event("complete", "The page confirms that the questionnaire is complete.")
                        return "complete"
                    if snapshot.busy:
                        self.wait("Waiting for the page to finish loading; rechecking automatically.")
                        continue
                    changed = [q for q in snapshot.questions if q.signature in finished_on_page
                               and q.signature in self.verified_states
                               and self.answer_state(q) != self.verified_states[q.signature]]
                    if changed:
                        for q in changed:
                            key = self.profile.key(q)
                            self.answer_recoveries[key] = self.answer_recoveries.get(key, 0) + 1
                            if self.answer_recoveries[key] > 2:
                                self.wait("The page keeps changing an answer. Rechecking automatically before another action.")
                                continue
                            answer = self.profile.recall(q)
                            if answer:
                                self.inflight.remember(q, answer)
                            finished_on_page.discard(q.signature)
                        continue
                    pending = [q for q in snapshot.questions if q.signature not in finished_on_page or q.invalid]
                    if pending:
                        q = pending[0]
                        if workstyle_answer(q) is None:
                            self.prepare_page(pending)
                        if self.answer_question(snapshot, q):
                            finished_on_page.add(q.signature)
                        continue
                    visual_read = None
                    if snapshot.questions and snapshot.visual:
                        self.wait("This page includes visual content. Watching and rechecking before navigation.")
                        continue
                    if not snapshot.questions and snapshot.visual:
                        if not self.settings.vision:
                            self.wait("This page needs visual interpretation. Enable local vision or complete it in the browser; changes are detected automatically.")
                            continue
                        self.event("vision", "Reading the current browser viewport with local vision…")
                        visual = VisionFallback(self.ai, self.settings.vision_model, self.stop,
                                                self.settings.confidence)
                        visual_read = visual.read(self.browser)
                        q = visual_read.question
                        if not q.answered or self.inflight.lookup(q) is not None:
                            try:
                                answer = self.choose(q)
                            except PersonalFactRequired as exc:
                                reply = self.pause(str(exc), q)
                                if not reply or reply.answer is None:
                                    continue
                                answer = reply.answer
                                validate_answer(q, answer)
                            self.inflight.remember(q, answer)
                            self.actions += 1
                            visual.apply(self.browser, visual_read, answer)
                            self.remember(q, answer)
                            self.inflight.answers.pop(self.profile.key(q), None)
                            self.answered += 1
                            self.event("verified", "Visual selection verified by a second image read.")
                            visual_read = visual.read(self.browser)
                    # Error banners may belong to the old page, or lag behind a
                    # valid control state. Current invalid fields are repaired above.
                    # They never open a manual operational-error/recheck dialog.
                    button, final = self.browser.navigation(snapshot)
                    if button is None:
                        raise RecheckRequired("Waiting for a Next or Submit control; rechecking automatically.")
                    if final and not self.settings.auto_submit:
                        reply = self.pause("Answers are filled. Review the browser before submitting.", submit=True)
                        if not reply or not reply.proceed:
                            continue
                        self.dismiss_request()
                    self.event("navigating", "Submitting the page…" if final else "Opening the next page…")
                    navigation_before = snapshot
                    try:
                        if visual_read:
                            def watch(original=snapshot, reader=visual, read=visual_read):
                                return reader.observe_navigation(self.browser, original, read, timeout=1)
                            after = visual.navigate(self.browser, snapshot, button, visual_read)
                        else:
                            def watch():
                                return self.browser.recheck_navigation(timeout=1)
                            after = self.browser.navigate(snapshot, button)
                    except NavigationUnconfirmed:
                        navigation_recheck = watch
                        self.actions += 1
                        self.event("rechecking", "Navigation is taking longer. Rechecking automatically and recovering when safe…")
                        continue
                    self.actions += 1
                    if after.complete:
                        self.event("complete", "The page confirms that the questionnaire is complete.")
                        return "complete"
                    if after.content_signature != snapshot.content_signature:
                        self.pages += 1
                    finished_on_page.clear()
                    self.verified_states.clear()
                except AssistanceRequired as exc:
                    self.wait(str(exc) + " Rechecking automatically.")
                    finished_on_page.clear()
            self.event("limit", "The page/action limit was reached. The browser remains open.")
            return "limit"
        except Stopped:
            self.event("stopped", "Stopped. No further browser actions will be started.")
            return "stopped"
