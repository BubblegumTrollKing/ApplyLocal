import json

from applylocal.audit import Audit


def test_audit_excludes_private_content(tmp_path):
    path = tmp_path / "audit.jsonl"
    audit = Audit(path)
    audit.record({"code": "verified", "message": "SSN 123-45-6789", "question": "private", "url": "https://secret.test?token=x", "answered": 1, "pages": 2})
    audit.close()
    text = path.read_text()
    assert "SSN" not in text and "private" not in text and "secret" not in text
    assert json.loads(text)["answered"] == 1
