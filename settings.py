"""
settings.py - Global state and default configuration for AutoTyper.
"""

from dataclasses import dataclass

# Default constants
DEFAULT_CHAR_DELAY = 30  # ms between each character
DEFAULT_LINE_DELAY = 50  # ms extra pause at each newline
DEFAULT_COUNTDOWN = 3  # seconds before typing begins

# Send-mode identifiers
MODE_CHAR = "char"  # character-by-character
MODE_LINE = "line"  # whole-line then Enter

# Status labels
STATUS_IDLE = "Idle"
STATUS_COUNTDOWN = "Countdown"
STATUS_TYPING = "Typing"
STATUS_PAUSED = "Paused"
STATUS_STOPPED = "Stopped"
STATUS_DONE = "Done"

# Human-like typing profiles
HUMAN_PROFILE_SMOOTH = "Smooth"
HUMAN_PROFILE_NATURAL = "Natural"
HUMAN_PROFILE_SLOW = "Slow & Deliberate"
HUMAN_PROFILE_CUSTOM = "Custom"
HUMAN_PROFILES = [
    HUMAN_PROFILE_SMOOTH,
    HUMAN_PROFILE_NATURAL,
    HUMAN_PROFILE_SLOW,
    HUMAN_PROFILE_CUSTOM,
]

# File types the Load File dialog accepts
FILE_TYPES = [
    (
        "All supported",
        "*.txt *.py *.js *.ts *.jsx *.tsx *.html *.css *.json "
        "*.md *.go *.rs *.c *.cpp *.h *.java *.ahk *.xml *.yaml *.yml *.toml",
    ),
    ("Text files", "*.txt"),
    ("Python", "*.py"),
    ("JavaScript", "*.js *.ts *.jsx *.tsx"),
    ("Web", "*.html *.css"),
    ("Data", "*.json *.xml *.yaml *.yml *.toml"),
    ("All files", "*.*"),
]


@dataclass
class HumanTypingConfig:
    """Configuration for the human-like delay strategy."""

    enabled: bool = False
    profile: str = HUMAN_PROFILE_NATURAL

    base_delay_ms: int = 45
    jitter_ms: int = 18

    punctuation_pause_multiplier: float = 2.0
    newline_pause_multiplier: float = 2.8

    burst_min_chars: int = 8
    burst_max_chars: int = 20
    burst_pause_min_ms: int = 150
    burst_pause_max_ms: int = 500

    typo_enabled: bool = False
    typo_probability: float = 0.01

    long_word_pause_min_ms: int = 20
    long_word_pause_max_ms: int = 110
    symbol_line_pause_min_ms: int = 25
    symbol_line_pause_max_ms: int = 100

    code_pause_probability: float = 0.35
    code_pause_min_ms: int = 200
    code_pause_max_ms: int = 650

    seed: int | None = None


def human_profile_defaults(profile: str) -> HumanTypingConfig:
    """Return preset settings for a human-like typing profile."""
    if profile == HUMAN_PROFILE_SMOOTH:
        return HumanTypingConfig(
            enabled=True,
            profile=HUMAN_PROFILE_SMOOTH,
            base_delay_ms=35,
            jitter_ms=8,
            punctuation_pause_multiplier=1.4,
            newline_pause_multiplier=1.9,
            burst_min_chars=14,
            burst_max_chars=24,
            burst_pause_min_ms=120,
            burst_pause_max_ms=260,
            typo_enabled=False,
            typo_probability=0.005,
            long_word_pause_min_ms=10,
            long_word_pause_max_ms=50,
            symbol_line_pause_min_ms=10,
            symbol_line_pause_max_ms=45,
            code_pause_probability=0.2,
            code_pause_min_ms=120,
            code_pause_max_ms=350,
        )
    if profile == HUMAN_PROFILE_SLOW:
        return HumanTypingConfig(
            enabled=True,
            profile=HUMAN_PROFILE_SLOW,
            base_delay_ms=85,
            jitter_ms=35,
            punctuation_pause_multiplier=2.8,
            newline_pause_multiplier=4.0,
            burst_min_chars=6,
            burst_max_chars=12,
            burst_pause_min_ms=260,
            burst_pause_max_ms=700,
            typo_enabled=False,
            typo_probability=0.008,
            long_word_pause_min_ms=35,
            long_word_pause_max_ms=150,
            symbol_line_pause_min_ms=45,
            symbol_line_pause_max_ms=140,
            code_pause_probability=0.5,
            code_pause_min_ms=300,
            code_pause_max_ms=900,
        )
    # Natural and Custom both start from Natural defaults.
    return HumanTypingConfig(
        enabled=True,
        profile=HUMAN_PROFILE_NATURAL,
        base_delay_ms=45,
        jitter_ms=18,
        punctuation_pause_multiplier=2.0,
        newline_pause_multiplier=2.8,
        burst_min_chars=8,
        burst_max_chars=20,
        burst_pause_min_ms=150,
        burst_pause_max_ms=500,
        typo_enabled=False,
        typo_probability=0.01,
        long_word_pause_min_ms=20,
        long_word_pause_max_ms=110,
        symbol_line_pause_min_ms=25,
        symbol_line_pause_max_ms=100,
        code_pause_probability=0.35,
        code_pause_min_ms=200,
        code_pause_max_ms=650,
    )


@dataclass
class AppState:
    """Mutable shared state used by the GUI and the typing thread."""

    status: str = STATUS_IDLE
    text: str = ""

    # Progress tracking
    line_index: int = 0
    char_index: int = 0
    total_chars: int = 0
    total_lines: int = 0

    # Pause / stop flags (checked by the typing thread)
    is_paused: bool = False
    stop_requested: bool = False

    # Target window
    target_hwnd: int = 0
    target_title: str = ""

    # Optional coordinate-click before typing
    coord_x: int = 0
    coord_y: int = 0
    use_coords: bool = False
