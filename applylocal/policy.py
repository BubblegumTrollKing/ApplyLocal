"""Conservative, deterministic gates before any model or profile answer."""
import re

from .domain import Question


HUMAN_ONLY = re.compile(
    r"human[- ]only|(?:do not|must not|cannot|may not) use (?:any )?(?:AI|artificial intelligence|automated|automation)|"
    r"(?:AI|automated|automation|outside) (?:tools?|assistance) (?:is |are )?(?:not permitted|prohibited)|"
    r"(?:complete|take) (?:this|the) (?:assessment|test) (?:entirely )?(?:on your own|without assistance)|"
    r"no (?:AI|automated|outside) assistance|"
    r"(?:use of |using )?(?:AI|artificial intelligence|automated tools?|automation) (?:is |are )?(?:strictly )?(?:prohibited|not permitted|not allowed|forbidden)|"
    r"without (?:the )?(?:use|aid|assistance|help) of (?:AI|artificial intelligence)", re.I)
IDENTITY = re.compile(
    r"captcha|verify (?:your |my )?identity|verification code|one[- ]time (?:password|code)|"
    r"social security|\bSSN\b|passport|driver'?s licen[cs]e|take a selfie|facial recognition|"
    r"upload (?:your )?(?:ID|identification)|\bpassword\b", re.I)
ATTESTATION = re.compile(
    r"\b(?:certify|attest|signature|e-signature|sign here|background check|"
    r"terms and conditions|I consent|I agree to|under penalty|legally binding)\b", re.I)
PERSONAL = re.compile(
    r"\b(?:have you|do you|are you|did you|were you|your (?:age|experience|availability|salary|"
    r"education|employment|work history|skills|citizenship|gender|ethnicity|disability)|"
    r"date of birth|work authori[sz]ation|sponsorship|willing to|how (?:often|many years)|"
    r"I (?:am|have|prefer|enjoy|always|never|often|rarely)|describe yourself|tell us about yourself|"
    r"agree or disagree|strongly agree|strongly disagree|most like me|least like me|"
    r"years of experience|highest (?:level|degree)|employment status|desired (?:pay|salary)|"
    r"birth date|preferred (?:name|pronouns|schedule)|legal name|full name|first name|last name|"
    r"email address|phone number|home address|gender|ethnicity|race|veteran|disability|"
    r"qualifications|current employer|previous employer|education history|work history)\b", re.I)
GENERAL = re.compile(
    r"^(?:what|which|how|when|why|where|select|choose|identify|calculate|solve|"
    r"a (?:customer|coworker|worker)|if |you (?:notice|see|find|are working))\b", re.I)


def page_restriction(text: str) -> str:
    if HUMAN_ONLY.search(text):
        return "This assessment explicitly requires human completion. Complete it yourself."
    return ""


def question_restriction(q: Question) -> str:
    if IDENTITY.search(q.prompt) or q.sensitive:
        return "Complete identity, credential, or verification steps directly in the browser."
    if ATTESTATION.search(q.prompt):
        return "Review and complete this consent or attestation directly in the browser."
    return ""


def requires_personal_answer(q: Question) -> bool:
    personal_you = re.search(r"\byour\s+(?!(?:coworker|colleague|manager|supervisor|customer|team|workplace|store|workstation|department)\b)", q.prompt, re.I)
    describes_you = re.search(r"\b(?:describes? you|applies? to you|about you)\b", q.prompt, re.I)
    return bool(personal_you or describes_you or PERSONAL.search(q.prompt + " " + " ".join(o.label for o in q.options)))


def can_reason_autonomously(q: Question) -> bool:
    # Bare labels (e.g. Job title, Nationality) are facts, not general knowledge prompts.
    return bool(GENERAL.search(q.prompt.strip())) and not requires_personal_answer(q)
