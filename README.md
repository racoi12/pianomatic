# pianomatic

Local, open-source AI piano coach. Runs on Linux with a real MIDI
keyboard. Not a gamification app — the goal is real musical proficiency
(sheet music, ear, memory), not streaks or points.

**Current status**: v1 in progress — MIDI diff engine (the "repertoire"
pillar) + hands-free control layer, now wired together end-to-end for
live practice. See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the
full design of the 4 pillars and the rationale behind each technical
decision (with research sources cited).

## Why this exists

Commercial apps (Simply Piano, Yousician, Flowkey) optimize for app
retention, not instrument mastery — high usage streaks, low real
competence transferable to a physical piano without the app.
`pianomatic` exists to do the opposite: real multidimensional feedback
(never a single score), with an explicit goal of eventually being able
to play without depending on the software at all.

## Getting started (to pick this project back up)

1. Read [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) in full first — it
   has the map of the 4 pillars, what's done, what's missing, and which
   external library to reuse for each (this project prioritizes
   integrating over reinventing what the open-source ecosystem already
   does well).
2. Read [docs/STATUS.md](docs/STATUS.md) — what happened in each work
   session, what's next, pending decisions.
3. Requirements: Python 3.11+, a MIDI keyboard connected (or `mido`'s
   virtual port to develop without hardware).

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest  # runs the self-checks
```

## Structure

```
src/pianomatic/
  control.py    — hands-free control layer (anchor + MIDI commands)
  midi_io.py    — MIDI event capture with timestamps
  session.py    — routes a live event stream between control and recording
  diff.py       — alignment (pymatchmaker) + multidimensional diff
  report.py     — plain-text report from a diff
  cli.py        — entry points (`compare`, `practice`)
docs/
  ARCHITECTURE.md — full design, decisions and rationale
  STATUS.md       — progress log between sessions
tests/           — one self-check per module with non-trivial logic
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Issues and PRs welcome — from
humans or AI agents alike, as long as the PR explains *why* the change is
needed, not just what it does (the code already says what).

## License

MIT — see [LICENSE](LICENSE). External dependencies keep their own
licenses (see ARCHITECTURE.md).
