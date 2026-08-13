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
import os
import shutil
import subprocess
import sys
import tempfile
import traceback
from pathlib import Path

import mido
from PySide6.QtCore import QObject, QThread, QTimer, QUrl, Signal
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QPushButton,
    QSpinBox,
    QSplitter,
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
from pianomatic.midi_io import MidiSession, note_name
from pianomatic.notation import convert as convert_to_musicxml
from pianomatic.report import generate_report
from pianomatic.session import PracticeSession

WEBVIEW_DIR = Path(__file__).parent / "webview"
MUSICXML_CACHE_DIR = DEFAULT_DATA_DIR.parent / "musicxml_cache"

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
                notes_before = len(session.performed_notes)
                session.handle_event(event)
                if len(session.performed_notes) > notes_before:
                    last_note = note_name(session.performed_notes[-1].pitch)
                    self.status.emit(f"{len(session.performed_notes)} notes played — last: {last_note}")
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
        self._practice_active = False
        self.resize(1300, 750)

        splitter = QSplitter()
        self.setCentralWidget(splitter)

        left = QWidget()
        layout = QVBoxLayout(left)
        splitter.addWidget(left)

        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Search catalog (composer or title)...")
        self.search_box.textChanged.connect(self._on_search)
        layout.addWidget(self.search_box)

        # ABRSM grade 5-6 is this project's long-term TARGET (see
        # ARCHITECTURE.md), not where a beginner should start — real
        # feedback (2026-08-12, see docs/STATUS.md): a first-time user
        # was shown a grade 6 piece by default and it looked "super
        # advanced" because it is. Without this, there was no way to
        # pick an appropriate starting level at all.
        grade_row = QHBoxLayout()
        grade_row.addWidget(QLabel("ABRSM grade:"))
        self.min_grade_spin = QSpinBox()
        self.min_grade_spin.setRange(0, 10)
        self.min_grade_spin.setValue(1)
        self.min_grade_spin.valueChanged.connect(self._on_grade_range_changed)
        grade_row.addWidget(self.min_grade_spin)
        grade_row.addWidget(QLabel("to"))
        self.max_grade_spin = QSpinBox()
        self.max_grade_spin.setRange(0, 10)
        self.max_grade_spin.setValue(2)
        self.max_grade_spin.valueChanged.connect(self._on_grade_range_changed)
        grade_row.addWidget(self.max_grade_spin)
        layout.addLayout(grade_row)

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
        # Real user need (2026-08-12, see docs/STATUS.md): sheet music
        # alone doesn't help someone who can't read notation yet. Rather
        # than build a falling-notes view from scratch, PianoBooster
        # (already installed, already fixed earlier this session) does
        # exactly that already — this button just opens the SAME piece
        # there instead of making the user hunt down the file manually.
        self.pianobooster_button = QPushButton("Open in PianoBooster")
        self.pianobooster_button.setEnabled(False)
        self.pianobooster_button.clicked.connect(self._open_in_pianobooster)
        control_row.addWidget(self.pianobooster_button)
        layout.addLayout(control_row)

        self.status_label = QLabel("Loading catalog...")
        layout.addWidget(self.status_label)

        self.report_view = QTextEdit()
        self.report_view.setReadOnly(True)
        self.report_view.setFontFamily("monospace")
        layout.addWidget(self.report_view)

        self._webview_ready = False
        self.sheet_music_view = QWebEngineView()
        self.sheet_music_view.loadFinished.connect(self._on_webview_loaded)
        self.sheet_music_view.load(QUrl.fromLocalFile(str(WEBVIEW_DIR / "viewer.html")))
        splitter.addWidget(self.sheet_music_view)
        splitter.setSizes([450, 850])

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
            f"{len(self._entries)} pieces loaded. Showing ABRSM grade "
            f"{self.min_grade_spin.value()}-{self.max_grade_spin.value()} — search or change the grade to narrow."
        )
        self._show_entries(self._graded_entries())

    def _graded_entries(self) -> list[CatalogEntry]:
        return filter_by_grade(
            self._entries, "ABRSM", self.min_grade_spin.value(), self.max_grade_spin.value()
        )

    def _on_grade_range_changed(self) -> None:
        if self.min_grade_spin.value() > self.max_grade_spin.value():
            self.max_grade_spin.setValue(self.min_grade_spin.value())
            return  # setValue above re-triggers this handler once more, cleanly
        logger.info("Grade range changed: %d-%d", self.min_grade_spin.value(), self.max_grade_spin.value())
        if len(self.search_box.text()) < 2:
            self._show_entries(self._graded_entries())

    def _on_search(self, text: str) -> None:
        if len(text) < 2:
            # empty/too-short search: fall back to the grade-filtered
            # list instead of an empty results pane — an app that looks
            # empty on open reads as broken, not "type something".
            self._show_entries(self._graded_entries())
            return
        self._show_entries(search(self._entries, text)[:50])

    def _show_entries(self, entries: list[CatalogEntry]) -> None:
        self.results_list.clear()
        for entry in entries:
            item = QListWidgetItem(entry_label(entry))
            item.setData(1, entry)
            self.results_list.addItem(item)

    def _on_webview_loaded(self, ok: bool) -> None:
        logger.info("Sheet music webview loaded: %s", ok)
        self._webview_ready = ok

    def _on_select(self) -> None:
        items = self.results_list.selectedItems()
        self._selected_entry = items[0].data(1) if items else None
        logger.info("Selected: %s", self._selected_entry.key if self._selected_entry else None)
        # Real bug (2026-08-12, see docs/STATUS.md): this used to
        # unconditionally re-enable the button on every selection, which
        # let a user start a SECOND practice session while the first was
        # still running (still listening for MIDI, never stopped) —
        # overwriting self._thread/self._worker while the old QThread
        # was still alive, the same Qt6-aborts-on-still-running-QThread
        # crash as the close-mid-session bug, just triggered a different
        # way. Must also check practice isn't already active.
        self.practice_button.setEnabled(self._selected_entry is not None and not self._practice_active)
        self.pianobooster_button.setEnabled(self._selected_entry is not None)
        if self._selected_entry is not None:
            self._show_sheet_music(self._selected_entry)

    def _open_in_pianobooster(self) -> None:
        if not self._selected_entry:
            return
        pianobooster_path = shutil.which("pianobooster")
        if not pianobooster_path:
            logger.error("pianobooster not found on PATH")
            self.status_label.setText("PianoBooster not found — is it installed?")
            return
        midi_path = resolve_midi_path(self._selected_entry, self._data_dir)
        logger.info("Opening in PianoBooster: %s", midi_path)
        # Inherits this process's display/session environment -- no need
        # for the XAUTHORITY/DISPLAY dance an SSH-launched process needs,
        # this runs from inside the already-running GUI session.
        # QT_QPA_PLATFORM=xcb: PianoBooster flickers under native Wayland
        # on this machine (fixed earlier this session via a .desktop
        # override, see docs/piano_midi_keystation.md memory) -- launching
        # the raw binary here bypasses that .desktop file, so the same
        # override has to be applied directly.
        env = {**os.environ, "QT_QPA_PLATFORM": "xcb"}
        subprocess.Popen([pianobooster_path, str(midi_path)], env=env)

    def _show_sheet_music(self, entry: CatalogEntry) -> None:
        midi_path = resolve_midi_path(entry, self._data_dir)
        try:
            xml_path = convert_to_musicxml(midi_path, MUSICXML_CACHE_DIR)
        except Exception:
            logger.error("MusicXML conversion failed for %s:\n%s", entry.key, traceback.format_exc())
            return
        js = f'loadScoreFromPath("file://{xml_path.resolve()}")'

        def run_js() -> None:
            self.sheet_music_view.page().runJavaScript(js)

        # viewer.html loads asynchronously; if it's not ready yet (e.g.
        # user searches+selects very fast right after startup), retry
        # shortly instead of silently no-op-ing against an undefined JS
        # function.
        if self._webview_ready:
            run_js()
        else:
            QTimer.singleShot(300, lambda: self._show_sheet_music(entry))

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
        if self._practice_active:
            # Defensive: _on_select() is what's supposed to prevent this
            # (see the comment there), this is a second line of defense
            # against the exact crash that comment describes.
            logger.warning("Practice already active, ignoring duplicate start request")
            return
        score_path = str(resolve_midi_path(self._selected_entry, self._data_dir))
        port_name = self.port_combo.currentText()
        logger.info("Starting practice: score_path=%s port=%r", score_path, port_name)

        self._practice_active = True
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
        self._practice_active = False
        self.status_label.setText("Done.")
        self.report_view.setPlainText(report_text)
        self.practice_button.setEnabled(True)

    def _on_error(self, message: str) -> None:
        logger.error("Practice error signal: %s", message)
        self._practice_active = False
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
