"""Routes a live MIDI event stream between the hands-free control layer
and the performance recording — the piece that turns midi_io + control
into an actual practice session, instead of two disconnected modules.

Pure logic (`PracticeSession`), unit tested with synthetic events — no
hardware needed. Wiring it to real MIDI capture (`midi_io.MidiSession`)
and a live `pianomatic practice` CLI command is the next step, see
docs/STATUS.md — not done here since it needs real hardware to verify
(coordinating live key presses over a chat turn is impractical, see the
keyboard-range calibration exchange earlier in the session).
"""

from __future__ import annotations

from pianomatic.control import HandsFreeControl
from pianomatic.diff import PerformedNote
from pianomatic.midi_io import ControlChangeEvent, Event, NoteEvent


class PracticeSession:
    """Feed it every MIDI event as it arrives (`handle_event`). Anchor
    presses/releases and any note played while armed are consumed by the
    control layer and never recorded as music. Everything else becomes a
    `PerformedNote`, timestamped in seconds from the first event received
    (so it lines up with `diff.extract_performed_notes`' time base for a
    plain MIDI file starting at t=0).

    Sustain pedal (CC64) is currently ignored — recording pedal state is
    future work, see docs/ARCHITECTURE.md, "Sustain pedal" section.
    """

    def __init__(self, control: HandsFreeControl) -> None:
        self._control = control
        self._start_time: float | None = None
        self.performed_notes: list[PerformedNote] = []

    def handle_event(self, event: Event) -> None:
        if isinstance(event, ControlChangeEvent):
            return
        if not isinstance(event, NoteEvent):
            return

        if self._start_time is None:
            self._start_time = event.timestamp

        if not event.on:
            self._control.handle_note_off(event.note)
            return

        consumed = self._control.handle_note_on(event.note, event.velocity)
        if not consumed:
            self.performed_notes.append(
                PerformedNote(
                    pitch=event.note,
                    time=event.timestamp - self._start_time,
                    velocity=event.velocity,
                )
            )
