"""Alignment + multidimensional diff of a performance against a reference.

`align()` wraps `pymatchmaker.Matchmaker` — manually verified, see
docs/STATUS.md, not in the fast pytest suite (real score-following pulls
in the full ML stack and takes real seconds per run).

Per-note diff (`match_notes`) is pure and unit tested: it takes plain
reference/performed note lists plus an alignment path and returns which
notes matched (with timing deviation in ms), which reference notes were
missed, and which performed notes were extra/wrong. Separate from
`align()` and the file-extraction helpers so the matching LOGIC is
testable without pulling in partitura/mido file I/O.

Dynamics comparison (performed velocity vs. expected) is NOT implemented
yet — a plain MIDI file's velocities aren't a reliable "expected dynamics"
reference; needs a score format with real dynamics markings first (see
docs/ARCHITECTURE.md). `match_notes` records the performed velocity so
that comparison can be added later without re-deriving matches.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

import mido
import numpy as np
import partitura
from matchmaker import Matchmaker

DEFAULT_MATCH_TOLERANCE_SECONDS = 0.5


@dataclass(frozen=True, slots=True)
class ReferenceNote:
    pitch: int
    beat: float


@dataclass(frozen=True, slots=True)
class PerformedNote:
    pitch: int
    time: float  # seconds
    velocity: int


@dataclass(frozen=True, slots=True)
class NoteMatch:
    pitch: int
    expected_beat: float
    expected_time: float  # seconds, from the alignment path
    actual_time: float
    timing_deviation_ms: float  # actual - expected, signed: late is positive
    velocity: int


@dataclass(frozen=True, slots=True)
class DiffResult:
    matched: list[NoteMatch]
    missed: list[ReferenceNote]  # in the score, nothing matched in the performance
    extra: list[PerformedNote]  # played, didn't match any reference note


@dataclass(frozen=True, slots=True)
class Alignment:
    # shape (N, 2): path[:, 0] = score position in beats, path[:, 1] =
    # performance time in seconds. Note: pymatchmaker's own docstring says
    # shape (2, N) — that's wrong, verified (N, 2) against real output,
    # see docs/STATUS.md.
    path: np.ndarray


def align(score_path: str | os.PathLike, performance_path: str | os.PathLike) -> Alignment:
    """Run online score-following of `performance_path` against
    `score_path` (both MIDI). Returns the beat<->seconds alignment path.
    """
    mm = Matchmaker(
        score_file=str(score_path),
        performance_file=str(performance_path),
        input_type="midi",
    )
    # run() is a generator; its return value (the alignment path) is only
    # reachable via StopIteration.value, not by exhausting it with list().
    gen = mm.run(verbose=False)
    try:
        while True:
            next(gen)
    except StopIteration as stop:
        path = stop.value
    return Alignment(path=np.asarray(path))


def extract_reference_notes(score_path: str | os.PathLike) -> list[ReferenceNote]:
    """Reads a score (MIDI or MusicXML, anything partitura.load_score
    supports) and returns its notes as (pitch, beat) — score-level, no
    absolute time, that's what alignment is for.
    """
    score = partitura.load_score(str(score_path))
    part = score[0]
    notes = sorted(part.notes, key=lambda n: n.start.t)
    beats = np.atleast_1d(part.beat_map([n.start.t for n in notes]))
    return [ReferenceNote(pitch=n.midi_pitch, beat=float(b)) for n, b in zip(notes, beats)]


def extract_performed_notes(
    performance_path: str | os.PathLike, channel: int | None = None
) -> list[PerformedNote]:
    """Reads a performance MIDI file and returns its NOTE_ON events with
    real elapsed seconds (MidiFile's own tempo-aware iteration) and
    velocity.

    `channel`: if given, only notes on that MIDI channel are returned.
    Matters for files with a full backing arrangement (drums, bass,
    accompaniment) rather than a clean solo-piano track — verified on a
    real PianoBooster demo file that this happens in practice: 196 total
    NOTE_ON events across 4 channels vs. 8 actual melody notes, see
    docs/STATUS.md. Filtering by channel alone isn't always enough if the
    melody pitch is doubled across channels (also observed on that same
    file) — the live-capture path (midi_io.MidiSession from the physical
    keyboard) never has this problem since it only ever captures what the
    user actually played.
    """
    midi_file = mido.MidiFile(str(performance_path))
    notes = []
    t = 0.0
    for msg in midi_file:
        t += msg.time
        if msg.type == "note_on" and msg.velocity > 0:
            if channel is not None and msg.channel != channel:
                continue
            notes.append(PerformedNote(pitch=msg.note, time=t, velocity=msg.velocity))
    return notes


def match_notes(
    reference: list[ReferenceNote],
    performed: list[PerformedNote],
    alignment: Alignment,
    tolerance_seconds: float = DEFAULT_MATCH_TOLERANCE_SECONDS,
) -> DiffResult:
    """Pure matching logic: for each reference note, interpolate its
    expected performance time from the alignment path, then greedily pick
    the nearest not-yet-used performed note of the same pitch within
    `tolerance_seconds`. Simple nearest-neighbor, not a globally optimal
    assignment — good enough for v1, revisit if it misbehaves on real
    playing (e.g. repeated notes close together).
    """
    path_beats = alignment.path[:, 0]
    path_times = alignment.path[:, 1]

    available = list(performed)
    matched: list[NoteMatch] = []
    missed: list[ReferenceNote] = []

    for ref in reference:
        expected_time = float(np.interp(ref.beat, path_beats, path_times))
        candidates = [
            p for p in available if p.pitch == ref.pitch and abs(p.time - expected_time) <= tolerance_seconds
        ]
        if not candidates:
            missed.append(ref)
            continue
        best = min(candidates, key=lambda p: abs(p.time - expected_time))
        available.remove(best)
        matched.append(
            NoteMatch(
                pitch=ref.pitch,
                expected_beat=ref.beat,
                expected_time=expected_time,
                actual_time=best.time,
                timing_deviation_ms=(best.time - expected_time) * 1000,
                velocity=best.velocity,
            )
        )

    return DiffResult(matched=matched, missed=missed, extra=available)


def compare(
    score_path: str | os.PathLike, performance_path: str | os.PathLike
) -> DiffResult:
    """End-to-end: align + extract + match. Manually verified, see
    docs/STATUS.md — not in the fast pytest suite (pulls in the full ML
    stack via align()).
    """
    alignment = align(score_path, performance_path)
    reference = extract_reference_notes(score_path)
    performed = extract_performed_notes(performance_path)
    return match_notes(reference, performed, alignment)
