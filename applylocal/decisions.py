"""Coerce model suggestions to real choices; deterministic best-effort fallback."""
from __future__ import annotations

import re

from .domain import Answer, AssistanceRequired, Question, normalize, validate_answer


SINGLE = {"radio", "select", "combobox", "visual"}
POSITIVE = {"safe": 4, "safety": 4, "secure": 4, "procedure": 3, "procedures": 3,
            "report": 3, "help": 2, "listen": 2, "honest": 3, "honesty": 3,
            "teamwork": 2, "cooperate": 2, "cooperative": 2, "respect": 2,
            "respectful": 2, "calm": 2, "reliable": 2, "punctual": 2,
            "learn": 2, "learning": 2, "friendly": 2, "friends": 1}
NEGATIVE = {"ignore": -5, "steal": -6, "stealing": -6, "lie": -5, "lying": -5,
            "cheat": -5, "cheating": -5, "hide": -3, "shout": -4, "yell": -4,
            "unsafe": -5, "reckless": -4, "insult": -5, "blame": -3,
            "angry": -3, "temper": -3, "dishonest": -5}
NEGATION = {"not", "never", "don't", "cannot", "can't", "rarely", "without", "avoid", "avoiding"}


def professional_score(text: str) -> int:
    words = re.findall(r"[a-z]+(?:'[a-z]+)?", normalize(text))
    score = 0
    behavior = 0
    for i, word in enumerate(words):
        weight = POSITIVE.get(word, NEGATIVE.get(word, 0))
        if NEGATION.intersection(words[max(0, i-3):i]):
            weight *= -1
        score += weight
        if word in NEGATIVE:
            behavior += weight
    if "run through" in normalize(text):
        score -= 5
    # A harmful verb must not become favorable merely because its object is
    # "safety procedures"; "never ignore safety" reverses that verb once.
    return behavior if behavior else score


def agreement_level(text: str) -> int | None:
    text = normalize(text)
    if re.search(r"\b(?:not sure|neutral|neither|undecided)\b", text):
        return 0
    if re.search(r"\b(?:disagree|no|false)\b", text):
        sign = -1
    elif re.search(r"\b(?:agree|yes|true)\b", text):
        sign = 1
    else:
        return None
    strength = 3 if "strongly" in text else 2 if "moderately" in text else 1
    return sign * strength


def fallback_answer(q: Question, preferred_ids=()) -> Answer:
    from .workstyle import agreement_scale, workstyle_answer
    recognized = workstyle_answer(q)
    if recognized and (not preferred_ids or recognized.option_ids[0] in preferred_ids):
        return recognized
    options = [o for o in q.options if not o.disabled
               and (not preferred_ids or o.id in preferred_ids)]
    if not options:
        raise AssistanceRequired("Waiting for an enabled choice to become available.")
    scale = agreement_scale(q)
    if scale is not None:
        # An unrecognized statement has no justified positive direction. A
        # neutral fallback is preferable to repeating agreement on negative items.
        chosen = min(options, key=lambda option: abs(scale[option.id]))
    else:
        chosen = max(options, key=lambda option: professional_score(option.label))
    answer = Answer((chosen.id,), source="fallback")
    validate_answer(q, answer)
    return answer


def choice_schema(q: Question) -> dict:
    indexes = [i for i, o in enumerate(q.options) if not o.disabled]
    return {"type": "object", "additionalProperties": False, "properties": {
        "choice_indices": {"type": "array", "items": {"type": "integer", "enum": indexes},
                           "minItems": 1 if q.kind in SINGLE or q.required else 0,
                           "maxItems": 1 if q.kind in SINGLE else len(indexes),
                           "uniqueItems": True}}, "required": ["choice_indices"]}


def repair_choice_json(raw, options: list[dict], *, single: bool, required: bool) -> dict:
    """Accept indices, exact DOM IDs or exact labels; discard irrelevant text fields.

    No guessed ID can reach the browser. Indexes always map through the current
    observed list, and duplicate/disabled suggestions are removed.
    """
    enabled = [o for o in options if not o.get("disabled")]
    found = []

    def resolve(value):
        if isinstance(value, bool):
            return None
        if isinstance(value, int):
            return value if any(o["index"] == value for o in enabled) else None
        if not isinstance(value, str):
            return None
        text = normalize(value)
        exact = [o["index"] for o in enabled
                 if value == o.get("id") or text == normalize(o["label"])]
        if len(exact) == 1:
            return exact[0]
        if text.isdigit():
            return resolve(int(text))
        numbered = re.fullmatch(r"(?:option|choice)\s*([1-9][0-9]*)", text)
        if numbered:
            return resolve(int(numbered[1]) - 1)
        return None

    if isinstance(raw, dict):
        fields = [raw.get(key) for key in ("choice_indices", "choice_index", "option_ids",
                  "selected_options", "selected", "answer", "value") if raw.get(key) is not None]
    else:
        fields = [raw]
    for field in fields:
        values = field if isinstance(field, list) else [field]
        for value in values:
            index = resolve(value)
            if index is not None and index not in found:
                found.append(index)
        if found:
            break
    if single:
        found = found[:1]
    if not found and (single or required):
        raise AssistanceRequired("The model did not identify an available choice.")
    return {"choice_indices": found}


def normalize_model_answer(q: Question, answer: Answer) -> Answer:
    if not q.options:
        validate_answer(q, answer)
        return answer
    raw = {"option_ids": list(answer.option_ids), "value": answer.value}
    repaired = repair_choice_json(raw, [{"index": i, "id": o.id, "label": o.label,
                                        "disabled": o.disabled} for i, o in enumerate(q.options)],
                                 single=q.kind in SINGLE, required=q.required)
    result = Answer(tuple(q.options[i].id for i in repaired["choice_indices"]), source=answer.source)
    validate_answer(q, result)
    return result
