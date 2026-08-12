"""Plain-text report from a diff.DiffResult.

v1 is plain text for a developer/CLI audience — English, like the rest of
the codebase (see docs/STATUS.md on the English-going-forward decision).
The eventual family-facing coach report (two-layer: immediate simple ping
+ next-day reflective LLM report, see docs/ARCHITECTURE.md) is a later
phase and will need actual localization for the people using it — not
addressed here, flagged as pending in docs/STATUS.md.

Design choices grounded in research (see docs/ARCHITECTURE.md /
docs/STATUS.md sub-agent reports):
- Report timing, pitch (missed/extra), and dynamics as SEPARATE numbers,
  never collapse into one score — pedagogy research is unanimous that a
  single score hides what actually needs fixing.
- Only flag timing deviations above the human just-noticeable-difference
  threshold (~20-50ms) — reporting sub-perceptual noise as "errors" is
  actively counterproductive.
"""

from __future__ import annotations

from pianomatic.diff import DiffResult
from pianomatic.midi_io import note_name

DEFAULT_TIMING_TOLERANCE_MS = 50.0
_MAX_LISTED_NOTES = 10


def generate_report(
    result: DiffResult, timing_tolerance_ms: float = DEFAULT_TIMING_TOLERANCE_MS
) -> str:
    total_reference_notes = len(result.matched) + len(result.missed)
    lines = [_summary_line(result, total_reference_notes)]

    if result.matched:
        lines.append(_timing_line(result, timing_tolerance_ms))

    off_timing = _sorted_by_worst_timing(result, timing_tolerance_ms)
    if off_timing:
        lines.append("")
        lines.append(f"Timing off by more than {timing_tolerance_ms:.0f}ms:")
        lines.extend(_format_note_list(off_timing, _format_timing_offender))

    if result.missed:
        lines.append("")
        lines.append("Missed notes:")
        lines.extend(_format_note_list(result.missed, _format_missed_note))

    if result.extra:
        lines.append("")
        lines.append(f"Extra/unexpected notes played: {len(result.extra)}")

    return "\n".join(lines)


def _summary_line(result: DiffResult, total_reference_notes: int) -> str:
    if total_reference_notes == 0:
        return "No reference notes to compare against."
    accuracy = len(result.matched) / total_reference_notes * 100
    return f"Notes: {len(result.matched)}/{total_reference_notes} matched ({accuracy:.0f}%)"


def _timing_line(result: DiffResult, timing_tolerance_ms: float) -> str:
    deviations = [abs(m.timing_deviation_ms) for m in result.matched]
    mean_deviation = sum(deviations) / len(deviations)
    off_count = sum(1 for d in deviations if d > timing_tolerance_ms)
    return f"Timing: {mean_deviation:.0f}ms average deviation, {off_count} notes off by more than {timing_tolerance_ms:.0f}ms"


def _sorted_by_worst_timing(result: DiffResult, timing_tolerance_ms: float) -> list:
    off = [m for m in result.matched if abs(m.timing_deviation_ms) > timing_tolerance_ms]
    return sorted(off, key=lambda m: abs(m.timing_deviation_ms), reverse=True)


def _format_note_list(notes: list, formatter) -> list[str]:
    lines = [f"  - {formatter(n)}" for n in notes[:_MAX_LISTED_NOTES]]
    if len(notes) > _MAX_LISTED_NOTES:
        lines.append(f"  ... and {len(notes) - _MAX_LISTED_NOTES} more")
    return lines


def _format_timing_offender(match) -> str:
    direction = "late" if match.timing_deviation_ms > 0 else "early"
    return f"{note_name(match.pitch)} at beat {match.expected_beat:.2f}: {abs(match.timing_deviation_ms):.0f}ms {direction}"


def _format_missed_note(note) -> str:
    return f"{note_name(note.pitch)} at beat {note.beat:.2f}"
