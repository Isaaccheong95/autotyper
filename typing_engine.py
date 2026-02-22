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
from enum import Enum
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


class TypingPhase(str, Enum):
    """State machine phases for human-like typo and correction behavior."""

    TYPING_NORMAL = "TYPING_NORMAL"
    TYPO_ACTIVE_UNNOTICED = "TYPO_ACTIVE_UNNOTICED"
    TYPO_NOTICED_HESITATING = "TYPO_NOTICED_HESITATING"
    CORRECTING_BACKSPACE = "CORRECTING_BACKSPACE"
    CORRECTING_RETYPE = "CORRECTING_RETYPE"
    RESUME_NORMAL = "RESUME_NORMAL"


@dataclass
class TypoEvent:
    """Represents one injected typo and its correction progress."""

    original_char: str
    typed_wrong_char: str
    typo_index: int
    chars_typed_after_typo: int
    awareness_threshold_chars: int
    awareness_threshold_words: int | None
    words_typed_after_typo: int = 0
    _current_word_has_chars: bool = False

    @property
    def chars_to_backspace(self) -> int:
        return self.chars_typed_after_typo + 1


class FixedDelayStrategy:
    """Constant delay strategy (classic mode)."""

    def __init__(self, char_delay_s: float, line_delay_s: float) -> None:
        self.char_delay_s = max(0.0, char_delay_s)
        self.line_delay_s = max(0.0, line_delay_s)

    def get_delay(self, _char: str, context: DelayContext, _state: AppState) -> float:
        if context.char == "\n":
            return self.line_delay_s
        return self.char_delay_s

    def build_typo_event(self, _context: DelayContext) -> TypoEvent | None:
        return None

    def typo_notice_reached(self, _event: TypoEvent) -> bool:
        return False

    def correction_hesitation_delay(self, _event: TypoEvent, _line_text: str) -> float:
        return 0.0

    def maybe_double_hesitation_delay(self) -> float:
        return 0.0

    def backspace_delay(self) -> float:
        return 0.0

    def should_backspace_pause(self, _done: int, _total: int) -> bool:
        return False

    def backspace_pause_delay(self) -> float:
        return 0.0

    def typo_cooldown_chars(self) -> int:
        return 0

    def debug(self, _message: str) -> None:
        return


def _is_word_char(ch: str) -> bool:
    return ch.isalnum() or ch == "_"


def _track_words_after_typo(event: TypoEvent, typed_char: str) -> None:
    if _is_word_char(typed_char):
        event._current_word_has_chars = True
        return
    if event._current_word_has_chars:
        event.words_typed_after_typo += 1
        event._current_word_has_chars = False


def _finalize_typo_word_count(event: TypoEvent) -> None:
    if event._current_word_has_chars:
        event.words_typed_after_typo += 1
        event._current_word_has_chars = False


def _build_delay_contexts(text: str) -> tuple[list[DelayContext], list[str]]:
    """Build per-character contexts for the full text stream."""
    lines = text.split("\n")
    contexts: list[DelayContext] = []
    prev_char = ""
    global_index = 0

    for li, line in enumerate(lines):
        for ci, ch in enumerate(line):
            next_char = (
                line[ci + 1]
                if ci + 1 < len(line)
                else ("\n" if li < len(lines) - 1 else "")
            )
            contexts.append(
                DelayContext(
                    char=ch,
                    line_text=line,
                    line_index=li,
                    col_index=ci,
                    global_index=global_index,
                    prev_char=prev_char,
                    next_char=next_char,
                )
            )
            prev_char = ch
            global_index += 1

        if li < len(lines) - 1:
            next_char = lines[li + 1][0] if lines[li + 1] else ""
            contexts.append(
                DelayContext(
                    char="\n",
                    line_text=line,
                    line_index=li,
                    col_index=len(line),
                    global_index=global_index,
                    prev_char=prev_char,
                    next_char=next_char,
                )
            )
            prev_char = "\n"
            global_index += 1

    return contexts, lines


class HumanLikeDelayStrategy:
    """Context-aware timing strategy with bursts, pauses, and typo realism."""

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

    def build_typo_event(self, context: DelayContext) -> TypoEvent | None:
        if not self.config.typo_enabled:
            return None
        if self.rng.random() >= max(0.0, min(1.0, self.config.typo_probability)):
            return None
        if not self._is_typo_candidate(context):
            return None

        lower = context.char.lower()
        if lower not in _NEARBY_KEYS:
            return None

        wrong = self.rng.choice(_NEARBY_KEYS[lower])
        if context.char.isupper():
            wrong = wrong.upper()
        if wrong == context.char:
            return None

        min_chars = max(1, self.config.typo_awareness_min_chars)
        max_chars = max(min_chars, self.config.typo_awareness_max_chars)
        awareness_words: int | None = None
        if self.config.typo_awareness_word_based:
            min_words = max(0, self.config.typo_awareness_min_words)
            max_words = max(min_words, self.config.typo_awareness_max_words)
            awareness_words = self.rng.randint(min_words, max_words)

        return TypoEvent(
            original_char=context.char,
            typed_wrong_char=wrong,
            typo_index=context.global_index,
            chars_typed_after_typo=0,
            awareness_threshold_chars=self.rng.randint(min_chars, max_chars),
            awareness_threshold_words=awareness_words,
        )

    def typo_notice_reached(self, event: TypoEvent) -> bool:
        if event.chars_typed_after_typo >= event.awareness_threshold_chars:
            return True
        if event.awareness_threshold_words is None:
            return False
        return event.words_typed_after_typo >= event.awareness_threshold_words

    def correction_hesitation_delay(self, event: TypoEvent, line_text: str) -> float:
        min_ms = max(0, self.config.correction_hesitation_min_ms)
        max_ms = max(min_ms, self.config.correction_hesitation_max_ms)

        bonus_ms = 0.0
        if event.chars_to_backspace >= 8:
            bonus_ms += self.rng.uniform(40.0, 180.0)
        if self._is_symbol_heavy_line(line_text):
            bonus_ms += self.rng.uniform(35.0, 160.0)

        low = min_ms + (bonus_ms * 0.35)
        high = max_ms + bonus_ms
        if high < low:
            high = low
        return self.rng.uniform(low, high) / 1000.0

    def maybe_double_hesitation_delay(self) -> float:
        probability = max(0.0, min(1.0, self.config.double_hesitation_probability))
        if self.rng.random() >= probability:
            return 0.0
        return self.rng.uniform(0.05, 0.24)

    def backspace_delay(self) -> float:
        min_ms = max(1, self.config.backspace_min_ms)
        max_ms = max(min_ms, self.config.backspace_max_ms)
        delay_ms = self.rng.uniform(min_ms, max_ms)
        if self.rng.random() < 0.23:
            delay_ms *= self.rng.uniform(0.75, 1.2)
            delay_ms = max(min_ms, min(max_ms, delay_ms))
        return delay_ms / 1000.0

    def should_backspace_pause(self, done: int, total: int) -> bool:
        every_n = max(0, self.config.backspace_pause_every_n)
        if every_n <= 0:
            return False
        if total < every_n + 1:
            return False
        if done >= total:
            return False
        if done % every_n != 0:
            return False
        return True

    def backspace_pause_delay(self) -> float:
        min_ms = max(0, self.config.backspace_pause_min_ms)
        max_ms = max(min_ms, self.config.backspace_pause_max_ms)
        return self.rng.uniform(min_ms, max_ms) / 1000.0

    def typo_cooldown_chars(self) -> int:
        min_chars = max(0, self.config.typo_cooldown_min_chars)
        max_chars = max(min_chars, self.config.typo_cooldown_max_chars)
        return self.rng.randint(min_chars, max_chars)

    def debug(self, message: str) -> None:
        if self.config.debug_typo_events:
            print(f"[typo-debug] {message}", flush=True)

    def _is_typo_candidate(self, context: DelayContext) -> bool:
        ch = context.char
        lower = ch.lower()
        if lower not in _NEARBY_KEYS:
            return False
        if not self.config.safe_code_typo_mode:
            return True

        if not ch.isalpha():
            return False
        if "\\" in context.line_text:
            return False
        if self._likely_inside_string(context.line_text, context.col_index):
            return False

        indent_len = len(context.line_text) - len(context.line_text.lstrip(" \t"))
        if context.col_index < indent_len:
            return False
        return True

    @staticmethod
    def _likely_inside_string(line: str, col_index: int) -> bool:
        active_quote = ""
        escaped = False
        for i, ch in enumerate(line):
            if i > col_index:
                break
            if escaped:
                escaped = False
                continue
            if ch == "\\":
                escaped = True
                continue
            if ch in ("'", '"'):
                if not active_quote:
                    active_quote = ch
                elif active_quote == ch:
                    active_quote = ""
        return bool(active_quote)

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
    contexts, lines = _build_delay_contexts(text)
    state.total_lines = len(lines)
    state.total_chars = len(text)
    next_index = 0
    phase = TypingPhase.TYPING_NORMAL
    typo_event: TypoEvent | None = None
    typo_cooldown_remaining = 0

    while True:
        if state.stop_requested:
            return False
        if not _wait_while_paused(state):
            return False

        if phase in (TypingPhase.TYPING_NORMAL, TypingPhase.TYPO_ACTIVE_UNNOTICED):
            if next_index >= len(contexts):
                if phase == TypingPhase.TYPO_ACTIVE_UNNOTICED and typo_event:
                    _finalize_typo_word_count(typo_event)
                    phase = TypingPhase.TYPO_NOTICED_HESITATING
                    continue
                return True

            context = contexts[next_index]
            state.line_index = context.line_index
            state.char_index = next_index

            emit_char = context.char
            injected = False
            if phase == TypingPhase.TYPING_NORMAL and typo_cooldown_remaining <= 0:
                candidate_event = delay_strategy.build_typo_event(context)
                if candidate_event:
                    typo_event = candidate_event
                    emit_char = candidate_event.typed_wrong_char
                    injected = True
                    phase = TypingPhase.TYPO_ACTIVE_UNNOTICED
                    delay_strategy.debug(
                        "injected typo at index "
                        f"{candidate_event.typo_index}: '{candidate_event.original_char}' "
                        f"-> '{candidate_event.typed_wrong_char}', awareness "
                        f"{candidate_event.awareness_threshold_chars} chars"
                        + (
                            f"/{candidate_event.awareness_threshold_words} words"
                            if candidate_event.awareness_threshold_words is not None
                            else ""
                        )
                    )

            send_fn(emit_char)
            next_index += 1
            on_progress(context.line_index, next_index, state.total_lines, state.total_chars)
            if typo_cooldown_remaining > 0:
                typo_cooldown_remaining -= 1

            if phase == TypingPhase.TYPO_ACTIVE_UNNOTICED and typo_event and not injected:
                typo_event.chars_typed_after_typo += 1
                _track_words_after_typo(typo_event, context.char)
                if delay_strategy.typo_notice_reached(typo_event):
                    phase = TypingPhase.TYPO_NOTICED_HESITATING
                    delay_strategy.debug(
                        "noticed typo after "
                        f"{typo_event.chars_typed_after_typo} chars / "
                        f"{typo_event.words_typed_after_typo} words"
                    )

            if not _sleep_with_controls(state, delay_strategy.get_delay(context.char, context, state)):
                return False
            continue

        if phase == TypingPhase.TYPO_NOTICED_HESITATING:
            if not typo_event:
                phase = TypingPhase.RESUME_NORMAL
                continue

            reference_index = min(max(0, next_index - 1), len(contexts) - 1) if contexts else 0
            line_text = contexts[reference_index].line_text if contexts else ""
            hesitation = delay_strategy.correction_hesitation_delay(typo_event, line_text)
            delay_strategy.debug(f"hesitation before correction: {hesitation * 1000:.0f} ms")
            if not _sleep_with_controls(state, hesitation):
                return False

            second_pause = delay_strategy.maybe_double_hesitation_delay()
            if second_pause > 0:
                delay_strategy.debug(f"second hesitation: {second_pause * 1000:.0f} ms")
                if not _sleep_with_controls(state, second_pause):
                    return False

            phase = TypingPhase.CORRECTING_BACKSPACE
            continue

        if phase == TypingPhase.CORRECTING_BACKSPACE:
            if not typo_event:
                phase = TypingPhase.RESUME_NORMAL
                continue

            to_backspace = max(0, next_index - typo_event.typo_index)
            for count in range(1, to_backspace + 1):
                if state.stop_requested:
                    return False
                if not _wait_while_paused(state):
                    return False
                send_fn("\b")
                if not _sleep_with_controls(state, delay_strategy.backspace_delay()):
                    return False
                if delay_strategy.should_backspace_pause(count, to_backspace):
                    pause_s = delay_strategy.backspace_pause_delay()
                    delay_strategy.debug(
                        f"mid-correction pause after {count} backspaces: {pause_s * 1000:.0f} ms"
                    )
                    if not _sleep_with_controls(state, pause_s):
                        return False

            delay_strategy.debug(f"backspaced {to_backspace} chars")
            phase = TypingPhase.CORRECTING_RETYPE
            continue

        if phase == TypingPhase.CORRECTING_RETYPE:
            if not typo_event:
                phase = TypingPhase.RESUME_NORMAL
                continue

            for idx in range(typo_event.typo_index, next_index):
                if state.stop_requested:
                    return False
                if not _wait_while_paused(state):
                    return False
                context = contexts[idx]
                state.line_index = context.line_index
                send_fn(context.char)
                if not _sleep_with_controls(state, delay_strategy.get_delay(context.char, context, state)):
                    return False

            delay_strategy.debug(
                "corrected typo at index "
                f"{typo_event.typo_index}; resumed typing at source index {next_index}"
            )
            typo_cooldown_remaining = delay_strategy.typo_cooldown_chars()
            phase = TypingPhase.RESUME_NORMAL
            continue

        if phase == TypingPhase.RESUME_NORMAL:
            typo_event = None
            phase = TypingPhase.TYPING_NORMAL
            continue


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
