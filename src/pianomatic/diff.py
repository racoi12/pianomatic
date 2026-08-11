"""Alignment + multidimensional diff of a performance against a reference.

`align()` is implemented and manually verified (see docs/STATUS.md for the
exact command) — it wraps `pymatchmaker.Matchmaker`, no hand-rolled DTW.
Not part of the fast pytest suite: real score-following pulls in the full
ML stack (numpy, hmm, partitura) and takes real seconds to run, not worth
paying that cost on every test run for a thin wrapper — verified manually
instead.

Per-dimension diff (timing/pitch/dynamics, see docs/ARCHITECTURE.md) is
NOT implemented yet — needs matching each reference note to its performed
counterpart through the alignment path, which is real design work of its
own, not just wiring. Don't half-do it; next session.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

import numpy as np
from matchmaker import Matchmaker


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
