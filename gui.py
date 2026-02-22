"""
gui.py - Tkinter GUI for AutoTyper.
"""

from __future__ import annotations

import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Optional

from settings import (
    AppState,
    DEFAULT_CHAR_DELAY,
    DEFAULT_COUNTDOWN,
    DEFAULT_LINE_DELAY,
    FILE_TYPES,
    HUMAN_PROFILES,
    HUMAN_PROFILE_CUSTOM,
    HUMAN_PROFILE_NATURAL,
    TYPO_PROFILE_NATURAL,
    TYPO_PROFILES,
    MODE_CHAR,
    MODE_LINE,
    STATUS_COUNTDOWN,
    STATUS_DONE,
    STATUS_IDLE,
    STATUS_PAUSED,
    STATUS_STOPPED,
    STATUS_TYPING,
    HumanTypingConfig,
    apply_typo_profile,
    human_profile_defaults,
)
from typing_engine import start_typing
from window_manager import get_window_list


class AutoTyperGUI:
    """Main application window."""

    def __init__(self, root: tk.Tk, state: AppState) -> None:
        self.root = root
        self.state = state
        self.typing_thread: Optional[threading.Thread] = None
        self._window_map: dict[str, int] = {}
        self._is_applying_human_profile = False

        self.root.title("AutoTyper")
        self.root.resizable(True, True)
        self.root.minsize(680, 860)
        self.root.configure(bg="#1e1e2e")

        self._setup_styles()
        self._build_ui()
        self._refresh_windows()
        self._update_status_display()

    def _setup_styles(self) -> None:
        style = ttk.Style()
        style.theme_use("clam")

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
        style.configure("TLabel", background=bg, foreground=text_fg, font=("Segoe UI", 10))
        style.configure(
            "TLabelframe",
            background=bg,
            foreground=accent2,
            font=("Segoe UI", 10, "bold"),
        )
        style.configure("TLabelframe.Label", background=bg, foreground=accent2)
        style.configure("Header.TLabel", font=("Segoe UI", 16, "bold"), foreground=accent2, background=bg)
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
        style.configure("TSpinbox", fieldbackground=surface, foreground=text_fg, background=bg)
        style.configure("TCombobox", fieldbackground=surface, foreground=text_fg, background=bg)
        style.map("TCombobox", fieldbackground=[("readonly", surface)])
        style.configure("TCheckbutton", background=bg, foreground=text_fg)
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

    def _build_ui(self) -> None:
        c = self._colors
        pad = {"padx": 8, "pady": 4}

        ttk.Label(self.root, text="AutoTyper", style="Header.TLabel").pack(pady=(12, 4))
        ttk.Label(self.root, text="Productivity auto-typing tool", foreground=c["muted"]).pack()

        # Text input
        frm_text = ttk.LabelFrame(self.root, text="  Text Input  ")
        frm_text.pack(fill="both", expand=True, **pad)

        btn_row = ttk.Frame(frm_text)
        btn_row.pack(fill="x", **pad)
        ttk.Button(btn_row, text="Load File", command=self._load_file).pack(side="left", padx=(0, 4))
        ttk.Button(btn_row, text="Clear", command=self._clear_text).pack(side="left")

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

        sx = ttk.Scrollbar(frm_text, orient="horizontal", command=self.txt_input.xview)
        sx.pack(fill="x", padx=8)
        self.txt_input.configure(xscrollcommand=sx.set)
        sy = ttk.Scrollbar(frm_text, orient="vertical", command=self.txt_input.yview)
        self.txt_input.configure(yscrollcommand=sy.set)

        # Target window
        frm_win = ttk.LabelFrame(self.root, text="  Target Window  ")
        frm_win.pack(fill="x", **pad)

        win_row = ttk.Frame(frm_win)
        win_row.pack(fill="x", **pad)
        self.cmb_windows = ttk.Combobox(win_row, state="readonly", width=55)
        self.cmb_windows.pack(side="left", fill="x", expand=True, padx=(0, 4))
        self.cmb_windows.bind("<<ComboboxSelected>>", self._on_window_selected)
        ttk.Button(win_row, text="Refresh", command=self._refresh_windows).pack(side="left")

        self.lbl_target = ttk.Label(frm_win, text="No window selected", foreground=self._colors["muted"])
        self.lbl_target.pack(anchor="w", padx=8, pady=(0, 6))

        # Coordinates
        frm_coord = ttk.LabelFrame(self.root, text="  Click Position (Optional)  ")
        frm_coord.pack(fill="x", **pad)

        coord_row = ttk.Frame(frm_coord)
        coord_row.pack(fill="x", **pad)

        self.var_use_coords = tk.BooleanVar(value=False)
        ttk.Checkbutton(coord_row, text="Click position before typing", variable=self.var_use_coords).pack(side="left")

        ttk.Label(coord_row, text="  X:").pack(side="left")
        self.spn_x = ttk.Spinbox(coord_row, from_=0, to=9999, width=6)
        self.spn_x.set(0)
        self.spn_x.pack(side="left", padx=2)

        ttk.Label(coord_row, text="Y:").pack(side="left")
        self.spn_y = ttk.Spinbox(coord_row, from_=0, to=9999, width=6)
        self.spn_y.set(0)
        self.spn_y.pack(side="left", padx=2)

        ttk.Button(coord_row, text="Capture (Ctrl+Shift+C)", command=self._capture_coords).pack(side="left", padx=(8, 0))

        # Typing settings
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
        ttk.Radiobutton(set_row2, text="Char-by-char", variable=self.var_mode, value=MODE_CHAR).pack(side="left", padx=(4, 12))
        ttk.Radiobutton(set_row2, text="Line-by-line", variable=self.var_mode, value=MODE_LINE).pack(side="left")

        set_row3 = ttk.Frame(frm_set)
        set_row3.pack(fill="x", **pad)
        self.var_background = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            set_row3,
            text="Background typing (type into target while you use other windows)",
            variable=self.var_background,
        ).pack(side="left")

        self._build_human_settings(frm_set, pad)

        # Controls
        frm_ctrl = ttk.Frame(self.root)
        frm_ctrl.pack(fill="x", padx=8, pady=(6, 2))

        self.btn_start = ttk.Button(frm_ctrl, text="Start (F6)", style="Accent.TButton", command=self._on_start)
        self.btn_start.pack(side="left", padx=4)

        self.btn_pause = ttk.Button(frm_ctrl, text="Pause (F7)", command=self._on_pause)
        self.btn_pause.pack(side="left", padx=4)

        self.btn_stop = ttk.Button(frm_ctrl, text="Stop (Esc)", style="Danger.TButton", command=self._on_stop)
        self.btn_stop.pack(side="left", padx=4)

        # Status bar
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
            text="Idle",
            anchor="w",
            font=("Segoe UI", 11, "bold"),
            fg=self._colors["success"],
            bg=self._colors["surface"],
            padx=10,
            pady=8,
        )
        self.lbl_status.pack(fill="x")

        self._apply_human_profile(HUMAN_PROFILE_NATURAL)
        self._update_human_preview()

    def _build_human_settings(self, parent: ttk.LabelFrame, pad: dict[str, int]) -> None:
        frm_human = ttk.LabelFrame(parent, text="  Human-like Typing  ")
        frm_human.pack(fill="x", padx=8, pady=(2, 8))

        h_row1 = ttk.Frame(frm_human)
        h_row1.pack(fill="x", **pad)

        self.var_human_enabled = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            h_row1,
            text="Enable human-like timing",
            variable=self.var_human_enabled,
            command=lambda: self._on_human_setting_changed(mark_custom=False),
        ).pack(side="left", padx=(0, 12))

        ttk.Label(h_row1, text="Profile:").pack(side="left")
        self.var_human_profile = tk.StringVar(value=HUMAN_PROFILE_NATURAL)
        self.cmb_human_profile = ttk.Combobox(
            h_row1,
            state="readonly",
            width=18,
            textvariable=self.var_human_profile,
            values=HUMAN_PROFILES,
        )
        self.cmb_human_profile.pack(side="left", padx=(4, 8))
        self.cmb_human_profile.bind("<<ComboboxSelected>>", self._on_human_profile_selected)

        h_row2 = ttk.Frame(frm_human)
        h_row2.pack(fill="x", **pad)

        ttk.Label(h_row2, text="Base speed (ms):").pack(side="left")
        self.spn_human_base = ttk.Spinbox(h_row2, from_=1, to=600, width=6)
        self.spn_human_base.pack(side="left", padx=(2, 10))

        ttk.Label(h_row2, text="Jitter (ms):").pack(side="left")
        self.spn_human_jitter = ttk.Spinbox(h_row2, from_=0, to=300, width=6)
        self.spn_human_jitter.pack(side="left", padx=(2, 10))

        ttk.Label(h_row2, text="Seed (blank=random):").pack(side="left")
        self.ent_human_seed = ttk.Entry(h_row2, width=12)
        self.ent_human_seed.pack(side="left", padx=(2, 2))

        h_row3 = ttk.Frame(frm_human)
        h_row3.pack(fill="x", **pad)

        ttk.Label(h_row3, text="Punctuation pause x").pack(side="left")
        self.spn_human_punct = ttk.Spinbox(h_row3, from_=1.0, to=6.0, increment=0.1, width=6)
        self.spn_human_punct.pack(side="left", padx=(2, 10))

        ttk.Label(h_row3, text="Newline pause x").pack(side="left")
        self.spn_human_newline = ttk.Spinbox(h_row3, from_=1.0, to=8.0, increment=0.1, width=6)
        self.spn_human_newline.pack(side="left", padx=(2, 2))

        h_row4 = ttk.Frame(frm_human)
        h_row4.pack(fill="x", **pad)

        ttk.Label(h_row4, text="Burst size range:").pack(side="left")
        self.spn_human_burst_min = ttk.Spinbox(h_row4, from_=1, to=100, width=5)
        self.spn_human_burst_min.pack(side="left", padx=(4, 4))
        ttk.Label(h_row4, text="to").pack(side="left")
        self.spn_human_burst_max = ttk.Spinbox(h_row4, from_=1, to=100, width=5)
        self.spn_human_burst_max.pack(side="left", padx=(4, 10))

        ttk.Label(h_row4, text="Correction profile:").pack(side="left")
        self.var_typo_profile = tk.StringVar(value=TYPO_PROFILE_NATURAL)
        self.cmb_typo_profile = ttk.Combobox(
            h_row4,
            state="readonly",
            width=18,
            textvariable=self.var_typo_profile,
            values=TYPO_PROFILES,
        )
        self.cmb_typo_profile.pack(side="left", padx=(4, 10))
        self.cmb_typo_profile.bind("<<ComboboxSelected>>", self._on_typo_profile_selected)

        self.var_typo_enabled = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            h_row4,
            text="Typo/correct simulation",
            variable=self.var_typo_enabled,
            command=self._on_human_setting_changed,
        ).pack(side="left", padx=(8, 8))

        h_row5 = ttk.Frame(frm_human)
        h_row5.pack(fill="x", **pad)

        ttk.Label(h_row5, text="Typo probability:").pack(side="left")
        self.spn_typo_probability = ttk.Spinbox(h_row5, from_=0.0, to=0.3, increment=0.001, width=7)
        self.spn_typo_probability.pack(side="left", padx=(2, 12))

        self.var_safe_code_typo_mode = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            h_row5,
            text="Safe code typo mode",
            variable=self.var_safe_code_typo_mode,
            command=self._on_human_setting_changed,
        ).pack(side="left", padx=(4, 10))

        self.lbl_human_preview = ttk.Label(
            frm_human,
            text="",
            foreground=self._colors["muted"],
            wraplength=620,
            justify="left",
        )
        self.lbl_human_preview.pack(anchor="w", padx=8, pady=(0, 8))

        self._human_input_widgets = [
            self.spn_human_base,
            self.spn_human_jitter,
            self.ent_human_seed,
            self.spn_human_punct,
            self.spn_human_newline,
            self.spn_human_burst_min,
            self.spn_human_burst_max,
            self.spn_typo_probability,
        ]
        for widget in self._human_input_widgets:
            self._bind_human_change_events(widget)

    def _bind_human_change_events(self, widget: ttk.Widget) -> None:
        for event_name in ("<KeyRelease>", "<FocusOut>", "<<Increment>>", "<<Decrement>>"):
            widget.bind(event_name, lambda _event: self._on_human_setting_changed(), add="+")

    def _set_spinbox_value(self, spin: ttk.Spinbox, value: str | int | float) -> None:
        spin.delete(0, "end")
        spin.insert(0, str(value))

    def _apply_human_profile(self, profile: str) -> None:
        preset = human_profile_defaults(profile)
        self._is_applying_human_profile = True
        try:
            self.var_human_profile.set(profile)
            self._set_spinbox_value(self.spn_human_base, preset.base_delay_ms)
            self._set_spinbox_value(self.spn_human_jitter, preset.jitter_ms)
            self._set_spinbox_value(self.spn_human_punct, f"{preset.punctuation_pause_multiplier:.1f}")
            self._set_spinbox_value(self.spn_human_newline, f"{preset.newline_pause_multiplier:.1f}")
            self._set_spinbox_value(self.spn_human_burst_min, preset.burst_min_chars)
            self._set_spinbox_value(self.spn_human_burst_max, preset.burst_max_chars)
            self._set_typo_controls_from_config(preset)
            self.ent_human_seed.delete(0, "end")
        finally:
            self._is_applying_human_profile = False

    def _set_typo_controls_from_config(self, config: HumanTypingConfig) -> None:
        self.var_typo_profile.set(config.typo_profile)
        self.var_typo_enabled.set(config.typo_enabled)
        self._set_spinbox_value(self.spn_typo_probability, f"{config.typo_probability:.3f}")
        self.var_safe_code_typo_mode.set(config.safe_code_typo_mode)

    def _apply_typo_profile(self, profile: str) -> None:
        preset = human_profile_defaults(HUMAN_PROFILE_NATURAL)
        apply_typo_profile(preset, profile)
        self._is_applying_human_profile = True
        try:
            self._set_typo_controls_from_config(preset)
        finally:
            self._is_applying_human_profile = False

    def _on_typo_profile_selected(self, _event=None) -> None:
        profile = self.var_typo_profile.get()
        self._apply_typo_profile(profile)
        self._on_human_setting_changed()

    def _on_human_profile_selected(self, _event=None) -> None:
        profile = self.var_human_profile.get()
        if profile != HUMAN_PROFILE_CUSTOM:
            self._apply_human_profile(profile)
        self._update_human_preview()

    def _on_human_setting_changed(self, mark_custom: bool = True) -> None:
        if self._is_applying_human_profile:
            return
        if mark_custom and self.var_human_profile.get() != HUMAN_PROFILE_CUSTOM:
            self.var_human_profile.set(HUMAN_PROFILE_CUSTOM)
        self._update_human_preview()

    @staticmethod
    def _clamp_int(value: int, min_value: int, max_value: int) -> int:
        return max(min_value, min(max_value, value))

    @staticmethod
    def _clamp_float(value: float, min_value: float, max_value: float) -> float:
        return max(min_value, min(max_value, value))

    def _read_int(self, widget: ttk.Widget, default: int, min_value: int, max_value: int) -> int:
        try:
            value = int(str(widget.get()).strip())
        except Exception:
            value = default
        return self._clamp_int(value, min_value, max_value)

    def _read_float(
        self, widget: ttk.Widget, default: float, min_value: float, max_value: float
    ) -> float:
        try:
            value = float(str(widget.get()).strip())
        except Exception:
            value = default
        return self._clamp_float(value, min_value, max_value)

    def _build_human_config_from_ui(self) -> HumanTypingConfig:
        profile = self.var_human_profile.get()
        base_profile = profile if profile != HUMAN_PROFILE_CUSTOM else HUMAN_PROFILE_NATURAL
        config = human_profile_defaults(base_profile)

        config.profile = profile
        config.enabled = self.var_human_enabled.get()
        config.base_delay_ms = self._read_int(self.spn_human_base, config.base_delay_ms, 1, 600)
        config.jitter_ms = self._read_int(self.spn_human_jitter, config.jitter_ms, 0, 300)
        config.punctuation_pause_multiplier = self._read_float(
            self.spn_human_punct, config.punctuation_pause_multiplier, 1.0, 6.0
        )
        config.newline_pause_multiplier = self._read_float(
            self.spn_human_newline, config.newline_pause_multiplier, 1.0, 8.0
        )
        config.burst_min_chars = self._read_int(self.spn_human_burst_min, config.burst_min_chars, 1, 100)
        config.burst_max_chars = self._read_int(self.spn_human_burst_max, config.burst_max_chars, 1, 100)
        if config.burst_max_chars < config.burst_min_chars:
            config.burst_max_chars = config.burst_min_chars

        typo_profile = self.var_typo_profile.get().strip() or TYPO_PROFILE_NATURAL
        apply_typo_profile(config, typo_profile)
        config.typo_profile = typo_profile
        config.typo_enabled = self.var_typo_enabled.get()
        config.typo_probability = self._read_float(
            self.spn_typo_probability, config.typo_probability, 0.0, 0.3
        )

        config.safe_code_typo_mode = self.var_safe_code_typo_mode.get()
        config.debug_typo_events = False

        seed_raw = self.ent_human_seed.get().strip()
        if not seed_raw:
            config.seed = None
        else:
            try:
                config.seed = int(seed_raw)
            except ValueError:
                config.seed = None

        return config

    def _human_preview_text(self, config: HumanTypingConfig) -> str:
        if not config.enabled:
            return (
                "Human-like mode is OFF. Typing uses the standard fixed-delay mode "
                "(constant char + line delays)."
            )

        if config.jitter_ms <= 8:
            variance = "low"
        elif config.jitter_ms <= 24:
            variance = "moderate"
        else:
            variance = "high"

        cps = 1000.0 / max(1, config.base_delay_ms)
        typo_text = "on" if config.typo_enabled else "off"
        seed_text = f"seed={config.seed}" if config.seed is not None else "random seed each run"

        return (
            f"{config.profile}: about {cps:.1f} chars/sec with {variance} timing variation "
            f"(+/-{config.jitter_ms}ms), punctuation pauses x{config.punctuation_pause_multiplier:.1f}, "
            f"newline pauses x{config.newline_pause_multiplier:.1f}, bursts {config.burst_min_chars}-"
            f"{config.burst_max_chars} chars, typo simulation {typo_text} "
            f"profile={config.typo_profile}, p={config.typo_probability:.3f}, "
            f"safe-mode {'on' if config.safe_code_typo_mode else 'off'}, {seed_text}."
        )

    def _update_human_preview(self) -> None:
        config = self._build_human_config_from_ui()
        self.lbl_human_preview.configure(text=self._human_preview_text(config))

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
        self.lbl_target.configure(text=f"Target: {title}", foreground=self._colors["accent2"])

    def _capture_coords(self) -> None:
        messagebox.showinfo(
            "Capture Position",
            "After clicking OK, you have 3 seconds to position your mouse\n"
            "at the desired click point. The coordinates will be captured automatically.",
        )
        self.lbl_status.configure(text="Capturing position in 3s...", fg=self._colors["warning"])
        self.root.update()

        def _do_capture() -> None:
            import pyautogui
            import time

            time.sleep(3)
            x, y = pyautogui.position()
            self.root.after(0, lambda: self._set_coords(x, y))

        threading.Thread(target=_do_capture, daemon=True).start()

    def _set_coords(self, x: int, y: int) -> None:
        self.spn_x.delete(0, "end")
        self.spn_x.insert(0, str(x))
        self.spn_y.delete(0, "end")
        self.spn_y.insert(0, str(y))
        self.var_use_coords.set(True)
        self.lbl_status.configure(text=f"Captured position: ({x}, {y})", fg=self._colors["success"])

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
            "Make sure the cursor is at the correct insertion point.\n"
            "Press OK to start the countdown.",
        )
        if not ok:
            return

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

        char_delay = self._read_int(self.spn_char_delay, DEFAULT_CHAR_DELAY, 1, 1000)
        line_delay = self._read_int(self.spn_line_delay, DEFAULT_LINE_DELAY, 0, 5000)
        countdown = self._read_int(self.spn_countdown, DEFAULT_COUNTDOWN, 0, 10)
        mode = self.var_mode.get()
        human_config = self._build_human_config_from_ui()
        self._update_human_preview()

        self.typing_thread = start_typing(
            state=self.state,
            char_delay_ms=char_delay,
            line_delay_ms=line_delay,
            mode=mode,
            countdown=countdown,
            on_progress=self._on_progress,
            on_done=self._on_done,
            background=self.var_background.get(),
            human_config=human_config,
        )

        self._poll_status()

    def _on_pause(self) -> None:
        if self.state.status == STATUS_TYPING:
            self.state.is_paused = True
            self.state.status = STATUS_PAUSED
            self.btn_pause.configure(text="Resume (F7)")
        elif self.state.status == STATUS_PAUSED:
            self.state.is_paused = False
            self.state.status = STATUS_TYPING
            self.btn_pause.configure(text="Pause (F7)")

    def _on_stop(self) -> None:
        self.state.stop_requested = True
        self.state.is_paused = False
        self.state.status = STATUS_STOPPED

    def _on_progress(self, line_idx: int, char_idx: int, total_lines: int, total_chars: int) -> None:
        self.state.line_index = line_idx
        self.state.char_index = char_idx
        self.state.total_lines = total_lines
        self.state.total_chars = total_chars

    def _on_done(self, completed: bool, error_msg: str = "") -> None:
        self.root.after(0, lambda: self._finish(completed, error_msg))

    def _finish(self, completed: bool, error_msg: str = "") -> None:
        self.btn_pause.configure(text="Pause (F7)")
        if error_msg:
            self.state.status = STATUS_STOPPED
            self.lbl_status.configure(text=f"Error: {error_msg.splitlines()[0]}", fg=self._colors["danger"])
            messagebox.showerror("Typing Error", error_msg)
        elif completed:
            self.state.status = STATUS_DONE
        self._update_status_display()

    def _poll_status(self) -> None:
        self._update_status_display()
        if self.state.status in (STATUS_TYPING, STATUS_COUNTDOWN, STATUS_PAUSED):
            self.root.after(100, self._poll_status)

    def _update_status_display(self) -> None:
        c = self._colors
        s = self.state

        if s.status == STATUS_IDLE:
            self.lbl_status.configure(text="Idle", fg=c["muted"])
        elif s.status == STATUS_COUNTDOWN:
            self.lbl_status.configure(text=f"Countdown... {s.char_index}s", fg=c["warning"])
        elif s.status == STATUS_TYPING:
            self.lbl_status.configure(
                text=f"Typing - line {s.line_index + 1}/{s.total_lines} | char {s.char_index}/{s.total_chars}",
                fg=c["success"],
            )
        elif s.status == STATUS_PAUSED:
            self.lbl_status.configure(
                text=f"Paused - line {s.line_index + 1}/{s.total_lines} | char {s.char_index}/{s.total_chars}",
                fg=c["warning"],
            )
        elif s.status == STATUS_STOPPED:
            self.lbl_status.configure(text="Stopped", fg=c["danger"])
        elif s.status == STATUS_DONE:
            self.lbl_status.configure(text="Done", fg=c["success"])

    # Public API for global hotkeys
    def hotkey_start(self) -> None:
        self.root.after(0, self._on_start)

    def hotkey_pause(self) -> None:
        self.root.after(0, self._on_pause)

    def hotkey_stop(self) -> None:
        self.root.after(0, self._on_stop)

    def hotkey_capture(self) -> None:
        self.root.after(0, self._capture_coords)
