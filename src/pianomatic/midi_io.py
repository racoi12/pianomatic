"""Raw MIDI event capture with timestamps.

Two layers: a pure translation function (`translate`, testable without
hardware) and `MidiSession` (thin real-port glue, needs a MIDI backend +
device — not unit-tested, exercised manually against real hardware).

Must also handle Control Change events, not just notes — the sustain
pedal arrives as CC64, not a note event (see docs/ARCHITECTURE.md,
"Sustain pedal" section). And must support merging multiple simultaneous
MIDI input ports into one event stream from the start (Keystation for
notes now, a separate MIDI foot-pedal unit later) — don't assume a single
connected device.
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from dataclasses import dataclass

import mido

POLL_INTERVAL_SECONDS = 0.001


@dataclass(frozen=True, slots=True)
class NoteEvent:
    note: int
    velocity: int
    on: bool
    timestamp: float
    port: str


@dataclass(frozen=True, slots=True)
class ControlChangeEvent:
    control: int
    value: int
    timestamp: float
    port: str


SUSTAIN_PEDAL_CONTROL = 64

Event = NoteEvent | ControlChangeEvent


def translate(message: mido.Message, timestamp: float, port: str) -> Event | None:
    """Pure: mido.Message -> our event type, or None for messages we don't care about."""
    if message.type == "note_on":
        return NoteEvent(
            note=message.note,
            velocity=message.velocity,
            on=message.velocity > 0,  # vel=0 note_on == note_off, MIDI convention
            timestamp=timestamp,
            port=port,
        )
    if message.type == "note_off":
        return NoteEvent(note=message.note, velocity=0, on=False, timestamp=timestamp, port=port)
    if message.type == "control_change":
        return ControlChangeEvent(
            control=message.control, value=message.value, timestamp=timestamp, port=port
        )
    return None


class MidiSession:
    """Opens one or more MIDI input ports and yields translated events in
    arrival order, merged, with wall-clock timestamps assigned on receipt.

    Polls each port's `iter_pending()` in a round-robin loop instead of
    using `mido.ports.MultiPort` — verified against real hardware
    (2026-08-12, see docs/STATUS.md) that MultiPort never delivers a
    single event in blocking mode: `_receive(block=True)` feeds
    `multi_receive()`'s generator (which loops forever when block=True)
    into `deque.extend()`, which can't return until the generator raises
    StopIteration — an infinite generator never does, so the call hangs
    forever on the very first receive and no event is ever yielded. A
    plain polling loop over `iter_pending()` (confirmed working directly
    against real hardware) sidesteps the bug entirely.
    """

    def __init__(self, port_names: list[str]) -> None:
        if not port_names:
            raise ValueError("MidiSession needs at least one port name")
        self._ports = [mido.open_input(name) for name in port_names]
        self._stopped = False

    def listen(self) -> Iterator[Event]:
        """Blocks forever waiting for MIDI input unless something calls
        `stop()` — a real bug (2026-08-12, see docs/STATUS.md) was
        calling code (the GUI) never having any way to interrupt this,
        so closing the window while a practice session was listening left
        a QThread running when Qt tore down the app, which Qt6 treats as
        fatal (aborts the whole process) rather than a soft warning.
        `stop()` is what a caller uses to end this cleanly from another
        thread.
        """
        while not self._stopped:
            for port in self._ports:
                for message in port.iter_pending():
                    event = translate(message, time.monotonic(), port=port.name)
                    if event is not None:
                        yield event
            time.sleep(POLL_INTERVAL_SECONDS)

    def stop(self) -> None:
        """Thread-safe enough for our use: a plain bool flip, read by the
        polling loop next iteration (at most POLL_INTERVAL_SECONDS later).
        """
        self._stopped = True

    def close(self) -> None:
        for port in self._ports:
            port.close()

    def __enter__(self) -> MidiSession:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()
