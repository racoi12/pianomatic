# pianomatic architecture

Local, open-source piano coach. Goal: take someone from zero to real
piano fluency (sheet music, ear, memory) for family enjoyment — not
training concert pianists. Progress anchor: ABRSM/RCM syllabus, target
grade 5-6 as graduation.

Four pillars of musical skill, four software modules. Only one
(repertoire) has its own engine; the rest lean on the existing
open-source ecosystem instead of being reinvented.

## 1. Repertoire (v1, implemented and wired end-to-end)

Compare your MIDI performance of a piece against a reference.

- **Capture**: `mido` + `python-rtmidi` — NOTE_ON/NOTE_OFF timestamps.
- **Alignment**: [`pymatchmaker`](https://github.com/pymatchmaker/matchmaker)
  (ISMIR 2025) — score-following already solved and evaluated on real
  datasets (ASAP), not hand-rolled DTW.
- **Diff**: separate dimensions — timing, pitch, dynamics/velocity —
  never a single score (pedagogy criticism of commercial apps is
  unanimous on this). Sensitivity threshold: >20-50ms deviation (human
  JND measured in rhythm-perception research).
- **Report**: plain text in v1. Two-layer feedback later: simple
  immediate live ping + reflective report via a local LLM (Ollama) the
  next day — neuroscience research shows both timings serve different
  goals (early precision vs. retention).
- **Live practice**: `session.PracticeSession` routes a live MIDI stream
  between the hands-free control layer and performance recording;
  `cli.py practice` wires capture → control → recording → save → compare
  → report end-to-end. Implemented, NOT yet verified against real
  hardware — see docs/STATUS.md.

## 2. Sight-reading (rendering done, procedural generation pending)

Doesn't use pillar 1's fixed reference — needs NEW material every time.

- Procedural generation: [Open Sheet Music Education](https://opensheetmusiceducation.org/)
  (BSD-3) or adapt [`ftrain/sightreading`](https://github.com/ftrain/sightreading)
  (LGPL-3.0, already has live MIDI input and 23 levels). Not started.
- **Rendering: done (2026-08-12)**. OpenSheetMusicDisplay (OSMD, BSD-3),
  bundled locally (`src/pianomatic/webview/opensheetmusicdisplay.min.js`,
  not a CDN — matches "100% local"), shown via `QWebEngineView` embedded
  in the desktop app (`gui.py`). OSMD needs MusicXML, not raw MIDI (a
  MIDI file lacks notation-level info like clefs/spelling) —
  `notation.py` converts via `partitura.save_musicxml`, cached to disk
  since conversion isn't instant. Currently used to show the score for
  the selected catalog piece (static) — the Cursor API's real-time
  note-highlighting synced to live MIDI input (what the mention above
  was originally about) is NOT wired up yet: that needs real-time
  score-following during capture, which is architecturally different
  from pillar 1's current batch alignment (runs `align()` AFTER the full
  performance is captured, not live during it). See docs/STATUS.md.

## 3. Ear training (pending)

The only pillar with no maintained OSS alternative — GNU Solfege is
GUI-only and its last stable release is from 2016, no API. Build it
small and custom (interval/chord quiz, a couple hundred lines).

## 4. Technique (pending)

Reuses pillar 1's diff engine, but against patterns (scales/arpeggios)
instead of full pieces.

## Content / song catalog

- **Classical**: [Piano Syllabus Dataset](https://zenodo.org/records/14794592)
  (CC) — 7,901 recordings already annotated by ABRSM/RCM/Trinity level,
  MIDI included. Solves graded-repertoire curation without manual work.
  Secondary MusicXML source: [OpenScore corpus](https://github.com/eduardomourar/music-scores-musicxml).
  IMSLP is NOT the primary source — it's mostly scanned PDF, not
  MusicXML.
- **Popular**: manual curation, song by song. Real legal wall
  (copyright), no honest shortcut or automatic pipeline.
- **OMR (plan C)**: only if a piece is missing from every digitized
  source. `oemer` (Python, pip-installable) preferred over Audiveris
  (Java, AGPL — if used, invoke via subprocess, never link, to avoid
  inheriting the license).

## Hands-free control

Real problem: coordinating mouse/keyboard/piano breaks flow state
mid-practice. Solution: reserve the Keystation 61es's extreme keys (real
range C2–C7, zones the repertoire up to grade 5-6 almost never touches)
as a modifier.

- **Anchor**: lowest note + highest note held at the same time (one
  pinky on each extreme).
- **Command**: while the anchor is held, each intermediate key played
  fires an action — mapped by **relative position** from the low anchor
  (1st white key = command 1, 2nd = command 2...), not a fixed note —
  memorizable by physical distance without looking.
- **Cancel**: releasing the anchor without playing anything = no-op.
- **Scope**: active only within a `pianomatic` session, never system-wide
  — outside the app the keyboard is 100% normal piano.
- **Consumption rule**: while armed, EVERY note is consumed (not just
  mapped commands) — the user's hands are pinning both anchors, they
  aren't playing real music at that moment. `HandsFreeControl.handle_note_on`/
  `handle_note_off` return whether an event was consumed, so
  `session.PracticeSession` knows whether to record it as music.

Implementation: `pianomatic.control` (pure gesture detection) +
`pianomatic.session` (routes a live event stream between control and
recording) — intercepts the raw MIDI stream BEFORE it reaches the
diff/recording engine.

## Sustain pedal

The Keystation 61es has dedicated sustain AND volume pedal jacks. Pedal
input arrives as MIDI Control Change (CC64 = damper/sustain), not as
note events — `midi_io.py`'s event model already has a case for CC
messages (`ControlChangeEvent`), but nothing downstream uses it yet.

- **Belongs in the diff engine** (Repertoire pillar), not just notes:
  pedal timing/duration should be compared against the reference too
  when the reference has explicit pedal markings. Most naive MIDI-diff
  tools ignore CC64 entirely and miss a real part of technique (legato
  pedaling vs. rhythmic pedaling).
- **On/off vs. continuous (half-pedaling)**: unconfirmed whether this
  specific controller reports CC64 as continuous 0-127 or just binary —
  verify against real hardware, don't assume either way.
- **Never repurpose the pedal as a hands-free control input** — keep it
  purely musical. Mixing it with the anchor+command layer would fire
  false commands every time the user pedals normally while playing.
- **Future: a separate 3-pedal MIDI unit** (e.g. Roland RPU-3, or any
  generic MIDI foot controller) connected via its own USB-MIDI port,
  independent from the Keystation. Implication:
  `midi_io.MidiSession` already merges multiple simultaneous MIDI input
  ports via `mido.ports.MultiPort` — this was built in from the start,
  no rewrite needed when that hardware arrives.

## User and progress

SQLite. Progress tracked **per pillar separately**, never a single number
(anti-pattern of "vanity metrics" — high retention on Duolingo/Yousician
doesn't imply real mastery). Ad-hoc user goals coexist with the
structured ABRSM-grade path.

## License

MIT for pianomatic's own code. External dependencies keep their own
licenses (LGPL/BSD/AGPL depending on the component, see above) — invoked
as libraries/subprocess, never vendored-and-modified.
