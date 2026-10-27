from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
import json
import re
import threading


class Stopped(Exception):
    """A cooperative stop; must never be retried."""


class AssistanceRequired(Exception):
    """A condition that cannot be resolved dependably without the user."""


def check_stop(stop: threading.Event) -> None:
    if stop.is_set():
        raise Stopped()


def normalize(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().casefold().rstrip(" *:?")


def digest(value: object) -> str:
    return sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


@dataclass(frozen=True)
class Option:
    id: str
    label: str
    selected: bool = False
    disabled: bool = False


@dataclass(frozen=True)
class Question:
    id: str
    prompt: str
    kind: str
    options: tuple[Option, ...] = ()
    value: str = ""
    required: bool = False
    sensitive: bool = False
    context: str = ""

    @property
    def signature(self) -> str:
        return digest([self.id, self.prompt, self.kind, self.context,
                       [(o.id, o.label, o.disabled) for o in self.options]])

    @property
    def answered(self) -> bool:
        return bool(self.value.strip()) if not self.options else any(o.selected for o in self.options)


@dataclass(frozen=True)
class Button:
    id: str
    label: str
    disabled: bool = False
    submit: bool = False


@dataclass
class Snapshot:
    url: str
    title: str
    text: str
    questions: list[Question]
    buttons: list[Button]
    errors: list[str] = field(default_factory=list)
    blocked: str = ""
    complete: bool = False
    visual: bool = False

    @property
    def structure(self) -> str:
        # Timers, answer values, and cosmetic changes are deliberately excluded.
        return digest([self.url, [q.signature for q in self.questions],
                       [(b.id, b.label) for b in self.buttons], self.complete])

    @property
    def content_signature(self) -> str:
        return digest([self.url, [q.signature for q in self.questions], self.complete])


@dataclass(frozen=True)
class Answer:
    option_ids: tuple[str, ...] = ()
    value: str | None = None
    source: str = "model"


def validate_answer(question: Question, answer: Answer) -> None:
    if question.kind in {"radio", "select", "combobox", "visual"}:
        if len(answer.option_ids) != 1:
            raise AssistanceRequired("Choose exactly one option.")
    if question.options:
        ids = [o.id for o in question.options if not o.disabled]
        if len(set(answer.option_ids)) != len(answer.option_ids):
            raise AssistanceRequired("The answer contains duplicate choices.")
        if not set(answer.option_ids) <= set(ids) or answer.value is not None:
            raise AssistanceRequired("The answer does not match the available choices.")
        if question.required and not answer.option_ids:
            raise AssistanceRequired("A required choice is missing.")
    elif answer.option_ids or answer.value is None:
        raise AssistanceRequired("A text answer is required.")
    elif len(answer.value) > 20000:
        raise AssistanceRequired("The text answer is too long.")
