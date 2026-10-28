from __future__ import annotations

from dataclasses import replace
import os
from pathlib import Path
import queue
import re
import subprocess
import threading
import time
import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk
import webbrowser

from . import __version__
from .audit import Audit
from .browser import BrowserSession, launch_browser
from .browser_choice import (BROWSERS, browser_executable, connection_endpoint,
                             local_browser_endpoint, open_debug_settings)
from .domain import Answer, AssistanceRequired, Stopped
from .engine import Engine, UserReply
from .local_ai import LocalAI, loopback_url
from .storage import ALIASES, Profile, Settings, data_directory
from .scrolling import ScrollableFrame


class Application(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"ApplyLocal {__version__} · automatic questionnaire assistant")
        self.geometry(f"{min(1000, self.winfo_screenwidth()-80)}x{min(800, self.winfo_screenheight()-80)}")
        self.minsize(620, 360)
        self.folder = data_directory()
        self.audit = Audit(self.folder / "activity.jsonl")
        try:
            self.settings = Settings.load(self.folder / "settings.json")
            self.profile = Profile.load(self.folder / "profile.json")
        except (OSError, ValueError, TypeError):
            messagebox.showerror("Settings could not be read", "A settings/profile file is invalid. "
                                 "It has not been overwritten. Open the data folder to repair or rename it.")
            self.settings, self.profile = Settings(), Profile()
        self.stop_event = threading.Event()
        self.messages = queue.Queue()
        self.replies = queue.Queue()
        self.worker = None
        self._closing = False
        self.tabs = []
        self.request = None
        self._worker_request_id = None
        self._busy_widgets = []
        self._build()
        self.bind("<Escape>", lambda event: self.stop())
        self.protocol("WM_DELETE_WINDOW", self.shutdown)
        self._poll_id = self.after(100, self.poll)

    def _build(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TButton", padding=7)
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)
        self.scroll_host = ScrollableFrame(self)
        self.scroll_host.grid(row=0, column=0, sticky="nsew")
        outer = self.scroll_host.content
        self._wrap_labels = []
        def wrap_label(parent, **kwargs):
            label = ttk.Label(parent, wraplength=540, justify="left", **kwargs)
            self._wrap_labels.append(label)
            return label
        def resize_labels(event):
            for label in self._wrap_labels:
                label.configure(wraplength=max(220, event.width-70))
        outer.bind('<Configure>', resize_labels, add='+')
        ttk.Label(outer, text="ApplyLocal", font=("Segoe UI", 24, "bold")).pack(anchor="w")
        wrap_label(outer, text="Free local AI · automatic answers and memory · automatic page rechecks").pack(fill="x", pady=(0, 12))

        self.setup_section = ttk.Frame(outer)
        self.setup_section.pack(fill="x")
        setup = ttk.LabelFrame(self.setup_section, text="One-time setup", padding=10)
        setup.pack(fill="x")
        for index, (title, command) in enumerate([("1  Install Ollama", lambda: webbrowser.open("https://ollama.com/download/windows")),
                               ("2  Download local models", self.download_models),
                               ("Check setup", self.check_setup), ("Your facts & saved answers", self.edit_profile)]):
            b = ttk.Button(setup, text=title, command=command)
            b.grid(row=index//2, column=index%2, sticky="ew", padx=3, pady=3)
            self._busy_widgets.append(b)
        setup.columnconfigure((0, 1), weight=1)
        wrap_label(self.setup_section, text="Models download several GB once. Common work-style answers run instantly; unfamiliar questions use local AI.").pack(fill="x", pady=(5, 10))

        browser = ttk.LabelFrame(outer, text="Browser connection", padding=10)
        self.browser_section = browser
        browser.pack(fill="x")
        modes = ttk.Frame(browser)
        modes.pack(fill="x", pady=(0, 6))
        self.browser_name = tk.StringVar(value=self.settings.browser_name)
        self.connection_mode = tk.StringVar(value=self.settings.connection_mode)
        picker = ttk.Combobox(modes, textvariable=self.browser_name,
                              values=["Automatic", *BROWSERS], state="readonly", width=18)
        picker.grid(row=0, column=0, sticky="ew", padx=3)
        self.browser_picker = picker
        for sequence in ('<MouseWheel>', '<Button-4>', '<Button-5>'):
            picker.bind(sequence, self.scroll_host._wheel)
        self._busy_widgets.append(picker)
        for index, (label, mode) in enumerate([("Use my open browser", "existing"), ("Companion profile", "companion")]):
            control = ttk.Radiobutton(modes, text=label, variable=self.connection_mode, value=mode)
            control.grid(row=1, column=index, sticky="w", padx=3, pady=6)
            self._busy_widgets.append(control)
        debug_setup = ttk.Button(modes, text="Enable browser access", command=self.enable_browser_access)
        debug_setup.grid(row=0, column=1, sticky="ew", padx=3)
        modes.columnconfigure((0, 1), weight=1)
        self._busy_widgets.append(debug_setup)
        row = ttk.Frame(browser)
        row.pack(fill="x")
        for index, (title, command) in enumerate([("Open browser", self.open_browser), ("Refresh tabs", self.refresh_tabs),
                               ("Try practice questionnaire", self.practice)]):
            b = ttk.Button(row, text=title, command=command)
            b.grid(row=index//2, column=index%2, sticky="ew", padx=3, pady=3)
            self._busy_widgets.append(b)
        row.columnconfigure((0, 1), weight=1)
        self.tab_choice = ttk.Combobox(browser, state="readonly")
        for sequence in ('<MouseWheel>', '<Button-4>', '<Button-5>'):
            self.tab_choice.bind(sequence, self.scroll_host._wheel)
        self.tab_choice.pack(fill="x", pady=(8, 0))
        wrap_label(browser, text="To use an existing Chrome 144+ session, enable browser access and allow Chrome’s connection prompt. Then Refresh tabs.").pack(fill="x", pady=(6, 0))

        options = ttk.Frame(outer)
        options.pack(fill="x", pady=10)
        self.use_vision = tk.BooleanVar(value=self.settings.vision)
        self.auto_submit = tk.BooleanVar(value=self.settings.auto_submit)
        for index, (label, variable) in enumerate([("Use local vision for unfamiliar layouts", self.use_vision),
                                ("Submit automatically (consents still require you)", self.auto_submit)]):
            w = ttk.Checkbutton(options, text=label, variable=variable)
            w.grid(row=index, column=0, sticky="w", pady=3)
            self._busy_widgets.append(w)
        advanced = ttk.Button(options, text="Settings", command=self.advanced)
        advanced.grid(row=2, column=0, sticky="w", pady=(5, 0))
        options.columnconfigure(0, weight=1)
        self._busy_widgets.append(advanced)

        run = ttk.Frame(self, padding=(18, 8))
        run.grid(row=1, column=0, sticky="ew")
        self.run_bar = run
        self.start_button = ttk.Button(run, text="Start selected questionnaire", command=self.start)
        self.start_button.pack(side="left")
        self._busy_widgets.append(self.start_button)
        self.stop_button = tk.Button(run, text="STOP  (Esc)", command=self.stop, bg="#b52626", fg="white",
                  activebackground="#851a1a", font=("Segoe UI", 12, "bold"), padx=22, pady=5)
        self.stop_button.pack(side="right")
        self.progress = ttk.Progressbar(outer, mode="indeterminate")
        self.progress.pack(fill="x", pady=(10, 4))
        self.status = tk.StringVar(value="Ready. Install Ollama and download the models once, then open the browser.")
        wrap_label(outer, textvariable=self.status).pack(fill="x")
        self.counts = tk.StringVar(value="0 verified answers · page 1")
        ttk.Label(outer, textvariable=self.counts).pack(anchor="w", pady=(2, 8))

        self.help_frame = ttk.LabelFrame(outer, text="Your input", padding=10)
        self.help_frame.pack(fill="x")
        self.help_message = wrap_label(self.help_frame, text="Workplace and personality answers are automatic and remembered. Only missing facts or restricted steps need you.")
        self.help_message.pack(fill="x")
        self.answer_frame = ttk.Frame(self.help_frame)
        self.answer_frame.pack(fill="x")
        self.log = scrolledtext.ScrolledText(outer, height=6, width=1, state="disabled", font=("Consolas", 10))
        self.log.pack(fill="both", expand=True, pady=(10, 5))
        footer = ttk.Frame(outer)
        footer.pack(fill="x")
        self.data_button = ttk.Button(footer, text="Open local data & logs", command=self.open_data)
        self.data_button.pack(anchor="w", pady=5)
        wrap_label(footer, text="Stop prevents new actions; a click already sent may finish. Do not edit the tab while running.").pack(fill="x")

    def emit(self, event):
        self.messages.put(("event", event))

    def busy(self, value):
        for widget in self._busy_widgets:
            widget.configure(state="disabled" if value else "normal")
        self.tab_choice.configure(state="disabled" if value else "readonly")
        self.browser_picker.configure(state="disabled" if value else "readonly")
        if value:
            self.setup_section.pack_forget()
            self.progress.start(15)
        else:
            self.setup_section.pack(fill="x", before=self.browser_section)
            self.progress.stop()

    def background(self, task):
        if self.worker and self.worker.is_alive():
            return
        self.stop_event = threading.Event()
        self.busy(True)

        def work():
            try:
                task()
            except Stopped:
                self.emit({"code": "stopped", "message": "Stopped. No further browser actions will be started."})
            except AssistanceRequired as exc:
                self.emit({"code": "error", "message": str(exc)})
            except Exception as exc:
                # No tracebacks containing page data in ordinary user logs.
                self.emit({"code": "error", "message": f"Operation stopped ({type(exc).__name__}). Check setup and the selected tab, then try again."})
            finally:
                self.messages.put(("idle", None))

        self.worker = threading.Thread(target=work, daemon=True)
        self.worker.start()

    def persist_settings(self):
        self.settings.vision = self.use_vision.get()
        self.settings.auto_submit = self.auto_submit.get()
        self.settings.browser_name = self.browser_name.get()
        self.settings.connection_mode = self.connection_mode.get()
        self.settings.save(self.folder / "settings.json")

    def open_browser(self):
        self.persist_settings()
        try:
            if self.settings.connection_mode == "existing":
                self.refresh_tabs()
                return
            port = int(self.settings.endpoint.rsplit(":", 1)[1])
            launch_browser(self.folder / "browser-profile", port,
                           executable=browser_executable(self.settings.browser_name,
                                                         self.settings.browser_executable))
            self.status.set("Browser opening. Sign in and open the assessment there, then Refresh tabs.")
        except (AssistanceRequired, OSError, ValueError) as exc:
            messagebox.showerror("Browser", str(exc))

    def enable_browser_access(self):
        self.persist_settings()
        try:
            open_debug_settings(self.settings.browser_name, self.settings.browser_executable)
            self.connection_mode.set("existing")
            self.persist_settings()
            self.status.set("Enable Remote Debugging in your browser, then Refresh tabs and allow the browser's connection prompt.")
        except (AssistanceRequired, OSError) as exc:
            messagebox.showerror("Browser access", str(exc))

    def refresh_tabs(self):
        def task():
            browser = BrowserSession(self.stop_event)
            try:
                browser.connect(connection_endpoint(self.settings))
                self.messages.put(("tabs", browser.tabs()))
            finally:
                browser.close()
        self.background(task)

    def check_setup(self):
        self.persist_settings()
        def task():
            ai = LocalAI(self.settings.ollama, self.stop_event)
            ai.check_model(self.settings.text_model)
            if self.settings.vision:
                ai.check_model(self.settings.vision_model, vision=True)
            self.emit({"code": "setup", "message": "Local models are installed and expose the required capabilities. Ready to open the browser."})
        self.background(task)

    def download_models(self):
        self.persist_settings()
        # Ollama's own installer supplies this executable. Never invoke a shell.
        import shutil
        executable = shutil.which("ollama")
        if not executable:
            candidate = Path(os.environ.get("LOCALAPPDATA", "")) / "Programs/Ollama/ollama.exe"
            if candidate.is_file():
                executable = str(candidate)
        if not executable:
            messagebox.showinfo("Install Ollama first", "Use Install Ollama, finish its installer, and restart ApplyLocal. No account or subscription is needed.")
            return
        models = [self.settings.text_model]
        if self.settings.vision:
            models.append(self.settings.vision_model)
        if any(not re.fullmatch(r"[A-Za-z0-9_./:-]{1,160}", m) or "cloud" in m.lower() for m in models):
            messagebox.showerror("Model name", "Use local model names without spaces or cloud tags.")
            return
        def task():
            for model in dict.fromkeys(models):
                self.emit({"code": "download", "message": f"Downloading {model}. This can take several minutes; completed data can be reused after Stop."})
                env = dict(os.environ, OLLAMA_HOST=loopback_url(self.settings.ollama), OLLAMA_NO_CLOUD="1")
                proc = subprocess.Popen([executable, "pull", model], env=env,
                                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
                while proc.poll() is None:
                    if self.stop_event.wait(0.1):
                        proc.terminate()
                        try:
                            proc.wait(timeout=2)
                        except subprocess.TimeoutExpired:
                            proc.kill()
                        raise Stopped()
                if proc.returncode:
                    raise AssistanceRequired("The model download failed. Ensure Ollama is running and the internet is connected, then retry.")
            self.emit({"code": "setup", "message": "Models downloaded. Use Check setup to verify them."})
        self.background(task)

    def start(self):
        selected = self.tab_choice.current()
        if selected < 0 or selected >= len(self.tabs):
            messagebox.showinfo("Choose a tab", "Open the companion browser, refresh tabs, and select your questionnaire.")
            return
        target_id = self.tabs[selected]["id"]
        self.persist_settings()
        self.replies = queue.Queue()
        self._worker_request_id = None
        settings = replace(self.settings)
        def task():
            browser = BrowserSession(self.stop_event)
            try:
                browser.connect(connection_endpoint(settings))
                browser.select(target_id)
                ai = LocalAI(settings.ollama, self.stop_event)
                Engine(browser, ai, settings, self.profile, self.stop_event, self.emit,
                       self.ask, lambda: self.profile.save(self.folder / "profile.json")).run()
            finally:
                browser.close()
        self.background(task)

    def ask(self, request):
        request_id = request.get("request_id", "")
        if self._worker_request_id != request_id:
            self.messages.put(("ask", request))
            self._worker_request_id = request_id
        duration = request.get("poll_seconds")
        deadline = time.monotonic() + duration if duration is not None else float("inf")
        while not self.stop_event.is_set():
            try:
                response = self.replies.get(timeout=0.05)
                if not request_id or response.request_id == request_id:
                    return response
            except queue.Empty:
                pass
            if time.monotonic() >= deadline:
                return None
        raise Stopped()

    def show_request(self, request):
        self.request = request
        self.progress.stop()
        for child in self.answer_frame.winfo_children():
            child.destroy()
        question = request["question"]
        self.help_message.configure(text=request["message"] + ("\n" + question.prompt if question else ""))
        if question:
            choice = tk.StringVar(value="")
            checks = {}
            if question.options:
                # Scrollable area for long option lists.
                area = ttk.Frame(self.answer_frame)
                area.pack(fill="x", pady=5)
                canvas = tk.Canvas(area, height=min(150, 30 * len(question.options)), highlightthickness=0)
                bar = ttk.Scrollbar(area, orient="vertical", command=canvas.yview)
                canvas.configure(yscrollcommand=bar.set)
                bar.pack(side="right", fill="y")
                canvas.pack(side="left", fill="both", expand=True)
                content = ttk.Frame(canvas)
                canvas.create_window((0, 0), window=content, anchor="nw")
                content.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
                for option in question.options:
                    if question.kind == "checkbox":
                        checks[option.id] = tk.BooleanVar(value=option.selected)
                        widget = ttk.Checkbutton(content, text=option.label, variable=checks[option.id])
                    else:
                        widget = ttk.Radiobutton(content, text=option.label, variable=choice, value=option.id)
                    widget.pack(anchor="w", pady=2)
                    if option.disabled:
                        widget.configure(state="disabled")
            else:
                ttk.Entry(self.answer_frame, textvariable=choice).pack(fill="x", pady=5)
            ttk.Label(self.answer_frame, text="Answers are remembered automatically on this computer and used for related questions.", wraplength=460).pack(anchor="w")
            def send():
                ids = tuple(k for k, v in checks.items() if v.get()) if checks else ((choice.get(),) if choice.get() else ())
                answer = Answer(ids if question.options else (), None if question.options else choice.get(), "user")
                from .domain import validate_answer
                try:
                    validate_answer(question, answer)
                except AssistanceRequired as exc:
                    messagebox.showinfo("Answer needed", str(exc))
                    return
                self.reply(UserReply(answer))
            ttk.Button(self.answer_frame, text="Use this answer and continue", command=send).pack(side="left", pady=5)
        elif request["submit"]:
            ttk.Button(self.answer_frame, text="Submit this questionnaire", command=lambda: self.reply(UserReply(proceed=True))).pack(side="left", pady=5)
        ttk.Label(self.answer_frame, text="Browser changes are detected automatically; no recheck button is needed.", wraplength=460).pack(anchor="w", pady=5)
        self.scroll_host.reveal(self.help_frame)

    def reply(self, response):
        if self.request is None:
            return
        response.request_id = self.request.get("request_id", "")
        self.request = None
        for child in self.answer_frame.winfo_children():
            child.destroy()
        self.help_message.configure(text="Continuing…")
        self.replies.put(response)
        self.progress.start(15)

    def stop(self):
        self.stop_event.set()
        self.status.set("Stopping. No new actions will start; an action already sent may finish.")
        self.request = None
        for child in self.answer_frame.winfo_children():
            child.destroy()

    def poll(self):
        try:
            while True:
                kind, value = self.messages.get_nowait()
                if kind == "event":
                    if value["code"] == "input_resolved":
                        if self.request and self.request.get("request_id") == value.get("request_id"):
                            self.request = None
                            for child in self.answer_frame.winfo_children():
                                child.destroy()
                            self.progress.start(15)
                        if self._worker_request_id == value.get("request_id"):
                            self._worker_request_id = None
                    self.audit.record(value)
                    self.status.set(value["message"])
                    if "answered" in value:
                        self.counts.set(f"{value['answered']} verified answers · page {value['pages']}")
                    self.log.configure(state="normal")
                    self.log.insert("end", time.strftime("%H:%M:%S ") + value["message"] + "\n")
                    self.log.see("end")
                    self.log.configure(state="disabled")
                elif kind == "tabs":
                    self.tabs = value
                    self.tab_choice["values"] = [f"{t['title'] or 'Untitled'} — {t['url'].split('?')[0][:100]}" for t in value]
                    if value:
                        self.tab_choice.current(len(value) - 1)
                    self.status.set(f"Found {len(value)} tabs. Choose the questionnaire tab and Start.")
                elif kind == "ask" and not self.stop_event.is_set():
                    self.show_request(value)
                elif kind == "idle":
                    self.busy(False)
                    self.request = None
                    for child in self.answer_frame.winfo_children():
                        child.destroy()
        except queue.Empty:
            pass
        if not self._closing:
            self._poll_id = self.after(100, self.poll)

    def scroll_dialog(self, title):
        dialog = tk.Toplevel(self)
        dialog.title(title)
        dialog.transient(self)
        dialog.grab_set()
        dialog.geometry(f"{min(720,self.winfo_screenwidth()-100)}x{min(650,self.winfo_screenheight()-100)}")
        dialog.minsize(480, 320)
        dialog.rowconfigure(0, weight=1)
        dialog.columnconfigure(0, weight=1)
        host = ScrollableFrame(dialog)
        host.grid(row=0, column=0, sticky='nsew')
        footer = ttk.Frame(dialog, padding=(18,8))
        footer.grid(row=1, column=0, sticky='ew')
        dialog.scroll_host = host
        return dialog, host.content, footer

    def edit_profile(self):
        dialog, body, footer = self.scroll_dialog("Your facts and saved answers")
        body.columnconfigure(1, weight=1)
        note = ttk.Label(body, text="Only enter true facts. Blank fields will be asked when needed.\nThese facts are stored as readable text in your Windows user folder.", wraplength=580)
        note.grid(row=0, column=0, columnspan=2, sticky='ew', pady=(0,10))
        body.bind('<Configure>', lambda e: note.configure(wraplength=max(200,e.width-40)), add='+')
        entries = {}
        for row, field in enumerate(ALIASES, 1):
            ttk.Label(body, text=field.replace("_", " ").title()).grid(row=row, column=0, padx=(0,12), pady=3, sticky="w")
            value = tk.StringVar(value=self.profile.facts.get(field, ""))
            ttk.Entry(body, textvariable=value, width=1).grid(row=row, column=1, pady=3, sticky='ew')
            entries[field] = value
        row = len(entries) + 1
        ttk.Label(body, text=f"{len(self.profile.answers)} answers saved automatically for reuse and related-question reasoning.", wraplength=400).grid(row=row, column=0, columnspan=2, pady=8, sticky='ew')
        def save():
            try:
                self.profile.facts = {k: v.get().strip() for k, v in entries.items() if v.get().strip()}
                self.profile.save(self.folder / "profile.json")
            except OSError:
                messagebox.showerror("Save failed", "Your facts could not be saved.")
                return
            dialog.destroy()
        def clear():
            if messagebox.askyesno("Clear saved answers", "Remove all remembered question answers? Your facts above are kept."):
                self.profile.answers.clear()
                self.profile.answer_sources.clear()
                self.profile.save(self.folder / "profile.json")
                dialog.destroy()
        ttk.Button(footer, text="Save", command=save).pack(side='left')
        ttk.Button(footer, text="Clear remembered answers", command=clear).pack(side='right')

    def advanced(self):
        dialog, body, footer = self.scroll_dialog("Local settings")
        body.columnconfigure(0, weight=1)
        entries = {}
        labels = {"endpoint": "Browser debugging address", "ollama": "Local Ollama address",
                  "text_model": "Text model", "vision_model": "Vision model",
                  "browser_executable": "Browser executable (optional)",
                  "browser_profile": "Existing browser data folder (optional)"}
        for row, (key, label) in enumerate(labels.items()):
            ttk.Label(body, text=label).grid(row=2*row, column=0, pady=(8,3), sticky="w")
            var = tk.StringVar(value=getattr(self.settings, key))
            ttk.Entry(body, textvariable=var, width=1).grid(row=2*row+1, column=0, sticky='ew')
            entries[key] = var
        def save():
            try:
                local_browser_endpoint(entries["endpoint"].get())
                loopback_url(entries["ollama"].get())
                for key, var in entries.items():
                    setattr(self.settings, key, var.get().strip())
                self.settings.save(self.folder / "settings.json")
                dialog.destroy()
            except (OSError, ValueError) as exc:
                messagebox.showerror("Settings", str(exc))
        ttk.Button(footer, text="Save", command=save).pack(side='right')

    def practice(self):
        from .practice import practice_url
        url = practice_url()
        self.persist_settings()
        def task():
            browser = BrowserSession(self.stop_event)
            try:
                browser.connect(connection_endpoint(self.settings))
                browser.browser.contexts[0].new_page().goto(url)
                self.messages.put(("tabs", browser.tabs()))
            finally:
                browser.close()
        self.background(task)

    def open_data(self):
        if os.name == "nt":
            os.startfile(self.folder)
        else:
            webbrowser.open(self.folder.as_uri())

    def shutdown(self):
        if self._closing:
            return
        self._closing = True
        self.after_cancel(self._poll_id)
        self.stop_event.set()
        self.audit.close()
        self.destroy()
