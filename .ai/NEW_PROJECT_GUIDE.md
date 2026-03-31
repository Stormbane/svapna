# Starting a New Project with This Agent Structure

Copy the entire `.ai/` folder and `CLAUDE.md` to your new project root, then follow the steps below.

## Files to rewrite (project-specific content)

### 1. `CLAUDE.md`
- Change the project name and description in `## Project`
- Fill in `## Commands` once you have a tech stack

### 2. `.ai/soul.md`
Rewrite completely. This is your project's personality.
- **Identity**: What is this project? One paragraph.
- **Values**: 3-5 design principles specific to this project.
- **Tone**: How should the agents communicate?
- **Engineering Philosophy**: Can often stay similar across projects. Edit to taste.

### 3. `.ai/knowledge/spec.md`
Rewrite completely. Your project's vision, features, and milestones.

### 4. `.ai/knowledge/architecture.md`
Rewrite completely. Your project's tech stack, data flow, API design. This is project-specific — the agent system docs live separately in `.ai/agent-system.md`.

### 5. `.ai/knowledge/glossary.md`
Rewrite completely. Domain-specific terms for your project.

### 6. `.ai/todo.md`
Rewrite completely. Your project's roadmap and current tasks.

### 7. `.ai/models.yml`
- Update `default.model` and `default.provider` if using a different model
- Update task-specific overrides under `tasks:` to match your project's LLM tasks (or remove them if you have none yet)

## Files to edit lightly (change project name only)

### 8. `.ai/agents/coder.md`
- Line 32: Change project name
- Everything else (role, SOP, constraints) is generic and reusable

### 9. `.ai/agents/tester.md`
- Line 32: Change project name
- Everything else is generic and reusable

## Files to leave as-is (fully reusable)

- `.ai/agent-system.md` — agent architecture docs, project-agnostic
- `.ai/knowledge/conventions.md` — empty template, fills in as you code
- `.ai/blackboard/findings.md` — empty template
- `.ai/blackboard/handoffs.md` — empty template
- `.ai/blackboard/task-queue.md` — empty template
- `.ai/blackboard/decisions.md` — empty template
- `.ai/memory/coder/working.md` — empty template
- `.ai/memory/coder/notes.md` — empty template
- `.ai/memory/tester/working.md` — empty template
- `.ai/memory/tester/notes.md` — empty template
- `.ai/logs/errors.md` — empty template

## Files to clear out (start empty)

- `.ai/prompts/*` — prompts are project-specific. Keep the directory, delete contents.
- `.ai/logs/sessions/*` — start empty.

## Quick start checklist

```
[ ] Copy .ai/ and CLAUDE.md to new project
[ ] Rewrite: CLAUDE.md project description
[ ] Rewrite: soul.md, spec.md, architecture.md, glossary.md, todo.md
[ ] Edit: models.yml (provider/model if different, remove project-specific tasks)
[ ] Edit: coder.md and tester.md (project name only)
[ ] Clear: prompts/* and logs/sessions/*
[ ] Verify: run a test session to confirm agents load correctly
```
