"""Record actual Windows CI results; never substitute model or live-site testing."""
from datetime import datetime, timezone
from hashlib import sha256
from importlib.metadata import version
import json
import os
from pathlib import Path
import platform
import sys
import xml.etree.ElementTree as ET

if sys.platform != "win32":
    raise SystemExit("Windows build evidence must be generated on Windows")

root = ET.parse("test-results.xml").getroot()
suites = [root] if root.tag == "testsuite" else list(root.findall("testsuite"))
totals = {key: sum(int(s.attrib.get(key, 0)) for s in suites)
          for key in ("tests", "failures", "errors", "skipped")}
if not totals["tests"] or totals["failures"] or totals["errors"] or totals["skipped"]:
    raise SystemExit("The Windows test suite did not pass completely")

source = json.loads(Path("source-smoke.json").read_text(encoding="utf-8"))
frozen = json.loads(Path("frozen-smoke.json").read_text(encoding="utf-8"))
if source.get("status") != "passed" or not source.get("gui_window"):
    raise SystemExit("Source GUI test evidence is missing")
if frozen.get("status") != "passed" or not frozen.get("gui_window") or not frozen.get("chromium_cdp"):
    raise SystemExit("Frozen GUI/browser evidence is missing")
if not all(report.get('workstyle_polarity') and report.get('window_scroll')
           and report.get('stop_button_visible') for report in (source, frozen)):
    raise SystemExit('Work-style polarity or whole-window scrolling evidence is missing')

executable = Path("dist/ApplyLocal.exe")
binary = executable.read_bytes()
if binary[:2] != b"MZ":
    raise SystemExit("The built artifact is not a Windows executable")

report = {
    "status": "passed", "created_utc": datetime.now(timezone.utc).isoformat(),
    "commit": os.environ.get("GITHUB_SHA"), "workflow_run": os.environ.get("GITHUB_RUN_ID"),
    "platform": platform.platform(), "python": sys.version.split()[0],
    "architecture": platform.machine(), "tests": totals,
    "source_gui": source, "frozen_gui_browser": frozen,
    "executable": {"name": executable.name, "bytes": len(binary), "sha256": sha256(binary).hexdigest()},
    "versions": {name: version(name) for name in ("playwright", "pyinstaller", "jsonschema", "greenlet")},
    "real_ollama_models_tested": False, "live_employer_sites_tested": False,
}
Path("build-info.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"status": "passed", "tests": totals, "executable": report["executable"]}))
