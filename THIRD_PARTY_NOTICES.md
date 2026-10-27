# Third-party software and model notices

ApplyLocal's own code is MIT-licensed; see LICENSE. Installed dependencies retain their upstream licenses. This source archive does not contain browser executables, model weights or an Ollama installer.

| Component | Upstream / license |
| --- | --- |
| Python | https://www.python.org/ — Python Software Foundation License |
| Tk / Tcl | https://www.tcl.tk/ — Tcl/Tk license (BSD-style) |
| Playwright Python and driver | https://github.com/microsoft/playwright-python — Apache-2.0 |
| Node.js bundled with Playwright | https://github.com/nodejs/node — MIT and bundled dependency notices |
| jsonschema | https://github.com/python-jsonschema/jsonschema — MIT |
| attrs | https://github.com/python-attrs/attrs — MIT |
| jsonschema-specifications | https://github.com/python-jsonschema/jsonschema-specifications — MIT |
| referencing | https://github.com/python-jsonschema/referencing — MIT |
| rpds-py | https://github.com/crate-py/rpds — MIT |
| pyee | https://github.com/jfhbrook/pyee — MIT |
| greenlet | https://github.com/python-greenlet/greenlet — MIT / PSF |
| typing_extensions | https://github.com/python/typing_extensions — PSF-2.0 |
| PyInstaller (build tool) | https://pyinstaller.org/ — GPL with exception permitting distribution of bundled applications under their chosen license |
| Ollama (separate installation) | https://github.com/ollama/ollama — MIT and its upstream third-party notices |
| Qwen2.5 7B (separate download) | https://ollama.com/library/qwen2.5:7b — Apache-2.0 |
| Qwen3-VL 4B (separate download) | https://ollama.com/library/qwen3-vl:4b — Apache-2.0 |

Chrome and Edge are separately installed browsers with their own terms. Chromium is used only for automated tests unless a developer chooses to configure it. Users of a packaged binary should retain its generated `licenses/` folder containing the installed distributions' license/notice files alongside this summary. The build script/workflow generates that folder before packaging. Model licenses are available in their Ollama model metadata and linked model pages; changing models may change license terms.
