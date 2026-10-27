"""Small, rotating metadata-only logs. No question, answer, URL, screenshot or model text."""
from datetime import datetime, timezone
import json
from logging.handlers import RotatingFileHandler
import logging
from pathlib import Path


class Audit:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.logger = logging.Logger("applylocal.audit")
        handler = RotatingFileHandler(path, maxBytes=1024 * 1024, backupCount=3, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(message)s"))
        self.logger.addHandler(handler)

    def record(self, event: dict):
        item = {"time": datetime.now(timezone.utc).isoformat(),
                "event": event.get("code", "unknown"),
                "answered": event.get("answered", 0), "pages": event.get("pages", 0)}
        self.logger.info(json.dumps(item))

    def close(self):
        for handler in self.logger.handlers:
            handler.close()
