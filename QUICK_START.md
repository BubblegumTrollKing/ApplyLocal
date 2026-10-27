# Start here

## With a Windows executable

1. Extract the entire portable ZIP. Open `ApplyLocal.exe`.
2. Click **1 Install Ollama**, complete its installer, start Ollama and restart ApplyLocal.
3. Click **2 Download local models**. This downloads several GB once. Then click **Check setup**.
4. Open **Your facts & saved answers** if you want to enter your real name/contact details. Leave unknown facts blank.
5. Click **Open browser**. This opens a separate Chrome/Edge profile. Sign in there if necessary.
6. Click **Try practice questionnaire**. Select its tab and click **Start selected questionnaire**. The practice stays on your computer.
7. For real use, open the employment questionnaire in that same browser. Click **Refresh tabs**, choose its tab, and **Start selected questionnaire**.

The agent handles clear general-knowledge and hypothetical workplace questions. If it needs a personal answer, choose it in the desktop window and click **Use this answer and continue**. Remembering an answer is optional. The final submission asks for review by default; the automatic-submit checkbox enables unattended submission for pages without consent/identity requirements.

For sign-in, CAPTCHA, identity verification, signatures, consent and explicitly human-only assessments, work directly in the browser. After a manual step, use **I handled it in the browser — recheck**. If the whole assessment requires human-only work, complete the whole assessment yourself and stop the agent.

**STOP or Esc (with ApplyLocal focused) stops new actions.** A click already sent may finish. Leave the selected tab untouched while the agent runs. The browser remains open when the agent disconnects.

## If you downloaded a source archive

To run it now on Windows, install Python 3.12 with the Python launcher and double-click `Run-From-Source.bat`.

For a ready-to-run executable, use the Windows download in the repository's Releases section. Source archives intentionally do not contain compiled binaries. The included Actions workflow tests and publishes Windows builds, and README.md explains how to build your own. You do not need Python to run the built executable.

## If something stops

| Message / symptom | What to do |
| --- | --- |
| Cannot connect to browser | Use Open browser; wait for its window; Refresh tabs. |
| Cannot get valid response from Ollama | Start Ollama; Download local models; Check setup. |
| Old ordinary browser tab missing | Copy its URL to the companion browser and sign in there. |
| Question needs your facts | Provide your true answer; optionally remember it. |
| Validation error | Correct the form in the browser, then recheck. |
| Navigation unconfirmed | Inspect the page. Navigate manually; the agent will not resend the same page automatically. |
| Covered/unsupported control | Use the control yourself, then recheck. |
| Local model is slow | Keep waiting or Stop; close memory-heavy apps; disable vision if you do not need it. |
| No Next/Submit found | Navigate manually, then recheck. Visual-only Next/Submit is not automated. |

Your saved facts are readable files in your Windows user folder. **Open local data & logs** shows them. Do not share that folder or your companion browser profile with others.
