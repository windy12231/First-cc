import datetime
import time
import threading
from typing import Optional

import win32gui
import win32process
import win32api
import psutil

from database import log_session

POLL_INTERVAL = 2  # seconds
IDLE_THRESHOLD = 120  # seconds — treat as idle break


class AppTracker:
    def __init__(self):
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

        self._current_app: Optional[str] = None
        self._current_title: Optional[str] = None
        self._session_start: Optional[datetime.datetime] = None
        self._was_idle = False

    # ── public api ──────────────────────────────────────────────

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        self._flush_current_session()

    @property
    def current_app(self) -> Optional[str]:
        with self._lock:
            return self._current_app

    @property
    def current_window_title(self) -> Optional[str]:
        with self._lock:
            return self._current_title

    @property
    def session_elapsed(self) -> int:
        """Seconds spent in current foreground app so far."""
        with self._lock:
            if self._session_start is None:
                return 0
            return int((datetime.datetime.now() - self._session_start).total_seconds())

    # ── internal ───────────────────────────────────────────────

    def _run_loop(self):
        self._check_window()  # initialise
        while self._running:
            time.sleep(POLL_INTERVAL)
            idle = self._is_user_idle()
            if idle and not self._was_idle:
                # just went idle — flush current session
                self._flush_current_session()
                self._was_idle = True
            elif not idle:
                self._was_idle = False
                self._check_window()

    def _check_window(self):
        try:
            hwnd = win32gui.GetForegroundWindow()
            if not hwnd:
                return

            # Skip desktop / task-switching windows
            window_title = win32gui.GetWindowText(hwnd)
            if not window_title:
                return

            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            try:
                proc = psutil.Process(pid)
                app_name = proc.name()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                app_name = "Unknown"

            # Normalise browser — group all browser tabs under the browser name
            app_name = self._normalise_app(app_name)

            self._update_session(app_name, window_title)

        except Exception:
            pass  # silently swallow transient errors

    def _update_session(self, app_name: str, window_title: str):
        now = datetime.datetime.now()

        with self._lock:
            same_app = app_name == self._current_app
            same_window = window_title == self._current_title

            if same_app and same_window:
                return  # still on the same thing

            # flush the previous session
            if self._current_app is not None and self._session_start is not None:
                if (now - self._session_start).total_seconds() >= 1:
                    log_session(self._current_app, self._current_title,
                                self._session_start, now)

            # start new session
            self._current_app = app_name
            self._current_title = window_title
            self._session_start = now

    def _flush_current_session(self):
        now = datetime.datetime.now()
        with self._lock:
            if self._current_app is not None and self._session_start is not None:
                if (now - self._session_start).total_seconds() >= 1:
                    log_session(self._current_app, self._current_title,
                                self._session_start, now)
                self._current_app = None
                self._current_title = None
                self._session_start = None

    def _is_user_idle(self) -> bool:
        """Return True if the user has been idle longer than the threshold."""
        try:
            last_input = win32api.GetLastInputInfo()
            now = win32api.GetTickCount()
            idle_ms = now - last_input
            return idle_ms > IDLE_THRESHOLD * 1000
        except Exception:
            return False

    @staticmethod
    def _normalise_app(name: str) -> str:
        low = name.lower()
        # Group common browser variants
        if "chrome" in low and low.endswith(".exe"):
            return "Chrome"
        if "msedge" in low or "edge" in low:
            return "Edge"
        if "firefox" in low:
            return "Firefox"
        if "opera" in low:
            return "Opera"
        if "brave" in low:
            return "Brave"
        # Strip .exe
        if low.endswith(".exe"):
            return name[:-4]
        return name
