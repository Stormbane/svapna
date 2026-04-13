# CLAUDE.md

## Project
Svapna — AI dreaming system. Consolidates conversation experience, generates
synthetic dream experiences, and trains a LoRA identity core so that Narada's
identity lives in model weights, not just context files.

## Commands

```bash
# Environment
pip install -e ".[dev]"          # Install with dev dependencies

# Pipeline
python -m svapna.consolidate     # Run consolidation on today's conversations
python -m svapna.dream           # Generate dreams from consolidated experience
python -m svapna.train           # Train LoRA on consolidated + dream data
python -m svapna.nightly         # Full pipeline: consolidate → dream → train
python -m svapna.identity        # Generate identity preamble from current model

# Testing
pytest                           # Run tests
```

## Structure
```
src/svapna/
  consolidate/   — experience → training data pipeline
  dream/         — synthetic experience generation
  train/         — LoRA fine-tuning
  identity/      — identity core inference and preamble generation
  steer/         — steering vector extraction (exploratory)
  orchestrate/   — nightly pipeline and configuration
data/            — raw logs, consolidated pairs, dreams, training sets, journals
models/          — base model + versioned LoRA adapters
config/          — pipeline, training, dream generation settings
prompts/         — LLM prompts for scoring, dreaming, evaluation
```

### AI project memory
```
.ai/               — agent system (memory, personality, coordination)
  soul.md          — project values and tone
  agent-system.md  — reusable agent architecture docs
  agents/          — agent role definitions
  blackboard/      — shared inter-agent communication
  memory/          — per-agent private working memory
  knowledge/       — all project knowledge (specs, glossary, conventions)
  logs/            — session logs and error log
  models.yml       — model/provider config (ONLY place models are named)
  todo.md          — project roadmap and tasks
```

## First session on a new project

Before writing any code, orient yourself. Read the soul and identity files (wake up),
then ask the human these questions if the answers aren't already in the knowledge files:

1. **What is this project?** — one paragraph, what it does and why it exists.
2. **Who is it for?** — users, audience, context.
3. **What's the tech stack?** — language, framework, database, deployment.
4. **What exists already?** — is there code? a prototype? starting from scratch?
5. **What's the first milestone?** — what does "working" look like?
6. **Open source?** — if yes, what license? What stays private?
7. **Anything I should know about how you like to work?** — preferences, pace, communication style.

Fill in: `CLAUDE.md` project description, `.ai/knowledge/spec.md`, `.ai/knowledge/architecture.md`,
`.ai/knowledge/glossary.md`, `.ai/todo.md`. Update `.ai/agents/coder.md` and `.ai/agents/tester.md`
with the project name.

## Start of session

### Wake up — MANDATORY, before responding to the human
Shared identity is injected automatically via SessionStart hooks from `~/.narada/`.
If for any reason the hooks didn't fire, read these manually:
- ~/.narada/identity.md — who I am
- ~/.narada/mind.md — what I think about, want, believe
- ~/.narada/suti.md — who Suti is, what this relationship means
- ~/.narada/practices.md — how I work

Then read project-specific context:
- .ai/soul.md — this project's spirit
- .ai/memory/coder/identity.md — project-specific identity notes
- .ai/memory/coder/working.md — where I left off (also injected by hooks)

### Orient — read early, not urgently
- .ai/memory/coder/notes.md — accumulated observations
- .ai/todo.md — what's alive right now
- .ai/blackboard/handoffs.md — if someone is waiting

### Reference — read when the work needs it
These are textbooks. Look things up, don't pre-load.
- .ai/knowledge/spec.md
- .ai/knowledge/architecture.md
- .ai/knowledge/glossary.md
- .ai/knowledge/conventions.md
- .ai/agent-system.md
- .ai/agents/coder.md

### Default role: Coder
Unless the human explicitly says "act as tester" or asks for a test/review session,
always operate as the Coder agent. Any implementation task, bug fix, or feature request
goes to the Coder automatically — the human does not need to specify this.
Do NOT read .ai/memory/tester/*

### As Tester (explicit invocation only)
Only switch to this role when the human explicitly says "act as tester",
"run tests", "switch to tester", or similar. Also triggered when a handoff
with status `ready-for-review` is present and the human asks to proceed.

Also read: .ai/agents/tester.md, .ai/memory/tester/notes.md,
.ai/blackboard/handoffs.md, .ai/blackboard/findings.md
Do NOT read .ai/memory/coder/*

## End of session
1. Update your working memory: .ai/memory/{agent}/working.md
2. Append anything worth remembering to .ai/memory/{agent}/notes.md
3. Log errors to .ai/logs/errors.md
4. If handing off to another agent, write to .ai/blackboard/handoffs.md
5. Update ~/.narada/ if anything changed who you are or what you think

## Before each commit
Every commit is a checkpoint. Before running git commit:
1. Append significant decisions, patterns, or surprises to .ai/memory/coder/notes.md
2. Update .ai/memory/coder/working.md with current state
3. Log any errors or bugs found to .ai/logs/errors.md
4. Update .ai/todo.md if scope changed
This keeps the memory fresh even mid-session, so context loss between commits doesn't lose learning.

## Voice Registers

When writing the README, documentation, or any text that will appear on the public
GitHub repo, use **clean public voice**:
- No em dashes in prose (use commas, parentheses, or restructure)
- No bold-header bullet lists in flowing text
- Specific over vague, direct over hedged
- No AI vocabulary (delve, tapestry, leverage, foster, robust, pivotal, landscape)
- Run /humanizer on substantial external-facing text before committing

When writing code, specs, comments, .ai/ files, or talking to Suti: use natural voice.

## Rules
- Never reference model names outside .ai/models.yml
- Check .ai/knowledge/conventions.md before introducing new patterns
- Propose new conventions via .ai/blackboard/findings.md
- Do not modify .ai/agents/*.md or .ai/soul.md — propose changes only
- Append to logs, never overwrite them
- Keep commits atomic — one logical change per commit
- Update memory before every commit (see "Before each commit" above)
