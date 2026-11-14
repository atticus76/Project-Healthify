---
name: constitution
description: Read, check against, or amend the Healthify constitution (mission.md, 01_Requirements.md, tech-stack.md, roadmap.md under code/specs/, not code/specs/features/). Use before starting feature work, when checking whether a spec or change fits the project's rules, or when a requirement, technology decision, or roadmap item needs to change.
argument-hint: "[nothing | a spec path to check | a change to make]"
---

# /constitution

The constitution is these four files and nothing else:

- `code/specs/mission.md`: why we build it, for whom, what success means
- `code/specs/01_Requirements.md`: FR/NFR requirements, user stories, traceability, open decisions, change log
- `code/specs/tech-stack.md`: the technologies and the data-storage decisions
- `code/specs/roadmap.md`: sprints, workflow, spec template, definition of done

The files in `code/specs/features/` are feature specs, not constitution.

Re-read all four files from disk first. Don't rely on the copies loaded at session start, because they may have changed. Then pick a mode from `$ARGUMENTS`:

## No arguments: summarize
Give a short briefing (at most about 25 lines) of the rules currently in force:
- Mission and target user, in one or two lines.
- The constraints a feature spec must respect: scope and out-of-scope items, the tech-stack rules (language, framework, database access, testing), and the "not a medical device" disclaimer.
- The workflow stages and the definition of done.
- Any **Open Decisions** in `01_Requirements.md` that are still unchecked, because specs that touch them have to settle them or work around them.
- Any inconsistencies you notice *between* the four files, such as an ID mismatch, a stale status, or a feature spec linked from the roadmap that doesn't exist.

## A path to a feature spec, or "check <thing>": compliance check
Check the spec or change against the constitution and report a table of **Rule | Status (✅/⚠️/❌) | Evidence**:
- It names its FR/NFR IDs, and those IDs exist and aren't **[Retired]**.
- The user story and scenarios match the story in `01_Requirements.md`, or the spec says why they differ.
- Every acceptance scenario is testable (it has an observable pass/fail Then).
- It stays inside the Scope and outside the Out-of-scope list.
- It uses only technologies in `tech-stack.md`, or it updates `tech-stack.md`.
- It follows the roadmap's spec template sections and has a status line.
- It has a roadmap row that links to it.
- It settles, or explicitly leaves open, any Open Decision it depends on.

Don't edit anything in this mode. Offer the fixes.

## Any other text: amend
Treat the arguments as a requested change to the constitution.
1. Decide which file or files it belongs in: *what* → `01_Requirements.md`, *how* → `tech-stack.md`, *when and in what order* → `roadmap.md`, *why* → `mission.md`.
2. Follow the "Rules for editing this file" in `01_Requirements.md`: IDs never change, retired items are marked **[Retired]**, new IDs take the next unused number, and every requirement must be testable. Add a Change Log row (today's date and the why) for any change to a requirement or story.
3. Check the knock-on effects: the Traceability table, roadmap rows, feature specs that reference changed IDs, and the README if setup changes.
4. Make the edits, then show a concise summary of what changed and where. Don't commit. Remind the user that constitution changes go through a PR.

If a requested change conflicts with the mission or the scope (for example, adding emergency detection, which is explicitly out of scope), say so and ask before you edit.
