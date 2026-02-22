# AutoTyper

A Windows desktop tool that types text or code into another app window (VS Code, Cursor, PyCharm, Notepad++, terminals, and more).

Built with Python 3, tkinter, Win32 APIs, `pyautogui`, and `pynput`.

> This is a personal productivity and accessibility tool. It does not bypass CAPTCHAs, anti-bot systems, or security controls.

## Latest Features

- Background typing via Win32 `PostMessage` (`WM_CHAR`) so typing can continue in the target while you use other windows.
- Foreground fallback mode for editors that do not accept background message-based input.
- Human-like typing engine with profile presets: `Smooth`, `Natural`, `Slow & Deliberate`, and `Custom`.
- Typo-and-correction simulation with typo profiles: `Off`, `Subtle`, `Natural`, and `Messy but realistic`.
- Safe code typo mode to avoid risky typo injection contexts (for example strings and escaped sections).
- Optional seed control for reproducible human-like timing runs.
- Context-aware timing effects:
  - punctuation and newline pause multipliers
  - burst typing with boundary pauses
  - extra pauses on long words, symbol-heavy lines, and likely code boundaries
- Optional coordinate click before typing (manual X/Y or delayed capture with `Ctrl+Shift+C`).
- Live status updates with line and character progress.

## Quick Start

### 1. Prerequisites

- Python 3.10+ ([python.org/downloads](https://www.python.org/downloads/))
- Windows 10/11

### 2. Install dependencies

```bash
cd autotyper
pip install -r requirements.txt
```

### 3. Run

```bash
python main.py
```

## How to Use

1. Paste text into the editor or click `Load File`.
2. Select the target window from the dropdown (`Refresh` if needed).
3. Place the target cursor at the insertion point.
4. Optional: enable `Click position before typing` and capture coordinates.
5. Choose typing settings:
   - `Char-by-char` or `Line-by-line`
   - background typing on/off
   - human-like typing profile and typo profile (optional)
6. Press `Start` (or `F6`), confirm, and wait for the countdown.
7. Use `F7` to pause/resume and `Esc` to stop immediately.

## Typing Modes

| Mode | Behavior |
|---|---|
| `Char-by-char` | Types one character at a time. Supports fixed delay mode or human-like timing mode. |
| `Line-by-line` | Types each line and submits newline boundaries quickly. Good fallback for some editors. |

## Send Modes

| Mode | Behavior |
|---|---|
| Background typing (default) | Activates the target window, locates focused control, and sends characters via Win32 messages. |
| Foreground typing | Uses `pyautogui` key events. Useful if background messaging does not work with a specific app. |

## Human-like Typing

Human-like mode is available in `Char-by-char` mode and includes:

- Configurable base speed and jitter.
- Punctuation/newline pause scaling.
- Burst rhythm simulation.
- Optional typo injection and realistic correction flow:
  - delayed typo awareness
  - hesitation before correction
  - backspacing with variable tempo and mini-pauses
  - retype and resume with cooldown

## Global Hotkeys

| Hotkey | Action |
|---|---|
| `F6` | Start typing |
| `F7` | Pause or resume |
| `Esc` | Stop |
| `Ctrl+Shift+C` | Capture mouse coordinates |

Hotkeys work globally, even when AutoTyper is not focused.

## Project Structure

```text
autotyper/
|-- main.py            # App entry point and global hotkeys
|-- gui.py             # Tkinter UI and handlers
|-- typing_engine.py   # Typing worker, strategies, typo simulation
|-- window_manager.py  # Window discovery/activation and clicking helpers
|-- settings.py        # Shared state, defaults, profiles
|-- requirements.txt   # Dependencies
`-- README.md          # Documentation
```

## Known Limitations

1. UAC and privilege boundaries: typing into elevated/admin apps may fail unless AutoTyper is run with matching privileges.
2. Background compatibility varies: some app frameworks may ignore `WM_CHAR`; use foreground mode in that case.
3. Special key behavior is app-specific: tabs/newlines may trigger editor features (autocomplete, indentation, command modes).
4. Coordinate drift: saved X/Y may become wrong after window moves, DPI changes, or monitor changes.
5. Foreground mode focus risk: if another window steals focus, input goes to the wrong app.
6. Very low delays can be unreliable because of OS scheduling and input stack limits.
7. `pyautogui` fail-safe is enabled; moving mouse to top-left can abort foreground typing.
