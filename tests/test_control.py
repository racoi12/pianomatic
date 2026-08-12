from pianomatic.control import (
    KEYSTATION_61ES_HIGH,
    KEYSTATION_61ES_LOW,
    HandsFreeControl,
)

LOW, HIGH = KEYSTATION_61ES_LOW, KEYSTATION_61ES_HIGH


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


def test_anchor_press_and_release_are_consumed():
    ctl, _ = _control()
    assert ctl.handle_note_on(LOW, 100) is True
    assert ctl.handle_note_on(HIGH, 100) is True
    assert ctl.handle_note_off(LOW) is True
    assert ctl.handle_note_off(HIGH) is True


def test_ordinary_note_outside_armed_mode_is_not_consumed():
    ctl, _ = _control()
    assert ctl.handle_note_on(60, 100) is False
    assert ctl.handle_note_off(60) is False


def test_any_note_while_armed_is_consumed_even_if_unmapped():
    ctl, fired = _control(commands=["only_one"])
    ctl.handle_note_on(LOW, 100)
    ctl.handle_note_on(HIGH, 100)
    unmapped_note = max(ctl._position_map) + 1
    assert ctl.handle_note_on(unmapped_note, 100) is True
    assert fired == []  # consumed, but didn't fire since it's not mapped


def test_release_of_consumed_note_is_also_consumed():
    ctl, _ = _control()
    ctl.handle_note_on(LOW, 100)
    ctl.handle_note_on(HIGH, 100)
    command_note = next(iter(ctl._position_map))
    ctl.handle_note_on(command_note, 100)
    assert ctl.handle_note_off(command_note) is True


def test_release_of_note_never_pressed_is_not_consumed():
    ctl, _ = _control()
    assert ctl.handle_note_off(60) is False
