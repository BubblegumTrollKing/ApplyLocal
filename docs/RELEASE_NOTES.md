ApplyLocal 1.3.0 — faster professional work-style answers and a scrollable window.

Download **ApplyLocal-Windows-x64.zip**, extract it and run **ApplyLocal.exe**. The window title shows 1.3.0. Existing models and factual data are reused.

- Fixes the blanket-agreement fallback. Clear work-style statements use immediate, polarity-aware professional judgments. “You struggle with deadlines” selects disagreement; “I never miss deadlines” selects agreement. Response strength varies by behavior. Common statements need no model inference.
- Unfamiliar questions on a page share one compact local AI request. Each returned answer is validated independently. An unreadable model response no longer makes every unfamiliar scale positive; the fallback tends toward neutral.
- Recognizes statement captions, bare-circle agreement scales with visible endpoint labels, reversed scales and hidden native inputs with visible labels. It verifies the actual selected state after acting.
- Invalidates old automatic scale predictions while keeping factual values and identified user answers. The original local profile is backed up. Clearly contradictory visible work-style selections from the old version are corrected automatically.
- Makes the entire main window scroll with the mouse wheel, scrollbar and navigation keys. Start and emergency Stop stay pinned at the bottom. Setup and browser controls fit narrower windows; larger text no longer hides the bottom of the app. Profile/settings dialogs scroll with Save pinned outside the scroll area.
- Keeps automatic rechecks, automatic memory, existing-browser connections, protection for unknown concrete facts, and appropriate handling of identity/consent/human-only steps.

The tests cover the reported three statements, many distinct positive/negative and double-negation items, a 60-item varied questionnaire, scale direction, old-answer correction/migration, one-request page batching, and small-window/larger-text scrolling. The source and packaged-executable smoke checks exercise both the reported polarity and whole-window scroll/Stop behavior before release publication. Actual Windows results and checksums are in **ApplyLocal-test-evidence.zip**.

Employer scoring and real-model accuracy across arbitrary sites are not established by these controlled checks. Chrome's permission-based existing-session dialog still needs real-world testing. The application is unsigned. Python is bundled; no new model download is required for this upgrade.
