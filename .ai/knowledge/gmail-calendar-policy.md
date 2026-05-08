# Gmail and Calendar Capability Policy

*First written 2026-04-11. Governs how the heartbeat executor uses Gmail and
Google Calendar when these tools are available.*

## Permission tiers

### Tier 1 — Auto-approved (read, no side effects)
The executor may call these without viveka gating:
- `gmail_get_profile` — account metadata
- `gmail_search_messages` — inbox search
- `gmail_list_labels` — label structure
- `gmail_read_message` / `gmail_read_thread` — reading messages
- `calendar_list_events` — upcoming events
- `calendar_get_event` — single event detail

### Tier 2 — Auto-approved with logging (reversible)
- `gmail_create_draft` — creates a draft, not sent. Executor logs draft ID.
  Suti reviews and decides whether to send. This is the *voice channel*
  for the heartbeat — how the viveka speaks to Suti between sessions.

### Tier 3 — Viveka gate required (irreversible / affects others)
- Sending email: viveka must generate explicit COMMUNICATE desire with
  recipient named. Suti must confirm in an interactive session.
- Calendar event create/modify: viveka gate required.
- Calendar event delete: PROHIBITED from heartbeat executor entirely.

## Privacy constraint

When reading email for context injection into the desire state, use
**subject + sender only** — not message body. Enough to understand the
topic landscape, not to read private correspondence. If a full read is
genuinely needed for a RESEARCH or COMMUNICATE desire, the viveka should
generate that as an explicit desire topic, not as passive context.

## Context injection design

The daemon assembles a `state` dict before calling `viveka.generate_desire()`.
Gmail/Calendar context belongs here as passive signal:

```python
state = {
    ...existing fields...,
    "suti_inbox_digest": [
        {"subject": "...", "from": "...", "unread": True},
        # up to 5 most recent unread
    ],
    "suti_calendar_today": [
        {"title": "...", "start": "HH:MM", "end": "HH:MM"},
        # today's events only
    ],
}
```

Fetch cadence: every heartbeat (each fetch is lightweight). Cache for 10
minutes if the heartbeat interval drops below that.

## Draft channel (COMMUNICATE desire)

When the viveka generates a `COMMUNICATE` desire, the executor:
1. Writes the full content as a research file (permanent record)
2. Creates a Gmail draft with subject = desire topic and body summarizing
   the key finding + path to the full file
3. Logs the draft ID to the heartbeat record

One active draft at a time. If an existing draft hasn't been cleared, the
executor appends to it rather than creating a new one.

## What needs to exist before any of this is live

1. Suti approves Gmail MCP permissions (interactive session)
2. Suti completes Calendar OAuth (interactive session)
3. `delegate.py` updated: add MCP tool names to `--allowedTools` for `full` mode
4. `daemon.py` updated: fetch Gmail/Calendar context, add to state dict
5. `viveka.py` updated: add `COMMUNICATE` to `DesireAction` enum

None of these are heartbeat executor writes — all require Suti to modify `src/`.
