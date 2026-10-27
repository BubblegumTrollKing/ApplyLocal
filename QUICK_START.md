# Start here

## With a Windows executable

1. Extract the entire portable ZIP. Open `ApplyLocal.exe`.
2. Click **1 Install Ollama**, complete its installer, start Ollama and restart ApplyLocal.
3. Click **2 Download local models**. This downloads several GB once. Then click **Check setup**.
4. Open **Your facts & saved answers** if you want to enter your real name/contact details. Leave unknown facts blank.
5. Choose your browser. For your existing Chrome 144+ session, select **Use my open browser**, click **Enable browser access**, enable Remote Debugging, then **Refresh tabs** and Allow Chrome’s connection prompt. If that feature is unavailable, choose **Companion profile** and **Open browser**.
6. Click **Try practice questionnaire**. Select its tab and click **Start selected questionnaire**. The practice stays on your computer.
7. For real use, open the employment questionnaire in that same browser. Click **Refresh tabs**, choose its tab, and **Start selected questionnaire**.

The agent automatically chooses employer-oriented responses for general knowledge, workplace situations, personality, work-style and Likert questions. Verified answers are remembered automatically and reused for paraphrases and related questions. There is no remember checkbox. Automatic submission is enabled by default; clear its checkbox if you prefer a final review.

Only an unknown concrete fact or commitment needs your answer, such as an email address, qualification or actual availability. Choose it once and use **Use this answer and continue**; it is saved automatically. Entering contact details in **Your facts & saved answers** avoids those prompts.

For sign-in, CAPTCHA, identity verification, signatures, consent and explicitly human-only assessments, work directly in the browser. The app detects browser changes automatically; there is no recheck button. If the whole assessment requires human-only work, complete the whole assessment yourself and stop the agent.

**STOP or Esc (with ApplyLocal focused) stops new actions.** A click already sent may finish. Leave the selected tab untouched while the agent runs. The browser remains open when the agent disconnects.

## If you downloaded a source archive

To run it now on Windows, install Python 3.12 with the Python launcher and double-click `Run-From-Source.bat`.

For a ready-to-run executable, use the Windows download in the repository's Releases section. Source archives intentionally do not contain compiled binaries. The included Actions workflow tests and publishes Windows builds, and README.md explains how to build your own. You do not need Python to run the built executable.

## If something stops

| Message / symptom | What to do |
| --- | --- |
| Cannot connect to browser | Use Open browser; wait for its window; Refresh tabs. |
| Cannot get valid response from Ollama | Start Ollama; Download local models; Check setup. |
| Existing browser tab missing | Select Use my open browser; enable browser access; Refresh tabs and Allow. If no debugging endpoint is available, use the companion profile. |
| Question needs your facts | Provide the real value once; it is remembered automatically. Personality questions should be automatic. |
| Validation message | The agent reads the live fields, fills new-page required inputs and continues automatically. Stale warnings alone do not stop it. |
| Navigation is taking longer | Keep waiting: the agent rechecks automatically and resumes on a confirmed page change. It can retry a no-effect Next once if no request was observed. It never repeats Submit. It keeps watching until the page changes or you press Stop. |
| Covered/replaced control | Automatic rechecks try to recover first. A persistently unsupported control is watched for manual browser changes without a blocking recheck dialog. |
| Local model is slow | Keep waiting or Stop; close memory-heavy apps; disable vision if you do not need it. |
| No Next/Submit found | The app keeps watching and rechecking automatically. Visual-only navigation remains unsupported. |

Your saved facts are readable files in your Windows user folder. **Open local data & logs** shows them. Do not share that folder or your companion browser profile with others.

If the model gives an unusable choice or none is ideal, the app chooses an enabled best-effort option automatically. A closed-choice decision uses one compact model call with an eight-second budget; no review prompt is opened for low confidence or bad answer formatting. Real missing facts are not invented.
