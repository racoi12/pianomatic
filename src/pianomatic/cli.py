"""Entry point: `pianomatic compare SCORE.mid PERFORMANCE.mid`.

Only wires the repertoire pillar's diff engine — the other three pillars
(sight-reading, ear training, technique) don't have anything to run yet,
see docs/STATUS.md.
"""

from __future__ import annotations

import argparse
import sys

from pianomatic.diff import compare
from pianomatic.report import generate_report


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="pianomatic")
    subparsers = parser.add_subparsers(dest="command", required=True)

    compare_parser = subparsers.add_parser(
        "compare", help="Compare a performance MIDI against a reference score"
    )
    compare_parser.add_argument("score", help="Reference score (MIDI or MusicXML)")
    compare_parser.add_argument("performance", help="Performed MIDI to evaluate")

    args = parser.parse_args(argv)

    if args.command == "compare":
        result = compare(args.score, args.performance)
        print(generate_report(result))
    else:  # pragma: no cover - unreachable, argparse enforces valid choices
        sys.exit(f"Unknown command: {args.command}")


if __name__ == "__main__":
    main()
