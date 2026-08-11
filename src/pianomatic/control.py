"""Control manos-libres: ancla (nota más grave + más aguda sostenidas)
más teclas blancas intermedias como comandos, mapeados por posición
relativa desde el ancla grave. Ver docs/ARCHITECTURE.md, sección
"Control manos-libres" para el porqué del diseño.

Puro: no toca hardware MIDI. `midi_io.py` alimenta esta clase con los
eventos ya parseados.
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
    """Detecta el gesto ancla+comando y dispara `on_command(nombre)`.

    Diseño: mientras `low_anchor` y `high_anchor` están sostenidas a la
    vez, cada tecla blanca intermedia tocada dispara el comando en esa
    posición (1ra tecla blanca sobre el ancla = commands[0], etc.).
    Soltar cualquier ancla sin tocar nada = no-op, vuelve a modo normal.
    """

    def __init__(
        self,
        low_anchor: int,
        high_anchor: int,
        commands: list[str],
        on_command: Callable[[str], None],
    ) -> None:
        if low_anchor >= high_anchor:
            raise ValueError("low_anchor debe ser menor que high_anchor")
        self._low = low_anchor
        self._high = high_anchor
        self._on_command = on_command
        self._low_held = False
        self._high_held = False
        self._position_map = self._build_position_map(commands)

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

    def handle_note_on(self, note: int, velocity: int) -> None:
        if velocity == 0:  # convención MIDI: NOTE_ON vel=0 == NOTE_OFF
            self.handle_note_off(note)
            return
        if note == self._low:
            self._low_held = True
            return
        if note == self._high:
            self._high_held = True
            return
        if self.armed:
            command = self._position_map.get(note)
            if command is not None:
                self._on_command(command)

    def handle_note_off(self, note: int) -> None:
        if note == self._low:
            self._low_held = False
        elif note == self._high:
            self._high_held = False
