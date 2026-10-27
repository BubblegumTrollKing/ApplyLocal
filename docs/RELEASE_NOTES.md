ApplyLocal 1.1.0 — automatic judgment, memory and recovery.

Download **ApplyLocal-Windows-x64.zip**, extract it, and run **ApplyLocal.exe**. Python is bundled. Your existing local models and saved data are reused; no new model download is required when upgrading from 1.0.0.

- Answers personality, work-style and Likert questions automatically using the response a reasonable employer would prefer. Subjectivity alone no longer asks you to answer.
- Automatically reviews uncertain/misclassified model decisions and chooses a valid best-fit response when possible.
- Automatically remembers verified answers. Equivalent paraphrases reuse answers without inference; relevant related answers guide the same AI call. No remember checkbox.
- Automatically rechecks interrupted/late navigation, recovers stale controls, and restores lost answers. A no-effect Next with no observed request can be retried once. Submit is never repeated automatically.
- Automatic submission is enabled by default, including migration from the old unversioned defaults. You can turn it off for final review. Identity, consent, human-only restrictions and unknown concrete facts remain protected.

This release is published only after the full Windows automated suite, source GUI test and frozen executable GUI/browser checks pass. **ApplyLocal-test-evidence.zip** contains the actual results, build information and binary checksum. The application is unsigned.

Real Ollama answer accuracy and compatibility with live employer sites are not established by the controlled automated suite. Employer scoring varies. Models and live sites still require real-world testing. The browser stays open when the agent stops.
