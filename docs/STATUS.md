# Progress log

Format: date, what was done, what decisions were made and why, what's
next. So that anyone (human or AI) can pick the project back up without
rereading the whole conversation history that originated it.

## 2026-08-12 — Sheet music display (OSMD embedded in the desktop app)

User feedback after the first real practice session ("no entiendo,
supongo falta mucho") plus explicitly choosing the big option when asked
"small GUI polish vs. sheet music display" — went for sheet music, the
thing that actually addresses "I don't understand what to play."

**Three real pieces verified working together, in order**:
1. `notation.py`: `convert()` wraps `partitura.save_musicxml()` — a real
   PSyllabus MIDI (1702 notes) converts to valid MusicXML in 0.74s,
   cached to disk (instant on re-run). OSMD needs MusicXML/MEI, not raw
   MIDI — a MIDI file has no clef/note-spelling info, which is why this
   conversion step exists at all.
2. OSMD itself: downloaded the npm package (`opensheetmusicdisplay`
   2.1.2, BSD-3), used the prebuilt
   `build/opensheetmusicdisplay.min.js` (1.3MB, single file) — bundled
   into `src/pianomatic/webview/`, NOT loaded from a CDN, matching the
   project's "100% local" principle.
3. `QWebEngineView` (PySide6) embeds `webview/viewer.html` (loads the
   bundled OSMD JS, exposes `loadScoreFromPath(path)` for Python to call
   via `page().runJavaScript()`) in a new right-hand panel of the main
   window (`QSplitter`, window resized to 1300x750). Selecting a catalog
   entry now converts+caches its MusicXML and loads it into the viewer.

**Real dependency finding**: plain `PySide6` alone does NOT expose
`QWebEngineView` — Qt6 splits PySide6 into Essentials + Addons, and
`QtWebEngineWidgets` lives in `PySide6-Addons`. Had to install it
separately before the import worked. `pyproject.toml`'s `gui` extra now
lists both.

**Verified headless** (offscreen platform, same pattern as everything
else in this project): loaded a real converted score into the real
embedded webview and confirmed via `runJavaScript` that OSMD actually
rendered SVG content into the DOM (`document.querySelectorAll('#osmd-container svg').length === 1`)
— not just "the page loaded without error," actual rendered sheet music
confirmed present. The "SkyBottomLineCalculator: width not > 0" console
messages seen during this are a known OSMD artifact of a zero-width
offscreen container (no real screen), not a real error — expected to be
silent on the MacBook's real visible window.

**NOT done — this is a big scope, only the first slice is finished**:
- **No real-time cursor sync yet.** The score displays statically when
  you select a piece; it does NOT highlight the current note while you
  play. OSMD has a Cursor API for exactly this, but wiring it up needs
  REAL-TIME score-following during capture — architecturally different
  from pillar 1's current `align()`, which runs as a batch step AFTER
  the full performance is captured (see `cli.py`/`gui.py`'s
  `_run_practice`/`PracticeWorker`). This is real, separate work, not a
  quick follow-up.
- Not yet verified on a real visible window (only offscreen) — next
  step, same as the base GUI's own pending item.
- Packaging caveat for later: `webview/` files are found via
  `Path(__file__).parent`, which works fine for the editable installs
  (`pip install -e .`) used throughout this whole project, but a real
  wheel build would need `package-data` configured in `pyproject.toml`
  to include the non-`.py` files (`.html`, `.js`). Not relevant yet,
  noting it so it isn't a surprise later.

## 2026-08-12 — Desktop app (`gui.py`, PySide6)

First real GUI — until now pianomatic was terminal-only. User explicitly
asked for "a decent desktop application", not a web page.

**Toolkit choice**: PySide6 (official Qt-for-Python bindings), not
PyQt6. Reasoning: PianoBooster itself is Qt (we've been patching its
`.ini`/launch flags all session), so the desktop already leans Qt; and
PySide6 is LGPL while PyQt6 is GPL/commercial-dual — LGPL fits this
MIT-licensed project's "external deps keep their own license, invoked
not vendored" principle better (see ARCHITECTURE.md, "License" section).

**Design**: the GUI is presentation only — `gui.py` imports and calls
`catalog`, `control`, `session`, `diff`, `report` exactly as `cli.py`
does, no duplicated logic. `PracticeWorker(QObject)` moved to a
`QThread` runs the same blocking capture loop as `cli.py`'s
`_run_practice`, emitting Qt signals instead of `print()`, so the UI
thread never blocks on `MidiSession.listen()`.

**What's testable and what isn't**: Qt widget/event-loop code isn't
meaningfully unit-testable (real windows, a running event loop) — this
is true of GUI code generally, not a gap specific to this project. What
IS pure and tested: `entry_label()` (how a catalog entry renders as
text, 3 tests). What's manually verified instead: constructed the real
`MainWindow` headless (`QT_QPA_PLATFORM=offscreen`, no physical display
needed) against the actual downloaded catalog — 7,901 pieces loaded,
searched "couperin" → 29 results, selected an entry, confirmed the
Practice button enables correctly. No crash. This is the same
"synthetic-fast-tests + manually-verified-real-run" split used
throughout the project (align(), download_dataset(), practice), applied
to GUI construction instead of MIDI/network I/O.

**Added**: `[project.optional-dependencies].gui = ["PySide6>=6.5"]`
(separate extra — the CLI/core doesn't need Qt installed) and a
`pianomatic-gui` console script.

**Not yet done**: only manually verified headless (offscreen) on this
machine — hasn't been run with a real visible window on the MacBook yet
(next step, see Pending). No sheet-music display (that's the
sight-reading pillar's OSMD integration, a separate and much bigger
scope, see ARCHITECTURE.md) — this v1 GUI is catalog search + practice +
plain-text report, not a music notation app.

## 2026-08-12 — Song catalog (`catalog.py`, PSyllabus dataset)

Wired the "Content / song catalog" piece from ARCHITECTURE.md — until
now every test used either 3 synthetic notes or PianoBooster's
backing-track demo file; this gives pianomatic its first real, clean,
graded repertoire to point at.

**Schema verified against the real dataset** (downloaded
`new_clean_data.json` + `mid.zip` directly from Zenodo's API,
`zenodo.org/api/records/14794592/files/...`), not assumed from the
earlier research summary:
- JSON is a dict keyed by `"{composer}{title}"`, matching MIDI filenames
  exactly (`mid/{key}.mid`) — 7,901 entries, 7,901 MIDI files.
- Every entry has `ps_rating` (0-10, a syllabus-independent unified
  difficulty scale) and `related_entries` (dict of `{syllabus: grade}`,
  e.g. `{"ABRSM": 6, "Trinity": 6, "RIAM": 8}` — the same piece can be
  graded differently by different bodies, and not every piece has every
  syllabus).
- 1,271 entries have an ABRSM grade, 1,814 have RCM — plenty for the
  project's grade 5-6 target (242 pieces at ABRSM grade 5-6 alone).
- **Real data-quality quirk found**: `related_entries` is a dict for
  7,899/7,901 entries but a **list** of
  `{title, syllabus, grade, ps}` dicts for the other 2 — not documented
  anywhere, only found by actually running the parser against the full
  dataset (the hand-written test fixture didn't catch it, being based on
  the schema doc, not the full real file — same lesson as the MultiPort
  bug: synthetic tests miss what only shows up against real data).
  `_parse_grades()` handles both shapes.

**Implementation**: `catalog.py`, same two-layer pattern as the rest of
the codebase — `parse_catalog()`/`filter_by_grade()` pure and unit
tested (8 tests, including one covering the list-vs-dict quirk above);
`download_dataset()`/`load_catalog()` real I/O, manually verified (not
just described — actually ran `download_dataset()` end-to-end: 105s,
7,901 MIDI files extracted correctly; re-ran it to confirm the
idempotent skip logic works, near-instant on the second call). No new
dependency — uses only stdlib (`urllib.request`, `zipfile`).

**CLI**: `pianomatic catalog fetch` (downloads ~64MB to
`~/.local/share/pianomatic/psyllabus/` by default) and
`pianomatic catalog list --syllabus ABRSM --min-grade 5 --max-grade 6`.
Verified against the real downloaded dataset, not just the synthetic
fixture.

**Also verified**: one real PSyllabus MIDI file (Couperin, ABRSM grade 6)
parses cleanly through the EXISTING `diff.extract_reference_notes()` —
1,702 notes extracted, no errors. The diff engine built in the previous
session works on real graded repertoire without any changes needed.

**Not done**: the 64MB dataset isn't committed to the repo (correctly —
`scratch_psyllabus/` used during this session's exploration is
gitignored). Popular-music content still has no pipeline at all (real
legal wall, see ARCHITECTURE.md) — `catalog.py` only covers the
classical/PSyllabus side.

## 2026-08-12 — First real-hardware verification of `practice`

Deployed pianomatic to the MacBook companion (`chayo-macbookair7-2`) and
ran `pianomatic practice` against the real ALSA MIDI graph for the first
time — confirming the note from 2026-08-11 that "the first real-world run
always finds something a synthetic test didn't."

**Deploy notes**: `apt`'s dpkg lock was held by `unattended-upgrades` for
10+ minutes after boot (legitimate, not stuck — just slow), blocking
`python3-venv`. Worked around it entirely: `python3 -m venv` needs
`ensurepip` (part of the blocked apt package), so skipped venv, bootstrapped
pip via `bootstrap.pypa.io/get-pip.py` (no apt needed), and installed with
`pip install --break-system-packages --no-deps` (skipping `pymatchmaker[devices]`'s
`pyaudio` extra, which needs Python.h / compiler headers we don't have —
not needed anyway since we only use MIDI input, not audio, and
`python3-rtmidi` was already installed system-wide from the PianoBooster
debugging session).

**Real bug found and fixed**: `MidiSession` used `mido.ports.MultiPort`
to merge input ports, following mido's own documented pattern
(`yield_ports=True`). Against real hardware it delivered **zero events,
always** — verified in isolation: `mido.open_input()` +
`iter_pending()` directly received all 12 injected test events
correctly; wrapping the exact same open port in
`MultiPort(yield_ports=True)` received 0. Root cause:
`MultiPort._receive(block=True)` passes `block=True` into
`multi_receive()`, whose generator loops forever (`while True`) when
`block=True` — and `deque.extend()` can't return until the generator
raises `StopIteration`, which an infinite generator never does. The call
hangs forever on the very first receive; no event is ever delivered to
the caller. **Fix**: `MidiSession.listen()` now polls each port's
`iter_pending()` directly in a round-robin loop, sidestepping
MultiPort/`multi_receive()` entirely — verified working with the same
real-hardware injection test.

**Test method** (since coordinating live key presses over a chat turn is
impractical, established 2026-08-11): used `aplaymidi` to inject a
constructed MIDI file into ALSA's standard "Midi Through Port-0" (client
14, exists on every Linux system, no virtual port setup needed), with
`pianomatic practice` listening on that same port instead of the real
Keystation port. This exercises the entire real ALSA/ layer
(`mido.open_input`, real sequencer events, real timestamps) — the only
difference from a physical keyboard is the event source, not any code
path pianomatic itself runs.

**Result after the fix**: full pipeline verified end-to-end against real
ALSA MIDI I/O — `pianomatic practice` correctly listened, recorded 3
performed notes (pitches 60/64/67) while correctly EXCLUDING the
anchor+stop gesture notes (36/96/38) from the recording, detected the
stop command and exited the loop, saved a valid MIDI file (verified:
exactly the 3 performed notes, none of the control notes), then ran
`align()` + `match_notes()` + `generate_report()` against the reference
score. Report: `Notes: 3/3 matched (100%), Timing: 0ms average deviation,
0 notes off by more than 50ms`. Saved file round-tripped correctly
through `extract_performed_notes()`.

**Pending**: the same MultiPort bug is worth reporting upstream to mido
— it affects anyone using the documented `yield_ports=True` blocking
pattern, not just this project. Not filed yet.

## 2026-08-11 — Project kickoff

**Origin context**: born out of setting up a 2015 MacBook Air (Ubuntu
24.04) as a dedicated "companion" for a MIDI keyboard (M-Audio Keystation
61es) for family use. After getting that setup working (fluidsynth +
PianoBooster + soundfonts + systemd autostart), the question of what the
"state of the art" of learning piano with AI/MIDI/Linux in 2026 would be
came up — nothing mature combined the 4 pillars (repertoire,
sight-reading, ear, technique) with real feedback (not empty
gamification), so the decision was made to build it.

**Research done** (6 sub-agents, see links cited in ARCHITECTURE.md):
piano pedagogy, neuroscience of motor learning, motivation/gamification
psychology, existing MIDI/DTW libraries, sight-reading/ear-training
tools, notation rendering + IMSLP + OMR + graded-repertoire datasets.

**Decisions made**:
- Stack: Python (latency isn't a real concern — real-time audio is
  already handled by fluidsynth in C; this project only analyzes MIDI
  timestamps in batch/post-hoc).
- Alignment engine: `pymatchmaker`, not a hand-rolled DTW.
- Curriculum: anchored on the ABRSM/RCM syllabus (grade 5-6 as the
  target), not a level system invented from scratch.
- Classical content: Piano Syllabus Dataset (Zenodo) — already graded by
  difficulty, avoids manual curation.
- Popular content: manual, song by song — real legal wall.
- License: MIT.
- Hands-free control: anchor at the keyboard's extremes (lowest + highest
  note held) + commands by relative position of intermediate keys —
  avoids interacting with mouse/keyboard during practice.

**Done this session**:
- Repo created on GitHub (`racoi12/pianomatic`, public, MIT).
- `docs/ARCHITECTURE.md` with the full design of the 4 pillars.
- Initial scaffold: `src/pianomatic/{control,midi_io,diff,report,cli}.py`.
- `control.py` implemented (anchor + relative-position mapping) with 6
  tests.
- `midi_io.py` implemented — pure `translate()` (tested) + `MidiSession`
  (real I/O, needs hardware, not unit tested). Uses `mido.ports.MultiPort`
  with `yield_ports=True` to merge multiple input ports.
- `diff.py`: `align()` implemented, wraps `Matchmaker.run()`. **Manually
  verified** (not in the pytest suite — the real engine pulls in the
  full ML stack and takes real seconds per run, not worth it on every
  `pytest`) with a self-comparison against
  `~/Music/BoosterMusicBooks4/Beginner Course/01-StartWithMiddleC.mid`:
  138 positions, correct monotonic progression. Exact command to
  re-verify:
  ```
  .venv/bin/python3 -c "
  import sys; sys.path.insert(0, 'src')
  from pianomatic.diff import align
  r = align('SCORE.mid', 'SCORE.mid')
  print(r.path.shape, r.path[:3])
  "
  ```
- **Bug found in pymatchmaker**: `Matchmaker.run()`'s docstring says the
  alignment path has shape `(2, N)` — in practice it's `(N, 2)`
  (verified, real shape `(138, 2)`). Also: the generator's return value
  (the path) is only reachable via `StopIteration.value`, not by
  exhausting it with `list()` — that silently discards the path if not
  handled correctly.
- Per-note diff (timing + pitch) in `diff.py`: `match_notes()`
  implemented with 7 unit tests (synthetic data, fast — no ML stack
  dependency). Algorithm: greedy nearest-neighbor by pitch within a
  tolerance window (0.5s default), each performed note used at most
  once. **Not a globally optimal assignment** — good enough for v1,
  revisit if it misbehaves on real playing with repeated notes close
  together.
- `compare()` end-to-end manually verified against a real file
  (self-comparison): 8/8 reference notes matched, ~0ms timing deviation
  (floating-point noise). **Real finding**: the test file
  (`~/Music/BoosterMusicBooks4/.../01-StartWithMiddleC.mid`, from
  PianoBooster) bundles a full backing band — drums, bass, accompaniment
  — 196 NOTE_ON events across 4 MIDI channels vs. only 8 actual melody
  notes. `extract_performed_notes()` now accepts `channel: int | None`
  to filter, though even that isn't enough for this specific file (the
  melody is doubled across channels). **Doesn't affect real usage**: live
  capture (`midi_io.MidiSession` from the physical keyboard) never has
  this problem — it only ever captures what the user actually played.
  For future tests, use a clean solo-piano reference MIDI (e.g.
  something from the PSyllabus dataset) instead of a full-band file.
- `report.py`: implemented, 8 unit tests (synthetic data). Only lists
  timing deviations above the JND threshold (default 50ms) — never
  reports sub-perceptual noise as an error, and keeps timing/missed/extra
  notes in separate sections (never a single score).
- `cli.py`: `pianomatic compare SCORE.mid PERFORMANCE.mid` works
  end-to-end, verified with the real installed command (`pip install -e`).
- **v1 of the Repertoire pillar closed out**: capture → alignment →
  per-note diff → report, each piece implemented and tested (26 tests).
  Missing: dynamics (blocked on needing a reference source with real
  expression markings) and report localization (see below).
- Real Keystation 61es range **verified against physical hardware**
  (aseqdump against the real MIDI port, not assumed): lowest note = 36
  (C2), highest = 96 (C7) — 60 semitones, 61 keys, matches the 5-octave
  spec. Now exposed as `control.KEYSTATION_61ES_LOW`/`KEYSTATION_61ES_HIGH`,
  reused by the tests instead of duplicating the literals.
- `control.py` API change: `handle_note_on`/`handle_note_off` now return
  `bool` (consumed by the control layer or not) instead of `None`. Rule:
  while armed, EVERY note is consumed (not just mapped commands) — the
  user's hands are pinning both anchors, they're not playing real music
  at that moment. Note-off of a consumed note is tracked via a
  `_suppressed` set so it's consumed too even after the anchors release.
- `session.py`: `PracticeSession` routes a live event stream between the
  control layer and performance recording — the missing link between
  `midi_io` (capture) and `diff`/`control` (which existed in isolation
  until now). 7 tests, synthetic events, no hardware needed.
- `diff.save_performed_notes()`: writes a live-captured session to a
  real MIDI file so it can feed the existing `compare()` pipeline instead
  of needing a separate live-scoring code path. Round-trip tested (save
  then `extract_performed_notes` recovers the same notes).
- `cli.py practice` command: wires `MidiSession` + `PracticeSession` +
  `save_performed_notes` + `compare` end-to-end. **NOT verified against
  real hardware in this session** — coordinating live key presses over a
  chat turn proved impractical (see the keyboard-range calibration
  exchange). Each piece it wires IS independently tested; the wiring
  itself needed a real run to confirm. ✅ Done the next session
  (2026-08-12, see that entry above) — found and fixed a real bug in the
  process (`mido.ports.MultiPort` never delivers events in blocking
  mode).
- Whole project translated to English (README, ARCHITECTURE, STATUS,
  CONTRIBUTING, `control.py` + its tests were the last holdouts from the
  kickoff session, written in Spanish at the time).

**Pending / next session**:
- [x] Run `pianomatic practice` against real hardware and fix whatever
  surfaced — done 2026-08-12, see that entry above.
- [ ] Dynamics (velocity) dimension: `match_notes()` already records the
  velocity of each matched note, but doesn't compare it against a
  reference — a plain MIDI file doesn't carry reliable dynamics
  markings. Needs a reference source with real expression data first.
- [ ] Sight-reading and ear-training modules: not started yet, see
  ARCHITECTURE.md for what to reuse.
- [ ] Sustain pedal (CC64) support in the diff engine (the event model
  already handles CC64 in `midi_io.py`, nothing downstream uses it yet
  — see ARCHITECTURE.md, "Sustain pedal" section). Verify with real
  hardware whether the Keystation 61es reports half-pedal (continuous)
  or on/off only.
- [ ] Report localization (see below) — not urgent, deferred on purpose.
- [x] Song catalog (PSyllabus dataset) — done 2026-08-12, see that entry
  above (`catalog.py`).
- [x] Wire the catalog into `practice`/`compare` — done 2026-08-12,
  `--catalog "search query"` on both commands, plus `catalog search` for
  discovery (the real `key` strings are too verbose to type/remember
  exactly — search resolves a fuzzy query to the exact piece). Ambiguous
  or no-match queries exit with the candidate list instead of guessing.
  Verified against the real dataset: search, ambiguous-match error,
  no-match error, and a full `compare --catalog` run all behave
  correctly. `pianomatic practice --catalog "couperin f les petits" --port ...`
  is now the real way someone would actually use this, not
  `practice /path/to/some.mid --port ...`.
- [ ] File the `mido.ports.MultiPort` bug upstream (see the 2026-08-12
  practice-verification entry above) — affects anyone using the
  documented `yield_ports=True` blocking pattern, not just this project.

### Pending: report localization

`report.py` generates text in English (consistent with the
English-going-forward decision). But this tool's real users (Akira,
Chayo, family) speak Spanish — an English coaching report isn't the
intended final experience. Not resolved here because:
- v1 is a developer tool (CLI, plain text) to prove the engine works,
  not the polished coaching experience.
- The real user-facing report will be generated by the local LLM (the
  pending "coach" phase, see ARCHITECTURE.md) — that's where language
  naturally gets resolved (a Spanish prompt), not in v1's plain-text
  `report.py`.
When that phase arrives, decide: does `report.py` become internal-only
(structured data the LLM consumes) and its English text stop being shown
directly to the user? Probably yes — don't design generic i18n for text
that's about to stop being user-facing.
