from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
import os
import re
from pathlib import Path
import tempfile

from .domain import Answer, AssistanceRequired, Question, normalize, validate_answer


def data_directory() -> Path:
    root = Path(os.environ.get("LOCALAPPDATA", Path.home() / ".local" / "share")) / "ApplyLocal"
    root.mkdir(parents=True, exist_ok=True)
    return root


def atomic_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=path.name, dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(value, f, indent=2, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


@dataclass
class Settings:
    endpoint: str = "http://127.0.0.1:9222"
    ollama: str = "http://127.0.0.1:11434"
    text_model: str = "qwen2.5:7b"
    vision_model: str = "qwen3-vl:4b"
    vision: bool = True
    auto_submit: bool = True
    confidence: float = 0.90
    max_pages: int = 150
    automation_version: int = 2
    browser_name: str = "Automatic"
    browser_executable: str = ""
    browser_profile: str = ""
    connection_mode: str = "companion"

    def __post_init__(self):
        for key in ("endpoint", "ollama", "text_model", "vision_model", "browser_name",
                    "browser_executable", "browser_profile", "connection_mode"):
            if not isinstance(getattr(self, key), str):
                raise ValueError("Local addresses and model names must be text")
        if self.connection_mode not in {"companion", "existing"}:
            raise ValueError("Choose an existing or companion browser connection")
        if type(self.vision) is not bool or type(self.auto_submit) is not bool:
            raise ValueError("Invalid checkbox setting")
        if not isinstance(self.confidence, (int, float)) or not 0 < self.confidence <= 1:
            raise ValueError("Confidence must be greater than zero and at most one")
        if type(self.max_pages) is not int or not 1 <= self.max_pages <= 500:
            raise ValueError("Page limit must be between 1 and 500")

    @classmethod
    def load(cls, path: Path) -> Settings:
        if not path.exists():
            return cls()
        raw = json.loads(path.read_text(encoding="utf-8"))
        # Upgrade the old review-every-run default to hands-off operation. Later
        # explicit checkbox choices are retained in versioned settings files.
        if "automation_version" not in raw:
            raw["auto_submit"] = True
        return cls(**{k: v for k, v in raw.items() if k in cls.__dataclass_fields__})

    def save(self, path: Path) -> None:
        atomic_json(path, asdict(self))


ALIASES = {
    "first_name": {"first name", "given name"},
    "last_name": {"last name", "surname", "family name"},
    "full_name": {"full name", "name", "legal name"},
    "email": {"email", "email address", "e-mail", "your email address"},
    "phone": {"phone", "phone number", "telephone", "mobile number"},
    "city": {"city", "your city"},
    "state": {"state", "state/province", "province"},
    "postal_code": {"zip", "zip code", "postal code"},
    "country": {"country", "country of residence"},
}


@dataclass
class Profile:
    facts: dict[str, str] = field(default_factory=dict)
    # Answers are keyed by exact normalized question AND available options.
    answers: dict[str, list[str]] = field(default_factory=dict)

    @classmethod
    def load(cls, path: Path) -> Profile:
        if not path.exists():
            return cls()
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict) or not all(isinstance(raw.get(k, {}), dict)
                                              for k in ("facts", "answers")):
            raise ValueError("Invalid profile file")
        profile = cls(raw.get("facts", {}), raw.get("answers", {}))
        if not all(isinstance(k, str) and isinstance(v, str) for k, v in profile.facts.items()):
            raise ValueError("Profile facts must be text")
        if not all(isinstance(k, str) and isinstance(v, list)
                   and all(isinstance(s, str) for s in v) for k, v in profile.answers.items()):
            raise ValueError("Saved answers must be lists of text")
        return profile

    def save(self, path: Path) -> None:
        atomic_json(path, asdict(self))

    @staticmethod
    def key(q: Question) -> str:
        return json.dumps([normalize(q.prompt), q.kind,
                           [normalize(o.label) for o in q.options], normalize(q.context)], ensure_ascii=False)

    def remember(self, q: Question, answer: Answer) -> None:
        validate_answer(q, answer)
        values = [o.label for o in q.options if o.id in answer.option_ids] if q.options else [answer.value or ""]
        self.answers[self.key(q)] = values

    def lookup(self, q: Question) -> Answer | None:
        values = self.answers.get(self.key(q))
        if values is None:
            field_prompt = re.sub(r"^(?:please )?(?:(?:enter|provide|type|confirm) (?:your )?|"
                                  r"what (?:is|are) (?:your )?|your )", "", normalize(q.prompt))
            field_prompt = re.sub(r"\s*\((?:required|optional)\)$", "", field_prompt)
            field_name = next((key for key, names in ALIASES.items()
                               if field_prompt in names), None)
            if field_name and self.facts.get(field_name):
                values = [self.facts[field_name]]
        if values is None:
            return None
        if q.options:
            ids = []
            for value in values:
                matches = [o for o in q.options if normalize(o.label) == normalize(value)]
                if len(matches) != 1:
                    raise AssistanceRequired("A saved answer no longer matches a unique option.")
                ids.append(matches[0].id)
            answer = Answer(tuple(ids), source="profile")
        else:
            if not values:
                raise AssistanceRequired("A saved text answer is empty. Enter your answer again.")
            answer = Answer(value=values[0], source="profile")
        validate_answer(q, answer)
        return answer

    def recall(self, q: Question) -> Answer | None:
        from .memory import fast_recall
        try:
            exact = self.lookup(q)
        except AssistanceRequired:
            exact = None  # A disabled/changed old choice should trigger new reasoning.
        return exact or fast_recall(q, self.answers)

    def related(self, q: Question) -> list[dict]:
        from .memory import relevant_memories
        return relevant_memories(q, self.answers)
