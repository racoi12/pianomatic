from pianomatic.control import HandsFreeControl
from pianomatic.midi_io import ControlChangeEvent, NoteEvent
from pianomatic.session import PracticeSession

LOW, HIGH = 36, 96


def _session(commands=("stop",)):
    fired = []
    control = HandsFreeControl(LOW, HIGH, list(commands), on_command=fired.append)
    return PracticeSession(control), fired


def test_ordinary_note_is_recorded_as_performed():
    session, _ = _session()
    session.handle_event(NoteEvent(note=60, velocity=90, on=True, timestamp=10.0, port="p"))
    assert len(session.performed_notes) == 1
    note = session.performed_notes[0]
    assert note.pitch == 60
    assert note.velocity == 90
    assert note.time == 0.0  # relative to first event, not absolute


def test_time_is_relative_to_first_event():
    session, _ = _session()
    session.handle_event(NoteEvent(note=60, velocity=90, on=True, timestamp=10.0, port="p"))
    session.handle_event(NoteEvent(note=62, velocity=90, on=True, timestamp=11.5, port="p"))
    assert session.performed_notes[1].time == 1.5


def test_anchor_notes_are_not_recorded_as_performed():
    session, _ = _session()
    session.handle_event(NoteEvent(note=LOW, velocity=100, on=True, timestamp=0.0, port="p"))
    session.handle_event(NoteEvent(note=HIGH, velocity=100, on=True, timestamp=0.1, port="p"))
    assert session.performed_notes == []


def test_command_note_while_armed_fires_command_and_is_not_recorded():
    session, fired = _session(commands=["stop"])
    session.handle_event(NoteEvent(note=LOW, velocity=100, on=True, timestamp=0.0, port="p"))
    session.handle_event(NoteEvent(note=HIGH, velocity=100, on=True, timestamp=0.1, port="p"))
    command_note = next(iter(session._control._position_map))
    session.handle_event(NoteEvent(note=command_note, velocity=100, on=True, timestamp=0.2, port="p"))
    assert fired == ["stop"]
    assert session.performed_notes == []


def test_music_before_and_after_control_gesture_is_recorded():
    session, _ = _session()
    session.handle_event(NoteEvent(note=60, velocity=90, on=True, timestamp=0.0, port="p"))
    session.handle_event(NoteEvent(note=LOW, velocity=100, on=True, timestamp=1.0, port="p"))
    session.handle_event(NoteEvent(note=HIGH, velocity=100, on=True, timestamp=1.1, port="p"))
    session.handle_event(NoteEvent(note=LOW, velocity=0, on=False, timestamp=1.2, port="p"))
    session.handle_event(NoteEvent(note=HIGH, velocity=0, on=False, timestamp=1.3, port="p"))
    session.handle_event(NoteEvent(note=64, velocity=90, on=True, timestamp=2.0, port="p"))
    assert [n.pitch for n in session.performed_notes] == [60, 64]


def test_control_change_events_are_ignored():
    session, _ = _session()
    session.handle_event(ControlChangeEvent(control=64, value=127, timestamp=0.0, port="p"))
    assert session.performed_notes == []


def test_note_off_does_not_create_a_performed_note():
    session, _ = _session()
    session.handle_event(NoteEvent(note=60, velocity=90, on=True, timestamp=0.0, port="p"))
    session.handle_event(NoteEvent(note=60, velocity=0, on=False, timestamp=0.5, port="p"))
    assert len(session.performed_notes) == 1  # only the note-on
