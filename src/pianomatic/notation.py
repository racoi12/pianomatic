"""MIDI -> MusicXML conversion for sheet-music display (OSMD needs
MusicXML/MEI, not raw MIDI — a MIDI file lacks notation-level info like
clefs and note spelling that OSMD needs to render anything).

Real I/O (partitura conversion), not unit tested — manually verified
against a real PSyllabus MIDI file, see docs/STATUS.md. Conversion is
cached to disk since it's not instant and the source MIDI never changes.
"""

from __future__ import annotations

import os
from pathlib import Path

import partitura


def musicxml_path_for(midi_path: str | os.PathLike, cache_dir: str | os.PathLike) -> Path:
    """Where the cached MusicXML for a given MIDI file would live."""
    return Path(cache_dir) / f"{Path(midi_path).stem}.musicxml"


def convert(midi_path: str | os.PathLike, cache_dir: str | os.PathLike) -> Path:
    """Converts midi_path to MusicXML, caching the result under
    cache_dir. Idempotent: skips conversion if already cached. Returns
    the cached file's path.
    """
    out_path = musicxml_path_for(midi_path, cache_dir)
    if not out_path.exists():
        out_path.parent.mkdir(parents=True, exist_ok=True)
        score = partitura.load_score(str(midi_path))
        partitura.save_musicxml(score, str(out_path))
    return out_path
