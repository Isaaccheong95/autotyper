"""
settings.py – Global state and default configuration for AutoTyper.
"""

from dataclasses import dataclass, field

# ── Default constants ──────────────────────────────────────────────
DEFAULT_CHAR_DELAY = 30      # ms between each character
DEFAULT_LINE_DELAY = 50      # ms extra pause at each newline
DEFAULT_COUNTDOWN  = 3       # seconds before typing begins

# Send‑mode identifiers
MODE_CHAR = "char"           # character-by-character
MODE_LINE = "line"           # whole-line then Enter

# Status labels
STATUS_IDLE      = "Idle"
STATUS_COUNTDOWN = "Countdown"
STATUS_TYPING    = "Typing"
STATUS_PAUSED    = "Paused"
STATUS_STOPPED   = "Stopped"
STATUS_DONE      = "Done"

# File types the Load File dialog accepts
FILE_TYPES = [
    ("All supported", "*.txt *.py *.js *.ts *.jsx *.tsx *.html *.css *.json "
                      "*.md *.go *.rs *.c *.cpp *.h *.java *.ahk *.xml *.yaml *.yml *.toml"),
    ("Text files", "*.txt"),
    ("Python",     "*.py"),
    ("JavaScript", "*.js *.ts *.jsx *.tsx"),
    ("Web",        "*.html *.css"),
    ("Data",       "*.json *.xml *.yaml *.yml *.toml"),
    ("All files",  "*.*"),
]


@dataclass
class AppState:
    """Mutable shared state used by the GUI and the typing thread."""

    status: str         = STATUS_IDLE
    text: str           = ""

    # Progress tracking
    line_index: int     = 0
    char_index: int     = 0
    total_chars: int    = 0
    total_lines: int    = 0

    # Pause / stop flags (checked by the typing thread)
    is_paused: bool     = False
    stop_requested: bool = False

    # Target window
    target_hwnd: int    = 0
    target_title: str   = ""

    # Optional coordinate-click before typing
    coord_x: int        = 0
    coord_y: int        = 0
    use_coords: bool    = False
