from pianomatic.catalog import CatalogEntry
from pianomatic.gui import entry_label


def test_entry_label_includes_grades():
    entry = CatalogEntry(
        key="k", composer="Couperin F.", title="Les Petits Moulins",
        period="Baroque", ps_rating=6, grades={"ABRSM": 6, "Trinity": 6},
    )
    assert entry_label(entry) == "Couperin F. — Les Petits Moulins  [ABRSM 6, Trinity 6]"


def test_entry_label_without_grades():
    entry = CatalogEntry(
        key="k", composer="Faure G.", title="Barcarolle",
        period="Romantic", ps_rating=7, grades={},
    )
    assert entry_label(entry) == "Faure G. — Barcarolle"


def test_entry_label_grades_sorted_for_stable_display():
    entry = CatalogEntry(
        key="k", composer="X", title="Y", period=None, ps_rating=5,
        grades={"Trinity": 5, "ABRSM": 5},
    )
    assert entry_label(entry) == "X — Y  [ABRSM 5, Trinity 5]"
