---
name: verify
description: Check a Healthify feature against its spec and the roadmap's definition of done (stage 6 of the spec-driven workflow), then update the spec status, the roadmap checkboxes, and requirement traceability.
argument-hint: "<spec ID or path>"
disable-model-invocation: true
---

# /verify: stage 6, check against the definition of done

## 1. Load
Resolve the spec in `code/specs/features/` from `$ARGUMENTS`, and re-read `code/specs/roadmap.md` (Workflow and definition of done) and `code/specs/01_Requirements.md`.

## 2. Scenario coverage
For each Gherkin scenario in the spec, find the test or tests that check it. Search `code/backend/tests/` and `code/frontend/tests/`. Report a table: **Scenario | Test(s) | Covered?**. Any scenario with no test is a gap. Offer to write it, but don't mark the feature done while it's open.

## 3. Run the tests
Run `pytest` from the repo root with `.venv` active. Report pass, fail, and skip counts. If database tests were skipped because `TEST_DATABASE_URL` isn't set, say clearly that coverage wasn't verified.

## 4. Spec vs. code
Spot-check that the Design matches the code: the tables and columns in `schema.sql`, the function names, the UI text quoted in the scenarios, and the error messages. List any drift, and propose whether to fix the code or the spec.

## 5. Definition of done
Check each item from `roadmap.md`, marking it ✅, ❌, or "needs a human":
- spec merged
- tests written from the spec and passing
- code reviewed and merged to `main` (check `git log main` for it)
- acceptance scenarios demoed (needs a human; give a short demo script, one step per scenario)
- requirement traceability updated

## 6. Update the records
Do this only for the items that pass, and show the edits:
- the spec's status line: **Implemented (YYYY-MM-DD)**, plus any exceptions
- `roadmap.md`: tick the item's **Spec** and **Tests** checkboxes, and update its status and the spec link note
- `01_Requirements.md`: the Traceability table, and tick off any Open Decision this feature settled

Don't commit unless asked.
