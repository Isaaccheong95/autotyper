"""
typing_engine.py – Background typing thread with pause / resume / stop.

Uses Win32 PostMessage + WM_CHAR to send characters directly to the target
window's edit control.  This allows the user to switch to other windows
while typing continues in the original target.

Fallback: if PostMessage doesn't work for a particular editor (e.g. some
Electron apps), the user can switch to "Foreground" mode which re-activates
the target window before each character.
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes
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

# We handle ALL timing ourselves (only used in foreground fallback mode).
pyautogui.PAUSE = 0
pyautogui.FAILSAFE = True

# ── Win32 constants & functions ───────────────────────────────────

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
VK_RETURN = 0x0D
VK_TAB = 0x09

# Delay between key-down and key-up for foreground mode (seconds).
_KEY_HOLD = 0.012


def _get_focused_child(hwnd: int) -> int:
    """Get the HWND of the focused child control inside *hwnd*.

    Uses AttachThreadInput to temporarily join the target's input queue
    so that GetFocus() returns the focused control in that window.
    Falls back to *hwnd* itself if nothing is focused.
    """
    remote_tid = GetWindowThreadProcessId(hwnd, None)
    local_tid = GetCurrentThreadId()

    AttachThreadInput(local_tid, remote_tid, True)
    focused = GetFocus()
    AttachThreadInput(local_tid, remote_tid, False)

    return focused if focused else hwnd


# ── Character senders ─────────────────────────────────────────────


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
    else:
        pyautogui.keyDown(ch)
        time.sleep(_KEY_HOLD)
        pyautogui.keyUp(ch)


# ── Callback types ────────────────────────────────────────────────

ProgressCB = Callable[[int, int, int, int], None]
DoneCB = Callable[[bool, str], None]


def _wait_while_paused(state: AppState) -> bool:
    """Spin-wait while paused (50 ms resolution)."""
    while state.is_paused:
        if state.stop_requested:
            return False
        time.sleep(0.05)
    return not state.stop_requested


# ── Typing loops ──────────────────────────────────────────────────


def _type_char_by_char(
    state: AppState,
    text: str,
    char_delay: float,
    line_delay: float,
    on_progress: ProgressCB,
    send_fn,
) -> bool:
    lines = text.split("\n")
    state.total_lines = len(lines)
    state.total_chars = len(text)
    global_char = 0

    for li, line in enumerate(lines):
        state.line_index = li

        for ch in line:
            if state.stop_requested:
                return False
            if not _wait_while_paused(state):
                return False

            state.char_index = global_char
            send_fn(ch)
            global_char += 1
            on_progress(li, global_char, state.total_lines, state.total_chars)
            time.sleep(char_delay)

        if li < len(lines) - 1:
            if state.stop_requested:
                return False
            if not _wait_while_paused(state):
                return False
            send_fn("\n")
            global_char += 1
            on_progress(li, global_char, state.total_lines, state.total_chars)
            time.sleep(line_delay)

    return True


def _type_line_by_line(
    state: AppState,
    text: str,
    line_delay: float,
    on_progress: ProgressCB,
    send_fn,
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
        time.sleep(line_delay)

    return True


# ── Main entry point ──────────────────────────────────────────────


def start_typing(
    state: AppState,
    char_delay_ms: int,
    line_delay_ms: int,
    mode: str,
    countdown: int,
    on_progress: ProgressCB,
    on_done: DoneCB,
    background: bool = True,
) -> threading.Thread:
    """Launch the typing process on a background thread."""

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

            # ── Activate target window & capture edit control ──
            if state.target_hwnd:
                if not activate_window(state.target_hwnd):
                    state.status = STATUS_STOPPED
                    on_done(False, "Could not activate target window")
                    return
            time.sleep(0.3)

            if state.use_coords and (state.coord_x or state.coord_y):
                click_at(state.coord_x, state.coord_y)
                time.sleep(0.15)

            # Capture the focused child control for background mode
            edit_hwnd = _get_focused_child(state.target_hwnd) if background else 0

            # Build the send function
            if background and edit_hwnd:

                def send_fn(ch: str) -> None:
                    _send_char_background(edit_hwnd, ch)

            else:
                send_fn = _send_char_foreground

            # ── Type ───────────────────────────────────────────
            state.status = STATUS_TYPING
            text = state.text

            if mode == "line":
                completed = _type_line_by_line(
                    state, text, line_delay, on_progress, send_fn
                )
            else:
                completed = _type_char_by_char(
                    state, text, char_delay, line_delay, on_progress, send_fn
                )

            state.status = STATUS_DONE if completed else STATUS_STOPPED
            on_done(completed, "")

        except Exception as e:
            state.status = STATUS_STOPPED
            on_done(False, f"Error: {e}\n{traceback.format_exc()}")

    t = threading.Thread(target=_worker, daemon=True)
    t.start()
    return t
