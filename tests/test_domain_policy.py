import threading

import pytest

from applylocal.domain import Answer, AssistanceRequired, Option, Question, Stopped, check_stop
from applylocal.domain import validate_answer
from applylocal.policy import page_restriction, question_restriction, requires_personal_answer
from applylocal.storage import Profile, Settings
from applylocal.local_ai import loopback_url


def question(kind="radio"):
    return Question("q", "Are you available on weekends?", kind, (Option("a", "Yes"), Option("b", "No")), required=True)


@pytest.mark.parametrize("answer", [Answer(("missing",)), Answer(("a", "b")), Answer(("a", "a")), Answer(), Answer(("a",), "invented")])
def test_invalid_answers_rejected(answer):
    with pytest.raises(AssistanceRequired):
        validate_answer(question(), answer)


def test_profile_roundtrip_and_exact_choice_scope(tmp_path):
    p = Profile({"email": "truth@example.test"})
    p.remember(question(), Answer(("b",)))
    path = tmp_path / "profile.json"
    p.save(path)
    loaded = Profile.load(path)
    assert loaded.lookup(question()).option_ids == ("b",)
    assert loaded.lookup(Question("e", "Email address", "text")).value == "truth@example.test"
    assert loaded.lookup(Question("new", "Are you available on weekends?", "radio",
                                  (Option("x", "Always"), Option("y", "Never")))) is None
    assert loaded.lookup(Question("x", "How many years of retail experience?", "text")) is None


def test_empty_profile_does_not_invent():
    assert Profile().lookup(question()) is None


@pytest.mark.parametrize("text", ["Human-only assessment", "Do not use AI tools", "You must not use automated assistance", "Complete this assessment on your own", "AI assistance is prohibited"])
def test_human_only_gate(text):
    assert page_restriction(text)


@pytest.mark.parametrize("text", ["Social security number", "Verification code", "Password", "I certify these answers are true", "I agree to the terms and conditions"])
def test_identity_and_attestation(text):
    assert question_restriction(Question("q", text, "text"))


@pytest.mark.parametrize("text", ["Have you worked in retail?", "Are you available weekends?", "Your salary expectations"])
def test_personal_question_is_not_inferred(text):
    assert requires_personal_answer(Question("q", text, "text"))


def test_hypothetical_is_answerable():
    assert not requires_personal_answer(Question("q", "What should you do when a customer reports a spill?", "text"))


@pytest.mark.parametrize("url", ["https://api.example.com", "http://192.168.1.2:11434", "http://127.0.0.1.evil:11434", "http://user:pass@localhost:11434", "http://localhost:11434/x", "file:///tmp/model", "http://localhost:11434?x=1"])
def test_nonlocal_endpoints_rejected(url):
    with pytest.raises(ValueError):
        loopback_url(url)


def test_local_endpoint_canonicalization():
    assert loopback_url("http://localhost:11434/") == "http://127.0.0.1:11434"
    assert loopback_url("http://[::1]:11434") == "http://[::1]:11434"


def test_settings_roundtrip(tmp_path):
    path = tmp_path / "settings.json"
    Settings(auto_submit=True).save(path)
    assert Settings.load(path).auto_submit


def test_stop():
    stop = threading.Event()
    stop.set()
    with pytest.raises(Stopped):
        check_stop(stop)
