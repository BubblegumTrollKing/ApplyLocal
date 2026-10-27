"""Deterministic boundaries for facts and restricted steps; judgment is delegated."""
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
    r"terms and conditions|I consent|I agree to (?:the )?(?:terms|conditions|privacy policy)|"
    r"under penalty|legally binding)\b", re.I)
# These are actual facts/commitments. First-person wording and Likert scales alone
# are deliberately NOT evidence that the applicant must answer a question.
FACTS = re.compile(
    r"\b(?:date of birth|birth date|nationality|citizenship|work authori[sz]ation|"
    r"authori[sz]ed to work|eligible to work|legally (?:work|eligible)|sponsorship|"
    r"legal name|full name|first name|last name|given name|surname|preferred name|pronouns|"
    r"email(?: address)?|e-mail|phone(?: number)?|telephone|mobile number|home address|"
    r"street address|postal code|zip code|country of residence|gender|ethnicity|race|"
    r"veteran|disability|medical history|criminal (?:record|history)|convicted|felony|"
    r"education|degree|diploma|university|college|qualifications|certifications?|"
    r"(?:retail|sales|customer service|hospitality|warehouse|manufacturing|management) experience|"
    r"current employer|previous employer|employment history|work history|"
    r"years? of (?:work |retail |relevant |professional )?experience|"
    r"salary|desired pay|hourly (?:pay|rate|wage)|pay expectations|"
    r"availability|available (?:on|for|to work|weekends|weekdays|evenings|nights)|"
    r"can you work|(?:are you )?(?:at least|over|under) \d+ years old|"
    r"(?:willing|able) to (?:work|relocate|travel)|start date|when can you start|"
    r"how (?:old|many years)|have you (?:ever )?(?:worked|been employed|been fired|been dismissed|"
    r"held|completed|graduated|managed|supervised|used|operated)|"
    r"(?:do you|I) (?:have|hold|possess) (?:a |an |any )?(?:licen[cs]e|degree|certificate|qualification)|"
    r"I have \d|I (?:worked|graduated|earned)|"
    r"in (?:your|my) (?:previous|last|current) (?:job|role|employment)|"
    r"tell us about (?:a time|yourself)|describe (?:a time|your (?:experience|background))|"
    r"how many (?:days|times).*(?:absent|missed|late))\b", re.I)
HYPOTHETICAL = re.compile(
    r"\b(?:(?:what|how) (?:would|should) (?:you|a (?:worker|manager)) "
    r"(?:do|respond|handle|react|deal|say|proceed)|which (?:action|response)|"
    r"imagine|suppose|hypothetical)\b|^a (?:customer|coworker|worker)\b", re.I)
GENERAL = re.compile(
    r"^(?:what|which|how|when|why|where|select|choose|identify|calculate|solve|"
    r"a (?:customer|coworker|worker)|if |you (?:notice|see|find|are working))\b", re.I)
PERSONALITY = re.compile(
    r"\b(?:I (?:am|prefer|enjoy|always|never|often|rarely|like|dislike|try|remain|stay)|"
    r"do you (?:enjoy|prefer|like)|describes? you|applies? to you|"
    r"describe yourself|agree or disagree|most like me|least like me)\b", re.I)


def page_restriction(text: str) -> str:
    if HUMAN_ONLY.search(text):
        return "This assessment explicitly requires human completion. Complete it yourself."
    return ""


def question_restriction(q: Question) -> str:
    if (IDENTITY.search(q.prompt) and not HYPOTHETICAL.search(q.prompt)) or q.sensitive:
        return "Complete identity, credential, or verification steps directly in the browser."
    if ATTESTATION.search(q.prompt):
        return "Review and complete this consent or attestation directly in the browser."
    return ""


def requires_personal_answer(q: Question) -> bool:
    # Hypotheticals can mention qualifications/availability without asking for the
    # applicant's own facts, e.g. "What should you do if your certification expires?"
    if HYPOTHETICAL.search(q.prompt):
        return False
    return bool(FACTS.search(q.prompt + " " + " ".join(o.label for o in q.options)) or re.fullmatch(
        r"\s*(?:name|age|address|city|state|province|country|experience|job title|"
        r"employment status|highest level|highest degree|schedule)\s*[:?*]?", q.prompt, re.I))


def can_reason_autonomously(q: Question) -> bool:
    if requires_personal_answer(q):
        return False
    # Complete labelled choices, including subjective/first-person statements,
    # should go to the model. A bare unknown text field still needs context.
    return bool(q.options or GENERAL.search(q.prompt.strip()) or PERSONALITY.search(q.prompt))
