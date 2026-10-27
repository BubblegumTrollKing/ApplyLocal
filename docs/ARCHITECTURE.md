# Architecture and invariants

## Components

| Module | Responsibility |
| --- | --- |
| `gui.py` | Tk main thread, setup, profile editor, target tab selection, progress and handoff UI |
| `engine.py` | Bounded questionnaire state machine; one question/action at a time |
| `browser.py`, `resources/extract.js` | Structured DOM/accessibility attributes, stable element references, verified mutations and navigation |
| `policy.py` | Human-only, identity, consent, concrete-fact and restricted-step gates |
| `local_ai.py` | Loopback-only Ollama transport, schema validation, capability checks and cancelable inference wait |
| `vision.py` | Stable viewport capture, visual single-choice extraction, bounded click and independent selected-state readback |
| `storage.py`, `memory.py` | Explicit facts, automatic verified-answer storage, fast paraphrase retrieval, related-answer ranking, atomic saves |
| `audit.py` | Rotating operational event counts without questions/answers/URLs |
| `practice.py` | Loopback-only practice page server |

There is no agent framework or arbitrary tool/code execution facility. A model can return only a question classification, exact available option IDs, a text value, and confidence/reason fields. It cannot choose a browser tab, run code, navigate to URLs or access the filesystem. Page text is untrusted data; prompts say so, and the executor independently enforces permitted choices and steps. Prompt injection and novel restriction wording remain imperfectly detectable, so unknown forms hand off.

## Worker ownership

The Tk thread owns widgets only. One background worker owns all synchronous Playwright objects. A queue carries events and another carries user answers. UI input remains responsive during inference. A `threading.Event` cancels waits; the HTTP request runs in an isolated daemon thread and any late result cannot initiate browser actions. HTTP requests are bounded and do not follow redirects or proxies. Browser operations have short timeouts and check Stop before each mutation. An already-issued browser/network operation cannot be recalled.

## Observe → decide → validate → act → verify

1. Read the selected tab and visible frames. Hidden inputs and hidden frames are excluded. Open shadow roots are traversed; controls are named from native labels, fieldset legends, `aria-labelledby` and `aria-label`.
2. Apply page restrictions before using saved answers or AI. Identity and attestations always hand off. Unknown concrete facts/history/commitments never receive an invented answer. Personality, attitudes, professional preferences and work-style questions are answered with employer-oriented judgment.
3. Preserve existing filled values. Otherwise resolve saved answers, explicitly entered facts, or a fast equivalent paraphrase. Matching uses locally normalized concepts, compatible choices and scenario context. Less exact matches are supplied as related-answer hints in the same local reasoning call. Factual extrapolation is limited to explicit contact aliases and unambiguous equivalent availability/industry-experience/past-dismissal paraphrases. The whole profile is never sent.
4. Validate returned JSON against a closed schema; reject unsupported kinds, invalid IDs, disabled choices, duplicates and wrong cardinality. Low reasoning confidence or a misclassification triggers one automatic review, then a valid best-fit closed choice may proceed. Vision extraction/verification keeps its stricter confidence gate.
5. Re-observe. The question prompt, option identities/labels, enabled state and current answer must match the observed question. Operate the existing Element handle, not a guessed coordinate or positional selector.
6. Read live selected/value state back and automatically remember verified answers. Stale DOM/control failures get bounded automatic rechecks using the in-flight answer, avoiding another inference call. Previously verified answers changed by later controls are restored automatically up to twice. A cosmetic pixel change is not counted as success.
7. Choose a unique recognized Next/Submit control. Final submission is enabled by default and can be disabled in the GUI. Verify changed semantic question content, a page marker or a completion message. DOM replacements, loading captions and blank interstitials are not completed page transitions. After an unconfirmed click the engine observes automatically for up to 120 seconds, then stops if progress is still unconfirmed. A non-final Next can be retried once only when no document/XHR/fetch/non-GET request was observed, the page and answers are unchanged, the button is ready and the page is stable. Any observed request suppresses retries; Submit is never automatically repeated. Visual transitions are re-observed without a second click.

Stable IDs are per-document WeakMap keys backed by direct DOM Element references. They are not selector strings supplied by a model. A re-render replaces references and therefore fails the stale-state check. IDs can restart on full document navigation; question structure and URL are also compared. A website that repeats exactly the same semantic content without a changing page marker cannot provide dependable transition evidence; recovery is bounded and no server submission is speculatively repeated.

The loop is limited to 150 pages and 1,000 actions. No persistent automatic resume is attempted after a crash or reboot; the current browser state is read from scratch when the user starts again. Already-filled controls are preserved. Saved facts/answers survive restarts.

## Visual fallback

The initial implementation supports precisely one visible single-choice question, not arbitrary computer control. The model transcribes choices and CSS-pixel click centers from a viewport screenshot. Duplicate/empty labels, coordinates out of bounds, restrictions or uncertain extraction cause handoff. Before clicking, dimensions and the entire screenshot hash must still match. After clicking, a separate image query must transcribe exactly the same question and the visibly selected label. Timers/animations that change the screenshot may trigger conservative pauses. Accessible DOM Next/Submit is still required.

Image readback is a model assertion, so it is weaker evidence than native checked/value state. The default vision model has not been accuracy-benchmarked in this distribution. See VERIFICATION.md for testing boundaries.

## Deliberate boundaries

This program assists the applicant; it does not evaluate or rank applicants for an employer. It does not discover jobs, create accounts, fill unrelated applications, take over the entire desktop, bypass bot detection, or impersonate personal history. Site-specific adapters can be added after creating regression fixtures and tests. Do not add force-clicks, arbitrary model-generated JavaScript or repeated server submissions as generic recovery mechanisms.
