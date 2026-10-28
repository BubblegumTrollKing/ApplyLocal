# Architecture and invariants

## Components

| Module | Responsibility |
| --- | --- |
| `gui.py`, `scrolling.py` | Tk main thread, full-window scrolling, pinned Start/Stop, responsive setup/browser controls, profile editor, progress and rare factual handoffs |
| `engine.py` | Bounded questionnaire state machine; one question/action at a time |
| `browser.py`, `browser_choice.py`, `resources/extract.js` | Structured DOM/accessibility attributes, stable element references, verified mutations and navigation |
| `policy.py` | Human-only, identity, consent, concrete-fact and restricted-step gates |
| `workstyle.py` | Clear professional work-style judgments, clause-local polarity, agreement-scale normalization, correction of clearly contradictory visible answers |
| `local_ai.py`, `decisions.py` | Loopback-only Ollama transport, schema validation, capability checks and cancelable inference wait |
| `vision.py` | Stable viewport capture, visual single-choice extraction, bounded click and independent selected-state readback |
| `storage.py`, `memory.py` | Explicit facts, automatic verified-answer storage, fast paraphrase retrieval, related-answer ranking, atomic saves |
| `audit.py` | Rotating operational event counts without questions/answers/URLs |
| `practice.py` | Loopback-only practice page server |

There is no agent framework or arbitrary tool/code execution facility. Closed choices use a dynamically constrained list of zero-based integer indices. Legacy IDs/labels and irrelevant non-null text fields are normalized against the observed choices before validation; unresolved suggestions use a deterministic enabled-choice fallback. Common interpretable work-style statements use a fast local professional policy before inference or old memory. The policy evaluates matched behavior, nearby negation/adverse modifiers and scale direction; it varies strength by trait. Conflicting clauses, comparisons and unfamiliar meanings are deferred. An unrecognized scale falls back toward neutral; non-scale choices use simple professional cues and finally the first enabled option. It is best effort, not another AI model or a guarantee of correctness. Free text retains a structured answer schema. It cannot choose a browser tab, run code, navigate to URLs or access the filesystem. Page text is untrusted data; prompts say so, and the executor independently enforces permitted choices and steps. Prompt injection and novel restriction wording remain imperfectly detectable, so restrictions are still enforced independently and unsupported forms are watched without blind actions.

## Worker ownership

The Tk thread owns widgets only. One background worker owns all synchronous Playwright objects. A queue carries events and another carries user answers. UI input remains responsive during inference. A `threading.Event` cancels waits; the HTTP request runs in an isolated daemon thread and any late result cannot initiate browser actions. HTTP requests are bounded and do not follow redirects or proxies. Browser operations have short timeouts and check Stop before each mutation. An already-issued browser/network operation cannot be recalled.

## Observe → decide → validate → act → verify

1. Read the selected tab and visible frames. Hidden inputs and hidden frames are excluded. Open shadow roots are traversed; controls are named from native labels, fieldset legends, `aria-labelledby` and `aria-label`.
2. Apply page restrictions before using saved answers or AI. Identity and attestations always hand off. Unknown concrete facts/history/commitments never receive an invented answer. Personality, attitudes, professional preferences and work-style questions are answered with employer-oriented judgment.
3. Preserve existing filled values. Otherwise check the fast work-style policy, then resolve saved answers, explicitly entered facts, an in-flight page batch or a fast equivalent paraphrase. Matching uses locally normalized concepts, compatible choices and scenario context. Less exact matches are supplied as related-answer hints in the same local reasoning call. Factual extrapolation is limited to explicit contact aliases and unambiguous equivalent availability/industry-experience/past-dismissal paraphrases. The whole profile is never sent.
4. Validate returned JSON against a closed schema; reject unsupported kinds, invalid IDs, disabled choices, duplicates and wrong cardinality. Clear work-style statements need no model call. Up to eight unfamiliar choices from one page share a constrained model request with one eight-second budget. Each returned selection is normalized and verified independently, so one corrupt item does not discard the valid others. Closed choices do not use a confidence/classification veto. A malformed suggestion is repaired or replaced by an enabled fallback; it never opens a choice-review request. Vision extraction/verification keeps its stricter confidence gate.
5. Re-observe. The question prompt, option identities/labels, enabled state and current answer must match the observed question. Operate the existing Element handle, not a guessed coordinate or positional selector.
6. Read live selected/value state back and automatically remember verified answers. Stale DOM/control failures get bounded automatic rechecks using the in-flight answer, avoiding another inference call. Previously verified answers changed by later controls are restored automatically up to twice. A cosmetic pixel change is not counted as success.
7. Choose a unique recognized Next/Submit control. Final submission is enabled by default and can be disabled in the GUI. Verify changed semantic question content, a page marker or a completion message. DOM replacements, loading captions and blank interstitials are not completed page transitions. After an unconfirmed click the engine keeps observing automatically until progress or Stop. Error text on a new page is not confused with rejection of the old page. Live native validity takes priority over stale ARIA flags; empty error containers are ignored. Real invalid fields are revisited before navigation; stale banners do not block valid controls. A non-final Next can be retried once only when no document/XHR/fetch/non-GET request was observed, the page and answers are unchanged, the button is ready and the page is stable. Any observed request suppresses retries; Submit is never automatically repeated. Visual transitions are re-observed without a second click.

Stable IDs are per-document WeakMap keys backed by direct DOM Element references. They are not selector strings supplied by a model. A re-render replaces references and therefore fails the stale-state check. IDs can restart on full document navigation; question structure and URL are also compared. A website that repeats exactly the same semantic content without a changing page marker cannot provide dependable transition evidence; click retries are bounded while observation continues, and no uncertain server submission is speculatively repeated.

The loop is limited to 150 pages and 1,000 attempted actions. Pure waiting/rechecking is cancelable and has no manual acknowledgment requirement. No persistent automatic resume is attempted after a crash or reboot; the current browser state is read from scratch when the user starts again. Already-filled controls are preserved. Saved facts/answers survive restarts.

## Visual fallback

The initial implementation supports precisely one visible single-choice question, not arbitrary computer control. The model transcribes choices and CSS-pixel click centers from a viewport screenshot. Duplicate/empty labels, coordinates out of bounds or uncertain extraction prevent clicks and trigger continued observation; restrictions are respected. Before clicking, dimensions and the entire screenshot hash must still match. After clicking, a separate image query must transcribe exactly the same question and the visibly selected label. Timers/animations that change the screenshot may defer a click until a later stable observation. Accessible DOM Next/Submit is still required.

Image readback is a model assertion, so it is weaker evidence than native checked/value state. The default vision model has not been accuracy-benchmarked in this distribution. See VERIFICATION.md for testing boundaries.

## Deliberate boundaries

This program assists the applicant; it does not evaluate or rank applicants for an employer. It does not discover jobs, create accounts, fill unrelated applications, take over the entire desktop, bypass bot detection, or impersonate personal history. Site-specific adapters can be added after creating regression fixtures and tests. Do not add force-clicks, arbitrary model-generated JavaScript or repeated server submissions as generic recovery mechanisms.

## Browser selection and existing sessions

The GUI can launch installed Chrome/Edge/Brave/Chromium or a chosen executable. Existing mode reads only the selected browser data directory’s DevToolsActivePort file, validates a literal-loopback WebSocket endpoint, then uses the same Playwright CDP worker. Chrome 144+ can publish this endpoint after the user enables Remote Debugging in chrome://inspect/#remote-debugging; Chrome must approve the incoming connection itself. No extension, cookie copying, paid API, Node installation or MCP server is required. Standard local CDP addresses remain supported. Tests launch an independent browser with a persistent test profile, discover its real ephemeral endpoint, complete its existing tab, disconnect and verify the tab stays open. The Chrome 144+ permission dialog itself is not covered by that controlled fixture.

## Requests that remain

Only unknown concrete applicant facts and explicitly requested final review use the GUI answer queue. Fact requests poll every 350 ms while keeping their widgets intact; filling the field or moving to a new page in the browser dismisses the request automatically. Request IDs reject stale replies from previous questions. Sign-in/identity/consent operations are observed without asking the user to press a recheck button. A human-only restriction stops the run. Operational exceptions log a status and recheck instead of invoking the answer UI.

## Work-style corrections and migration

Agreement scales are interpreted by label meaning and relative strength rather than control position. Three/five/seven-option unlabeled scales may be named only when visible Agree/Disagree endpoints unambiguously bracket their DOM positions. The extractor recognizes statement captions and can operate a hidden native radio through its visible associated label, with normal selected-state readback. Scale direction is never invented when endpoints/labels provide no evidence.

The local professional policy includes reliability, organization, attention to detail, openness, evidence-based judgment, sociability, cooperation, respect, integrity, composure, feedback and safety. “Struggle with deadlines” has negative direction; “never miss deadlines” reverses the negative behavior. This is a declared professional persona, not an assertion about the applicant’s actual biography or an employer’s scoring key. Unknown concrete facts remain gated.

Old automatic scale predictions can encode the former default-to-agreement bug. Profile migration removes those legacy nonfactual scale records unless marked as explicit user answers, keeps factual data, and backs up the original JSON before saving any changes. New answers record their source and decision policy version. Clearly contradictory visible work-style selections are corrected; the agent does not navigate backwards through already completed pages to rewrite unseen answers.

Whole-window scrolling is independent of nested option/log controls. Wheel events route to an inner scroller when it can move and chain to the outer canvas at its limits. Browser dropdown wheel events scroll the window without changing the selected browser. Start/Stop live in a separate grid row and remain reachable. Native source/frozen smoke checks assert the reported three-item polarity and window scroll/Stop behavior at 660×440.
