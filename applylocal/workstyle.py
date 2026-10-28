"""Immediate, polarity-aware professional work-style decisions.

Only interpretable agreement scales and clear statements use this path. Conflicting
clauses and unfamiliar meanings go to the local model instead of blanket agreement.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from .domain import Answer, Question, normalize, validate_answer
from .policy import page_restriction, question_restriction, requires_personal_answer


@dataclass(frozen=True)
class Judgment:
    target: float
    trait: str


# Strength varies by the behavior, not the position of a control. Clear reliability
# and integrity failures use a stronger response than ordinary social preferences.
RULES = [
    ("reliability", -3, r"\bstruggl\w*\s+(?:with|to meet|meeting)\s+(?:(?:your|my|tight|work)\s+)?(?:deadlines?|due dates?|time management)\b"),
    ("reliability", -3, r"\b(?:miss|misses|missing|ignore|ignores|ignoring)\s+(?:(?:your|my|work|important)\s+)?(?:deadlines?|due dates?|commitments?)\b"),
    ("reliability", 3, r"\b(?:meet|meets|meeting|keep|keeps|honou?r|honou?rs)\s+(?:(?:your|my|all|tight|work|important)\s+)?(?:deadlines?|due dates?|commitments?|promises)\b"),
    ("reliability", 3, r"\b(?:finish|finishes|complete|completes|deliver|delivers)\b.{0,35}\b(?:on time|ahead of schedule|before (?:the )?deadline)\b"),
    ("organization", -2, r"\b(?:procrastinat\w*|disorgani[sz]ed|put(?:ting)? off (?:important )?(?:tasks|work)|leave.{0,25}(?:last minute|unfinished))\b"),
    ("organization", 2, r"\b(?:am|are|being|stay|staying|keep|keeping|remain|remaining)\s+(?:(?:not|never|usually|well|highly|quite|very|rarely|seldom|always|particularly|fairly)\s+){0,3}(?P<behavior>organi[sz]ed)\b"),
    ("organization", 2, r"\b(?:plan(?:ning)? ahead|plan (?:your|my) (?:work|day|tasks)|prioriti[sz]e\w* (?:your|my|important) (?:work|tasks))\b"),
    ("care", -3, r"\b(?:careless|overlook\w* (?:important )?details|make careless mistakes|rush through.{0,20}without checking)\b"),
    ("care", 3, r"\b(?:pay(?:ing)? (?:close )?attention to detail|check\w* (?:your|my) work|careful about details|follow through)\b"),
    ("openness", 2, r"\b(?:enjoy|enjoys|like|likes|welcome|welcomes|explor\w*|open to|curious about)\b.{0,45}\b(?:new|unfamiliar|different)\b.{0,30}\b(?:ideas|viewpoints|perspectives|approaches|skills|experiences)\b"),
    ("openness", -2, r"\b(?:reject|rejects|avoid|avoids|dismiss|dismisses)\b.{0,20}\b(?:new ideas|different viewpoints|learning new skills)\b"),
    ("judgment", -2, r"\b(?:swayed|persuaded)\s+by\s+(?:purely )?emotional arguments\b"),
    ("judgment", 2, r"\b(?:consider|considers|use|uses|weigh|weighs|rely on)\b.{0,25}\b(?:facts|evidence|logic)\b"),
    ("judgment", -2, r"\b(?:rely|relies)\s+(?:only|entirely)\s+on\s+(?:feelings|gut feelings|emotions)\b"),
    ("sociability", 1, r"\b(?:make|makes|making)\s+(?:new\s+)?friends\b|\b(?:friendly|approachable)\b"),
    ("sociability", 1, r"\b(?:enjoy|like|start)\b.{0,20}\b(?:conversations|meeting new people|social gatherings)\b"),
    ("teamwork", 2, r"\b(?:enjoy|like|prefer|value)\b.{0,25}\b(?:teamwork|collaborat\w*|working (?:with others|in a team|as part of a team))\b"),
    ("teamwork", -2, r"\b(?:dislike|hate|avoid)\b.{0,20}\b(?:teamwork|collaborat\w*|working with others)\b"),
    ("teamwork", 2, r"\b(?:cooperate|cooperative|help(?:ing)? (?:your|my|a)?\s*(?:coworkers?|colleagues?|teammates?))\b"),
    ("respect", 2, r"\b(?:treat|treating)\b.{0,25}\b(?:respect|courtesy)\b|\brespect(?:ful of)? (?:others|coworkers|customers)\b"),
    ("respect", -3, r"\b(?:rude|disrespectful|insult\w*|blame others|take credit for (?:others|other people))\b"),
    ("integrity", 3, r"\b(?:honest|honesty|truthful|integrity|admit\w* (?:your|my)?\s*(?:mistakes|errors)|take responsibility)\b"),
    ("integrity", -3, r"\b(?:lie|lying|dishonest|steal|stealing|cheat|cheating|conceal\w* (?:your|my)?\s*mistakes)\b"),
    ("composure", 2, r"\b(?:remain|remains|stay|stays|keep|keeps)\s+(?:very )?(?:calm|composed|patient)\b"),
    ("composure", -2, r"\b(?:lose|losing)\s+(?:your|my)?\s*temper\b|\b(?:get angry|easily upset|easily overwhelmed)\b"),
    ("feedback", 2, r"\b(?:welcome|accept|seek|value|learn from|open to|receptive to)\b.{0,25}\b(?:feedback|constructive criticism|suggestions)\b"),
    ("feedback", -2, r"\b(?:resent|ignore|reject|defensive about)\b.{0,20}\b(?:feedback|criticism)\b"),
    ("safety", 3, r"\b(?:follow|following|respect|comply with)\b.{0,20}\b(?:safety|procedures|rules)\b|\breport\w*\s+(?:hazards|unsafe conditions)\b"),
    ("safety", -3, r"\bignore\w*\s+(?:the )?(?:safety|procedures|rules)\b|\bcut corners\b"),
]
COMPILED = [(trait, target, re.compile(pattern, re.I)) for trait, target, pattern in RULES]
NEGATORS = {"not", "never", "rarely", "seldom", "hardly", "don't", "doesn't", "isn't",
            "aren't", "can't", "cannot", "wouldn't", "won't", "couldn't", "without"}
NEGATORS |= {"dislike", "hate", "avoid", "avoiding", "refuse", "refusing"}


def agreement_strength(label: str) -> float | None:
    text = normalize(label)
    if re.search(r"\b(?:not sure|neutral|neither|undecided)\b", text):
        return 0
    if re.search(r"\bdisagree\b|^(?:no|false)$", text):
        sign = -1
    elif re.search(r"\bagree\b|^(?:yes|true)$", text):
        sign = 1
    else:
        return None
    strength = (3 if re.search(r"\b(?:strongly|completely|totally|absolutely)\b", text) else
                2 if "moderately" in text else 0.5 if "slightly" in text else
                1 if re.search(r"\b(?:somewhat|rather|tend)\b", text) else 1.5)
    return sign * strength


def agreement_scale(q: Question) -> dict[str, float] | None:
    options = [o for o in q.options if not o.disabled]
    raw = {o.id: agreement_strength(o.label) for o in options}
    if len(options) < 2 or any(v is None for v in raw.values()):
        return None
    if len(set(raw.values())) != len(raw) or not any(v > 0 for v in raw.values()) or not any(v < 0 for v in raw.values()):
        return None
    result = {key: 0.0 for key, v in raw.items() if v == 0}
    for sign in (-1, 1):
        side = sorted(((key, abs(v)) for key, v in raw.items() if v * sign > 0), key=lambda p: p[1])
        for rank, (key, _) in enumerate(side, 1):
            result[key] = sign * (1.5 if len(side) == 1 else 3 * rank / len(side))
    return result


def judge_statement(text: str) -> Judgment | None:
    text = normalize(text).replace("’", "'")
    if re.search(r"\b(?:wish|unless|rather than|instead of|as opposed to)\b|"
                 r"\bprefer\b.{0,60}\b(?:over|rather than|to)\b", text):
        return None
    found = []
    for trait, target, pattern in COMPILED:
        for match in pattern.finditer(text):
            offset = match.start('behavior') if 'behavior' in pattern.groupindex else match.start()
            prefix = re.split(r"[.!?;,]|\b(?:but|although|however|yet)\b", text[:offset])[-1]
            prefix = re.sub(r"\bnot (?:only|just)\b", "", prefix)
            words = re.findall(r"[a-z]+(?:'[a-z]+)?", prefix)[-5:]
            negations = sum(word in NEGATORS for word in words)
            negations += sum(bool(re.fullmatch(r"struggl\w*|fail\w*|trouble|difficult|hard|lack\w*", word))
                             for word in words)
            found.append(Judgment(-target if negations % 2 else target, trait))
    if not found or len({item.target > 0 for item in found}) > 1:
        return None
    return max(found, key=lambda item: abs(item.target))


def workstyle_answer(q: Question) -> Answer | None:
    if (q.kind not in {"radio", "select", "combobox", "visual"} or not q.options
            or requires_personal_answer(q) or question_restriction(q)
            or page_restriction(q.prompt + " " + q.context)):
        return None
    scale = agreement_scale(q)
    judgment = judge_statement(q.prompt)
    if scale is None or judgment is None:
        return None
    option = min((o for o in q.options if not o.disabled),
                 key=lambda o: abs(scale[o.id] - judgment.target))
    answer = Answer((option.id,), source="workstyle")
    validate_answer(q, answer)
    return answer


def contradicts_workstyle(q: Question) -> bool:
    scale = agreement_scale(q)
    judgment = judge_statement(q.prompt)
    if scale is None or judgment is None or workstyle_answer(q) is None:
        return False
    selected = [scale[o.id] for o in q.options if o.selected and o.id in scale]
    return bool(selected and any(value * judgment.target <= 0 for value in selected))
