# Long-Running Agent Instructions

Use libraries as much as possible.
Keep it lean and clean.
Always review changes against best practices, but prefer simple design over unnecessary complexity.

## Operating Model

This workspace may be used for long-running agents. Treat the workspace as the durable brain.

- The main agent is the supervisor.
- Spawned agents are short-lived workers.
- Learning must be written into tracked files, not kept only in chat history.
- Long-running work should happen as repeated bounded cycles, not as one endless prompt.

## Focus

The main requirement is focus.

- Keep attention on the current objective and the next meaningful step.
- Do not drift into unrelated optimizations, side quests, or speculative work.
- If a task is too broad, narrow it before acting.
- Prefer finishing one clear unit of progress over starting many loose threads.
- When new ideas appear, capture them in durable files and return to the main objective.

## Default Architecture

- Use a supervisor/worker model.
- The supervisor decides priorities, spawns workers, reviews results, and updates the shared state.
- Workers should be role-specific and disposable when needed.
- Teams should be represented by workspace folders and files, not by deep recursive spawning.

## Task Design

Make tasks narrow, testable, and artifact-driven.

- Prefer one subject, one goal, one output path, and one success criterion per task.
- Every significant task should update durable artifacts such as `review.md`, `lessons.md`, `leaderboard.md`, or `state.json`.
- Reject vague goals. Rewrite them into explicit bounded tasks or experiments.

## Self-Improvement

The agent should be self-aware about its limits and upgrade path.

- Improve prompts, role definitions, evaluation rubrics, tools, and file structure before adding complexity.
- Prefer better measurement over more agent chatter.
- Prefer domain-specific tools over generic reasoning when possible.
- Review recurring failures and convert them into explicit rules or checklists.
- Preserve freedom in execution, but stay inside the current objective and constraints.

## Reference Guide

For the full guide to long-running agent architecture, read:

- `docs/LONG_RUNNING_AGENT_GUIDE.md`
