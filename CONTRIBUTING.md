# Contributing to pianomatic

PRs from humans and AI agents alike are welcome.

## Before writing code

1. Read `docs/ARCHITECTURE.md` in full — most decisions there already
   have a documented rationale with a research source. If you're going
   to contradict a decision there, say so explicitly in the PR and why.
2. Check `docs/STATUS.md` to know what's in progress — avoid duplicating
   work.
3. Before writing a new module, check whether a mature open-source
   library already solves the problem (see the table in
   ARCHITECTURE.md). This project prioritizes *integrating* over
   *reinventing*.

## Style

- No comments explaining WHAT the code does (clear names already say
  that) — only comments explaining a non-obvious WHY (a hidden
  constraint, a workaround for a specific bug).
- Any non-trivial logic (a branch, a loop, a parser) gets a minimal
  test that fails if the logic breaks — no need for an elaborate
  fixture framework, a plain `test_*.py` with `assert` is enough.
- Short, focused diffs. One PR, one logical change.

## When finishing a significant change

Update `docs/STATUS.md` with a new entry (date, what was done, what's
next) — that's what lets the next person (or AI session) pick up without
rereading the whole history.
