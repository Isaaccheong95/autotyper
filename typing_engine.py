"""
typing_engine.py - Background typing thread with pause / resume / stop.

Uses Win32 PostMessage + WM_CHAR to send characters directly to the target
window's edit control. This allows the user to switch to other windows
while typing continues in the original target.

Fallback: if PostMessage does not work for a particular editor (for example
some Electron apps), the user can switch to foreground mode.
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes
import random
import threading
import time
import traceback
from dataclasses import dataclass
from typing import Callable

import pyautogui

from settings import (
    AppState,
    HumanTypingConfig,
    MODE_LINE,
    STATUS_COUNTDOWN,
    STATUS_DONE,
    STATUS_STOPPED,
    STATUS_TYPING,
)
from window_manager import activate_window, click_at

# We handle all timing ourselves (only used in foreground fallback mode).
pyautogui.PAUSE = 0
pyautogui.FAILSAFE = True

# Win32 constants and functions
_user32 = ctypes.windll.user32
_kernel32 = ctypes.windll.kernel32

PostMessageW = _user32.PostMessageW
GetWindowThreadProcessId = _user32.GetWindowThreadProcessId
AttachThreadInput = _user32.AttachThreadInput
GetFocus = _user32.GetFocus
GetCurrentThreadId = _kernel32.GetCurrentThreadId

WM_CHAR = 0x0102
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
VK_BACK = 0x08
VK_TAB = 0x09
VK_RETURN = 0x0D

# Delay between key-down and key-up for foreground mode (seconds).
_KEY_HOLD = 0.012

# Optional typo simulation map (QWERTY-nearby characters).
_NEARBY_KEYS = {
    "a": "qwsz",
    "b": "vghn",
    "c": "xdfv",
    "d": "ersfcx",
    "e": "wsdr",
    "f": "drtgvc",
    "g": "ftyhbv",
    "h": "gyujnb",
    "i": "ujko",
    "j": "huikmn",
    "k": "jiolm",
    "l": "kop",
    "m": "njk",
    "n": "bhjm",
    "o": "iklp",
    "p": "ol",
    "q": "wa",
    "r": "edft",
    "s": "awedxz",
    "t": "rfgy",
    "u": "yihj",
    "v": "cfgb",
    "w": "qase",
    "x": "zsdc",
    "y": "tugh",
    "z": "asx",
}

_PUNCTUATION_PAUSE_CHARS = {",", ".", ";", ":"}
_CLOSING_BRACKETS = {")", "]", "}"}


def _get_focused_child(hwnd: int) -> int:
    """Get the HWND of the focused child control inside *hwnd*."""
    remote_tid = GetWindowThreadProcessId(hwnd, None)
    local_tid = GetCurrentThreadId()

    AttachThreadInput(local_tid, remote_tid, True)
    focused = GetFocus()
    AttachThreadInput(local_tid, remote_tid, False)

    return focused if focused else hwnd


def _send_char_background(target_hwnd: int, ch: str) -> None:
    """Send *ch* to *target_hwnd* via PostMessage (background-safe)."""
    if ch == "\n":
        PostMessageW(target_hwnd, WM_KEYDOWN, VK_RETURN, 0)
        time.sleep(0.002)
        PostMessageW(target_hwnd, WM_KEYUP, VK_RETURN, 0)
    elif ch == "\t":
        PostMessageW(target_hwnd, WM_KEYDOWN, VK_TAB, 0)
        time.sleep(0.002)
        PostMessageW(target_hwnd, WM_KEYUP, VK_TAB, 0)
    elif ch == "\b":
        PostMessageW(target_hwnd, WM_KEYDOWN, VK_BACK, 0)
        time.sleep(0.002)
        PostMessageW(target_hwnd, WM_KEYUP, VK_BACK, 0)
    else:
        PostMessageW(target_hwnd, WM_CHAR, ord(ch), 0)


def _send_char_foreground(ch: str) -> None:
    """Send *ch* via pyautogui (requires target to be foreground window)."""
    if ch == "\t":
        pyautogui.keyDown("tab")
        time.sleep(_KEY_HOLD)
        pyautogui.keyUp("tab")
    elif ch == "\n":
        pyautogui.keyDown("enter")
        time.sleep(_KEY_HOLD)
        pyautogui.keyUp("enter")
    elif ch == "\b":
        pyautogui.keyDown("backspace")
        time.sleep(_KEY_HOLD)
        pyautogui.keyUp("backspace")
    else:
        pyautogui.keyDown(ch)
        time.sleep(_KEY_HOLD)
        pyautogui.keyUp(ch)


ProgressCB = Callable[[int, int, int, int], None]
DoneCB = Callable[[bool, str], None]


def _wait_while_paused(state: AppState) -> bool:
    """Spin-wait while paused (50 ms resolution)."""
    while state.is_paused:
        if state.stop_requested:
            return False
        time.sleep(0.05)
    return not state.stop_requested


def _sleep_with_controls(state: AppState, delay_s: float) -> bool:
    """Sleep with pause/stop awareness so long pauses stay interruptible."""
    if delay_s <= 0:
        return True

    deadline = time.perf_counter() + delay_s
    while True:
        if state.stop_requested:
            return False
        if state.is_paused:
            paused_at = time.perf_counter()
            if not _wait_while_paused(state):
                return False
            deadline += time.perf_counter() - paused_at
            continue

        remaining = deadline - time.perf_counter()
        if remaining <= 0:
            return True
        time.sleep(min(0.02, remaining))


@dataclass
class DelayContext:
    """Inputs for delay strategy calculations."""

    char: str
    line_text: str
    line_index: int
    col_index: int
    global_index: int
    prev_char: str
    next_char: str


class FixedDelayStrategy:
    """Constant delay strategy (classic mode)."""

    def __init__(self, char_delay_s: float, line_delay_s: float) -> None:
        self.char_delay_s = max(0.0, char_delay_s)
        self.line_delay_s = max(0.0, line_delay_s)

    def get_delay(self, _char: str, context: DelayContext, _state: AppState) -> float:
        if context.char == "\n":
            return self.line_delay_s
        return self.char_delay_s

    def maybe_typo(self, _char: str, _context: DelayContext) -> str | None:
        return None

    def typo_delay(self) -> float:
        return 0.0

    def correction_delay(self) -> float:
        return 0.0


class HumanLikeDelayStrategy:
    """Context-aware timing strategy with bursts, pauses, and optional typos."""

    def __init__(self, config: HumanTypingConfig) -> None:
        self.config = config
        self.rng = random.Random(config.seed)
        self._burst_remaining = 0

    def get_delay(self, _char: str, context: DelayContext, _state: AppState) -> float:
        base_ms = self._base_delay_ms(context)

        if context.char in _PUNCTUATION_PAUSE_CHARS:
            base_ms *= max(1.0, self.config.punctuation_pause_multiplier)
        elif context.char in _CLOSING_BRACKETS:
            base_ms *= max(1.1, self.config.punctuation_pause_multiplier * 0.85)

        if context.char == "\n":
            base_ms *= max(1.0, self.config.newline_pause_multiplier)
            self._burst_remaining = 0

            if self._line_looks_like_code_boundary(context.line_text):
                if self.rng.random() < self.config.code_pause_probability:
                    base_ms += self.rng.uniform(
                        self.config.code_pause_min_ms,
                        self.config.code_pause_max_ms,
                    )
        else:
            base_ms += self._burst_delay_component()
            base_ms += self._word_pause_component(context)
            base_ms += self._symbol_line_pause_component(context)

        return max(0.001, base_ms / 1000.0)

    def maybe_typo(self, char: str, _context: DelayContext) -> str | None:
        if not self.config.typo_enabled:
            return None
        if self.rng.random() >= self.config.typo_probability:
            return None

        lower = char.lower()
        if lower not in _NEARBY_KEYS:
            return None

        wrong = self.rng.choice(_NEARBY_KEYS[lower])
        if char.isupper():
            wrong = wrong.upper()
        if wrong == char:
            return None
        return wrong

    def typo_delay(self) -> float:
        return self.rng.uniform(0.015, 0.055)

    def correction_delay(self) -> float:
        return self.rng.uniform(0.010, 0.045)

    def _base_delay_ms(self, _context: DelayContext) -> float:
        jitter = self.rng.uniform(-self.config.jitter_ms, self.config.jitter_ms)
        return max(1.0, self.config.base_delay_ms + jitter)

    def _burst_delay_component(self) -> float:
        if self._burst_remaining <= 0:
            self._burst_remaining = self.rng.randint(
                max(1, self.config.burst_min_chars),
                max(1, self.config.burst_max_chars),
            )

        # Faster within a burst.
        burst_speedup = self.rng.uniform(0.18, 0.32) * self.config.base_delay_ms
        self._burst_remaining -= 1

        # Pause briefly at burst boundary.
        if self._burst_remaining <= 0:
            return -burst_speedup + self.rng.uniform(
                self.config.burst_pause_min_ms,
                self.config.burst_pause_max_ms,
            )
        return -burst_speedup

    def _word_pause_component(self, context: DelayContext) -> float:
        if not self._is_word_start(context):
            return 0.0

        word_len = self._word_length_from(context.line_text, context.col_index)
        if word_len < 8:
            return 0.0
        if self.rng.random() > 0.35:
            return 0.0

        return self.rng.uniform(
            self.config.long_word_pause_min_ms, self.config.long_word_pause_max_ms
        )

    def _symbol_line_pause_component(self, context: DelayContext) -> float:
        if context.col_index != 0:
            return 0.0
        if not self._is_symbol_heavy_line(context.line_text):
            return 0.0
        return self.rng.uniform(
            self.config.symbol_line_pause_min_ms, self.config.symbol_line_pause_max_ms
        )

    @staticmethod
    def _word_length_from(line: str, start: int) -> int:
        count = 0
        for idx in range(start, len(line)):
            ch = line[idx]
            if ch.isalnum() or ch == "_":
                count += 1
            else:
                break
        return count

    @staticmethod
    def _is_word_start(context: DelayContext) -> bool:
        ch = context.char
        if not (ch.isalnum() or ch == "_"):
            return False
        if context.col_index == 0:
            return True
        return not (context.prev_char.isalnum() or context.prev_char == "_")

    @staticmethod
    def _is_symbol_heavy_line(line: str) -> bool:
        stripped = line.strip()
        if not stripped:
            return False
        total = len(stripped)
        symbols = sum(
            1
            for ch in stripped
            if not (ch.isalnum() or ch.isspace() or ch == "_")
        )
        return (symbols / total) >= 0.28

    @staticmethod
    def _line_looks_like_code_boundary(line: str) -> bool:
        stripped = line.strip()
        if not stripped:
            return False

        starts = ("def ", "class ", "function ", "fn ", "if ", "for ", "while ")
        if stripped.startswith(starts):
            return True
        if stripped.endswith(("{", "}", ":", ");", "};")):
            return True
        return False


def _type_char_by_char(
    state: AppState,
    text: str,
    on_progress: ProgressCB,
    send_fn: Callable[[str], None],
    delay_strategy: FixedDelayStrategy | HumanLikeDelayStrategy,
) -> bool:
    lines = text.split("\n")
    state.total_lines = len(lines)
    state.total_chars = len(text)
    global_char = 0
    prev_char = ""

    for li, line in enumerate(lines):
        state.line_index = li

        for ci, ch in enumerate(line):
            if state.stop_requested:
                return False
            if not _wait_while_paused(state):
                return False

            next_char = line[ci + 1] if ci + 1 < len(line) else ("\n" if li < len(lines) - 1 else "")
            context = DelayContext(
                char=ch,
                line_text=line,
                line_index=li,
                col_index=ci,
                global_index=global_char,
                prev_char=prev_char,
                next_char=next_char,
            )

            typo_char = delay_strategy.maybe_typo(ch, context)
            if typo_char:
                send_fn(typo_char)
                if not _sleep_with_controls(state, delay_strategy.typo_delay()):
                    return False
                send_fn("\b")
                if not _sleep_with_controls(state, delay_strategy.correction_delay()):
                    return False

            state.char_index = global_char
            send_fn(ch)
            global_char += 1
            on_progress(li, global_char, state.total_lines, state.total_chars)

            if not _sleep_with_controls(
                state, delay_strategy.get_delay(ch, context, state)
            ):
                return False

            prev_char = ch

        if li < len(lines) - 1:
            if state.stop_requested:
                return False
            if not _wait_while_paused(state):
                return False

            next_char = lines[li + 1][0] if lines[li + 1] else ""
            context = DelayContext(
                char="\n",
                line_text=line,
                line_index=li,
                col_index=len(line),
                global_index=global_char,
                prev_char=prev_char,
                next_char=next_char,
            )

            send_fn("\n")
            global_char += 1
            on_progress(li, global_char, state.total_lines, state.total_chars)

            if not _sleep_with_controls(
                state, delay_strategy.get_delay("\n", context, state)
            ):
                return False

            prev_char = "\n"

    return True


def _type_line_by_line(
    state: AppState,
    text: str,
    line_delay: float,
    on_progress: ProgressCB,
    send_fn: Callable[[str], None],
) -> bool:
    lines = text.split("\n")
    state.total_lines = len(lines)
    state.total_chars = len(text)
    global_char = 0

    for li, line in enumerate(lines):
        if state.stop_requested:
            return False
        if not _wait_while_paused(state):
            return False

        state.line_index = li

        for ch in line:
            if state.stop_requested:
                return False
            send_fn(ch)
        global_char += len(line)

        if li < len(lines) - 1:
            send_fn("\n")
            global_char += 1

        on_progress(li, global_char, state.total_lines, state.total_chars)
        if not _sleep_with_controls(state, line_delay):
            return False

    return True


def start_typing(
    state: AppState,
    char_delay_ms: int,
    line_delay_ms: int,
    mode: str,
    countdown: int,
    on_progress: ProgressCB,
    on_done: DoneCB,
    background: bool = True,
    human_config: HumanTypingConfig | None = None,
) -> threading.Thread:
    """Launch the typing process on a background thread."""

    def _worker() -> None:
        try:
            char_delay = char_delay_ms / 1000.0
            line_delay = line_delay_ms / 1000.0

            # Countdown
            state.status = STATUS_COUNTDOWN
            for remaining in range(countdown, 0, -1):
                if state.stop_requested:
                    state.status = STATUS_STOPPED
                    on_done(False, "")
                    return
                on_progress(-1, remaining, 0, 0)
                time.sleep(1)

            # Activate target window and capture edit control
            if state.target_hwnd:
                if not activate_window(state.target_hwnd):
                    state.status = STATUS_STOPPED
                    on_done(False, "Could not activate target window")
                    return
            time.sleep(0.3)

            if state.use_coords and (state.coord_x or state.coord_y):
                click_at(state.coord_x, state.coord_y)
                time.sleep(0.15)

            edit_hwnd = _get_focused_child(state.target_hwnd) if background else 0

            if background and edit_hwnd:

                def send_fn(ch: str) -> None:
                    _send_char_background(edit_hwnd, ch)

            else:
                send_fn = _send_char_foreground

            state.status = STATUS_TYPING
            text = state.text

            strategy: FixedDelayStrategy | HumanLikeDelayStrategy
            if human_config and human_config.enabled and mode != MODE_LINE:
                strategy = HumanLikeDelayStrategy(human_config)
            else:
                strategy = FixedDelayStrategy(char_delay, line_delay)

            if mode == MODE_LINE:
                completed = _type_line_by_line(
                    state=state,
                    text=text,
                    line_delay=line_delay,
                    on_progress=on_progress,
                    send_fn=send_fn,
                )
            else:
                completed = _type_char_by_char(
                    state=state,
                    text=text,
                    on_progress=on_progress,
                    send_fn=send_fn,
                    delay_strategy=strategy,
                )

            state.status = STATUS_DONE if completed else STATUS_STOPPED
            on_done(completed, "")

        except Exception as e:
            state.status = STATUS_STOPPED
            on_done(False, f"Error: {e}\n{traceback.format_exc()}")

    t = threading.Thread(target=_worker, daemon=True)
    t.start()
    return t
