from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import threading
import time

import pytest

from applylocal.domain import AssistanceRequired, Option, Question, Stopped
from applylocal.local_ai import LocalAI


@pytest.fixture
def fake_ollama():
    state = {"reply": {"kind": "knowledge", "option_ids": ["a"], "value": None,
                       "confidence": 0.98, "reason": "Routine safety knowledge"},
             "remote": False, "delay": 0, "requests": [], "invalid": False, "redirect": False}
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            request = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            state["requests"].append((self.path, request))
            if state["redirect"]:
                self.send_response(302)
                self.send_header("Location", "https://example.com/")
                self.end_headers()
                return
            if self.path == "/api/show":
                value = {"capabilities": ["completion", "vision"]}
                if state["remote"]:
                    value["remote_host"] = "https://remote.invalid"
            else:
                time.sleep(state["delay"])
                value = {"message": {"content": "not JSON" if state["invalid"] else json.dumps(state["reply"])}}
            body = json.dumps(value).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            try:
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                pass
        def log_message(self, *args):
            pass
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}", state
    server.shutdown()
    server.server_close()


def q():
    return Question("q", "Which action is safest?", "radio", (Option("a", "Report"), Option("b", "Ignore")))


def test_real_http_request_and_schema(fake_ollama):
    url, state = fake_ollama
    ai = LocalAI(url, threading.Event())
    assert ai.decide("test:local", q(), 0.9).option_ids == ("a",)
    body = state["requests"][-1][1]
    assert body["stream"] is False
    assert body["format"]["type"] == "object"
    assert "UNTRUSTED" in body["messages"][0]["content"]
    assert "api_key" not in body


@pytest.mark.parametrize("update", [{"option_ids": ["invented"]}, {"kind": "personal"}, {"kind": "human_only"}, {"option_ids": ["a", "b"]}, {"unexpected": True}])
def test_model_failures_fail_closed(fake_ollama, update):
    url, state = fake_ollama
    state["reply"].update(update)
    with pytest.raises(AssistanceRequired):
        LocalAI(url, threading.Event()).decide("test:local", q(), 0.9)


def test_malformed_model_json(fake_ollama):
    url, state = fake_ollama
    state["invalid"] = True
    with pytest.raises(AssistanceRequired, match="invalid structured"):
        LocalAI(url, threading.Event()).decide("test:local", q(), 0.9)


def test_cloud_model_metadata_rejected(fake_ollama):
    url, state = fake_ollama
    state["remote"] = True
    with pytest.raises(AssistanceRequired, match="remote service"):
        LocalAI(url, threading.Event()).check_model("test:local")
    assert all(path != "/api/chat" for path, _ in state["requests"])


def test_cloud_name_rejected_before_request(fake_ollama):
    url, state = fake_ollama
    with pytest.raises(AssistanceRequired, match="cloud"):
        LocalAI(url, threading.Event()).check_model("qwen:cloud")
    assert state["requests"] == []


def test_redirect_rejected(fake_ollama):
    url, state = fake_ollama
    state["redirect"] = True
    with pytest.raises(AssistanceRequired, match="redirect"):
        LocalAI(url, threading.Event()).check_model("test:local")


def test_stop_during_slow_inference(fake_ollama):
    url, state = fake_ollama
    state["delay"] = 2
    stop = threading.Event()
    ai = LocalAI(url, stop)
    ai.check_model("test:local")
    timer = threading.Timer(0.15, stop.set)
    timer.start()
    started = time.monotonic()
    with pytest.raises(Stopped):
        ai.decide("test:local", q(), 0.9)
    assert time.monotonic() - started < 0.8
    timer.join()


def test_subjective_personality_is_answered_automatically(fake_ollama):
    url, state = fake_ollama
    state["reply"].update(kind="personality", confidence=0.98)
    item = Question("q", "Are you traditional?", "radio", (Option("a", "Yes"), Option("b", "No")))
    assert LocalAI(url, threading.Event()).decide("test:local", item, 0.9).option_ids == ("a",)
    assert len([r for r in state["requests"] if r[0] == "/api/chat"]) == 1


def test_uncertainty_gets_automatic_review_then_best_supported_choice(fake_ollama):
    url, state = fake_ollama
    state["reply"]["confidence"] = 0.55
    ai = LocalAI(url, threading.Event())
    assert ai.decide("test:local", q(), 0.9).option_ids == ("a",)
    chats = [r[1] for r in state["requests"] if r[0] == "/api/chat"]
    assert len(chats) == 2
    assert "Review the question" in chats[1]["messages"][0]["content"]


def test_misclassified_spill_question_is_reconsidered_without_user(fake_ollama, monkeypatch):
    url, _ = fake_ollama
    ai = LocalAI(url, threading.Event())
    replies = iter([
        {"kind": "personal", "option_ids": [], "value": None, "confidence": 0.98, "reason": "First person"},
        {"kind": "knowledge", "option_ids": ["a"], "value": None, "confidence": 0.98, "reason": "Safe response"},
    ])
    monkeypatch.setattr(ai, "structured", lambda *args: next(replies))
    assert ai.decide("test:local", q(), 0.9).option_ids == ("a",)


def test_relevant_answer_history_is_sent_in_same_call(fake_ollama):
    url, state = fake_ollama
    history = [{"question": "I like teamwork", "selected": ["Agree"]}]
    LocalAI(url, threading.Event()).decide("test:local", q(), 0.9, memories=history)
    chats = [r[1] for r in state["requests"] if r[0] == "/api/chat"]
    assert len(chats) == 1
    assert json.loads(chats[0]["messages"][1]["content"])["answer_history"] == history
    assert chats[0]["options"]["num_predict"] == 512


def test_factual_unknown_never_sent_to_model(fake_ollama):
    url, state = fake_ollama
    item = Question("q", "Are you available weekends?", "radio", (Option("a", "Yes"), Option("b", "No")))
    with pytest.raises(AssistanceRequired, match="actual personal fact"):
        LocalAI(url, threading.Event()).decide("test:local", item, 0.9)
    assert state["requests"] == []
