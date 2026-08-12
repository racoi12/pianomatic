"""Fixture below mirrors the real new_clean_data.json schema, verified
against the actual dataset (see docs/STATUS.md) — download_dataset()
itself isn't tested here (real network I/O), only the pure parsing.
"""

from pianomatic.catalog import CatalogEntry, filter_by_grade, parse_catalog

_FIXTURE = {
    "Faure G.Barcarolle 9 - op 101 A minor": {
        "composer": "Faure G.",
        "period": "Romantic",
        "PS_title": "Barcarolle 9 - op 101 A minor",
        "syllabus": "Piano St",
        "ps_rating": "7",
        "related_entries": {"Piano St": 7},
    },
    "Couperin F.Les Petits Moulins a Vent": {
        "composer": "Couperin F.",
        "period": "Baroque",
        "PS_title": "Les Petits Moulins a Vent",
        "syllabus": "ABRSM",
        "ps_rating": "6",
        "related_entries": {"ABRSM": 6, "GCSE": 6, "Trinity": 6, "RIAM": 8},
    },
    "Czerny C.Study - op 299 no 27 Bb major": {
        "composer": "Czerny C.",
        "period": "Classical",
        "PS_title": "Study - op 299 no 27 Bb major",
        "syllabus": "RCM",
        "ps_rating": "5",
        "related_entries": {"RCM": 5, "ABRSM": 5},
    },
}


def test_parse_catalog_extracts_all_entries():
    entries = parse_catalog(_FIXTURE)
    assert len(entries) == 3


def test_parse_catalog_fields():
    entries = parse_catalog(_FIXTURE)
    couperin = next(e for e in entries if e.composer == "Couperin F.")
    assert couperin.title == "Les Petits Moulins a Vent"
    assert couperin.period == "Baroque"
    assert couperin.ps_rating == 6
    assert couperin.grades == {"ABRSM": 6, "GCSE": 6, "Trinity": 6, "RIAM": 8}


def test_midi_filename_matches_key():
    entry = CatalogEntry(
        key="Faure G.Barcarolle 9 - op 101 A minor",
        composer="Faure G.",
        title="Barcarolle 9 - op 101 A minor",
        period="Romantic",
        ps_rating=7,
        grades={},
    )
    assert entry.midi_filename() == "Faure G.Barcarolle 9 - op 101 A minor.mid"


def test_grade_returns_none_when_syllabus_absent():
    entries = parse_catalog(_FIXTURE)
    faure = next(e for e in entries if e.composer == "Faure G.")
    assert faure.grade("ABRSM") is None
    assert faure.grade("Piano St") == 7


def test_filter_by_grade_selects_range():
    entries = parse_catalog(_FIXTURE)
    result = filter_by_grade(entries, "ABRSM", min_grade=5, max_grade=6)
    assert {e.composer for e in result} == {"Couperin F.", "Czerny C."}


def test_filter_by_grade_excludes_entries_without_that_syllabus():
    entries = parse_catalog(_FIXTURE)
    result = filter_by_grade(entries, "ABRSM", min_grade=0, max_grade=10)
    composers = {e.composer for e in result}
    assert "Faure G." not in composers  # only graded under "Piano St", not ABRSM


def test_filter_by_grade_excludes_out_of_range():
    entries = parse_catalog(_FIXTURE)
    result = filter_by_grade(entries, "ABRSM", min_grade=7, max_grade=10)
    assert result == []


def test_related_entries_as_list_is_handled():
    # 2 of 7901 real entries have related_entries as a list of dicts
    # instead of a dict — a real data-quality quirk in the dataset,
    # see docs/STATUS.md.
    fixture = {
        "Anonymous.Little mazurka": {
            "composer": "Anonymous",
            "period": None,
            "PS_title": "Little mazurka",
            "ps_rating": "3",
            "related_entries": [{"title": "Little mazurka", "syllabus": "AMEB", "grade": "3", "ps": "3"}],
        }
    }
    entries = parse_catalog(fixture)
    assert entries[0].grade("AMEB") == 3
