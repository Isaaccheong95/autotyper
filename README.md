# AutoTyper

A Windows desktop productivity tool that automatically types text/code into any editor window (VS Code, Cursor, PyCharm, Notepad++, etc.). Built with Python 3, tkinter, and pyautogui.

> **This is a personal productivity / accessibility tool.** It does not bypass CAPTCHAs, anti-bot systems, or any security protections.

---

## Quick Start

### 1. Prerequisites

- **Python 3.10+** – [python.org/downloads](https://www.python.org/downloads/)
- **Windows 10/11**

### 2. Install dependencies

```bash
cd autotyper
pip install -r requirements.txt
```

### 3. Run

```bash
python main.py
```

---

## How to Use

1. **Paste or load text** – type/paste code into the text box, or click **Load File** to open a file.
2. **Select target window** – pick the editor from the dropdown (click **Refresh** if it's missing).
3. **Place your cursor** – click the exact insertion point in the target editor.
4. **Click Start (or press F6)** – confirm the dialog, then the countdown begins. Switch to your editor during the countdown.
5. **Pause / Resume** – press **F7** at any time.
6. **Emergency Stop** – press **Esc** to halt immediately.

### Optional: Coordinate Click Mode

If you want AutoTyper to click a specific position before typing:

1. Check **"Click position before typing"**.
2. Click **Capture (Ctrl+Shift+C)** → position your mouse → coordinates are saved after 3 seconds.
3. When you press Start, the tool will click that position first, then type.

---

## Global Hotkeys

| Hotkey | Action |
|---|---|
| **F6** | Start typing |
| **F7** | Pause / Resume |
| **Esc** | Emergency stop |
| **Ctrl+Shift+C** | Capture mouse coordinates |

These work even when the AutoTyper window is not focused.

---

## Typing Modes

| Mode | Behavior |
|---|---|
| **Char-by-char** | Types each character individually with the configured delay. Best for realistic typing simulation. |
| **Line-by-line** | Types each whole line at once, then presses Enter. Faster, useful as a fallback if an editor handles character input oddly. |

---

## Project Structure

```
autotyper/
├── main.py            # Entry point, global hotkeys
├── gui.py             # Tkinter GUI layout and event handlers
├── typing_engine.py   # Background typing thread (pause/resume/stop)
├── window_manager.py  # Window enumeration, activation (Win32 API)
├── settings.py        # Shared state dataclass, default constants
├── requirements.txt   # Python dependencies
└── README.md          # This file
```

### Key Functions

| Module | Function | Purpose |
|---|---|---|
| `window_manager` | `get_window_list()` | Enumerates visible windows via Win32 `EnumWindows` |
| `window_manager` | `activate_window(hwnd)` | Brings a window to the foreground |
| `typing_engine` | `start_typing(...)` | Launches the typing thread with countdown, mode dispatch, and progress callbacks |
| `typing_engine` | `_type_char_by_char(...)` | Character-level typing loop with pause/stop checks |
| `typing_engine` | `_type_line_by_line(...)` | Line-level typing loop |
| `gui` | `AutoTyperGUI` | Builds the full UI and handles button/hotkey events |

---

## Limitations

1. **UAC-elevated windows** – Windows blocks simulated input to admin/elevated processes. Run AutoTyper as admin if the target is elevated.
2. **`pyautogui.write()` is ASCII-only** – Unicode characters (non-Latin alphabets, emoji) may not type correctly. Use clipboard-paste mode (see v2 ideas) as a workaround.
3. **Tab handling** – Some editors (VS Code, PyCharm) intercept Tab for autocompletion/indentation. Character-by-char mode sends `Tab` keypresses, which may trigger editor features instead of inserting a tab character.
4. **Coordinate drift** – Saved (x, y) coordinates become invalid if the target window is moved or resized after capture.
5. **Focus stealing** – Other popups or notifications that steal focus during typing will cause characters to go to the wrong window.
6. **Speed floor** – Very low delays (< 5 ms) may be unreliable due to OS scheduling and `pyautogui`'s overhead.
7. **pyautogui fail-safe** – Moving the mouse to the top-left corner of the screen triggers `pyautogui.FailSafeException` and aborts typing. This is a safety feature.

---

## Suggested v2 Improvements

- **Save / load presets** – save text + settings as named profiles
- **Recent windows list** – remember the last few target windows
- **Hotkey customization** – let the user rebind F6/F7/Esc in settings
- **Clipboard-paste mode** – copy chunks to clipboard and Ctrl+V for Unicode support
- **Syntax-aware pauses** – add extra delays after certain tokens (`;`, `{`, etc.) for more natural-looking typing
- **Progress bar** – visual progress indicator in the GUI
- **System tray icon** – minimize to tray with status indicator
- **Logging** – save typing history to a log file
- **Multi-monitor support** – better coordinate handling across monitors
