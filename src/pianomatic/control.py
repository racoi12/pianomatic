"""Hands-free control: anchor (lowest + highest note held together) plus
intermediate white keys as commands, mapped by relative position from the
low anchor. See docs/ARCHITECTURE.md, "Hands-free control" section for
the rationale.

Pure: doesn't touch MIDI hardware. `midi_io.py` / `session.py` feed this
class already-parsed events.
"""

from __future__ import annotations

from collections.abc import Callable

_WHITE_KEY_PITCH_CLASSES = frozenset({0, 2, 4, 5, 7, 9, 11})  # C D E F G A B

# M-Audio Keystation 61es real range, captured with aseqdump against the
# physical hardware on 2026-08-11 (see docs/STATUS.md) — C2 to C7, 60
# semitones / 61 keys. Not a guess: verified by pressing the two extreme
# keys and reading the actual NOTE_ON values.
KEYSTATION_61ES_LOW = 36
KEYSTATION_61ES_HIGH = 96


def _is_white_key(note: int) -> bool:
    return note % 12 in _WHITE_KEY_PITCH_CLASSES


class HandsFreeControl:
    """Detects the anchor+command gesture and fires `on_command(name)`.

    Design: while `low_anchor` and `high_anchor` are held at the same
    time, each intermediate white key played fires the command at that
    position (1st white key above the anchor = commands[0], etc.).
    Releasing an anchor without playing anything = no-op, back to normal
    piano mode.

    `handle_note_on`/`handle_note_off` return whether the event was
    consumed by the control layer (anchor press/release, or any note
    while armed — armed mode suppresses everything as music, matched or
    not, since the user's hands are pinning both extremes and won't be
    playing real music at that moment). Callers (e.g. `session.py`) use
    this to decide whether to also record the note as a performed note.
    """

    def __init__(
        self,
        low_anchor: int,
        high_anchor: int,
        commands: list[str],
        on_command: Callable[[str], None],
    ) -> None:
        if low_anchor >= high_anchor:
            raise ValueError("low_anchor must be less than high_anchor")
        self._low = low_anchor
        self._high = high_anchor
        self._on_command = on_command
        self._low_held = False
        self._high_held = False
        self._position_map = self._build_position_map(commands)
        # notes consumed while armed, so their later note-off is consumed too
        self._suppressed: set[int] = set()

    def _build_position_map(self, commands: list[str]) -> dict[int, str]:
        mapping: dict[int, str] = {}
        note = self._low + 1
        idx = 0
        while note < self._high and idx < len(commands):
            if _is_white_key(note):
                mapping[note] = commands[idx]
                idx += 1
            note += 1
        return mapping

    @property
    def armed(self) -> bool:
        return self._low_held and self._high_held

    def handle_note_on(self, note: int, velocity: int) -> bool:
        """Returns True if consumed by the control layer (not music)."""
        if velocity == 0:  # MIDI convention: NOTE_ON vel=0 == NOTE_OFF
            return self.handle_note_off(note)
        if note == self._low:
            self._low_held = True
            return True
        if note == self._high:
            self._high_held = True
            return True
        if self.armed:
            command = self._position_map.get(note)
            if command is not None:
                self._on_command(command)
            self._suppressed.add(note)
            return True
        return False

    def handle_note_off(self, note: int) -> bool:
        """Returns True if consumed by the control layer (not music)."""
        if note == self._low:
            self._low_held = False
            return True
        if note == self._high:
            self._high_held = False
            return True
        if note in self._suppressed:
            self._suppressed.discard(note)
            return True
        return False
