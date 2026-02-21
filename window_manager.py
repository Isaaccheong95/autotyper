"""
window_manager.py – Window enumeration, activation, and coordinate capture.
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes
import time
from typing import List, Tuple

import pyautogui


# ── Win32 helpers ──────────────────────────────────────────────────
user32 = ctypes.windll.user32

EnumWindows = user32.EnumWindows
GetWindowTextW = user32.GetWindowTextW
GetWindowTextLengthW = user32.GetWindowTextLengthW
IsWindowVisible = user32.IsWindowVisible
SetForegroundWindow = user32.SetForegroundWindow
ShowWindow = user32.ShowWindow
IsIconic = user32.IsIconic

SW_RESTORE = 9

ENUM_PROC = ctypes.WINFUNCTYPE(
    ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM
)

# Titles to filter out (system / shell windows)
_IGNORE_TITLES = {
    "",
    "Program Manager",
    "Windows Input Experience",
    "Microsoft Text Input Application",
    "Settings",
}


def get_window_list() -> List[Tuple[str, int]]:
    """Return a list of (title, hwnd) for all visible, titled windows."""
    results: List[Tuple[str, int]] = []

    def _callback(hwnd, _lParam):
        if IsWindowVisible(hwnd):
            length = GetWindowTextLengthW(hwnd)
            if length > 0:
                buf = ctypes.create_unicode_buffer(length + 1)
                GetWindowTextW(hwnd, buf, length + 1)
                title = buf.value
                if title not in _IGNORE_TITLES:
                    results.append((title, hwnd))
        return True  # continue enumeration

    EnumWindows(ENUM_PROC(_callback), 0)
    # Sort alphabetically for the dropdown
    results.sort(key=lambda t: t[0].lower())
    return results


def activate_window(hwnd: int) -> bool:
    """Bring *hwnd* to the foreground. Returns True on success."""
    try:
        if IsIconic(hwnd):
            ShowWindow(hwnd, SW_RESTORE)
        # Small delay so Windows processes the restore
        time.sleep(0.15)
        SetForegroundWindow(hwnd)
        time.sleep(0.15)
        return True
    except Exception:
        return False


def click_at(x: int, y: int) -> None:
    """Move the mouse to (x, y) and left-click."""
    pyautogui.click(x, y)
    time.sleep(0.1)
