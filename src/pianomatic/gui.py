"""Desktop GUI (PySide6). Wraps the same pure/tested modules (catalog,
control, session, diff, report) used by cli.py — no duplicated logic,
this is presentation only.

Qt widget/event-loop code itself isn't meaningfully unit-testable (real
windows, a running event loop) — verified manually by running the app,
see docs/STATUS.md. Pure logic that CAN be extracted and tested (e.g.
`entry_label`) lives separately from the widget classes for exactly that
reason.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import mido
from PySide6.QtCore import QObject, QThread, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from pianomatic.catalog import (
    DEFAULT_DATA_DIR,
    CatalogEntry,
    load_catalog,
    resolve_midi_path,
    search,
)
from pianomatic.control import KEYSTATION_61ES_HIGH, KEYSTATION_61ES_LOW, HandsFreeControl
from pianomatic.diff import align as diff_align
from pianomatic.diff import extract_reference_notes, match_notes, save_performed_notes
from pianomatic.midi_io import MidiSession
from pianomatic.report import generate_report
from pianomatic.session import PracticeSession

STOP_COMMAND = "stop"


def entry_label(entry: CatalogEntry) -> str:
    """Pure, tested: how a catalog entry shows up in the results list."""
    grades = ", ".join(f"{syllabus} {grade}" for syllabus, grade in sorted(entry.grades.items()))
    return f"{entry.composer} — {entry.title}  [{grades}]" if grades else f"{entry.composer} — {entry.title}"


class PracticeWorker(QObject):
    """Runs the blocking capture loop off the UI thread. Same wiring as
    cli.py's _run_practice, just emitting Qt signals instead of print().
    """

    status = Signal(str)
    finished = Signal(str)  # report text
    error = Signal(str)

    def __init__(self, score_path: str, port_name: str) -> None:
        super().__init__()
        self._score_path = score_path
        self._port_name = port_name
        self._stop_requested = False

    def run(self) -> None:
        try:
            self._run()
        except Exception as e:  # noqa: BLE001 - surfaced to the UI, not swallowed
            self.error.emit(str(e))

    def _run(self) -> None:
        def on_command(command: str) -> None:
            if command == STOP_COMMAND:
                self._stop_requested = True

        control = HandsFreeControl(
            KEYSTATION_61ES_LOW, KEYSTATION_61ES_HIGH, [STOP_COMMAND], on_command=on_command
        )
        session = PracticeSession(control)

        self.status.emit(f"Listening on {self._port_name}. Hold lowest+highest key, then the next white key, to stop.")
        with MidiSession([self._port_name]) as midi_session:
            for event in midi_session.listen():
                session.handle_event(event)
                self.status.emit(f"{len(session.performed_notes)} notes played")
                if self._stop_requested:
                    break

        self.status.emit("Analyzing performance...")
        target = Path(tempfile.mktemp(suffix=".mid"))
        save_performed_notes(session.performed_notes, target)
        alignment = diff_align(self._score_path, target)
        reference = extract_reference_notes(self._score_path)
        result = match_notes(reference, session.performed_notes, alignment)
        target.unlink(missing_ok=True)

        self.finished.emit(generate_report(result))


class MainWindow(QMainWindow):
    def __init__(self, data_dir: Path = DEFAULT_DATA_DIR) -> None:
        super().__init__()
        self.setWindowTitle("pianomatic")
        self.resize(700, 600)

        self._data_dir = data_dir
        self._entries: list[CatalogEntry] = []
        self._selected_entry: CatalogEntry | None = None
        self._thread: QThread | None = None
        self._worker: PracticeWorker | None = None

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Search catalog (composer or title)...")
        self.search_box.textChanged.connect(self._on_search)
        layout.addWidget(self.search_box)

        self.results_list = QListWidget()
        self.results_list.itemSelectionChanged.connect(self._on_select)
        layout.addWidget(self.results_list)

        control_row = QHBoxLayout()
        control_row.addWidget(QLabel("MIDI port:"))
        self.port_combo = QComboBox()
        self.port_combo.addItems(mido.get_input_names())
        control_row.addWidget(self.port_combo)
        self.practice_button = QPushButton("Practice")
        self.practice_button.setEnabled(False)
        self.practice_button.clicked.connect(self._start_practice)
        control_row.addWidget(self.practice_button)
        layout.addLayout(control_row)

        self.status_label = QLabel("Loading catalog...")
        layout.addWidget(self.status_label)

        self.report_view = QTextEdit()
        self.report_view.setReadOnly(True)
        self.report_view.setFontFamily("monospace")
        layout.addWidget(self.report_view)

        self._load_catalog()

    def _load_catalog(self) -> None:
        metadata_path = self._data_dir / "new_clean_data.json"
        if not metadata_path.exists():
            self.status_label.setText(
                f"Catalog not found at {self._data_dir}. Run 'pianomatic catalog fetch' first."
            )
            return
        self._entries = load_catalog(metadata_path)
        self.status_label.setText(f"{len(self._entries)} pieces loaded. Search above to begin.")

    def _on_search(self, text: str) -> None:
        self.results_list.clear()
        if len(text) < 2:
            return
        for entry in search(self._entries, text)[:50]:
            item = QListWidgetItem(entry_label(entry))
            item.setData(1, entry)
            self.results_list.addItem(item)

    def _on_select(self) -> None:
        items = self.results_list.selectedItems()
        self._selected_entry = items[0].data(1) if items else None
        self.practice_button.setEnabled(self._selected_entry is not None)

    def _start_practice(self) -> None:
        if not self._selected_entry or not self.port_combo.currentText():
            return
        score_path = str(resolve_midi_path(self._selected_entry, self._data_dir))
        port_name = self.port_combo.currentText()

        self.practice_button.setEnabled(False)
        self.report_view.clear()

        self._thread = QThread()
        self._worker = PracticeWorker(score_path, port_name)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.status.connect(self.status_label.setText)
        self._worker.finished.connect(self._on_finished)
        self._worker.error.connect(self._on_error)
        self._worker.finished.connect(self._thread.quit)
        self._worker.error.connect(self._thread.quit)
        self._thread.start()

    def _on_finished(self, report_text: str) -> None:
        self.status_label.setText("Done.")
        self.report_view.setPlainText(report_text)
        self.practice_button.setEnabled(True)

    def _on_error(self, message: str) -> None:
        self.status_label.setText(f"Error: {message}")
        self.practice_button.setEnabled(True)


def main() -> None:
    from PySide6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
