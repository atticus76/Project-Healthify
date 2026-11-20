---
name: plan-tasks
description: Break an approved Healthify feature spec into an ordered, test-first task list (stage 3 of the spec-driven workflow) and draft the GitHub issues for it.
argument-hint: "<spec ID or path, e.g. S2-05>"
disable-model-invocation: true
---

# /plan-tasks: stage 3, break the spec into tasks

## 1. Load
Resolve `$ARGUMENTS` to a file in `code/specs/features/`. Read it, and re-read the constitution (`code/specs/01_Requirements.md`, `tech-stack.md`, `roadmap.md`).

**Gate:** check the status line. If it isn't **Approved** (or later), tell the user that the roadmap says nothing gets implemented from an unmerged spec, and ask whether to plan anyway. Planning a draft is fine for discussion, but make that clear in your reply.

## 2. Check the design is complete
- Every "**Spec must define:**" bullet for this item in `roadmap.md` is answered.
- Every acceptance scenario can be traced to the code that will satisfy it.
- The design names the real modules, tables, and functions involved. Read the code to confirm they exist and to find what will need to change.
- Fill gaps in the **Design** section, and ask the user (in one batch, with recommendations) about anything that's a product decision rather than an implementation detail. Tag new decisions "(decided YYYY-MM-DD)".

## 3. Write the tasks
Add or replace a `## Tasks` section in the spec, using the numbered style of `S2-04-cloud-data-storage.md`:
- Each task is small enough for one PR and has a clear done check.
- Each task says which acceptance scenario(s) it covers and which tests it writes **first**. For example: "Write `test_<x>.py` cases for scenarios 1–2 against `healthify-test`, see them fail, then implement."
- Order them by dependency. Schema and backend come before the UI, and anything other tasks rely on (e.g. the `users` table) comes first.
- End with a task for docs: `tech-stack.md`, the README setup steps, and the spec status.

## 4. Draft the issues
The roadmap's stage 3 says each task becomes a GitHub issue using `.github/ISSUE_TEMPLATE/user-story.md`, linked back to the spec. Show the issue titles and bodies in the reply. Create them only if the user asks and `gh` is available. Otherwise they can paste them in.

## 5. Hand off
Summarize the task list, and point to `/implement <ID> 1` to start.
