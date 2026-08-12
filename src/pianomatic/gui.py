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

import logging
import sys
import tempfile
import traceback
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
    filter_by_grade,
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

LOG_PATH = DEFAULT_DATA_DIR.parent / "gui.log"

logger = logging.getLogger("pianomatic.gui")


def setup_logging() -> None:
    """Logs to a persistent file (survives across runs, readable after
    the process is gone — e.g. over SSH after a crash) AND stdout.

    Real bug this fixes (2026-08-12, see docs/STATUS.md): the app closed
    silently when selecting the Keystation port, with only
    'QThread: Destroyed while thread '' is still running' in the
    redirected stdout log — Qt/PySide's C++ layer had swallowed whatever
    Python exception actually caused it. `install_excepthook` below is
    the other half of the fix: it's what actually surfaces exceptions
    raised inside Qt slots, which PySide6 does not always propagate as a
    normal Python exception.
    """
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[logging.FileHandler(LOG_PATH), logging.StreamHandler()],
    )


def install_excepthook() -> None:
    """PySide6 does not reliably propagate exceptions raised inside a Qt
    slot as a normal Python exception — depending on the Qt event that
    triggered the slot, they can be silently swallowed, which is exactly
    what made the original crash unfixable from the stdout log alone
    (see docs/STATUS.md, 2026-08-12). `sys.excepthook` is the one hook
    that's actually reached in both cases.
    """

    def handle(exc_type, exc_value, exc_traceback):
        logger.error("Unhandled exception:\n%s", "".join(traceback.format_exception(exc_type, exc_value, exc_traceback)))
        sys.__excepthook__(exc_type, exc_value, exc_traceback)

    sys.excepthook = handle


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
        self._abort = False
        self._midi_session: MidiSession | None = None

    def request_stop(self) -> None:
        """Called from another thread (MainWindow.closeEvent) to abort a
        running session immediately — skips the analysis step, just ends
        the capture loop. Real bug this exists to fix (2026-08-12, see
        docs/STATUS.md): closing the window while this worker was still
        blocked listening for MIDI left its QThread running when Qt tore
        the app down, and Qt6 treats destroying a running QThread as
        fatal — the whole process aborted, which looked like a crash.
        """
        logger.info("PracticeWorker.request_stop() called")
        self._abort = True
        self._stop_requested = True
        if self._midi_session is not None:
            self._midi_session.stop()

    def run(self) -> None:
        logger.info("PracticeWorker starting: score=%s port=%r", self._score_path, self._port_name)
        try:
            self._run()
        except Exception as e:  # noqa: BLE001 - surfaced to the UI, not swallowed
            logger.error("PracticeWorker failed:\n%s", traceback.format_exc())
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
            self._midi_session = midi_session
            for event in midi_session.listen():
                session.handle_event(event)
                self.status.emit(f"{len(session.performed_notes)} notes played")
                if self._stop_requested:
                    midi_session.stop()
                    break
        self._midi_session = None

        if self._abort:
            logger.info("PracticeWorker aborted, skipping analysis")
            return

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
        port_names = mido.get_input_names()
        logger.info("MIDI input ports detected: %r", port_names)
        self.port_combo.addItems(port_names)
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
        self.status_label.setText(
            f"{len(self._entries)} pieces loaded. Showing ABRSM grade 5-6 by default — search to narrow."
        )
        self._show_entries(filter_by_grade(self._entries, "ABRSM", 5, 6))

    def _on_search(self, text: str) -> None:
        if len(text) < 2:
            # empty/too-short search: fall back to the default grade 5-6
            # list instead of an empty results pane — an app that looks
            # empty on open reads as broken, not "type something".
            self._show_entries(filter_by_grade(self._entries, "ABRSM", 5, 6))
            return
        self._show_entries(search(self._entries, text)[:50])

    def _show_entries(self, entries: list[CatalogEntry]) -> None:
        self.results_list.clear()
        for entry in entries:
            item = QListWidgetItem(entry_label(entry))
            item.setData(1, entry)
            self.results_list.addItem(item)

    def _on_select(self) -> None:
        items = self.results_list.selectedItems()
        self._selected_entry = items[0].data(1) if items else None
        logger.info("Selected: %s", self._selected_entry.key if self._selected_entry else None)
        self.practice_button.setEnabled(self._selected_entry is not None)

    def _start_practice(self) -> None:
        try:
            self._start_practice_impl()
        except Exception:
            logger.error("_start_practice failed:\n%s", traceback.format_exc())
            self.status_label.setText("Error starting practice — see gui.log")
            self.practice_button.setEnabled(True)
            raise

    def _start_practice_impl(self) -> None:
        if not self._selected_entry or not self.port_combo.currentText():
            logger.warning(
                "Practice clicked with no selection: entry=%s port=%r",
                self._selected_entry, self.port_combo.currentText(),
            )
            return
        score_path = str(resolve_midi_path(self._selected_entry, self._data_dir))
        port_name = self.port_combo.currentText()
        logger.info("Starting practice: score_path=%s port=%r", score_path, port_name)

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
        logger.info("Practice finished, report:\n%s", report_text)
        self.status_label.setText("Done.")
        self.report_view.setPlainText(report_text)
        self.practice_button.setEnabled(True)

    def _on_error(self, message: str) -> None:
        logger.error("Practice error signal: %s", message)
        self.status_label.setText(f"Error: {message}")
        self.practice_button.setEnabled(True)

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt override, not our naming convention
        """Real bug this fixes (2026-08-12, see docs/STATUS.md): closing
        the window while a practice session was still listening for MIDI
        left its QThread running when Qt tore the app down — Qt6 treats
        that as fatal and aborts the whole process (looked like a crash,
        not a graceful close). Must stop the worker and actually wait for
        its thread to finish before letting the window close.
        """
        if self._thread is not None and self._thread.isRunning():
            logger.info("Closing while practice session active — stopping worker first")
            self._worker.request_stop()
            # request_stop() aborts the worker's _run() without it ever
            # emitting finished/error — those signals are what normally
            # trigger self._thread.quit(). Without calling quit() here
            # too, the QThread's own event loop never gets told to stop
            # even after the worker's Python method returns, and Qt6
            # aborts the whole process on a still-"running" QThread
            # (verified: this exact gap reproduced the crash, see
            # docs/STATUS.md 2026-08-12).
            self._thread.quit()
            self._thread.wait(2000)
        event.accept()


def main() -> None:
    from PySide6.QtWidgets import QApplication

    setup_logging()
    install_excepthook()
    logger.info("pianomatic-gui starting")

    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
