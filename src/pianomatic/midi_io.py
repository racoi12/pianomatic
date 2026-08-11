"""Raw MIDI event capture with timestamps.

Not implemented yet — see docs/STATUS.md. Planned interface:

    from pianomatic.midi_io import MidiSession

    session = MidiSession(port_name="USB Keystation 61es MIDI 1")
    for event in session.listen():
        # event: NoteEvent(note: int, velocity: int, on: bool, timestamp: float)
        ...

Backed by `mido` + `python-rtmidi` (already a dependency via
pymatchmaker[devices]). Events get forwarded to both
`control.HandsFreeControl` (for command detection) and `diff.py` (for
recording the performance), same stream, no duplicate MIDI connections.

Must also handle Control Change events, not just notes — the sustain
pedal arrives as CC64, not a note event (see docs/ARCHITECTURE.md,
"Sustain pedal" section). And must support merging multiple simultaneous
MIDI input ports into one event stream from the start (Keystation for
notes now, a separate MIDI foot-pedal unit later) — don't assume a single
connected device.
"""
