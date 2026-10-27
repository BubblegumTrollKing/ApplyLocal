# Initial Linux verification report

The following checks record the initial Linux source-validation baseline, before Windows CI was available. This file is historical evidence, not the current status of a Windows release. Each published Windows build includes `ApplyLocal-test-evidence.zip` with its own test results, GUI/browser smoke reports, source commit and executable checksum. Windows release assets are published only when those checks pass.

## Checks actually run

| Check | Result / boundary |
| --- | --- |
| Automated suite | **94 passed, 0 failed, 0 skipped** in the final full run; JUnit evidence: `test-results.xml` |
| Static checks | `python -m ruff check .` passed |
| Compilation | Python application and tests compiled successfully |
| Dependency consistency | `python -m pip check` passed after installing the pinned runtime requirements |
| Browser automation | Real Chromium Headless Shell 141.0.7390.37 through Playwright 1.56.0; browser tests did not substitute mocked DOM elements |
| CDP attachment | Real loopback connection, explicit target selection, DOM filling, disconnect/reconnect and browser-preservation checks passed |
| Desktop UI | Tk launched under a Linux virtual display; user-choice handoffs, final-review button, Stop and worker integration were exercised |
| GUI → worker → browser | The GUI started its actual background worker, filled a supplied email fact over CDP and submitted a synthetic questionnaire; completion reached the GUI |
| Local model protocol | Real HTTP calls to a loopback test server, with scripted model replies: schema validation, bad IDs, malformed JSON, low confidence, missing information, redirects, cloud routing and cancellation were exercised |
| Screenshot fallback | Real browser screenshots and real clicks on a synthetic canvas; scripted visual-model replies tested stable-screen checks, coordinate bounds, independent readback, rejection and restrictions |
| Frozen application | PyInstaller 6.16.0 built a native **Linux** binary from the included spec; resource/Tcl/driver checks, GUI launch and actual CDP control passed |
| Workflow configuration | GitHub Actions YAML parsed, referenced build inputs exist; execution on a Windows runner remains pending |
| Archive | Packaged with complete source, requirements, docs, tests, license, workflow and build scripts; ZIP integrity and file checksums checked |

The frozen Linux browser smoke test used a **test-only launcher** pointing at the downloaded Chromium Headless Shell. That launcher supplied the Linux container's sandbox flag and is not part of the delivered application. This validates frozen imports, packaged resources, bundled Playwright driver, GUI startup and CDP behavior. It does **not** validate launching Microsoft Edge or Google Chrome on Windows.

The source runtime was Python 3.12.14 on Linux. The system's Tcl/Tk is 9.0; the Windows build uses the Tcl/Tk supplied by the selected Windows Python distribution. Pinned runtime versions and machine-readable results are in `verification.json`, `source-smoke.json` and `frozen-linux-smoke.json`.

## Defects found and addressed

- Stale question/control or scenario context must be detected before acting.
- Native radio selection must not try to uncheck a radio independently.
- A user's own direct edit must not be overwritten during reasoning.
- A loading-button label change must not be mistaken for successful page navigation.
- Unconfirmed Next/Submit must be latched instead of resent automatically.
- Completion instructions mentioning a future confirmation must not be counted as actual completion.
- If a later field clears a previously verified answer, submission must stop.
- Mixed structured/visual questions must not silently skip the visual portion.
- Human-only instructions must remain binding after a page transition.
- Manual consent can resume only after the person handles it; saved answers cannot auto-check it.
- Tk polling is canceled during shutdown; GUI tests use the single-interpreter lifecycle of the real app. The native greenlet dependency was updated after a threading/cleanup crash was exposed by the integrated GUI test.
- GUI tests wait for completion events to reach the GUI, rather than assuming worker-thread termination means the UI queue has already drained.
- Custom-prefix Linux Tcl/Tk shared libraries are included by the build spec.

## Still requires validation

| Area | What is not established |
| --- | --- |
| Windows executable | PE build, frozen Tk behavior, actual installed Chrome/Edge launch, DPI scaling, SmartScreen behavior and clean-machine startup have not run here |
| Real local text model | No real Ollama model weights were loaded; answer correctness, refusal behavior and confidence calibration are unmeasured |
| Real local vision model | OCR/grounding/selection-readback accuracy and correlated model errors are unmeasured |
| Hardware performance | No CPU/GPU timing, VRAM/RAM minimum or long-run stability benchmark was performed |
| Employer websites | No live employment assessment was opened, answered or submitted; vendor-specific behavior and accessibility vary |
| Restriction detection | English patterns and model checks cover tested wording, not every possible instruction or proctoring arrangement |

Do not interpret passing synthetic tests as evidence of universal site compatibility or guaranteed correct answers. The app deliberately pauses where evidence is insufficient. This is source-ready for a Windows build and a supervised pilot; it is not qualified as unattended production automation on arbitrary assessments.

## Reproduce and finish acceptance testing

1. Run the included Windows Actions workflow in a public repository, or `scripts/build-windows.ps1` on Windows. Both run tests and a frozen GUI/browser smoke test; the hosted workflow withholds the executable artifact if a check fails.
2. Test the produced executable on a separate Windows 10/11 x64 machine without Python. Install Ollama and download the default local models through the GUI.
3. Run Check setup and the built-in practice questionnaire using the real models. Independently inspect the safety answer, email entry, weekend-availability handoff and final review. Check Stop while inference and navigation are active.
4. Check a low-memory/CPU-only machine and a GPU-equipped machine; measure actual response time. Check display scaling at 100%, 125% and 150% and confirm that Stop and answer controls stay usable.
5. Before relying on a real site, supervise a permitted routine questionnaire and compare every answer with the question. Verify unknown facts, attestations, CAPTCHA, disabled/covered controls, site validation, delayed navigation and final submission behavior. Human-only work remains manual.
