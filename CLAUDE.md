# Healthify: working rules for Claude

This project uses **spec-driven development**. Every feature gets a written spec before any code, and the spec stays the source of truth for the implementation, tests, and review.

## The constitution

The constitution is the four files directly under `code/specs/`. They are loaded below and apply to every task:

- Mission (why we build it, for whom): @code/specs/mission.md
- Requirements (what we build; FR/NFR IDs, user stories, open decisions): @code/specs/01_Requirements.md
- Tech stack (how we build it): @code/specs/tech-stack.md
- Roadmap (the order of work, the workflow, the spec template, the definition of done): @code/specs/roadmap.md

The specs in `code/specs/features/` are **not** part of the constitution. Each one is a single feature's spec. It must agree with the constitution, and you read it only when working on that feature.

When the documents disagree, the constitution wins over a feature spec, and `01_Requirements.md` wins over everything else for *what* the app does. Don't resolve a conflict silently. Point it out and propose an edit to the constitution, or to the spec, in the same change.

### Amending the constitution
- Follow the "Rules for editing this file" in `01_Requirements.md`: IDs never change, retired items are marked **[Retired]** and never deleted, new IDs take the next unused number, and every requirement must be testable.
- Add a row to the requirements Change Log for any change to a requirement or story, with today's date and the reason.
- Record new technology decisions in `tech-stack.md` before code depends on them. Don't add a library, service, or ORM the tech stack doesn't list unless a spec decides it and updates `tech-stack.md`.
- Constitution changes go through a PR, like everything else.

## Workflow

Follow the stages in `roadmap.md` → Workflow. Each stage has a slash command:

| Stage | Command | Output |
|---|---|---|
| Read or amend the constitution | `/constitution [change]` | Summary of the rules that apply, or a proposed edit |
| 1. Specify | `/specify <roadmap ID or idea>` | `code/specs/features/<ID>-<slug>.md`, status **Draft** |
| 2. Review | (a teammate reviews the PR) | Spec status → **Approved** |
| 3. Plan | `/plan-tasks <spec>` | Design decisions and a numbered **Tasks** list in the spec |
| 4–5. Test first, implement | `/implement <spec> [task #]` | Failing tests from the scenarios, then code that passes them |
| 6. Verify | `/verify <spec>` | Definition-of-done check, roadmap and traceability updated |

### Hard rules
1. **No code without a spec.** Before you change app code for a feature, find its spec in `code/specs/features/`. If there isn't one, stop and offer `/specify`. Bug fixes and refactors that don't change behaviour don't need a new spec. If one does change behaviour, update the spec it touches.
2. **Nothing gets implemented from an unapproved spec.** If the spec's status is Draft or In review, say so and ask before going further. Proceed only if the user explicitly overrides, and if they do, note it in the spec's status line, as S1-03 does ("written alongside the code, not approved before it").
3. **Tests come from the acceptance scenarios.** Write one or more tests per Gherkin scenario under `code/backend/tests/` or `code/frontend/tests/`, run them, and watch them fail before implementing.
4. **The spec moves with the code.** If the implementation has to differ from the spec, update the spec in the same change and say why. Record decisions with their date ("decided YYYY-MM-DD").
5. **Trace everything.** Every spec names its FR/NFR IDs. Every new user story appears in the Traceability table in `01_Requirements.md`.

## Project facts

- Python 3.12 and Reflex 0.9.12. The app runs from `code/frontend` (`reflex run`). Dependencies go in `code/requirements.txt`.
- Run the tests from the repo root with `pytest` and the `.venv` active. Database tests use `TEST_DATABASE_URL`, which must never equal `DATABASE_URL`.
- Use PostgreSQL on Supabase through `backend.db.connect()` with plain SQL (`%s` placeholders). There's no ORM and no Supabase SDK. The schema lives in `code/backend/db/schema.sql`.
- Healthify is not a medical device. Any feature that shows health readings or alerts carries the FR-03 disclaimer.
