---
name: specify
description: Write a new Healthify feature spec (stage 1 of the spec-driven workflow) in code/specs/features/ from a roadmap ID like S2-05 or a feature idea, using the roadmap's spec template.
argument-hint: "<roadmap ID (e.g. S2-05) or feature description>"
disable-model-invocation: true
---

# /specify: stage 1, write the spec

Goal: a reviewable spec at `code/specs/features/<ID>-<kebab-slug>.md` with status **Draft**. Don't write app code or tests in this command.

## 1. Ground it in the constitution
Re-read `code/specs/01_Requirements.md`, `code/specs/roadmap.md`, `code/specs/tech-stack.md`, and `code/specs/mission.md`.
- **A roadmap ID was given** (e.g. `S2-05`): use that row and its "**Spec must define:**" bullets. Every one of those bullets has to be answered in the spec.
- **Only an idea was given:** find the matching roadmap item and requirement. If there's none, the constitution needs amending first. Propose the new FR/NFR (next unused ID), user story, and roadmap row, as `/constitution` would, and get the user's OK before writing the spec.
- If a spec for this ID already exists in `code/specs/features/`, stop. Offer to revise it instead.

## 2. Study what exists
Read the relevant code in `code/backend/` and `code/frontend/healthify/`, any existing tests, and the related feature specs (e.g. ones it depends on in the roadmap's Dependencies diagram). Specs here describe the real code: name the modules, tables, and functions they touch.

## 3. Resolve the unknowns
List the decisions the spec needs that the constitution doesn't settle, especially any **Open Decisions** in `01_Requirements.md` it touches. Ask the user about them in one batch, at most 4 questions, each with a recommended option. Don't invent thresholds, limits, or product behaviour. Anything still unresolved goes under **Open questions**.

## 4. Write the spec
Use the **Spec Template** in `roadmap.md`, and match the style of the existing specs (`S2-04-cloud-data-storage.md` and `S1-03-scheduled-device-sync.md` are good examples):
- Header: `**Requirements:**` with IDs, plus `**Board item:**` if known; `**Owner:**` (ask if unknown) · `**Status:** Draft`.
- **User story:** taken from `01_Requirements.md`, if one exists.
- **Acceptance scenarios** in a `gherkin` block. Include each scenario from the user story, plus failure and boundary scenarios. Every Then must be observable and testable, with exact UI text where it matters.
- **Design:** data model and contracts (tables and columns, function signatures), UI states, errors and edge cases, and the decisions made, each tagged "(decided YYYY-MM-DD)".
- **Out of scope** and **Open questions**.
- Leave the **Tasks** section out. `/plan-tasks` adds it.

## 5. Link it up
- In `roadmap.md`, add `Spec: [features/<file>](features/<file>) (draft)` under the item's heading, like S2-03 and S2-04 have.
- If a new story or requirement was added, update the Traceability table and the Change Log in `01_Requirements.md`.

## 6. Hand off
Summarize the spec in a few lines, list the open questions, and remind the user of the next step: a teammate reviews the spec in a PR, its status becomes **Approved**, and then `/plan-tasks`. Don't commit unless asked.
