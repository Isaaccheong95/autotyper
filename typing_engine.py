"""
typing_engine.py – Background typing thread with pause / resume / stop.

Uses pyautogui.keyDown()/keyUp() with an explicit sleep between them so that
every keystroke is reliably registered by the OS and target editor.
"""

from __future__ import annotations

import threading
import time
import traceback
from typing import Callable

import pyautogui

from settings import (
    AppState,
    STATUS_COUNTDOWN,
    STATUS_TYPING,
    STATUS_STOPPED,
    STATUS_DONE,
)
from window_manager import activate_window, click_at

# We handle ALL timing ourselves.
pyautogui.PAUSE = 0
pyautogui.FAILSAFE = True

# Delay between key-down and key-up (seconds).
_KEY_HOLD = 0.012


def _send_char(ch: str) -> None:
    """Send a single character with an explicit hold between press and release."""
    if ch == "\t":
        pyautogui.keyDown("tab")
        time.sleep(_KEY_HOLD)
        pyautogui.keyUp("tab")
    elif ch == "\n":
        pyautogui.keyDown("enter")
        time.sleep(_KEY_HOLD)
        pyautogui.keyUp("enter")
    else:
        pyautogui.keyDown(ch)
        time.sleep(_KEY_HOLD)
        pyautogui.keyUp(ch)


# ── Callback types ────────────────────────────────────────────────

ProgressCB = Callable[
    [int, int, int, int], None
]  # line_idx, char_idx, total_lines, total_chars
DoneCB = Callable[[bool, str], None]  # completed?, error_msg


def _wait_while_paused(state: AppState) -> bool:
    """Spin-wait while paused. Returns False if stop was requested."""
    while state.is_paused:
        if state.stop_requested:
            return False
        time.sleep(0.05)
    return not state.stop_requested


def _type_char_by_char(
    state: AppState,
    text: str,
    char_delay: float,
    line_delay: float,
    on_progress: ProgressCB,
) -> bool:
    """Type *text* one character at a time. Returns True if completed."""
    lines = text.split("\n")
    state.total_lines = len(lines)
    state.total_chars = len(text)
    global_char = 0

    for li, line in enumerate(lines):
        state.line_index = li

        for ci, ch in enumerate(line):
            if state.stop_requested:
                return False
            if not _wait_while_paused(state):
                return False

            state.char_index = global_char
            _send_char(ch)

            global_char += 1
            on_progress(li, global_char, state.total_lines, state.total_chars)
            time.sleep(char_delay)

        # Newline (don't send after the very last line)
        if li < len(lines) - 1:
            if state.stop_requested:
                return False
            if not _wait_while_paused(state):
                return False
            _send_char("\n")
            global_char += 1
            on_progress(li, global_char, state.total_lines, state.total_chars)
            time.sleep(line_delay)

    return True


def _type_line_by_line(
    state: AppState,
    text: str,
    line_delay: float,
    on_progress: ProgressCB,
) -> bool:
    """Type *text* one full line at a time. Returns True if completed."""
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
            _send_char(ch)
        global_char += len(line)

        if li < len(lines) - 1:
            _send_char("\n")
            global_char += 1

        on_progress(li, global_char, state.total_lines, state.total_chars)
        time.sleep(line_delay)

    return True


def start_typing(
    state: AppState,
    char_delay_ms: int,
    line_delay_ms: int,
    mode: str,
    countdown: int,
    on_progress: ProgressCB,
    on_done: DoneCB,
) -> threading.Thread:
    """Launch the typing process on a background thread and return it."""

    def _worker():
        try:
            char_delay = char_delay_ms / 1000.0
            line_delay = line_delay_ms / 1000.0

            # ── Countdown ──────────────────────────────────────
            state.status = STATUS_COUNTDOWN
            for remaining in range(countdown, 0, -1):
                if state.stop_requested:
                    state.status = STATUS_STOPPED
                    on_done(False, "")
                    return
                on_progress(-1, remaining, 0, 0)
                time.sleep(1)

            # ── Activate target window ─────────────────────────
            if state.target_hwnd:
                if not activate_window(state.target_hwnd):
                    state.status = STATUS_STOPPED
                    on_done(False, "Could not activate target window")
                    return
            time.sleep(0.3)

            if state.use_coords and (state.coord_x or state.coord_y):
                click_at(state.coord_x, state.coord_y)
                time.sleep(0.15)

            # ── Type ───────────────────────────────────────────
            state.status = STATUS_TYPING
            text = state.text

            if mode == "line":
                completed = _type_line_by_line(state, text, line_delay, on_progress)
            else:
                completed = _type_char_by_char(
                    state, text, char_delay, line_delay, on_progress
                )

            state.status = STATUS_DONE if completed else STATUS_STOPPED
            on_done(completed, "")

        except Exception as e:
            state.status = STATUS_STOPPED
            on_done(False, f"Error: {e}\n{traceback.format_exc()}")

    t = threading.Thread(target=_worker, daemon=True)
    t.start()
    return t
