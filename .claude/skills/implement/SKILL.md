---
name: implement
description: Implement one approved phase from a PRD and plan with TDD, run the feedback loops, and commit it.
argument-hint: "@prd/<feature>.md @plans/<feature>.md implement phase <N>"
disable-model-invocation: true
---

# Implement

Implement exactly one phase of a plan, then stop.

## 1. Understand the phase

- Read the referenced PRD and plan. If the request does not name a phase, ask
  which one and wait.
- Check that every earlier phase is already committed (`git log`). If one is
  missing, stop and say so.
- Explore the code the phase touches and follow its existing patterns and the
  conventions in `CLAUDE.md`.
- Work on the current feature branch. Do not create a branch per phase.

## 2. Build it test-first

- Write the phase's tests first and run them to watch them fail for the right
  reason.
- Write the smallest code that makes them pass, then refactor while green.
- Build only what this phase lists. Never start the next phase.
- If the plan turns out to be wrong or incomplete, stop and ask before
  deviating from it or editing it.

## 3. Run the feedback loops

Run all of these and fix every failure before moving on:

- `uv run pytest` (the whole suite, not just the new tests)
- `uv run ruff check .`
- `uv run ruff format .`
- `uv run python manage.py makemigrations --check --dry-run` (no missing migrations)
- `uv run python manage.py tailwind build`, if templates or CSS changed

If a failure is still unresolved after three focused attempts, stop and report
what is failing and what was tried.

## 4. Hand off manual verification

Do not tick the plan's `Manual:` checks yourself. List them for the user,
along with the commands needed to see the phase (for example `migrate`,
`seed`, `tailwind runserver`) and which demo login to use.

## 5. Commit the phase

- Stage only the files this phase changed. Never stage `db.sqlite3`,
  `media/`, or backup files.
- Commit with the subject `<Feature> phase <N>: <phase title>` and a short
  body describing what a user can now do.
- Commit only: do not push and do not open a PR.
- Do not write to `PROMPTS.md`; session logs are added only when the user asks.

## 6. Report

Summarize what was built, the test count, the commit hash, the manual checks
waiting on the user, and anything that deviated from the plan. Then stop.
