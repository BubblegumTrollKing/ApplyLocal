# ApplyLocal

A free, MIT-licensed Windows desktop application that fills routine employment questionnaires using local AI and verifies browser actions. No account with an AI provider, subscription, API key, or per-question charge is required. Model downloads happen once; inference stays on the computer.

**Start with [QUICK_START.md](QUICK_START.md).** [Windows downloads](https://github.com/BubblegumTrollKing/ApplyLocal/releases) appear after the Windows CI checks pass. Download the portable ZIP there and run `ApplyLocal.exe`; Python is bundled. Source archives contain the application, practice questionnaire, tests and build pipeline. The [verification report](docs/VERIFICATION.md) records the initial Linux baseline; each Windows release includes its own test evidence and binary checksum.

## What it does

- Uses Playwright over a loopback Chrome DevTools Protocol connection to the selected Chrome/Edge tab.
- Reads labels, fieldsets, ARIA names/states, native inputs/selects, ARIA radio/checkbox/combobox controls, iframes and open shadow roots.
- Automatically remembers verified answers locally. Reuses equivalent question/choice paraphrases without another model call, and supplies relevant related answers to the existing reasoning call for consistency. It never sends your whole profile to a model.
- Uses local Ollama models for knowledge, workplace situations, personality, work-style and Likert questions. It selects the response a reasonable employer would prefer, including subjective items such as “Are you traditional?”. JSON-schema and available-choice checks still apply. An uncertain or misclassified answer gets one automatic review; a valid best-fit choice can proceed without asking you to settle the uncertainty.
- Checks for human-only instructions and identity/consent steps before answering. Only unknown concrete facts/commitments (such as email, credentials, work authorization or hours you can actually work) need a truthful value. First-person wording and personality scales do not trigger a personal-answer handoff.
- Verifies live selected states and entered values. Automatically rechecks stale/replaced controls and restores answers lost during page re-renders. Watches delayed navigation automatically for up to two minutes; no manual recheck button is needed. A Next click with no effect and no observed request may be retried once after a stable-state check. Submit and navigation that sent a request are never repeated automatically.
- Offers an optional visual fallback for **one visible single-choice question** with inaccessible/canvas choices. It captures only the browser viewport in memory, checks screen stability, and uses a second local image read to verify the selection. Next/Submit must still be an accessible DOM control.
- Shows progress, verified-answer/page counts, a log, and a Stop button / Esc shortcut.
- Preserves existing answers and corrects changes to its own verified answers during a run. Submission is automatic by default; clear the automatic-submit checkbox if you want a final review. Consent and identity steps remain manual. Old unversioned settings migrate to the new hands-off default; subsequent checkbox choices are retained.

## Operating limits

The default prioritizes minimal user intervention and fast reuse. It is not a promise to complete every employer website or to choose the employer’s actual scoring key. Model confidence is self-reported, **not** a measured probability of correctness. Two image reads can share the same mistake. Site changes, unusual widgets and restrictions may require your input.

An ordinary browser window cannot be attached retroactively. Click **Open browser**, sign in and open the assessment in that companion Chrome/Edge profile, then **Refresh tabs**. Modern Chrome requires a non-default profile for remote debugging. The app does not copy your normal browser cookies or passwords. You may reuse the companion profile on later runs.

Firefox, closed shadow DOM, drag-and-drop/ranking, file uploads, arbitrary desktop windows, visual-only navigation, multi-question canvas pages, mixed DOM/canvas question pages, and unlabelled custom widgets are manual handoffs. Lazy-created combobox options that are absent from the DOM are also handed off. The initial policy/navigation recognition is English. It does not bypass CAPTCHA, proctoring, site blocks or rules against assistance, and does not invent concrete applicant facts or employment history. It does synthesize employer-oriented personality/work-style responses as requested. A detected human-only restriction blocks the remainder of the run even after changing pages; the person must complete that assessment.

Keep the selected tab untouched while running. Stop prevents new actions and cancels waiting for local inference; a browser action already sent may finish. Esc works while the ApplyLocal window has focus. **Closing or disconnecting ApplyLocal leaves the browser open.** Nothing can retract an application already submitted.

## Free local setup

1. Use Windows 10/11 x64 with Chrome or Edge installed. A modern PC with 16 GB RAM and at least 12 GB free disk is a practical starting recommendation, not a validated minimum. A compatible GPU helps; CPU-only inference may be slow.
2. Install [Ollama for Windows](https://ollama.com/download/windows), version 0.12.7 or newer for the default vision model. Start Ollama; no cloud sign-in is needed.
3. In ApplyLocal click **Download local models**. Defaults are `qwen2.5:7b` for text and `qwen3-vl:4b` for vision, both published with Apache-2.0 model licenses. Alternatively, in a terminal:

   ```powershell
   ollama pull qwen2.5:7b
   ollama pull qwen3-vl:4b
   ```

4. Click **Check setup**, optionally enter **Your facts & saved answers**, then **Open browser**.
5. Use **Try practice questionnaire** first. Its email and weekend-availability questions deliberately demonstrate truthful personal-data handoffs. No employer receives practice responses.

For an additional server-wide cloud restriction, set `OLLAMA_NO_CLOUD=1` in your Windows user environment and restart Ollama, or use Ollama's documented `disable_ollama_cloud` setting. ApplyLocal itself accepts only literal loopback HTTP endpoints, rejects cloud-tagged models and model metadata that reports remote routing, ignores HTTP proxy environment variables, and rejects HTTP redirects. These checks assume your local Ollama installation is trustworthy.

Running questionnaires still requires the employer website's normal internet access. Initial software/model downloads use internet bandwidth; local inference uses your hardware and electricity. Neither is a paid API dependency.

## Run from source on Windows

Install [Python 3.12](https://www.python.org/downloads/windows/) with the Python launcher, extract this folder, and double-click `Run-From-Source.bat`. It creates a virtual environment, installs the pinned runtime requirements and opens the GUI. For subsequent starts, the same file reuses that environment. Python is not required for users of a built executable; Ollama and a browser still are.

Manual equivalent:

```powershell
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\pythonw.exe -m applylocal
```

No Playwright browser download is needed for normal use: ApplyLocal uses your installed Chrome/Edge. Browser downloads below are for automated tests only.

## Produce a downloadable Windows executable

**GitHub Actions:** create a public GitHub repository and upload the **contents of this folder at its root**, including `.github/workflows/windows.yml`. You can upload through GitHub's web UI, or run `git init`, commit and push it. Open **Actions → Test and build Windows application → Run workflow**. After a successful run, download the `ApplyLocal-Windows-x64` artifact, unzip the artifact and the portable ZIP inside it, and run `ApplyLocal.exe`.

The workflow installs dependencies, runs the real Chromium suite, smoke-tests the source GUI, bundles Python/Tk/Playwright's driver with PyInstaller, then smoke-tests the **frozen executable's GUI and actual Edge/Chrome CDP connection** on Windows. Artifacts are withheld if any check fails. Test evidence is uploaded separately. It never needs model weights or access to a live assessment to build.

Successful builds on `main` automatically publish a prerelease named for the source commit, containing the `.exe`, portable ZIP, source archive, license notices and Windows test evidence. Version tags such as `v1.0.0` publish a regular release. Failed tests or executable smoke checks prevent publication. No model weights are included in the downloads.

The workflow uses standard GitHub-hosted runners. GitHub documents free use of standard runners for public repositories; artifact storage has account allowances, so keep only needed artifacts or use the local build route to avoid hosted-service billing. Builds are unsigned; Windows may display a publisher/reputation prompt. No paid signing certificate is needed to build or run the app.

**Local Windows build:** in PowerShell, from this folder:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build-windows.ps1
```

This runs a local script for this process; it does not change the machine's execution-policy setting. Review the script before running it. The output is `dist\ApplyLocal.exe`. A Windows build must run on Windows; PyInstaller does not cross-compile a Windows executable from the Linux environment used to prepare this source.

## Tests

```powershell
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.venv\Scripts\python.exe -m playwright install chromium
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe -m ruff check .
.venv\Scripts\python.exe -m applylocal --self-test
```

On Linux, use `python` instead and install Playwright's system dependencies if Chromium reports missing shared libraries. `pytest -m "not browser"` runs the non-browser portion. Browser tests fail rather than silently skipping if Chromium is missing.

The suite exercises native controls, ARIA controls, hidden/disabled elements, frames, open shadow roots, asynchronous SPA transitions, factual profile filling, automatic personality answers, automatic answer persistence, paraphrase reuse, reversed-question handling, related-answer context, user handoffs, optional final review, identity/human-only restrictions, stale-state recovery, validation failures, nonpersistent input, delayed navigation, bounded retries, duplicate-submission prevention, cancellation, HTTP schema failures, cloud rejection, real CDP attachment/disconnection and scripted visual read/click/readback. Model HTTP tests use an actual local test server with controlled replies. Vision tests use scripted model replies with real browser screenshots and clicks. **These tests do not measure the answer accuracy of real Ollama models.**

## Data and architecture

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) and [docs/PRIVACY.md](docs/PRIVACY.md). All application data lives in `%LOCALAPPDATA%\ApplyLocal`: `profile.json`, `settings.json`, rotating metadata-only `activity.jsonl` logs, and `browser-profile`. Facts and saved answers are readable local text; browser cookies are managed by Chrome/Edge. Screenshots exist only in memory and are not written to logs or exported. No analytics, telemetry, paid service or model-provider key is implemented.

Questions/answers are not written to the activity log. The on-screen log reports operational messages. `Open local data & logs` opens the folder for inspection. To reset, stop the app, close the companion browser and remove this folder. To remove only saved questionnaire answers, use **Your facts & saved answers → Clear remembered answers**.

## Primary technical references

- [Playwright CDP support and limits](https://playwright.dev/python/docs/api/class-browsertype#browser-type-connect-over-cdp)
- [Chrome remote debugging profile requirement](https://developer.chrome.com/blog/remote-debugging-port)
- [Ollama structured outputs](https://docs.ollama.com/capabilities/structured-outputs) and [local-only configuration](https://docs.ollama.com/faq)
- [Default text model and license](https://ollama.com/library/qwen2.5:7b) and [default vision model and license](https://ollama.com/library/qwen3-vl:4b)
- [PyInstaller target-platform build requirement](https://www.pyinstaller.org/)
- [GitHub Actions free use and storage allowances](https://docs.github.com/en/billing/concepts/product-billing/github-actions)

The application source is licensed under MIT. Dependencies and models retain their own licenses; see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
