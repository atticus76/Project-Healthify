---
name: implement
description: Implement one task of an approved Healthify feature spec test-first (stages 4–5 of the spec-driven workflow), writing failing tests from the acceptance scenarios, then code until they pass, keeping the spec in sync.
argument-hint: "<spec ID or path> [task number]"
disable-model-invocation: true
---

# /implement: stages 4–5, test first, then implement

## 1. Load and gate
- Resolve the spec in `code/specs/features/` from `$ARGUMENTS`. Read it in full, along with the relevant parts of the constitution (`code/specs/tech-stack.md` especially).
- **Gate:** the spec's status must be **Approved** or later. If it's Draft or In review, stop and ask. Continue only on an explicit override, and if you do, add "implemented before approval" to the status line.
- **Gate:** the spec must have a `## Tasks` section. If it doesn't, suggest `/plan-tasks` first.
- Pick the task: the number given, or else the first task that isn't done. State which task and which scenarios you're doing.

## 2. Test first (stage 4)
- Turn each acceptance scenario that the task covers into tests under `code/backend/tests/` (backend logic) or `code/frontend/tests/` (Reflex state). Name tests after the behaviour, and add a docstring or comment that quotes the scenario name.
- Follow the existing test conventions in `conftest.py`. Database tests use `TEST_DATABASE_URL` and are skipped without it.
- Run `pytest <the new test files>` from the repo root with `.venv` active, and **confirm the tests fail for the right reason** (missing behaviour, not an import error or a typo). Show the failure summary.

## 3. Implement (stage 5)
- Write the smallest change that makes the tests pass while following the spec's Design and the tech stack: plain SQL through `backend.db.connect()`, schema changes in `code/backend/db/schema.sql` that are safe to re-run, and no new libraries unless the spec decided them.
- Then run the **full** suite with `pytest` and report the results honestly. If some failures were already there before your change, say so.

## 4. Keep the spec true
- If the code had to differ from the spec, edit the spec in the same change and say why, tagging the decision "(decided YYYY-MM-DD)".
- Mark the task ✅ in the spec's Tasks list, with a short note on anything a reviewer should know, in the style of `S2-04-cloud-data-storage.md`.
- If a new dependency or env var was added, update `code/requirements.txt`, `.env.example`, and `tech-stack.md`.

## 5. Hand off
Report what changed, the test results, and the next task. Don't commit or push unless the user asks. When every task is done, suggest `/verify <ID>`.
