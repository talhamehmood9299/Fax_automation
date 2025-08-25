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
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from shutil import which

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


def _load_env_robust():
    """Load .env from sensible locations for both source and PyInstaller onefile.

    Priority:
    1) .env next to the executable (PyInstaller onefile)
    2) .env in current working directory
    3) default dotenv search
    """
    try:
        env_loaded = False
        # If frozen by PyInstaller, sys.executable points to the bundled binary
        if getattr(sys, "frozen", False):
            exe_dir = os.path.dirname(sys.executable)
            candidate = os.path.join(exe_dir, ".env")
            if os.path.exists(candidate):
                load_dotenv(candidate)
                env_loaded = True
        if not env_loaded:
            # Try CWD .env
            cwd_env = os.path.join(os.getcwd(), ".env")
            if os.path.exists(cwd_env):
                load_dotenv(cwd_env)
                env_loaded = True
        if not env_loaded:
            # Try .env next to this script (frontend/.env)
            here_env = os.path.join(os.path.dirname(__file__), ".env")
            if os.path.exists(here_env):
                load_dotenv(here_env)
                env_loaded = True
        if not env_loaded:
            load_dotenv()
    except Exception:
        # Best-effort; continue without .env
        pass


_load_env_robust()
API = os.getenv("API_BASE_URL", "https://60915e37b2d3.ngrok-free.app")
DEBUGGER_ADDRESS = os.getenv("DEBUGGER_ADDRESS", "localhost:9222")
SLEEP_BETWEEN_OK_RUNS = int(os.getenv("SLEEP_BETWEEN_OK_RUNS", "3"))


def _discover_chromedriver() -> str | None:
    """Find a chromedriver in a consistent, cross-platform way.

    Priority:
    1) CHROMEDRIVER_PATH env var if it exists
    2) Same directory as the built binary (PyInstaller onefile)
    3) Current working directory
    4) Project root (repo root) and frontend/ directory
    5) chromedriver on PATH (via Selenium Manager or system install)
    """
    # 1) Explicit env var
    env_path = os.getenv("CHROMEDRIVER_PATH")
    if env_path and os.path.exists(env_path):
        return env_path

    exe_name = "chromedriver.exe" if os.name == "nt" else "chromedriver"

    candidates = []
    # 2) Next to the bundled executable (PyInstaller onefile)
    if getattr(sys, "frozen", False):
        exe_dir = os.path.dirname(sys.executable)
        candidates.append(os.path.join(exe_dir, exe_name))

    # 3) Current working directory
    candidates.append(os.path.join(os.getcwd(), exe_name))

    # 4) Project root and frontend dir (use this file as anchor)
    here = os.path.dirname(__file__)
    repo_root = os.path.abspath(os.path.join(here, ".."))
    candidates.append(os.path.join(repo_root, exe_name))
    candidates.append(os.path.join(here, exe_name))

    for p in candidates:
        if os.path.exists(p) and os.access(p, os.X_OK):
            return p

    # 5) On PATH
    path_found = which("chromedriver") or which(exe_name)
    if path_found:
        return path_found

    return None


def build_driver() -> webdriver.Chrome:
    chrome_options = Options()
    chrome_options.add_experimental_option("debuggerAddress", DEBUGGER_ADDRESS)
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

        self._current_md = ""
        self._build_menu()
        self._build_ui()

    def _build_ui(self):
        top = ttk.Frame(self)
        top.pack(fill=tk.X, padx=10, pady=10)

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
            f"Backend: {API}\n"
            f"Chrome debugger: {DEBUGGER_ADDRESS}\n"
        )
        messagebox.showinfo("About", info)

    # ---- Normal Mode (local Selenium loop) ----
    def start_normal(self):
        if hasattr(self, "_normal_thread") and self._normal_thread and self._normal_thread.is_alive():
            return
        self._stop_normal = threading.Event()
        self._log("Starting Normal Mode…")

        def _task():
            driver = None
            try:
                driver = build_driver()
                bot = TalkEHRBot(driver)
                while not self._stop_normal.is_set():
                    ok = self._run_once(bot)
                    if not ok:
                        self._log("Normal iteration failed; stopping.")
                        break
                    self._log("Iteration complete. Waiting…")
                    time.sleep(SLEEP_BETWEEN_OK_RUNS)
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
                r = requests.get(f"{API}/health", timeout=10)
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
                    self._driver = build_driver()
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
        r = requests.post(f"{API}/process_url", json={"url": link}, timeout=None)
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
                r = requests.post(f"{API}/training/save_correction", json=body, timeout=20)
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
