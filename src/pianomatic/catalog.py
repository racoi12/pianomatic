"""Song catalog backed by the Piano Syllabus Dataset (Zenodo, CC license,
see docs/ARCHITECTURE.md "Content / song catalog"). 7,901 classical
pieces already graded by real syllabi (ABRSM, RCM, Trinity, etc.) — no
manual curation needed, unlike popular music which stays a real legal
wall (see ARCHITECTURE.md).

Two layers, same pattern as the rest of the codebase: `parse_catalog`
(pure, unit tested with a small synthetic fixture matching the real
schema) and `download_dataset`/`load_catalog` (real network/file I/O,
not unit tested — manually verified, see docs/STATUS.md).
"""

from __future__ import annotations

import io
import json
import os
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path

METADATA_URL = "https://zenodo.org/api/records/14794592/files/new_clean_data.json/content"
MIDI_ZIP_URL = "https://zenodo.org/api/records/14794592/files/mid.zip/content"

DEFAULT_DATA_DIR = Path.home() / ".local" / "share" / "pianomatic" / "psyllabus"


@dataclass(frozen=True, slots=True)
class CatalogEntry:
    key: str  # matches the MIDI filename (without .mid) — "{composer}{title}"
    composer: str
    title: str
    period: str | None
    ps_rating: int  # 0-10, unified difficulty scale present on every entry
    grades: dict[str, int]  # syllabus name -> grade, e.g. {"ABRSM": 6, "Trinity": 6}

    def midi_filename(self) -> str:
        return f"{self.key}.mid"

    def grade(self, syllabus: str) -> int | None:
        return self.grades.get(syllabus)


def _parse_grades(related_entries: dict | list) -> dict[str, int]:
    """`related_entries` is a dict {syllabus: grade} for ~99.97% of the
    real dataset, but 2 of 7901 entries (verified, see docs/STATUS.md)
    have it as a list of {"syllabus": ..., "grade": ...} dicts instead —
    a data-quality inconsistency in the upstream dataset, not something
    we can fix upstream, so both shapes are handled here.
    """
    if isinstance(related_entries, dict):
        return {k: int(g) for k, g in related_entries.items()}
    return {item["syllabus"]: int(item["grade"]) for item in related_entries}


def parse_catalog(data: dict) -> list[CatalogEntry]:
    """Pure: the raw new_clean_data.json dict -> a list of CatalogEntry.
    Key format and fields verified against the real dataset, see
    docs/STATUS.md.
    """
    entries = []
    for key, v in data.items():
        entries.append(
            CatalogEntry(
                key=key,
                composer=v.get("composer", ""),
                title=v.get("PS_title", ""),
                period=v.get("period"),
                ps_rating=int(v["ps_rating"]),
                grades=_parse_grades(v.get("related_entries", {})),
            )
        )
    return entries


def filter_by_grade(
    entries: list[CatalogEntry], syllabus: str, min_grade: int, max_grade: int
) -> list[CatalogEntry]:
    """Pure: entries within [min_grade, max_grade] for the given syllabus.
    Entries with no grade under that syllabus are excluded (not everything
    in the dataset is graded by every syllabus — see docs/STATUS.md).
    """
    return [
        e
        for e in entries
        if (g := e.grade(syllabus)) is not None and min_grade <= g <= max_grade
    ]


def load_catalog(json_path: str | os.PathLike) -> list[CatalogEntry]:
    with open(json_path, encoding="utf-8") as f:
        return parse_catalog(json.load(f))


def download_dataset(dest_dir: str | os.PathLike = DEFAULT_DATA_DIR) -> Path:
    """Downloads new_clean_data.json + mid.zip (extracted) from Zenodo
    into `dest_dir`. ~64MB total. Not unit tested (real network I/O) —
    manually verified, see docs/STATUS.md. Idempotent: skips whatever
    already exists.
    """
    dest = Path(dest_dir)
    dest.mkdir(parents=True, exist_ok=True)

    metadata_path = dest / "new_clean_data.json"
    if not metadata_path.exists():
        urllib.request.urlretrieve(METADATA_URL, metadata_path)

    midi_dir = dest / "mid"
    if not midi_dir.exists():
        with urllib.request.urlopen(MIDI_ZIP_URL) as response:
            zip_bytes = response.read()
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            zf.extractall(dest)

    return dest
