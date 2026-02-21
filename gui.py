"""
gui.py – Tkinter GUI for AutoTyper.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
from typing import Optional

from settings import (
    AppState,
    DEFAULT_CHAR_DELAY,
    DEFAULT_LINE_DELAY,
    DEFAULT_COUNTDOWN,
    FILE_TYPES,
    MODE_CHAR,
    MODE_LINE,
    STATUS_IDLE,
    STATUS_COUNTDOWN,
    STATUS_TYPING,
    STATUS_PAUSED,
    STATUS_STOPPED,
    STATUS_DONE,
)
from window_manager import get_window_list, activate_window
from typing_engine import start_typing


class AutoTyperGUI:
    """Main application window."""

    def __init__(self, root: tk.Tk, state: AppState) -> None:
        self.root = root
        self.state = state
        self.typing_thread: Optional[threading.Thread] = None
        self._window_map: dict[str, int] = {}  # title -> hwnd

        self.root.title("AutoTyper")
        self.root.resizable(True, True)
        self.root.minsize(620, 680)
        self.root.configure(bg="#1e1e2e")

        # Apply dark theme styles
        self._setup_styles()
        self._build_ui()
        self._refresh_windows()
        self._update_status_display()

    # ── Styles ─────────────────────────────────────────────────
    def _setup_styles(self) -> None:
        style = ttk.Style()
        style.theme_use("clam")

        # Color palette
        bg = "#1e1e2e"
        surface = "#2a2a3d"
        accent = "#7c3aed"
        accent2 = "#a78bfa"
        text_fg = "#e2e8f0"
        muted = "#94a3b8"
        danger = "#ef4444"
        success = "#22c55e"
        warning = "#f59e0b"

        style.configure(".", background=bg, foreground=text_fg, font=("Segoe UI", 10))
        style.configure("TFrame", background=bg)
        style.configure(
            "TLabel", background=bg, foreground=text_fg, font=("Segoe UI", 10)
        )
        style.configure(
            "TLabelframe",
            background=bg,
            foreground=accent2,
            font=("Segoe UI", 10, "bold"),
        )
        style.configure("TLabelframe.Label", background=bg, foreground=accent2)
        style.configure(
            "Header.TLabel",
            font=("Segoe UI", 16, "bold"),
            foreground=accent2,
            background=bg,
        )
        style.configure(
            "Status.TLabel",
            font=("Segoe UI", 11, "bold"),
            foreground=success,
            background=surface,
            padding=8,
        )

        # Buttons
        style.configure(
            "Accent.TButton",
            background=accent,
            foreground="white",
            font=("Segoe UI", 10, "bold"),
            padding=(12, 6),
        )
        style.map("Accent.TButton", background=[("active", "#6d28d9")])
        style.configure(
            "Danger.TButton",
            background=danger,
            foreground="white",
            font=("Segoe UI", 10, "bold"),
            padding=(12, 6),
        )
        style.map("Danger.TButton", background=[("active", "#dc2626")])
        style.configure(
            "TButton",
            background=surface,
            foreground=text_fg,
            font=("Segoe UI", 10),
            padding=(10, 5),
        )
        style.map("TButton", background=[("active", "#3a3a5a")])

        # Spinbox
        style.configure(
            "TSpinbox", fieldbackground=surface, foreground=text_fg, background=bg
        )
        # Combobox
        style.configure(
            "TCombobox", fieldbackground=surface, foreground=text_fg, background=bg
        )
        style.map("TCombobox", fieldbackground=[("readonly", surface)])
        # Checkbutton
        style.configure("TCheckbutton", background=bg, foreground=text_fg)

        # Radiobutton
        style.configure("TRadiobutton", background=bg, foreground=text_fg)

        self._colors = {
            "bg": bg,
            "surface": surface,
            "accent": accent,
            "accent2": accent2,
            "text": text_fg,
            "muted": muted,
            "danger": danger,
            "success": success,
            "warning": warning,
        }

    # ── UI Construction ────────────────────────────────────────
    def _build_ui(self) -> None:
        c = self._colors
        pad = {"padx": 8, "pady": 4}

        # Header
        ttk.Label(self.root, text="⌨  AutoTyper", style="Header.TLabel").pack(
            pady=(12, 4)
        )
        ttk.Label(
            self.root, text="Productivity auto-typing tool", foreground=c["muted"]
        ).pack()

        # ── Text input ─────────────────────────────────────────
        frm_text = ttk.LabelFrame(self.root, text="  Text Input  ")
        frm_text.pack(fill="both", expand=True, **pad)

        btn_row = ttk.Frame(frm_text)
        btn_row.pack(fill="x", **pad)
        ttk.Button(btn_row, text="📂 Load File", command=self._load_file).pack(
            side="left", padx=(0, 4)
        )
        ttk.Button(btn_row, text="✕ Clear", command=self._clear_text).pack(side="left")

        self.txt_input = tk.Text(
            frm_text,
            wrap="none",
            height=10,
            font=("Consolas", 11),
            bg=c["surface"],
            fg=c["text"],
            insertbackground=c["accent2"],
            selectbackground=c["accent"],
            relief="flat",
            bd=0,
            padx=6,
            pady=6,
        )
        self.txt_input.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        # Scrollbars
        sx = ttk.Scrollbar(frm_text, orient="horizontal", command=self.txt_input.xview)
        sx.pack(fill="x", padx=8)
        self.txt_input.configure(xscrollcommand=sx.set)
        sy = ttk.Scrollbar(frm_text, orient="vertical", command=self.txt_input.yview)
        # pack scrollbar on the right of text
        self.txt_input.configure(yscrollcommand=sy.set)

        # ── Target window ─────────────────────────────────────
        frm_win = ttk.LabelFrame(self.root, text="  Target Window  ")
        frm_win.pack(fill="x", **pad)

        win_row = ttk.Frame(frm_win)
        win_row.pack(fill="x", **pad)
        self.cmb_windows = ttk.Combobox(win_row, state="readonly", width=55)
        self.cmb_windows.pack(side="left", fill="x", expand=True, padx=(0, 4))
        self.cmb_windows.bind("<<ComboboxSelected>>", self._on_window_selected)
        ttk.Button(win_row, text="🔄 Refresh", command=self._refresh_windows).pack(
            side="left"
        )

        self.lbl_target = ttk.Label(
            frm_win, text="No window selected", foreground=self._colors["muted"]
        )
        self.lbl_target.pack(anchor="w", padx=8, pady=(0, 6))

        # ── Coordinates ────────────────────────────────────────
        frm_coord = ttk.LabelFrame(self.root, text="  Click Position (Optional)  ")
        frm_coord.pack(fill="x", **pad)

        coord_row = ttk.Frame(frm_coord)
        coord_row.pack(fill="x", **pad)

        self.var_use_coords = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            coord_row, text="Click position before typing", variable=self.var_use_coords
        ).pack(side="left")

        ttk.Label(coord_row, text="  X:").pack(side="left")
        self.spn_x = ttk.Spinbox(coord_row, from_=0, to=9999, width=6)
        self.spn_x.set(0)
        self.spn_x.pack(side="left", padx=2)

        ttk.Label(coord_row, text="Y:").pack(side="left")
        self.spn_y = ttk.Spinbox(coord_row, from_=0, to=9999, width=6)
        self.spn_y.set(0)
        self.spn_y.pack(side="left", padx=2)

        ttk.Button(
            coord_row, text="🎯 Capture (Ctrl+Shift+C)", command=self._capture_coords
        ).pack(side="left", padx=(8, 0))

        # ── Settings ──────────────────────────────────────────
        frm_set = ttk.LabelFrame(self.root, text="  Typing Settings  ")
        frm_set.pack(fill="x", **pad)

        set_row1 = ttk.Frame(frm_set)
        set_row1.pack(fill="x", **pad)

        ttk.Label(set_row1, text="Char delay (ms):").pack(side="left")
        self.spn_char_delay = ttk.Spinbox(set_row1, from_=1, to=1000, width=6)
        self.spn_char_delay.set(DEFAULT_CHAR_DELAY)
        self.spn_char_delay.pack(side="left", padx=(2, 12))

        ttk.Label(set_row1, text="Line delay (ms):").pack(side="left")
        self.spn_line_delay = ttk.Spinbox(set_row1, from_=0, to=5000, width=6)
        self.spn_line_delay.set(DEFAULT_LINE_DELAY)
        self.spn_line_delay.pack(side="left", padx=(2, 12))

        ttk.Label(set_row1, text="Countdown (s):").pack(side="left")
        self.spn_countdown = ttk.Spinbox(set_row1, from_=0, to=10, width=4)
        self.spn_countdown.set(DEFAULT_COUNTDOWN)
        self.spn_countdown.pack(side="left", padx=2)

        set_row2 = ttk.Frame(frm_set)
        set_row2.pack(fill="x", **pad)

        ttk.Label(set_row2, text="Mode:").pack(side="left")
        self.var_mode = tk.StringVar(value=MODE_CHAR)
        ttk.Radiobutton(
            set_row2, text="Char-by-char", variable=self.var_mode, value=MODE_CHAR
        ).pack(side="left", padx=(4, 12))
        ttk.Radiobutton(
            set_row2, text="Line-by-line", variable=self.var_mode, value=MODE_LINE
        ).pack(side="left")

        set_row3 = ttk.Frame(frm_set)
        set_row3.pack(fill="x", **pad)

        self.var_background = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            set_row3,
            text="Background typing (type into target while you use other windows)",
            variable=self.var_background,
        ).pack(side="left")

        # ── Controls ──────────────────────────────────────────
        frm_ctrl = ttk.Frame(self.root)
        frm_ctrl.pack(fill="x", padx=8, pady=(6, 2))

        self.btn_start = ttk.Button(
            frm_ctrl,
            text="▶  Start (F6)",
            style="Accent.TButton",
            command=self._on_start,
        )
        self.btn_start.pack(side="left", padx=4)

        self.btn_pause = ttk.Button(
            frm_ctrl, text="⏸  Pause (F7)", command=self._on_pause
        )
        self.btn_pause.pack(side="left", padx=4)

        self.btn_stop = ttk.Button(
            frm_ctrl,
            text="⏹  Stop (Esc)",
            style="Danger.TButton",
            command=self._on_stop,
        )
        self.btn_stop.pack(side="left", padx=4)

        # ── Status bar ────────────────────────────────────────
        frm_status = ttk.Frame(self.root, style="TFrame")
        frm_status.pack(fill="x", padx=8, pady=(4, 10))

        status_bg = tk.Frame(
            frm_status,
            bg=self._colors["surface"],
            bd=0,
            highlightthickness=1,
            highlightbackground=self._colors["accent"],
        )
        status_bg.pack(fill="x")
        self.lbl_status = tk.Label(
            status_bg,
            text="● Idle",
            anchor="w",
            font=("Segoe UI", 11, "bold"),
            fg=self._colors["success"],
            bg=self._colors["surface"],
            padx=10,
            pady=8,
        )
        self.lbl_status.pack(fill="x")

    # ── Actions ────────────────────────────────────────────────
    def _load_file(self) -> None:
        path = filedialog.askopenfilename(filetypes=FILE_TYPES)
        if path:
            try:
                with open(path, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read()
                self.txt_input.delete("1.0", "end")
                self.txt_input.insert("1.0", content)
            except Exception as e:
                messagebox.showerror("Error", f"Could not read file:\n{e}")

    def _clear_text(self) -> None:
        self.txt_input.delete("1.0", "end")

    def _refresh_windows(self) -> None:
        windows = get_window_list()
        self._window_map = {title: hwnd for title, hwnd in windows}
        titles = list(self._window_map.keys())
        self.cmb_windows["values"] = titles
        if titles:
            self.cmb_windows.current(0)
            self._on_window_selected(None)

    def _on_window_selected(self, _event) -> None:
        title = self.cmb_windows.get()
        hwnd = self._window_map.get(title, 0)
        self.state.target_title = title
        self.state.target_hwnd = hwnd
        self.lbl_target.configure(
            text=f"Target: {title}", foreground=self._colors["accent2"]
        )

    def _capture_coords(self) -> None:
        """Capture mouse position after a short delay."""
        messagebox.showinfo(
            "Capture Position",
            "After clicking OK, you have 3 seconds to position your mouse\n"
            "at the desired click point. The coordinates will be captured automatically.",
        )
        self.lbl_status.configure(
            text="● Capturing position in 3s…", fg=self._colors["warning"]
        )
        self.root.update()

        def _do_capture():
            import time, pyautogui

            time.sleep(3)
            x, y = pyautogui.position()
            # Update GUI from thread-safe callback
            self.root.after(0, lambda: self._set_coords(x, y))

        threading.Thread(target=_do_capture, daemon=True).start()

    def _set_coords(self, x: int, y: int) -> None:
        self.spn_x.delete(0, "end")
        self.spn_x.insert(0, str(x))
        self.spn_y.delete(0, "end")
        self.spn_y.insert(0, str(y))
        self.var_use_coords.set(True)
        self.lbl_status.configure(
            text=f"● Captured position: ({x}, {y})", fg=self._colors["success"]
        )

    # ── Start / Pause / Stop ───────────────────────────────────
    def _on_start(self) -> None:
        text = self.txt_input.get("1.0", "end-1c")
        if not text.strip():
            messagebox.showwarning("No Text", "Please paste or load some text first.")
            return

        if not self.state.target_hwnd:
            messagebox.showwarning("No Target", "Please select a target window first.")
            return

        if self.state.status in (STATUS_TYPING, STATUS_COUNTDOWN, STATUS_PAUSED):
            messagebox.showinfo("Running", "Typing is already in progress.")
            return

        ok = messagebox.askokcancel(
            "Confirm",
            f"AutoTyper will type into:\n\n"
            f'  "{self.state.target_title}"\n\n'
            f"Make sure the cursor is at the correct insertion point.\n"
            f"Press OK to start the countdown.",
        )
        if not ok:
            return

        # Reset state
        self.state.text = text
        self.state.is_paused = False
        self.state.stop_requested = False
        self.state.line_index = 0
        self.state.char_index = 0
        self.state.use_coords = self.var_use_coords.get()
        try:
            self.state.coord_x = int(self.spn_x.get())
            self.state.coord_y = int(self.spn_y.get())
        except ValueError:
            self.state.coord_x = 0
            self.state.coord_y = 0

        char_delay = int(self.spn_char_delay.get())
        line_delay = int(self.spn_line_delay.get())
        countdown = int(self.spn_countdown.get())
        mode = self.var_mode.get()

        self.typing_thread = start_typing(
            state=self.state,
            char_delay_ms=char_delay,
            line_delay_ms=line_delay,
            mode=mode,
            countdown=countdown,
            on_progress=self._on_progress,
            on_done=self._on_done,
            background=self.var_background.get(),
        )

        # Start polling status
        self._poll_status()

    def _on_pause(self) -> None:
        if self.state.status == STATUS_TYPING:
            self.state.is_paused = True
            self.state.status = STATUS_PAUSED
            self.btn_pause.configure(text="▶  Resume (F7)")
        elif self.state.status == STATUS_PAUSED:
            self.state.is_paused = False
            self.state.status = STATUS_TYPING
            self.btn_pause.configure(text="⏸  Pause (F7)")

    def _on_stop(self) -> None:
        self.state.stop_requested = True
        self.state.is_paused = False
        self.state.status = STATUS_STOPPED

    # ── Callbacks (called from typing thread) ──────────────────
    def _on_progress(
        self, line_idx: int, char_idx: int, total_lines: int, total_chars: int
    ) -> None:
        """Store progress; the _poll_status loop reads it."""
        # These are simple int assignments – thread-safe in CPython.
        self.state.line_index = line_idx
        self.state.char_index = char_idx
        self.state.total_lines = total_lines
        self.state.total_chars = total_chars

    def _on_done(self, completed: bool, error_msg: str = "") -> None:
        self.root.after(0, lambda: self._finish(completed, error_msg))

    def _finish(self, completed: bool, error_msg: str = "") -> None:
        self.btn_pause.configure(text="⏸  Pause (F7)")
        if error_msg:
            self.state.status = STATUS_STOPPED
            self.lbl_status.configure(
                text=f"● Error: {error_msg.splitlines()[0]}",
                fg=self._colors["danger"],
            )
            messagebox.showerror("Typing Error", error_msg)
        elif completed:
            self.state.status = STATUS_DONE
        self._update_status_display()

    # ── Status polling ─────────────────────────────────────────
    def _poll_status(self) -> None:
        self._update_status_display()
        if self.state.status in (STATUS_TYPING, STATUS_COUNTDOWN, STATUS_PAUSED):
            self.root.after(100, self._poll_status)

    def _update_status_display(self) -> None:
        c = self._colors
        s = self.state

        if s.status == STATUS_IDLE:
            self.lbl_status.configure(text="● Idle", fg=c["muted"])
        elif s.status == STATUS_COUNTDOWN:
            self.lbl_status.configure(
                text=f"● Countdown… {s.char_index}s", fg=c["warning"]
            )
        elif s.status == STATUS_TYPING:
            self.lbl_status.configure(
                text=f"● Typing — line {s.line_index + 1}/{s.total_lines}  |  "
                f"char {s.char_index}/{s.total_chars}",
                fg=c["success"],
            )
        elif s.status == STATUS_PAUSED:
            self.lbl_status.configure(
                text=f"● Paused — line {s.line_index + 1}/{s.total_lines}  |  "
                f"char {s.char_index}/{s.total_chars}",
                fg=c["warning"],
            )
        elif s.status == STATUS_STOPPED:
            self.lbl_status.configure(text="● Stopped", fg=c["danger"])
        elif s.status == STATUS_DONE:
            self.lbl_status.configure(text="● Done ✓", fg=c["success"])

    # ── Public API for global hotkeys ──────────────────────────
    def hotkey_start(self) -> None:
        self.root.after(0, self._on_start)

    def hotkey_pause(self) -> None:
        self.root.after(0, self._on_pause)

    def hotkey_stop(self) -> None:
        self.root.after(0, self._on_stop)

    def hotkey_capture(self) -> None:
        self.root.after(0, self._capture_coords)
