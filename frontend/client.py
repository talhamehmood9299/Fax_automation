"""
Tkinter client that talks to the FastAPI server for Normal and Training flows.

Run server first:
  uvicorn backend.server:app --reload

Then run this client:
  python -m frontend.client
"""

import os
import sys
import time
import threading
import tkinter as tk
from tkinter import ttk, messagebox

import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from shutil import which
import subprocess
import platform
from pathlib import Path

try:
    # When running as a package (python -m frontend.client)
    from .talkehr_agent import TalkEHRBot  # type: ignore
except Exception:
    try:
        # When frozen by PyInstaller or run as a script
        from frontend.talkehr_agent import TalkEHRBot  # type: ignore
    except Exception:
        # Last resort if neither package name is available
        from talkehr_agent import TalkEHRBot  # type: ignore


def _get_settings() -> dict:
    """Return hardcoded client settings (no .env needed)."""
    return {
        "API_BASE_URL": "https://aa4af14f7f47.ngrok.app/",
        "DEBUGGER_ADDRESS": "localhost:9222",
        "SLEEP_BETWEEN_OK_RUNS": 3,
    }


def _discover_chromedriver() -> str | None:
    """Find chromedriver from the build directory or next to the binary.

    Priority:
    1) Same directory as the packaged binary (PyInstaller)
    2) Dist build directory in the repo (…/dist/chromedriver)
    3) Current working directory
    4) Project root and frontend/ directory
    5) chromedriver on PATH (fallback)

    Note: Intentionally ignores any CHROMEDRIVER_PATH from .env.
    """
    exe_name = "chromedriver.exe" if os.name == "nt" else "chromedriver"

    candidates: list[str] = []

    # 1) Next to the bundled executable (PyInstaller onefile)
    if getattr(sys, "frozen", False):
        exe_dir = os.path.dirname(sys.executable)
        candidates.append(os.path.join(exe_dir, exe_name))

    # 2) Dist build directory in the repo
    here = os.path.dirname(__file__)
    repo_root = os.path.abspath(os.path.join(here, ".."))
    candidates.append(os.path.join(repo_root, "dist", exe_name))

    # 3) Current working directory (e.g., when launched from dist/)
    candidates.append(os.path.join(os.getcwd(), exe_name))

    # 4) Project root and frontend dir (additional fallbacks)
    candidates.append(os.path.join(repo_root, exe_name))
    candidates.append(os.path.join(here, exe_name))

    for p in candidates:
        if os.path.exists(p) and os.access(p, os.X_OK):
            return p

    # 5) On PATH as a last resort
    path_found = which("chromedriver") or which(exe_name)
    if path_found:
        return path_found

    return None


def build_driver(debugger_address: str) -> webdriver.Chrome:
    chrome_options = Options()
    chrome_options.add_experimental_option("debuggerAddress", debugger_address)
    # Prefer a bundled/sibling chromedriver if found; otherwise let Selenium Manager resolve
    cd_path = _discover_chromedriver()
    if cd_path:
        service = Service(cd_path)
        driver = webdriver.Chrome(service=service, options=chrome_options)
    else:
        # Selenium 4.6+ can auto-manage drivers; no path needed
        driver = webdriver.Chrome(options=chrome_options)
    time.sleep(2)
    return driver


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Fax Automation - Client")
        self.geometry("720x520")

        # Load runtime settings once per app instance
        cfg = _get_settings()
        self.api_base_url = cfg["API_BASE_URL"]
        self.debugger_address = cfg["DEBUGGER_ADDRESS"]
        self.sleep_between_ok_runs = cfg["SLEEP_BETWEEN_OK_RUNS"]

        self._current_md = ""
        self._build_menu()
        self._build_ui()

    def _build_ui(self):
        top = ttk.Frame(self)
        top.pack(fill=tk.X, padx=10, pady=10)

        ttk.Button(top, text="Start Chrome (Debug Mode)", command=self.start_chrome_debug).pack(side=tk.LEFT, padx=5)
        ttk.Button(top, text="Attach/Verify Debugger", command=self.check_debugger).pack(side=tk.LEFT, padx=5)
        ttk.Separator(top, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=6)
        ttk.Button(top, text="Start Normal Mode", command=self.start_normal).pack(side=tk.LEFT, padx=5)
        ttk.Button(top, text="Stop Normal", command=self.stop_normal).pack(side=tk.LEFT, padx=5)
        ttk.Button(top, text="Health Check", command=self.health_check).pack(side=tk.LEFT, padx=5)

        ttk.Separator(self).pack(fill=tk.X, padx=10, pady=8)

        train = ttk.LabelFrame(self, text="Training Mode")
        train.pack(fill=tk.BOTH, expand=True, padx=10, pady=8)

        grid = ttk.Frame(train)
        grid.pack(fill=tk.X, padx=8, pady=8)

        ttk.Label(grid, text="Predicted doc_type:").grid(row=0, column=0, sticky=tk.W, padx=4, pady=4)
        self.pred_doctype_var = tk.StringVar()
        ttk.Entry(grid, textvariable=self.pred_doctype_var, state="readonly", width=56).grid(row=0, column=1, sticky=tk.W, padx=4, pady=4)

        ttk.Label(grid, text="Predicted doc_subtype:").grid(row=1, column=0, sticky=tk.W, padx=4, pady=4)
        self.pred_subtype_var = tk.StringVar()
        ttk.Entry(grid, textvariable=self.pred_subtype_var, state="readonly", width=56).grid(row=1, column=1, sticky=tk.W, padx=4, pady=4)

        ttk.Label(grid, text="Correct doc_type:").grid(row=2, column=0, sticky=tk.W, padx=4, pady=6)
        self.correct_doctype_var = tk.StringVar()
        ttk.Entry(grid, textvariable=self.correct_doctype_var, width=56).grid(row=2, column=1, sticky=tk.W, padx=4, pady=6)

        ttk.Label(grid, text="Correct doc_subtype:").grid(row=3, column=0, sticky=tk.W, padx=4, pady=6)
        self.correct_subtype_var = tk.StringVar()
        ttk.Entry(grid, textvariable=self.correct_subtype_var, width=56).grid(row=3, column=1, sticky=tk.W, padx=4, pady=6)

        btns = ttk.Frame(train)
        btns.pack(fill=tk.X, padx=8, pady=6)

        ttk.Button(btns, text="Next Fax", command=self.training_next).pack(side=tk.LEFT, padx=5)
        ttk.Button(btns, text="Save Correction", command=self.save_correction).pack(side=tk.LEFT, padx=5)

        self.log = tk.Text(train, height=12)
        self.log.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        self._log("Ready.")

    def _log(self, msg: str):
        self.log.insert(tk.END, f"{msg}\n")
        self.log.see(tk.END)

    # ----- Menu -----
    def _build_menu(self):
        menubar = tk.Menu(self)
        helpmenu = tk.Menu(menubar, tearoff=0)
        helpmenu.add_command(label="About", command=self.show_about)
        menubar.add_cascade(label="Help", menu=helpmenu)
        self.config(menu=menubar)

    def show_about(self):
        app_name = "Fax Automation"
        version = "0.1.0"
        info = (
            f"{app_name} v{version}\n\n"
            f"Backend: {self.api_base_url}\n"
            f"Chrome debugger: {self.debugger_address}\n"
        )
        messagebox.showinfo("About", info)

    # ----- Chrome Debugger helpers -----
    def _debug_port(self) -> int:
        try:
            host, port = self.debugger_address.split(":", 1)
            return int(port)
        except Exception:
            return 9222

    def _chrome_candidates(self) -> list[str]:
        system = platform.system().lower()
        paths: list[str] = []
        if system == "windows":
            paths.extend([
                r"C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
                r"C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe",
            ])
            # where on PATH
            for name in ("chrome.exe", "google-chrome.exe"):
                p = which(name)
                if p:
                    paths.append(p)
        elif system == "darwin":
            paths.append("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
            p = which("google-chrome")
            if p:
                paths.append(p)
        else:  # linux and others
            for name in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser"):
                p = which(name)
                if p:
                    paths.append(p)
        # Remove non-existent
        return [p for p in paths if os.path.exists(p)]

    def _debug_profile_dir(self) -> str:
        system = platform.system().lower()
        if system == "windows":
            base = os.environ.get("LOCALAPPDATA") or str(Path.home())
            return str(Path(base) / "FaxAutomation" / "chrome-profile")
        elif system == "darwin":
            return str(Path.home() / "Library" / "Application Support" / "FaxAutomation" / "chrome-profile")
        else:
            return str(Path.home() / ".fax_automation" / "chrome-profile")

    def check_debugger(self):
        def _task():
            try:
                r = requests.get(f"http://{self.debugger_address}/json/version", timeout=2)
                r.raise_for_status()
                v = r.json().get("Browser", "")
                self._log(f"Chrome debugger detected ({v}).")
            except Exception as e:
                self._log(f"Debugger not reachable on {self.debugger_address}: {e}")
        threading.Thread(target=_task, daemon=True).start()

    def start_chrome_debug(self):
        port = self._debug_port()
        profile_dir = self._debug_profile_dir()
        os.makedirs(profile_dir, exist_ok=True)

        # If already running, just report
        try:
            r = requests.get(f"http://{self.debugger_address}/json/version", timeout=1)
            if r.ok:
                self._log("Chrome debugger already running; using existing instance.")
                return
        except Exception:
            pass

        cands = self._chrome_candidates()
        if not cands:
            self._log("Could not find Chrome. Please install Google Chrome.")
            messagebox.showerror("Chrome not found", "Google Chrome was not found on this system.")
            return

        chrome_path = cands[0]
        args = [
            chrome_path,
            f"--remote-debugging-port={port}",
            f"--user-data-dir={profile_dir}",
            "--no-first-run",
            "--no-default-browser-check",
        ]
        try:
            subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self._log(f"Launched Chrome with debugger on port {port}.")
            # Give it a moment and verify
            def _verify():
                for _ in range(10):
                    try:
                        r = requests.get(f"http://{self.debugger_address}/json/version", timeout=1.5)
                        if r.ok:
                            v = r.json().get("Browser", "")
                            self._log(f"Debugger ready ({v}). You can now click 'Start Normal Mode'.")
                            return
                    except Exception:
                        time.sleep(0.5)
                self._log("Chrome started but debugger not reachable yet.")
            threading.Thread(target=_verify, daemon=True).start()
        except Exception as e:
            self._log(f"Failed to launch Chrome: {e}")

    # ---- Normal Mode (local Selenium loop) ----
    def start_normal(self):
        if hasattr(self, "_normal_thread") and self._normal_thread and self._normal_thread.is_alive():
            return
        self._stop_normal = threading.Event()
        self._log("Starting Normal Mode…")

        def _task():
            driver = None
            try:
                driver = build_driver(self.debugger_address)
                bot = TalkEHRBot(driver)
                while not self._stop_normal.is_set():
                    ok = self._run_once(bot)
                    if not ok:
                        self._log("Normal iteration failed; stopping.")
                        break
                    self._log("Iteration complete. Waiting…")
                    time.sleep(self.sleep_between_ok_runs)
            except Exception as e:
                self._log(f"Normal error: {e}")
            finally:
                if driver:
                    try:
                        driver.quit()
                    except Exception:
                        pass
        self._normal_thread = threading.Thread(target=_task, daemon=True)
        self._normal_thread.start()

    def stop_normal(self):
        if hasattr(self, "_stop_normal"):
            self._stop_normal.set()
            self._log("Stop requested.")

    def health_check(self):
        def _task():
            try:
                r = requests.get(f"{self.api_base_url}/health", timeout=10)
                r.raise_for_status()
                self._log(f"Health: {r.json()}")
            except Exception as e:
                self._log(f"Health check failed: {e}")
        threading.Thread(target=_task, daemon=True).start()

    # ---- Training Mode ----
    def training_next(self):
        self._log("Processing next fax…")
        def _task():
            try:
                if not hasattr(self, "_driver") or self._driver is None:
                    self._driver = build_driver(self.debugger_address)
                    self._bot = TalkEHRBot(self._driver)
                ok = self._run_once(self._bot, capture=True)
                if not ok:
                    self._log("Training next failed or no fax.")
                    return
            except Exception as e:
                self._log(f"Training next error: {e}")
        threading.Thread(target=_task, daemon=True).start()

    # ----- Shared run_once used by both modes (frontend) -----
    def _run_once(self, bot: TalkEHRBot, capture: bool = False) -> bool:
        link = bot.get_url()
        if not link:
            self._log("No unread fax found.")
            return False
        # Ask backend to convert and process with LLM + RAG
        self._log("Sending URL to server for processing…")
        r = requests.post(f"{self.api_base_url}/process_url", json={"url": link}, timeout=None)
        r.raise_for_status()
        st = r.json()
        self._current_md = st.get("md", "")
        doctype = st.get("doc_type", "")
        subtype = st.get("doc_subtype", "")
        date_of_birth = st.get("date_of_birth", "")
        patient_name = st.get("patient_name", "")
        provider_name = st.get("provider_name", "")
        comment = st.get("comment", "")

        # Update UI predicted/correct fields
        self.after(0, lambda: (
            self.pred_doctype_var.set(doctype),
            self.pred_subtype_var.set(subtype),
            self.correct_doctype_var.set(doctype),
            self.correct_subtype_var.set(subtype),
        ))

        if not all([patient_name, doctype, provider_name]):
            self._log("Required fields missing; skipping this fax.")
            try:
                bot.cancel_button()
            except Exception:
                pass
            return True

        comment_with_subtype = f"**{subtype}**\n\n{comment}" if subtype else comment

        if not bot.select_patient(date_of_birth, patient_name):
            self._log("Patient selection failed; cancel and continue.")
            try:
                bot.cancel_button()
                return True
            except Exception:
                return False

        time.sleep(1)
        if not bot.select_doc_type(doctype):
            self._log(f"Doc type '{doctype}' not found.")
            return False

        time.sleep(1)
        if subtype and not bot.select_doc_sub_type(subtype):
            self._log(f"Doc subtype '{subtype}' not found.")
            return False

        time.sleep(1)
        if not bot.select_assigned_to(provider_name):
            self._log(f"Provider '{provider_name}' not found.")
            return False

        time.sleep(1)
        if not bot.add_comments(comment_with_subtype):
            self._log("Failed to add comments.")
            return False

        bot.save_button()
        time.sleep(3)
        self._log("Selections completed successfully.")
        return True

    def save_correction(self):
        if not self._current_md:
            messagebox.showinfo("Info", "No document loaded/processed yet.")
            return
        body = {
            "doc_text": self._current_md,
            "doc_type": self.correct_doctype_var.get().strip(),
            "doc_subtype": self.correct_subtype_var.get().strip(),
        }
        def _task():
            try:
                r = requests.post(f"{self.api_base_url}/training/save_correction", json=body, timeout=20)
                r.raise_for_status()
                self._log("Saved correction to server RAG store.")
            except Exception as e:
                self._log(f"Save correction failed: {e}")
        threading.Thread(target=_task, daemon=True).start()


def main():
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
