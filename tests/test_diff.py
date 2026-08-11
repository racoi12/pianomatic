"""Only tests the StopIteration-return-value plumbing in isolation — the
real Matchmaker call is exercised manually (see docs/STATUS.md), not here:
it pulls in the full ML stack and takes real seconds per run, not worth
the cost on every `pytest` invocation for what is a thin wrapper.
"""

import numpy as np
import pytest

from pianomatic.diff import Alignment, align


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
