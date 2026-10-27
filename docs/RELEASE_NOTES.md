ApplyLocal 1.2.0 — pick an available answer, keep rechecking, reuse your browser.

Download **ApplyLocal-Windows-x64.zip**, extract it, and run **ApplyLocal.exe**. Existing models and saved data are reused.

- Closed choices use one compact integer-constrained model call. Malformed IDs, label answers and extra non-null text fields are repaired. If the model still cannot choose, an enabled best-effort fallback proceeds without a question-review prompt. Imperfect options and uncertainty no longer ask you to decide. The inference budget is eight seconds per choice.
- Validation is rechecked from live controls. Empty error containers, stale ARIA flags, error banners and required fields on newly opened pages no longer open a manual validation dialog.
- Navigation and operational failures keep being observed until progress or Stop. There is no recheck button. Click retries remain bounded, and uncertain server submissions are not repeated.
- A fact entered directly in the browser is detected automatically even while a fact-entry prompt is visible. Consent/identity steps also resume on observed browser changes. Unknown concrete applicant facts are not invented; human-only assessments stop the run.
- Browser selection includes Chrome, Edge, Brave, Chromium and a custom executable. Existing-session mode discovers a local DevToolsActivePort endpoint and attaches to the open tabs. In Chrome 144+, enable Remote Debugging through Enable browser access, then Refresh tabs and approve Chrome's connection prompt. Other browsers need an available CDP endpoint. Firefox is unsupported.
- Automatic memory ignores question/page numbering when matching equivalent questions. The regression suite includes a 60-question run with malformed model answers and stale error banners, without user prompts.

Publication requires the full Windows suite plus source and packaged-executable GUI/browser smoke checks. **ApplyLocal-test-evidence.zip** contains actual results and the binary checksum. The application is unsigned.

The browser-attachment tests use a controlled Chromium profile and its real debugging endpoint. Chrome's newer permission dialog, individual Chrome/Edge/Brave versions, live employer sites and real-model answer accuracy still need real-world testing. Best-effort fallback is intentionally permitted to choose an imperfect answer; it does not establish an employer's scoring key.
