# Progress log

Format: date, what was done, what decisions were made and why, what's
next. So that anyone (human or AI) can pick the project back up without
rereading the whole conversation history that originated it.

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
  real hardware** — coordinating live key presses over a chat turn
  proved impractical this session (see the keyboard-range calibration
  exchange). Each piece it wires IS independently tested; the wiring
  itself needs a real run to confirm.
- Whole project translated to English (README, ARCHITECTURE, STATUS,
  CONTRIBUTING, `control.py` + its tests were the last holdouts from the
  kickoff session, written in Spanish at the time).

**Pending / next session**:
- [ ] Run `pianomatic practice` against the real Keystation 61es and fix
  whatever the first real-world run surfaces (there will likely be
  something — synthetic tests never catch everything).
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
