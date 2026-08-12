"""Entry points:

  pianomatic compare SCORE.mid PERFORMANCE.mid
  pianomatic compare --catalog "couperin" PERFORMANCE.mid
  pianomatic practice SCORE.mid --port "PORT NAME"
  pianomatic practice --catalog "couperin" --port "PORT NAME"
  pianomatic catalog fetch
  pianomatic catalog search "couperin"
  pianomatic catalog list --syllabus ABRSM --min-grade 5 --max-grade 6

Only wires the repertoire pillar's diff engine — the other three pillars
(sight-reading, ear training, technique) don't have anything to run yet,
see docs/STATUS.md.
"""

from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

from pianomatic.catalog import (
    DEFAULT_DATA_DIR,
    download_dataset,
    filter_by_grade,
    load_catalog,
    resolve_midi_path,
    search,
)
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
    compare_parser.add_argument("score", nargs="?", default=None, help="Reference score (MIDI or MusicXML)")
    compare_parser.add_argument("performance", help="Performed MIDI to evaluate")
    compare_parser.add_argument("--catalog", default=None, help="Find the score in the catalog instead (search query)")
    compare_parser.add_argument("--dest", default=None, help=f"Catalog data directory (default: {DEFAULT_DATA_DIR})")

    practice_parser = subparsers.add_parser(
        "practice",
        help="Capture a live performance from a MIDI keyboard, then report against a score",
    )
    practice_parser.add_argument("score", nargs="?", default=None, help="Reference score (MIDI or MusicXML)")
    practice_parser.add_argument("--catalog", default=None, help="Find the score in the catalog instead (search query)")
    practice_parser.add_argument("--dest", default=None, help=f"Catalog data directory (default: {DEFAULT_DATA_DIR})")
    practice_parser.add_argument("--port", required=True, help="MIDI input port name")
    practice_parser.add_argument(
        "--save-to",
        default=None,
        help="Also save the captured performance to this MIDI file (default: discarded after the report)",
    )

    catalog_parser = subparsers.add_parser("catalog", help="Piano Syllabus Dataset song catalog")
    catalog_subparsers = catalog_parser.add_subparsers(dest="catalog_command", required=True)

    fetch_parser = catalog_subparsers.add_parser(
        "fetch", help="Download the catalog (metadata + MIDI files, ~64MB) if not already present"
    )
    fetch_parser.add_argument("--dest", default=None, help=f"Data directory (default: {DEFAULT_DATA_DIR})")

    search_parser = catalog_subparsers.add_parser("search", help="Search the catalog by composer/title")
    search_parser.add_argument("query")
    search_parser.add_argument("--dest", default=None, help=f"Data directory (default: {DEFAULT_DATA_DIR})")

    list_parser = catalog_subparsers.add_parser("list", help="List catalog entries")
    list_parser.add_argument("--dest", default=None, help=f"Data directory (default: {DEFAULT_DATA_DIR})")
    list_parser.add_argument("--syllabus", default="ABRSM", help="Grading syllabus (default: ABRSM)")
    list_parser.add_argument("--min-grade", type=int, default=5)
    list_parser.add_argument("--max-grade", type=int, default=6)

    args = parser.parse_args(argv)

    if args.command == "compare":
        score_path = _resolve_score(args.score, args.catalog, args.dest)
        result = compare(score_path, args.performance)
        print(generate_report(result))
    elif args.command == "practice":
        score_path = _resolve_score(args.score, args.catalog, args.dest)
        _run_practice(score_path, args.port, args.save_to)
    elif args.command == "catalog":
        _run_catalog(args)
    else:  # pragma: no cover - unreachable, argparse enforces valid choices
        sys.exit(f"Unknown command: {args.command}")


def _resolve_score(score_arg: str | None, catalog_query: str | None, dest_arg: str | None) -> str:
    """Either a direct file path (`score_arg`) or a catalog search query
    (`catalog_query`) must be given — resolves either into an actual file
    path. Ambiguous/no-match catalog searches exit with the candidates
    instead of guessing.
    """
    if score_arg and catalog_query:
        sys.exit("Pass either a score path or --catalog, not both.")
    if score_arg:
        return score_arg
    if not catalog_query:
        sys.exit("Pass either a score path or --catalog QUERY.")

    dest = Path(dest_arg) if dest_arg else DEFAULT_DATA_DIR
    entries = load_catalog(dest / "new_clean_data.json")
    matches = search(entries, catalog_query)
    if not matches:
        sys.exit(f"No catalog match for '{catalog_query}'. Try 'pianomatic catalog search \"{catalog_query}\"'.")
    if len(matches) > 1:
        listing = "\n".join(f"  {e.composer} — {e.title}" for e in matches[:10])
        more = f"\n  ... and {len(matches) - 10} more" if len(matches) > 10 else ""
        sys.exit(f"'{catalog_query}' matches {len(matches)} pieces, be more specific:\n{listing}{more}")
    return str(resolve_midi_path(matches[0], dest))


def _run_catalog(args: argparse.Namespace) -> None:
    dest = Path(args.dest) if args.dest else DEFAULT_DATA_DIR
    if args.catalog_command == "fetch":
        print(f"Downloading Piano Syllabus Dataset to {dest} (~64MB, skips what's already there)...")
        download_dataset(dest)
        print("Done.")
    elif args.catalog_command == "search":
        entries = load_catalog(dest / "new_clean_data.json")
        matches = search(entries, args.query)
        print(f"{len(matches)} matches for '{args.query}':")
        for e in matches:
            print(f"  {e.composer} — {e.title} (ps_rating {e.ps_rating}, grades: {e.grades})")
    elif args.catalog_command == "list":
        entries = load_catalog(dest / "new_clean_data.json")
        selected = filter_by_grade(entries, args.syllabus, args.min_grade, args.max_grade)
        print(f"{len(selected)} pieces, {args.syllabus} grade {args.min_grade}-{args.max_grade}:")
        for e in selected:
            print(f"  {e.composer} — {e.title} (grade {e.grade(args.syllabus)})")
    else:  # pragma: no cover - unreachable, argparse enforces valid choices
        sys.exit(f"Unknown catalog command: {args.catalog_command}")


def _run_practice(score_path: str, port_name: str, save_to: str | None) -> None:
    """Verified end-to-end against real ALSA MIDI I/O, see docs/STATUS.md
    (2026-08-12 entry). Play the anchor gesture (lowest + highest key
    together) then the first mapped command key to stop and get the
    report.
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
