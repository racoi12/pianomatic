"""convert() itself is real I/O (partitura conversion) — manually
verified against a real PSyllabus MIDI file (0.74s for a 1702-note
piece, cached instantly on re-run), see docs/STATUS.md. Only the pure
path-construction logic is unit tested here.
"""

from pianomatic.notation import musicxml_path_for


def test_musicxml_path_uses_stem_and_cache_dir():
    path = musicxml_path_for("/data/mid/Faure G.Barcarolle 9.mid", "/cache")
    assert str(path) == "/cache/Faure G.Barcarolle 9.musicxml"
