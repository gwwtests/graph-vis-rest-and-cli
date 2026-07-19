---
title: agent-tasks/ — the dispatch desk for standing helper agents
captured_on: 2026-07-19
summary: Folder-per-task convention for handing filesystem-based briefs to standing helper agents (e.g. the fable helper) and receiving their outputs back — clear in/out split, date-sorted subfolders.
---

# `agent-tasks/` — the dispatch desk

This is the **desk** where the lead (`ubertmux-adm`) hands *folder-shaped tasks*
to a **standing helper agent** — most commonly the **fable helper**
(`ubertmux-nested:fable`, a `claude --model claude-fable-5 --effort high`
window) — and the agent hands **outputs** back. One directory per task, so a
brief + its inputs + its deliverables + its provenance all live together and
survive across sessions.

The mechanics (ensure the right agent is running in the window → `/clear` it →
verified-send the brief pointer) are automated by
**`skills/dispatch-task-to-fable-helper`** (L1) wrapping
**`scripts/dispatch_task_to_agent.sh`** (L0). This README is just the **data
contract** those tools read/write against.

Why folder-shaped (not a one-shot inline prompt): a helper agent discovers work
by *reading files*, not by holding a huge prompt in context. Inputs as files +
symlinks = cheap discovery; outputs as files = durable, reviewable, git-tracked.
This is the "build the loop, don't be the loop" + context-economy principle made
concrete (see `docs/design/build-the-loop-dont-be-the-loop.md`,
`docs/design/manager-context-economy-inline-route-or-spawn-delegation-ladder.md`).

## Layout

```
agent-tasks/
  README.md                     ← this file (the contract)
  YYMMDD-<slug>/                ← one task; date-prefixed so it sorts chronologically
    TASK.md                     ← THE brief. The agent reads this FIRST. (SOP-shaped, see below)
    STATUS.md                   ← one-screen lifecycle state (open|dispatched|in-progress|delivered|reviewed|closed)
    in/                         ← INPUTS the agent READS: context .md, research, symlinks to repo artifacts
    misc/                       ← supporting scratch / oversized raw material (still read-only to the agent)
    archive/                    ← superseded inputs, kept for provenance
    out/                        ← the agent WRITES deliverables here
    out-meta/                   ← the agent WRITES provenance here: sources, run-log, self-assessment
```

`YYMMDD-<slug>` (e.g. `260719-fleet-orchestration-design-review`) — the
`YYMMDD` prefix makes `ls agent-tasks/` a chronological list; the slug is a
short kebab-case topic.

## The in/out contract (memorise — every agent relies on it)

* **READ from:** `TASK.md`, `in/`, `misc/`. Follow symlinks in `in/` to reach
  live repo artifacts without copying them.
* **WRITE to:** `out/` (deliverables) and `out-meta/` (provenance). Nothing else.
* **NEVER write to** `in/`, `misc/`, or `archive/` — those are the lead's inputs.
  If an input is wrong, note it in `out-meta/`, don't edit the input.
* **`TASK.md` is authoritative** over any looser instruction in a tmux message.
  The tmux hand-off is just a pointer ("read `@…/TASK.md`, then begin").
* **`STATUS.md`** is the shared status line — both the lead and the agent may
  update it; keep it to one screen.

## TASK.md shape (SOP)

A good brief has, in order: **Goal** (one sentence) · **Context** (what the thing
is, links/symlinks into `in/`) · **Inputs map** (what's in `in/`/`misc/` and why)
· **Deliverables** (exactly what files to write to `out/`, in what shape) ·
**Return protocol** (how to signal done + talk back over tmux) · **Constraints**
(PII gate, no-pip, read-only-outside-out, quiesce, etc.). Keep it skimmable.

## Conventions & guards

* **PII gate.** Never place real pane captures / PII-laden corpora in `in/`.
  Tasks here are about *our own design/tooling*; if a task ever needs live
  captures, redact first (`scripts/redact_pane_capture.py`).
* **Git.** Task folders are git-tracked (durable, reviewable). `.gitignore`
  excludes heavy/binary fetches under `misc/` — keep `in/`/`out/` text-first.
* **Symlink, don't copy** repo artifacts into `in/` (avoids drift; the symlink
  always points at the live file).
* **One task = one folder.** Don't reuse a folder for a new task; make a new
  dated one so history stays clean.

## See also

* `skills/dispatch-task-to-fable-helper/SKILL.md` — the L1 how/when.
* `scripts/dispatch_task_to_agent.sh` — the L0 driver.
* `scripts/spawn_task_session.sh` — the session-level analog (dedicated instance
  + Remote Control), for tasks too big for a co-located helper window.
* `skills/dispatch-helper` + `briefs/` — the *subagent* (context-isolation)
  analog, for one-shot summaries that don't need a standing agent.
