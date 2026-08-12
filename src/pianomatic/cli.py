"""Entry points:

  pianomatic compare SCORE.mid PERFORMANCE.mid
  pianomatic practice SCORE.mid --port "PORT NAME"

Only wires the repertoire pillar's diff engine — the other three pillars
(sight-reading, ear training, technique) don't have anything to run yet,
see docs/STATUS.md.
"""

from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

from pianomatic.control import KEYSTATION_61ES_HIGH, KEYSTATION_61ES_LOW, HandsFreeControl
from pianomatic.diff import align as diff_align
from pianomatic.diff import compare, extract_reference_notes, match_notes, save_performed_notes
from pianomatic.midi_io import MidiSession
from pianomatic.report import generate_report
from pianomatic.session import PracticeSession

STOP_COMMAND = "stop"


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="pianomatic")
    subparsers = parser.add_subparsers(dest="command", required=True)

    compare_parser = subparsers.add_parser(
        "compare", help="Compare a performance MIDI against a reference score"
    )
    compare_parser.add_argument("score", help="Reference score (MIDI or MusicXML)")
    compare_parser.add_argument("performance", help="Performed MIDI to evaluate")

    practice_parser = subparsers.add_parser(
        "practice",
        help="Capture a live performance from a MIDI keyboard, then report against a score",
    )
    practice_parser.add_argument("score", help="Reference score (MIDI or MusicXML)")
    practice_parser.add_argument("--port", required=True, help="MIDI input port name")
    practice_parser.add_argument(
        "--save-to",
        default=None,
        help="Also save the captured performance to this MIDI file (default: discarded after the report)",
    )

    args = parser.parse_args(argv)

    if args.command == "compare":
        result = compare(args.score, args.performance)
        print(generate_report(result))
    elif args.command == "practice":
        _run_practice(args.score, args.port, args.save_to)
    else:  # pragma: no cover - unreachable, argparse enforces valid choices
        sys.exit(f"Unknown command: {args.command}")


def _run_practice(score_path: str, port_name: str, save_to: str | None) -> None:
    """NOTE: not verified against real hardware, see docs/STATUS.md — the
    pieces it wires (MidiSession, PracticeSession, diff.compare) are each
    independently tested/verified, but this specific end-to-end path
    needs a real keyboard session to confirm. Play the anchor gesture
    (lowest + highest key together) then the first mapped command key to
    stop and get the report.
    """
    stop_requested = False

    def on_command(command: str) -> None:
        nonlocal stop_requested
        if command == STOP_COMMAND:
            stop_requested = True

    control = HandsFreeControl(
        KEYSTATION_61ES_LOW, KEYSTATION_61ES_HIGH, [STOP_COMMAND], on_command=on_command
    )
    session = PracticeSession(control)

    print(f"Listening on '{port_name}'. Hold lowest+highest key, then the next white key, to stop.")
    with MidiSession([port_name]) as midi_session:
        for event in midi_session.listen():
            session.handle_event(event)
            if stop_requested:
                break

    target = Path(save_to) if save_to else Path(tempfile.mktemp(suffix=".mid"))
    save_performed_notes(session.performed_notes, target)
    alignment = diff_align(score_path, target)
    reference = extract_reference_notes(score_path)
    result = match_notes(reference, session.performed_notes, alignment)
    print(generate_report(result))
    if not save_to:
        target.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
