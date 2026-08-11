import mido

from pianomatic.midi_io import ControlChangeEvent, NoteEvent, SUSTAIN_PEDAL_CONTROL, translate


def test_note_on_translates_to_note_event():
    msg = mido.Message("note_on", note=60, velocity=100)
    event = translate(msg, timestamp=1.5, port="test")
    assert event == NoteEvent(note=60, velocity=100, on=True, timestamp=1.5, port="test")


def test_note_on_with_zero_velocity_is_note_off():
    msg = mido.Message("note_on", note=60, velocity=0)
    event = translate(msg, timestamp=1.5, port="test")
    assert isinstance(event, NoteEvent)
    assert event.on is False


def test_note_off_translates_to_note_event_off():
    msg = mido.Message("note_off", note=60, velocity=64)
    event = translate(msg, timestamp=2.0, port="test")
    assert isinstance(event, NoteEvent)
    assert event.on is False
    assert event.note == 60


def test_sustain_pedal_translates_to_control_change_event():
    msg = mido.Message("control_change", control=SUSTAIN_PEDAL_CONTROL, value=127)
    event = translate(msg, timestamp=3.0, port="test")
    assert event == ControlChangeEvent(
        control=SUSTAIN_PEDAL_CONTROL, value=127, timestamp=3.0, port="test"
    )


def test_unhandled_message_type_returns_none():
    msg = mido.Message("pitchwheel", pitch=0)
    assert translate(msg, timestamp=0.0, port="test") is None
