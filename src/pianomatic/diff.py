"""Alignment + multidimensional diff of a performance against a reference.

Not implemented yet — see docs/STATUS.md. Planned approach:

- Alignment: `pymatchmaker` (already a dependency) does the heavy lifting —
  don't hand-roll DTW, see docs/ARCHITECTURE.md.
- Output three SEPARATE dimensions, never a single score (pedagogy
  research is unanimous that a single score hides what actually needs
  fixing — see ARCHITECTURE.md):
    - timing: per-note offset in ms vs reference
    - pitch: wrong/missed/extra notes
    - dynamics: velocity deviation vs reference
- Flag deviations only above the human just-noticeable-difference
  threshold (~20-50ms for timing) — don't report noise as errors.

Planned interface:

    from pianomatic.diff import compare

    result = compare(performance_midi_path, reference_midi_path)
    # result: DiffResult(timing=[...], pitch=[...], dynamics=[...])
"""
