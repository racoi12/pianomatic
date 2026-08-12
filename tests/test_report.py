from pianomatic.diff import DiffResult, NoteMatch, PerformedNote, ReferenceNote
from pianomatic.report import generate_report


def _match(pitch=60, expected_beat=1.0, deviation_ms=0.0, velocity=90):
    return NoteMatch(
        pitch=pitch,
        expected_beat=expected_beat,
        expected_time=expected_beat,
        actual_time=expected_beat + deviation_ms / 1000,
        timing_deviation_ms=deviation_ms,
        velocity=velocity,
    )


def test_perfect_performance_reports_full_match_no_offenders():
    result = DiffResult(matched=[_match(), _match(pitch=62, expected_beat=2.0)], missed=[], extra=[])
    report = generate_report(result)
    assert "2/2 matched (100%)" in report
    assert "Missed notes" not in report
    assert "off by more than" not in report or "0 notes off" in report


def test_late_note_beyond_tolerance_is_listed():
    result = DiffResult(matched=[_match(deviation_ms=120.0)], missed=[], extra=[])
    report = generate_report(result, timing_tolerance_ms=50.0)
    assert "1 notes off by more than 50ms" in report
    assert "120ms late" in report


def test_early_note_beyond_tolerance_reports_early_direction():
    result = DiffResult(matched=[_match(deviation_ms=-80.0)], missed=[], extra=[])
    report = generate_report(result, timing_tolerance_ms=50.0)
    assert "80ms early" in report


def test_note_within_tolerance_not_listed_as_offender():
    result = DiffResult(matched=[_match(deviation_ms=20.0)], missed=[], extra=[])
    report = generate_report(result, timing_tolerance_ms=50.0)
    assert "0 notes off by more than 50ms" in report
    assert "Timing off by more than" not in report  # no detail section


def test_missed_notes_are_listed():
    result = DiffResult(matched=[], missed=[ReferenceNote(pitch=64, beat=3.0)], extra=[])
    report = generate_report(result)
    assert "0/1 matched (0%)" in report
    assert "E4 at beat 3.00" in report


def test_extra_notes_are_counted():
    result = DiffResult(matched=[_match()], missed=[], extra=[PerformedNote(pitch=70, time=1.5, velocity=80)])
    report = generate_report(result)
    assert "Extra/unexpected notes played: 1" in report


def test_note_list_is_capped_with_overflow_count():
    missed = [ReferenceNote(pitch=60 + i, beat=float(i)) for i in range(15)]
    result = DiffResult(matched=[], missed=missed, extra=[])
    report = generate_report(result)
    assert "... and 5 more" in report


def test_no_reference_notes_reports_that_explicitly():
    result = DiffResult(matched=[], missed=[], extra=[])
    report = generate_report(result)
    assert "No reference notes" in report
