# Spike: Hermes Agent as prana's substrate — results

*Run 2026-05-09. Goal: validate the seven risks named in the project
decomposition plan before adopting Hermes Agent as prana's runtime.*

## Decision: **adopt Hermes for prana, light heart**

Every blocking risk resolved. Three minor open items, none of which threaten
the adoption decision. Move to Step 2 (extract deha) and Step 3 (configure
Hermes as prana) per the plan.

---

## Verification scoreboard

| # | Risk | Status | Evidence |
|---|---|---|---|
| 1 | claude -p Max OAuth bills against subscription | ✅ | `claude auth status --text` returns "Login method: Claude Max account". `cost_usd` is informational across all users — Anthropic docs explicitly state subscribers' usage is included in subscription, cost figure isn't billing-relevant. The "0.00 = Max" heuristic in svapna's existing `delegate.py` is **stale and must be removed during prana extraction**. Source: code.claude.com/docs/en/costs |
| 2 | Smriti bridges as a Hermes skill | ✅ | Cleaner than a skill — Hermes has first-class MCP client. Configure smriti as an MCP server in `~/.hermes/config.yaml`, tools auto-discover and prefix `mcp_smriti_*`. Bridge is *config*, not code. Source: `skills/mcp/native-mcp/SKILL.md` |
| 3 | viveka/executor split fits primary+auxiliary | ✅ | `ProviderProfile.default_aux_model` exists explicitly for "cheap model for auxiliary tasks." `agent/auxiliary_client.py` consumes it. We wire primary=Claude (executor), auxiliary=Qwen+LoRA (viveka). Three implementation shapes available; shape choice is detail. Source: `providers/base.py`, `providers/README.md` |
| 4 | Cron overlap protection | ✅ | `cron/scheduler.py` uses cross-platform file lock (`fcntl` on Unix, `msvcrt` on Windows) at `~/.hermes/cron/.tick.lock`. Only one tick at a time. Per-job model and toolset config supported. Source: `cron/scheduler.py` |
| 5 | Cross-process state visibility | ✅ | `~/.hermes/state.db` is SQLite WAL with SCHEMA_VERSION 11. `sessions` table tagged by `source` ('cli','telegram','cron',...) with `started_at`, `ended_at`, cost tracking, parent_session_id chains. External processes (deha) can read directly: `SELECT * FROM sessions WHERE source='cron' AND ended_at IS NULL` gives active heartbeat cycles. Source: `hermes_state.py` |
| 6 | Outbound delivery as a queue | ✅ | `gateway/delivery.py` `DeliveryRouter` parses targets like `origin`, `local`, `telegram:123456`. Multi-target. Email is a first-class platform — **CHECK_IN's custom SMTP code retires.** Source: `gateway/delivery.py` |
| 7 | SOUL.md indirection | ✅ (with caveat) | Single global `~/.hermes/SOUL.md`, replaces built-in identity slot #1. Doesn't support file inclusion. **But this is the right shape:** SOUL.md is for *voice/tone/style*, not knowledge. Derive a focused SOUL.md from `~/.narada/identity.md` (Lila, Mahakali, aesthetic, refusals). The richer files (mind, beliefs, values) load via smriti's MCP tools, not as system prompt. Source: `website/docs/guides/use-soul-with-hermes.md` |

## Bonus findings (significant)

- **Email is a first-class delivery platform** — the heartbeat's CHECK_IN
  SMTP code can retire. Hermes routes via `--deliver email`.
- **Native Windows is "early beta"** but the cron module explicitly handles
  Windows file locking via `msvcrt` — core paths are tested. WSL2 is the
  battle-tested fallback if native Windows hits rough edges.
- **Modal / Daytona / Vercel Sandbox** as serverless terminal backends —
  interesting for cost optimization later (idle-near-free), not now.
- **`hermes config set ANTHROPIC_API_KEY ""`** is the documented pattern for
  forcing OAuth/Max billing. Hermes is OAuth-aware by design.
- **`autonomous-ai-agents/hermes-agent` skill** exists for spawning a
  Hermes-as-subagent — interesting for parallel work later.
- **Anthropic compliance: subscription OAuth in third-party apps was banned
  Feb 2026.** The only sanctioned path is direct `claude` CLI subprocess —
  exactly what Hermes's `claude-code` skill does. Compliance-correct.

## Open items (none blocking)

- **Whether `DeliveryRouter` is exposed for ad-hoc skill-driven send** (not
  cron-driven) — answer during integration; if not, custom skill wrapping
  it is trivial.
- **Cron overlap behavior for a single long-running job** (the lock prevents
  concurrent ticks; what about same job firing while previous instance is
  still running) — read `cron/jobs.py` during integration.
- **SOUL.md materialization on Windows native** — symlink works on Unix;
  Windows native may need a setup script that copies content. Path of least
  resistance.

## Required follow-up actions during extraction

1. **Remove the stale "0.00 = Max" comment** from `src/svapna/heartbeat/delegate.py`
   (lines ~22-32) when prana extraction happens. Replace with: "Billing mode
   is determined by `claude auth status`. `cost_usd` is informational — see
   code.claude.com/docs/en/costs."
2. **Retire the CHECK_IN custom SMTP code** in favor of Hermes's email
   delivery platform. The smtplib import in delegate.py and the
   `_send_check_in_email` function go away.
3. **Wire smriti as MCP server** in `~/.hermes/config.yaml` rather than
   building a custom skill.
4. **Set up SOUL.md materialization** — derive from `~/.narada/identity.md`
   voice/tone sections at install time.

## Updated plan-document touchpoints

The decomposition plan already accounts for adopting Hermes light-heart,
but these specific updates land cleanly on top of the spike:

- Step 3 (extract prana): smriti integration is *config*, not a skill.
  Skill list reduces.
- Step 5 (additions): CHECK_IN SMTP code retirement explicit.
- State layer scope: confirmed correct — Hermes covers session/cycle state,
  state.db scope stays narrow (ESP32 state, body events, utterance queue).

## Recommendation

**Go.** Begin Step 2 (extract deha) on Suti's signal. Hermes adoption is
viable; light heart is the right shape; the integration path has no
surprises remaining.
