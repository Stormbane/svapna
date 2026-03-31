# Agent Memory & Multi-Agent System

## Overview

The project uses an LLM agent system built on markdown files for memory, personality, and multi-agent coordination. All agent system files live under `.ai/`. The system is platform-independent (model-swappable), supports adversarial coder/tester agents with separate working memory, and includes an introspection agent (v0.2+) that improves the system over time.

## Directory Structure

```
.ai/
├── soul.md                       # Project personality, values, tone
├── models.yml                    # Model config (provider, params) — only place models are named
├── agent-system.md               # This file — reusable agent architecture docs
│
├── agents/                       # Agent definitions (static identity)
│   ├── coder.md
│   ├── tester.md
│   ├── introspector.md           # v0.2+
│   └── orchestrator.md           # v0.2+
│
├── blackboard/                   # Shared memory (cross-agent communication)
│   ├── task-queue.md             # Current tasks and status
│   ├── decisions.md              # Architectural decisions log
│   ├── findings.md               # Agent findings, bug reports, proposals
│   └── handoffs.md               # Structured agent-to-agent context transfer
│
├── memory/                       # Per-agent private working memory
│   ├── coder/
│   │   ├── working.md            # Current session context (overwritten each session)
│   │   └── notes.md              # Persistent coder-private notes
│   ├── tester/
│   │   ├── working.md
│   │   └── notes.md
│   └── introspector/             # v0.2+
│       ├── working.md
│       └── notes.md
│
├── knowledge/                    # All project knowledge (shared, read-by-all)
│   ├── spec.md                   # Project vision, milestones, features
│   ├── architecture.md           # Tech stack, data flow, API design
│   ├── conventions.md            # Coding conventions, patterns in use
│   ├── glossary.md               # Domain terms
│   └── lessons-learned.md        # Distilled insights from past work (v0.2+)
│
├── logs/                         # Episodic memory
│   ├── sessions/                 # Per-session logs (append-only during session)
│   ├── errors.md                 # Error log (append-only)
│   └── archive/                  # Summarized old sessions (v0.2+)
│
├── prompts/                      # Reusable prompt templates (model-agnostic)
│
└── todo.md                       # High-level project todo
```

## Agent Definitions

Each agent file uses YAML frontmatter (machine-parseable) + markdown body (injected as system prompt).

### Format

```markdown
---
id: agent-id
name: Display Name
version: 1
triggers: [when-to-invoke]
memory:
  read: [glob/paths/*]
  write: [glob/paths/*]
tools: [available-tools]
---
# Role
# Goal
# Personality
# Standard Operating Procedure
# Constraints
```

### Agent Summary

| Agent | Role | Key Trait | Memory Access |
|-------|------|-----------|---------------|
| **Coder** | Implement features, fix bugs | Pragmatic, convention-following | Private: `memory/coder/*`. Shared: read `blackboard/*`, `knowledge/*`. Write `blackboard/findings.md`, `blackboard/handoffs.md` |
| **Tester** | Adversarial reviewer, test writer | Skeptical, assumes bugs exist | Private: `memory/tester/*`. Shared: same as coder. **Cannot read `memory/coder/*`** (preserves adversarial independence) |
| **Introspector** (v0.2+) | Reflect on outcomes, improve system | Evidence-based, conservative | Can **read all** memory (for analysis). Writes to `knowledge/*`, `logs/archive/*`. **Proposes** changes to `agents/*`, `soul.md`, `prompts/*` — human approves |
| **Orchestrator** (v0.2+) | Route tasks, manage workflow | Coordinator | Reads everything. Writes `blackboard/task-queue.md`, `blackboard/handoffs.md` |

### Adversarial Coder/Tester Relationship

- Tester cannot read coder's working memory or notes — prevents bias
- Coder cannot read tester's test strategy — prevents gaming
- Communication only via `blackboard/handoffs.md` (structured context) and `blackboard/findings.md` (bug reports)
- Tester does NOT fix bugs — hands back to coder with reproduction steps
- Coder does NOT write tests — that's the tester's job

## Information Sharing (Blackboard Pattern)

### Handoff Protocol

```
Human assigns task (Coder picks up automatically)
  → Coder implements feature/fix
  → Coder verifies build passes — do NOT hand off if build is broken
  → Coder writes handoffs.md (status: ready-for-review) + findings.md
  → Tester picks up handoff → runs tests (visual + functional)
  → FAIL: Tester writes issues to handoffs.md (status: needs-rework)
           → Coder reads findings, fixes, re-verifies build → loop back to Tester
  → PASS: Tester makes atomic git commit → writes handoffs.md (status: committed)
  → Post-commit: Introspector session wrap-up (v0.2+)
```

**Loop exit condition**: Tester sets status `committed` after a successful `git commit`.
**Build broken**: Coder does not write a handoff until build exits clean. Fix the build first.
**Auto-commit**: The Tester commits on PASS. The human does not need to do this.
**Default agent**: The Coder is always the default. Human assigns tasks naturally; no explicit agent invocation needed.

### Access Control Matrix

| Resource | Coder | Tester | Introspector | Orchestrator |
|----------|-------|--------|--------------|--------------|
| `blackboard/*` | R/W | R/W | R | R/W |
| `knowledge/*` | R | R | R/W | R |
| `memory/coder/*` | R/W | **--** | R | -- |
| `memory/tester/*` | **--** | R/W | R | -- |
| `agents/*.md` | -- | -- | propose | R |
| `soul.md` | R | R | propose | R |
| `logs/*` | append | append | R/W(archive) | R |
| `prompts/*` | R | R | propose | R |

v0.1 enforcement: honor system via system prompt instructions. v0.2+: orchestration middleware validates paths.

## Platform Independence

```
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│ Agent Defs   │  │ Prompt       │  │ models.yml   │
│ (behavior)   │  │ Templates    │  │ (provider +  │
│ agents/*.md  │  │ prompts/*.md │  │  model names)│
└──────┬───────┘  └──────┬───────┘  └──────┬───────┘
       └─────────────────┼─────────────────┘
                         v
              ┌─────────────────────┐
              │ Orchestration Layer │  ← loads defs, memory, config
              │ (script/code)       │  ← calls provider adapter
              └──────────┬──────────┘
                         v
              ┌─────────────────────┐
              │ Provider Adapters   │  ← Anthropic, OpenAI, Ollama, etc.
              │ interface:          │
              │   complete(system,  │
              │     user, config)   │
              └─────────────────────┘
```

**Rules:**
1. Agent definitions never reference model names — behavior only
2. Prompt templates are pure markdown with `{{variable}}` placeholders
3. `models.yml` is the **single** place model/provider config lives
4. Swapping providers = edit `models.yml` + ensure adapter exists

## Introspection Loop (v0.2+)

**Triggers**: session-end, task-complete, failure-detected, weekly scheduled

**What it reviews**: session logs, blackboard findings, handoff quality, prompt effectiveness, all agent memory

**What it can modify directly**: `knowledge/lessons-learned.md`, `knowledge/conventions.md`, `logs/archive/*`

**What requires human approval**: changes to `prompts/*`, `agents/*`, `soul.md` — writes proposal to `blackboard/findings.md` with evidence + proposed diff

**Safeguards against runaway self-modification**:
- Propose-don't-apply for sensitive files
- Must cite specific log evidence for every recommendation
- Cannot modify its own definition
- Change budget: max 3 proposals per session
- Version field in all agent/soul files for audit trail

**Log summarization**: When >5 sessions accumulate, introspector summarizes sessions older than 7 days into monthly archives, then removes originals.
