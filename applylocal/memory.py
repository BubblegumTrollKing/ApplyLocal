"""Fast, local answer retrieval. Models handle less exact paraphrases in one call."""
from __future__ import annotations

import json
import re

from .domain import Answer, AssistanceRequired, Option, Question, normalize, validate_answer
from .policy import requires_personal_answer


STOP = set("a an the i me my you your we our it is am are be being do does did to of as in on for at and or with much how what which would should that this very really".split())
SYNONYMS = {
    "enjoy": "prefer", "enjoys": "prefer", "like": "prefer", "likes": "prefer",
    "love": "prefer", "prefers": "prefer", "working": "work",
    "reliable": "dependable", "reliability": "dependable",
    "punctual": "ontime", "punctuality": "ontime",
    "traditional": "traditional", "conventional": "traditional",
    "adaptability": "adaptable", "flexible": "adaptable", "flexibility": "adaptable",
    "honesty": "honest", "truthful": "honest",
    "calmness": "calm", "patient": "calm",
    "never": "not", "don't": "not", "cannot": "not", "can't": "not",
}

TOPICS = [
    {"traditional", "tradition", "change", "adaptable", "innovation", "innovative"},
    {"teamwork", "independent", "independently", "alone", "solo"},
    {"feedback", "criticism", "learning", "learn", "improve", "improvement"},
    {"honest", "integrity", "truth", "truthful"},
    {"calm", "stress", "pressure", "angry", "anger", "temper"},
]


def concept_sequence(text: str) -> tuple[str, ...]:
    value = normalize(text).replace("’", "'")
    value = re.sub(r"^(?:question|item)\s*\d+\s*(?:of\s*\d+|/\s*\d+)?\s*[:.]?\s*", "", value)
    value = re.sub(r"\b(?:work(?:ing)? (?:as part of a|in a|with a|with my) team|"
                   r"work(?:ing)? with others|collaborat\w*|cooperat\w*|teamwork)\b", "teamwork", value)
    value = re.sub(r"\bon time\b", "ontime", value)
    value = re.sub(r"\b(?:isn't|aren't|wasn't|wouldn't|shouldn't|doesn't|didn't)\b", "not", value)
    return tuple(SYNONYMS.get(t, t) for t in re.findall(r"[a-z0-9]+(?:'[a-z]+)?", value)
                 if t not in STOP)


def concepts(text: str) -> frozenset[str]:
    return frozenset(concept_sequence(text))


def choice_meaning(text: str) -> str:
    value = normalize(text)
    return {"yes": "affirm", "true": "affirm", "agree": "affirm",
            "no": "deny", "false": "deny", "disagree": "deny"}.get(value, value)


def records(answers: dict):
    for key, selected in reversed(list(answers.items())):
        try:
            prompt, kind, options, context = json.loads(key)
            if (not all(isinstance(v, str) for v in (prompt, kind, context))
                    or not isinstance(options, list) or not all(isinstance(o, str) for o in options)):
                continue
            yield {"question": prompt, "type": kind, "options": options,
                   "context": context, "selected": selected}
        except (ValueError, TypeError):
            continue


def professional(record) -> bool:
    # Never turn a remembered biography/commitment into an inferred new fact.
    return not requires_personal_answer(Question("memory", record["question"], record["type"],
               tuple(Option(str(i), label) for i, label in enumerate(record["options"]))))


def factual_key(text: str) -> str:
    """Reuse equivalent supplied facts, never turn a similar fact into a new one."""
    value = normalize(text)
    value = re.sub(r"(?:saturdays? and sundays?|saturdays? & sundays?)", "weekends", value)
    value = re.sub(r"[^a-z ]", "", value)
    available = re.fullmatch(r"(?:are you available (?:on |to work )?|can you work (?:on )?)"
                             r"(weekends|weekdays|evenings|nights|holidays)", value)
    if available:
        return "available:" + available[1]
    industry = r"(retail|sales|customer service|hospitality|warehouse|manufacturing|management)"
    experience = re.fullmatch(r"(?:have you (?:ever )?worked in |do you have (?:any )?"
                              r"experience (?:working )?in )" + industry, value)
    experience = experience or re.fullmatch(r"do you have (?:any )?" + industry + r" experience", value)
    if experience:
        return "experience:" + experience[1]
    if re.fullmatch(r"have you (?:ever )?been (?:fired|dismissed)(?: from (?:a |your )?job)?", value):
        return "past-dismissal"
    return ""


def fast_recall(q: Question, answers: dict) -> Answer | None:
    if not q.options:
        return None
    factual = requires_personal_answer(q)
    fact_key = factual_key(q.prompt) if factual else ""
    if factual and not fact_key:
        return None
    target = concept_sequence(q.prompt)
    if not target:
        return None
    labels = [choice_meaning(o.label) for o in q.options]
    if len(set(labels)) != len(labels):
        return None
    for record in records(answers):
        same_topic = (factual_key(record["question"]) == fact_key if factual else
                      professional(record) and concept_sequence(record["question"]) == target)
        if (not same_topic
                or concept_sequence(record["context"]) != concept_sequence(q.context)
                or set(map(choice_meaning, record["options"])) != set(labels)):
            continue
        ids = tuple(o.id for o in q.options
                    if choice_meaning(o.label) in set(map(choice_meaning, record["selected"])))
        answer = Answer(ids, source="memory")
        try:
            validate_answer(q, answer)
            return answer
        except AssistanceRequired:
            continue
    return None


def relevant_memories(q: Question, answers: dict, limit: int = 6) -> list[dict]:
    target = concepts(q.prompt + " " + q.context)
    def topics(tokens):
        return {f"topic:{i}" for i, group in enumerate(TOPICS) if group & tokens}
    target = target | topics(target)
    ranked = []
    for index, record in enumerate(records(answers)):
        if not record["options"] or not professional(record):
            continue
        tokens = concepts(record["question"] + " " + record["context"])
        tokens = tokens | topics(tokens)
        overlap = len(target & tokens) / max(1, len(target | tokens))
        if overlap:
            ranked.append((overlap, -index, record))
    ranked.sort(key=lambda item: (item[0], item[1]), reverse=True)
    # Bound the prompt as well as the number of memories; retrieval is local and
    # does not need another AI/embedding model, network request, or model call.
    result, size = [], 0
    for _, _, record in ranked[:limit]:
        size += len(json.dumps(record))
        if size > 5000:
            break
        result.append(record)
    return result
