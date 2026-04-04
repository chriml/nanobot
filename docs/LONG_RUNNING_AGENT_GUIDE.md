# Long-Running Agent Guide

This guide explains how to structure a long-running nanobot so it can pursue an open-ended objective while remaining disciplined, inspectable, and improvable.

## Core Mental Model

Do not think of a long-running agent as one immortal thread that keeps thinking forever.

Instead:

- The workspace is the durable brain.
- The main nanobot is the supervisor.
- Spawned agents are short-lived workers.
- Learning is what gets written down in durable artifacts.
- Progress happens through repeated bounded cycles.

This keeps the system inspectable and prevents the agent from drifting into vague, untestable work.

## Primary Principle

The most important quality is focus.

- Keep the main objective stable.
- Keep the current task narrow.
- Keep progress visible in durable artifacts.
- Capture distractions instead of following them immediately.
- Reduce scope when the system becomes noisy or confused.

## What The User Should Define

The user should define the non-negotiables.

- The objective.
- The risk boundaries.
- The allowed tools and environments.
- The promotion rules for experiments.
- What counts as success or failure.

The agent can create the scaffold and operate it, but the principal constraints should come from the user.

Practical rule:

- The user defines the constitution.
- The agent builds and runs the operating system under that constitution.

## What The Agent Should Define

The agent should define the execution details.

- Folder structure.
- Role prompts.
- Experiment templates.
- Evaluation rubrics.
- Review cadence.
- Scoreboards and state files.
- Improvement backlog.

The agent should be encouraged to refine these over time as long as it stays within the user-defined constraints.

The framework should remain generic. The agent should have freedom in how it structures execution, as long as it stays focused on the objective and works in a bounded, inspectable way.

## Recommended Architecture

Use a supervisor/worker model.

- `supervisor`: chooses priorities, allocates work, compares results, updates state.
- Additional worker roles should be created only when they improve clarity and execution.
- Worker roles are a tool, not a requirement. Use only the roles that materially help the objective.

Important runtime constraint:

- The top-level agent should own orchestration.
- Spawned agents should be treated as workers, not as free-form managers of more workers.

## Recommended Workspace Layout

```text
workspace/
  AGENTS.md
  HEARTBEAT.md
  memory/
    MEMORY.md
    HISTORY.md
    LEARNINGS.md
  harness/
    definition.yaml
    roles/
      supervisor.md
      worker_a.md
      worker_b.md
  plans/
  work/
  reviews/
  scoreboard/
```

This is only a pattern. The exact layout should be adapted to the objective.

## Long-Running Loop

The correct loop is:

1. Read current workspace state.
2. Choose one bounded next task.
3. Spawn the right workers.
4. Collect outputs.
5. Review against explicit criteria.
6. Update durable files.
7. Decide: reject, revise, test further, or promote.
8. Schedule the next cycle.

This is what "long-running" should mean in practice.

## Task Design Rules

Every task should be bounded.

Good task shape:

- One subject.
- One scope.
- One expected artifact.
- One decision at the end.

Examples:

- "Evaluate idea X under condition Y and write the result to file Z."
- "Review the latest iteration of project X and recommend `reject`, `revise`, or `promote`."

Bad task shape:

- "Solve the whole problem."

If a task is vague, rewrite it into an experiment before acting.

## Self-Awareness And Improvement

A long-running agent should be explicitly self-aware about how it improves itself.

It should continuously ask:

- Are the role prompts good enough?
- Are the tasks too broad?
- Are the evaluation criteria weak?
- Are there recurring failure modes?
- Is the file structure missing important state?
- Are there missing tools that would outperform generic reasoning?
- Am I over-trusting backtests, summaries, or recent performance?

The preferred order of self-improvement is:

1. Clarify goals and constraints.
2. Improve task design.
3. Improve evaluation rubrics.
4. Improve durable artifacts and scoreboards.
5. Add domain-specific tools.
6. Only then add more agents or complexity.

## Improvement Backlog Categories

The agent should maintain an explicit backlog for improving itself.

- Prompt quality.
- Role definitions.
- Review checklists.
- Metrics and scoreboards.
- Data pipelines.
- Testing and backtesting harnesses.
- Paper-trading instrumentation.
- Risk controls.
- Automation cadence.

Each improvement should be written down, prioritized, and either accepted, deferred, or rejected.

## Risk And Promotion Gates

Open-ended objectives are dangerous unless promotion gates are explicit.

Use stages like:

- `idea`
- `prototype`
- `backtested`
- `paper_trade`
- `candidate`
- `live`
- `retired`

Promotion should require evidence, not enthusiasm.

Minimum expectations before promotion:

- Clear thesis.
- Reproducible implementation.
- Review of weaknesses.
- Measured results.
- Risk review.
- Written decision.

## Domain-Specific Advice

For any domain, do not let the agent optimize directly for a vague end state without intermediate gates.

Use layered objectives:

- obey constraints
- improve evidence quality
- improve process quality
- improve outcomes

Do not rely on one kind of evidence alone. Require review, comparison, and explicit promotion criteria.

## When To Change Core nanobot

Do not start by changing the framework.

Start with workspace structure and disciplined prompts.

Only consider core changes when there is repeated evidence that the workspace-level design is insufficient. The highest-value core changes usually are:

- better structured control over spawned agents
- a first-class experiment queue
- stronger domain tools
- clearer status and inspection views

## Practical Rule Of Thumb

Use the following split:

- The user defines the objective and hard boundaries.
- The workspace stores memory, rules, scoreboards, and plans.
- The supervisor agent runs the loop.
- Workers do bounded tasks.
- Reviews and lessons make the system smarter over time.

If the system becomes confusing, reduce scope and make the next task smaller.
