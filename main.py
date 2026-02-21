"""
main.py – Entry point for AutoTyper.

Run with:  python main.py
"""

import tkinter as tk
from pynput import keyboard

from settings import AppState
from gui import AutoTyperGUI


def main() -> None:
    state = AppState()

    root = tk.Tk()
    app = AutoTyperGUI(root, state)

    # ── Global hotkeys (work even when the window is not focused) ──
    def _on_f6():
        app.hotkey_start()

    def _on_f7():
        app.hotkey_pause()

    def _on_esc():
        app.hotkey_stop()

    def _on_capture():
        app.hotkey_capture()

    hotkeys = keyboard.GlobalHotKeys(
        {
            "<f6>": _on_f6,
            "<f7>": _on_f7,
            "<esc>": _on_esc,
            "<ctrl>+<shift>+c": _on_capture,
        }
    )
    hotkeys.daemon = True
    hotkeys.start()

    # ── Run ────────────────────────────────────────────────────
    root.protocol("WM_DELETE_WINDOW", lambda: _shutdown(root, hotkeys))
    root.mainloop()


def _shutdown(root: tk.Tk, hotkeys: keyboard.GlobalHotKeys) -> None:
    """Clean up and exit."""
    hotkeys.stop()
    root.destroy()


if __name__ == "__main__":
    main()
