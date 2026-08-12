"""align() and match_notes()'s real-file behavior are verified manually
(see docs/STATUS.md), not here: the real Matchmaker call pulls in the full
ML stack and takes real seconds per run, not worth the cost on every
`pytest` invocation. This file only tests pure logic with synthetic data:
the StopIteration-return-value plumbing in align(), and match_notes()'s
matching/tolerance/greedy-assignment behavior in isolation.
"""

import numpy as np
import pytest

from pianomatic.diff import (
    Alignment,
    PerformedNote,
    ReferenceNote,
    align,
    extract_performed_notes,
    match_notes,
    save_performed_notes,
)


def test_align_extracts_generator_return_value(monkeypatch):
    expected_path = np.array([[0.0, 0.0], [1.0, 0.5]])

    def fake_run(self, verbose=True):
        yield 0.0
        yield 1.0
        return expected_path

    class FakeMatchmaker:
        def __init__(self, **kwargs):
            pass

        run = fake_run

    monkeypatch.setattr("pianomatic.diff.Matchmaker", FakeMatchmaker)

    result = align("score.mid", "performance.mid")
    assert isinstance(result, Alignment)
    np.testing.assert_array_equal(result.path, expected_path)


# identity alignment: beat N happens at N seconds, simplest possible path
_IDENTITY_ALIGNMENT = Alignment(path=np.array([[0.0, 0.0], [10.0, 10.0]]))


def test_matches_note_played_exactly_on_time():
    reference = [ReferenceNote(pitch=60, beat=2.0)]
    performed = [PerformedNote(pitch=60, time=2.0, velocity=90)]
    result = match_notes(reference, performed, _IDENTITY_ALIGNMENT)
    assert len(result.matched) == 1
    assert result.matched[0].timing_deviation_ms == pytest.approx(0.0)
    assert result.missed == []
    assert result.extra == []


def test_late_note_within_tolerance_matches_with_positive_deviation():
    reference = [ReferenceNote(pitch=60, beat=2.0)]
    performed = [PerformedNote(pitch=60, time=2.2, velocity=90)]
    result = match_notes(reference, performed, _IDENTITY_ALIGNMENT, tolerance_seconds=0.5)
    assert len(result.matched) == 1
    assert result.matched[0].timing_deviation_ms == pytest.approx(200.0)


def test_note_outside_tolerance_counts_as_missed_and_extra():
    reference = [ReferenceNote(pitch=60, beat=2.0)]
    performed = [PerformedNote(pitch=60, time=5.0, velocity=90)]
    result = match_notes(reference, performed, _IDENTITY_ALIGNMENT, tolerance_seconds=0.5)
    assert result.matched == []
    assert len(result.missed) == 1
    assert len(result.extra) == 1


def test_wrong_pitch_does_not_match():
    reference = [ReferenceNote(pitch=60, beat=2.0)]
    performed = [PerformedNote(pitch=61, time=2.0, velocity=90)]
    result = match_notes(reference, performed, _IDENTITY_ALIGNMENT)
    assert result.matched == []
    assert len(result.missed) == 1
    assert len(result.extra) == 1


def test_nearest_candidate_wins_when_multiple_same_pitch_in_range():
    reference = [ReferenceNote(pitch=60, beat=2.0)]
    performed = [
        PerformedNote(pitch=60, time=2.4, velocity=90),
        PerformedNote(pitch=60, time=2.05, velocity=100),
    ]
    result = match_notes(reference, performed, _IDENTITY_ALIGNMENT, tolerance_seconds=0.5)
    assert len(result.matched) == 1
    assert result.matched[0].velocity == 100  # the closer one (2.05), not 2.4
    assert len(result.extra) == 1  # the other same-pitch note is left over


def test_each_performed_note_used_at_most_once():
    reference = [ReferenceNote(pitch=60, beat=2.0), ReferenceNote(pitch=60, beat=2.01)]
    performed = [PerformedNote(pitch=60, time=2.0, velocity=90)]
    result = match_notes(reference, performed, _IDENTITY_ALIGNMENT, tolerance_seconds=0.5)
    assert len(result.matched) == 1
    assert len(result.missed) == 1


def test_save_then_extract_performed_notes_roundtrips(tmp_path):
    notes = [
        PerformedNote(pitch=60, time=0.0, velocity=90),
        PerformedNote(pitch=64, time=0.5, velocity=100),
        PerformedNote(pitch=67, time=1.234, velocity=80),
    ]
    path = tmp_path / "session.mid"
    save_performed_notes(notes, path)
    recovered = extract_performed_notes(path)

    assert [n.pitch for n in recovered] == [n.pitch for n in notes]
    assert [n.velocity for n in recovered] == [n.velocity for n in notes]
    for original, got in zip(notes, recovered):
        assert got.time == pytest.approx(original.time, abs=0.01)


def test_save_performed_notes_handles_empty_list(tmp_path):
    path = tmp_path / "empty.mid"
    save_performed_notes([], path)
    assert extract_performed_notes(path) == []
