from pianomatic.control import HandsFreeControl

LOW, HIGH = 36, 96  # placeholder range, see docs/STATUS.md pending calibration


def _control(commands=("play_pause", "repeat", "save")):
    fired = []
    ctl = HandsFreeControl(LOW, HIGH, list(commands), on_command=fired.append)
    return ctl, fired


def test_command_fires_when_both_anchors_held():
    ctl, fired = _control()
    ctl.handle_note_on(LOW, 100)
    ctl.handle_note_on(HIGH, 100)
    first_command_note = next(iter(ctl._position_map))
    ctl.handle_note_on(first_command_note, 100)
    assert fired == ["play_pause"]


def test_no_command_without_both_anchors():
    ctl, fired = _control()
    ctl.handle_note_on(LOW, 100)
    first_command_note = next(iter(ctl._position_map))
    ctl.handle_note_on(first_command_note, 100)
    assert fired == []


def test_releasing_anchor_without_command_is_noop():
    ctl, fired = _control()
    ctl.handle_note_on(LOW, 100)
    ctl.handle_note_on(HIGH, 100)
    ctl.handle_note_off(LOW)
    assert fired == []
    assert not ctl.armed


def test_note_on_with_zero_velocity_is_note_off():
    ctl, fired = _control()
    ctl.handle_note_on(LOW, 100)
    ctl.handle_note_on(HIGH, 100)
    ctl.handle_note_on(LOW, 0)  # running-status note-off
    assert not ctl.armed


def test_second_and_third_command_positions_are_distinct():
    ctl, fired = _control()
    positions = list(ctl._position_map.items())
    assert len(positions) == 3
    notes = [n for n, _ in positions]
    assert notes == sorted(notes)
    assert len(set(notes)) == 3


def test_note_outside_mapping_does_not_fire():
    ctl, fired = _control(commands=["only_one"])
    ctl.handle_note_on(LOW, 100)
    ctl.handle_note_on(HIGH, 100)
    unmapped_note = max(ctl._position_map) + 1
    ctl.handle_note_on(unmapped_note, 100)
    assert fired == []
