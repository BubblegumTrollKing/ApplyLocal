# Local data and privacy

ApplyLocal implements no analytics, telemetry or paid API integrations. Its model client accepts HTTP loopback endpoints only, canonicalizes `localhost` to `127.0.0.1`, rejects redirects, ignores proxy environment settings and rejects known cloud-routing model metadata. These measures assume the local server/browser installation is trusted; a compromised local server can lie about where it sends data.

Initial installer, package and model downloads use the internet. Your browser sends entered answers to the employer's website as normal. Local inference sends the current question/options or viewport image to Ollama on this computer. The application does not send the entire stored applicant profile. Ollama/browser behavior is governed by those separately installed applications.

Saved files under `%LOCALAPPDATA%\ApplyLocal`:

| Item | Contains |
| --- | --- |
| `profile.json` | Readable facts and exact saved questionnaire answers |
| `settings.json` | Local endpoints, model names and UI choices |
| `activity.jsonl` and rotated backups | UTC timestamp, event code, verified-answer count and page count |
| `browser-profile/` | Browser-managed persistent cookies, login sessions, history and site data |

Screenshots are kept in memory only; the app does not save them as files. Model messages/reasons, full URLs, question text, answer text, passwords and tokens are excluded from the audit logger. Operating-system swap/crash dumps and other software are outside this guarantee. The desktop window necessarily displays current questions and user input.

The companion browser exposes its debug connection on loopback. Any local process with access to that port may control that browser session. Do not expose it to your network or use this profile for unrelated sensitive browsing. No credentials are copied from your ordinary browser profile.

Use **Open local data & logs** to inspect files. Clear remembered answers in the profile editor, or close ApplyLocal and the companion browser and delete `%LOCALAPPDATA%\ApplyLocal` for a complete reset. Deleting the app folder alone does not delete saved profile data or Ollama model downloads.
