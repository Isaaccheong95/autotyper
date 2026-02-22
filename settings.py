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

# Typo correction profiles
TYPO_PROFILE_OFF = "Off"
TYPO_PROFILE_SUBTLE = "Subtle"
TYPO_PROFILE_NATURAL = "Natural"
TYPO_PROFILE_MESSY = "Messy but realistic"
TYPO_PROFILES = [
    TYPO_PROFILE_OFF,
    TYPO_PROFILE_SUBTLE,
    TYPO_PROFILE_NATURAL,
    TYPO_PROFILE_MESSY,
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

    typo_profile: str = TYPO_PROFILE_NATURAL
    typo_enabled: bool = False
    typo_probability: float = 0.006
    typo_cooldown_min_chars: int = 28
    typo_cooldown_max_chars: int = 72

    typo_awareness_min_chars: int = 2
    typo_awareness_max_chars: int = 9
    typo_awareness_word_based: bool = False
    typo_awareness_min_words: int = 0
    typo_awareness_max_words: int = 1

    correction_hesitation_min_ms: int = 240
    correction_hesitation_max_ms: int = 900
    double_hesitation_probability: float = 0.16

    backspace_min_ms: int = 45
    backspace_max_ms: int = 170
    backspace_pause_every_n: int = 6
    backspace_pause_min_ms: int = 80
    backspace_pause_max_ms: int = 260

    safe_code_typo_mode: bool = True
    debug_typo_events: bool = False

    long_word_pause_min_ms: int = 20
    long_word_pause_max_ms: int = 110
    symbol_line_pause_min_ms: int = 25
    symbol_line_pause_max_ms: int = 100

    code_pause_probability: float = 0.35
    code_pause_min_ms: int = 200
    code_pause_max_ms: int = 650

    seed: int | None = None


def apply_typo_profile(config: HumanTypingConfig, profile: str) -> None:
    """Apply typo timing defaults for the given correction profile."""
    if profile == TYPO_PROFILE_OFF:
        config.typo_profile = TYPO_PROFILE_OFF
        config.typo_enabled = False
        config.typo_probability = 0.0
        config.typo_cooldown_min_chars = 60
        config.typo_cooldown_max_chars = 120
        config.typo_awareness_min_chars = 2
        config.typo_awareness_max_chars = 8
        config.typo_awareness_word_based = False
        config.typo_awareness_min_words = 0
        config.typo_awareness_max_words = 1
        config.correction_hesitation_min_ms = 220
        config.correction_hesitation_max_ms = 700
        config.double_hesitation_probability = 0.10
        config.backspace_min_ms = 40
        config.backspace_max_ms = 130
        config.backspace_pause_every_n = 7
        config.backspace_pause_min_ms = 70
        config.backspace_pause_max_ms = 220
        return

    if profile == TYPO_PROFILE_SUBTLE:
        config.typo_profile = TYPO_PROFILE_SUBTLE
        config.typo_enabled = True
        config.typo_probability = 0.003
        config.typo_cooldown_min_chars = 45
        config.typo_cooldown_max_chars = 110
        config.typo_awareness_min_chars = 2
        config.typo_awareness_max_chars = 6
        config.typo_awareness_word_based = False
        config.typo_awareness_min_words = 0
        config.typo_awareness_max_words = 1
        config.correction_hesitation_min_ms = 220
        config.correction_hesitation_max_ms = 680
        config.double_hesitation_probability = 0.12
        config.backspace_min_ms = 42
        config.backspace_max_ms = 135
        config.backspace_pause_every_n = 7
        config.backspace_pause_min_ms = 70
        config.backspace_pause_max_ms = 220
        return

    if profile == TYPO_PROFILE_MESSY:
        config.typo_profile = TYPO_PROFILE_MESSY
        config.typo_enabled = True
        config.typo_probability = 0.014
        config.typo_cooldown_min_chars = 20
        config.typo_cooldown_max_chars = 60
        config.typo_awareness_min_chars = 3
        config.typo_awareness_max_chars = 12
        config.typo_awareness_word_based = True
        config.typo_awareness_min_words = 0
        config.typo_awareness_max_words = 2
        config.correction_hesitation_min_ms = 280
        config.correction_hesitation_max_ms = 1200
        config.double_hesitation_probability = 0.28
        config.backspace_min_ms = 50
        config.backspace_max_ms = 190
        config.backspace_pause_every_n = 5
        config.backspace_pause_min_ms = 90
        config.backspace_pause_max_ms = 320
        return

    # Natural
    config.typo_profile = TYPO_PROFILE_NATURAL
    config.typo_enabled = True
    config.typo_probability = 0.006
    config.typo_cooldown_min_chars = 28
    config.typo_cooldown_max_chars = 72
    config.typo_awareness_min_chars = 2
    config.typo_awareness_max_chars = 9
    config.typo_awareness_word_based = False
    config.typo_awareness_min_words = 0
    config.typo_awareness_max_words = 1
    config.correction_hesitation_min_ms = 240
    config.correction_hesitation_max_ms = 900
    config.double_hesitation_probability = 0.16
    config.backspace_min_ms = 45
    config.backspace_max_ms = 170
    config.backspace_pause_every_n = 6
    config.backspace_pause_min_ms = 80
    config.backspace_pause_max_ms = 260


def human_profile_defaults(profile: str) -> HumanTypingConfig:
    """Return preset settings for a human-like typing profile."""
    if profile == HUMAN_PROFILE_SMOOTH:
        config = HumanTypingConfig(
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
            long_word_pause_min_ms=10,
            long_word_pause_max_ms=50,
            symbol_line_pause_min_ms=10,
            symbol_line_pause_max_ms=45,
            code_pause_probability=0.2,
            code_pause_min_ms=120,
            code_pause_max_ms=350,
        )
        apply_typo_profile(config, TYPO_PROFILE_OFF)
        return config
    if profile == HUMAN_PROFILE_SLOW:
        config = HumanTypingConfig(
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
            long_word_pause_min_ms=35,
            long_word_pause_max_ms=150,
            symbol_line_pause_min_ms=45,
            symbol_line_pause_max_ms=140,
            code_pause_probability=0.5,
            code_pause_min_ms=300,
            code_pause_max_ms=900,
        )
        apply_typo_profile(config, TYPO_PROFILE_OFF)
        return config
    # Natural and Custom both start from Natural defaults.
    config = HumanTypingConfig(
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
        long_word_pause_min_ms=20,
        long_word_pause_max_ms=110,
        symbol_line_pause_min_ms=25,
        symbol_line_pause_max_ms=100,
        code_pause_probability=0.35,
        code_pause_min_ms=200,
        code_pause_max_ms=650,
    )
    apply_typo_profile(config, TYPO_PROFILE_OFF)
    return config


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
