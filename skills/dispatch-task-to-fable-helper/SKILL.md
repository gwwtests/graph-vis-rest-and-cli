---
name: dispatch-task-to-fable-helper
description: Use when you want to hand a self-contained, folder-shaped task to a STANDING helper agent (default = the fable helper at ubertmux-nested:fable, a claude-fable-5 --effort high window) and get file deliverables back — e.g. "get fable to review X", "hand this off to the fable helper", "dispatch a design/research/audit job to a standing agent". Ensures the right agent is running in the window, /clear's a reused idle one, then verified-sends a short brief POINTER (the agent reads the brief file, nothing large is pasted). Wraps scripts/dispatch_task_to_agent.sh + the agent-tasks/ desk convention. NOT for one-shot context-isolation summaries (use skills/dispatch-helper) and NOT for a big task that needs its own Remote-Control instance (use skills/delegate-or-spawn + spawn_task_session.sh).
---

# `dispatch-task-to-fable-helper`

Hand a **folder-shaped task** to a **standing helper agent** in a co-located
tmux window and get **file deliverables** back. The default target is the
**fable helper** — `ubertmux-nested:fable`, launched as
`claude --model claude-fable-5 --effort high --remote-control ubertmux-fable`
(skip-perms) — a high-effort peer that reviews, researches, drafts, and audits
*for the lead*, writing durable outputs the lead can pick up later.

This is the "build the loop, don't be the loop" move made concrete: instead of
hand-driving a helper each time (ensure it's up → `/clear` → paste a task), you
invoke **`scripts/dispatch_task_to_agent.sh`** and it does the mechanical dance.

## When to use

* You have a **chunk of work worth a fresh, focused context** (a design review,
  a research synthesis, a corpus audit, a draft) and you want it **off the lead's
  context** but **not** as a throwaway subagent — you want a durable,
  human-driveable (Remote Control) agent with file outputs you can review.
* The task is **describable as a folder**: a brief + inputs in, deliverables out.
* You'll come back for the **files**, not a one-line answer.

## When NOT to use

* **One-shot summary, no standing agent needed** → `skills/dispatch-helper` +
  `briefs/` (context-isolation subagent; its exploration dies on return).
* **A big task that should own its whole session + be driven from a phone** →
  `skills/delegate-or-spawn` + `scripts/spawn_task_session.sh` (dedicated `-L`
  session, not a co-located window).
* **You just need to read one known file** → Read it inline.
* **The target agent is mid-run** → don't dispatch; wait or pick another target.
  (The script guards this and aborts, but don't fight it.)

## Reflex

```
1. Make the task folder:  agent-tasks/YYMMDD-<slug>/  with in/ misc/ archive/ out/ out-meta/
   (see agent-tasks/README.md for the in/out contract).
2. Write TASK.md (SOP-shaped: Goal · Context · Inputs map · Deliverables ·
   Return protocol · Constraints). Symlink repo artifacts into in/ (don't copy).
   Delegate any wide web-research to a subagent that writes into in/ (parallel).
3. Dry-run:   scripts/dispatch_task_to_agent.sh --task-dir agent-tasks/YYMMDD-<slug> --dry-run
4. Dispatch:  scripts/dispatch_task_to_agent.sh --task-dir agent-tasks/YYMMDD-<slug>
   (creates+launches the fable window if missing; /clear's a reused idle agent;
   verified-sends the brief pointer; aborts rather than clobber a busy agent).
5. The agent reads TASK.md, works, writes out/ + out-meta/, updates STATUS.md,
   and pings you as "(ubertmux:fable):". Review the files; don't re-do the work.
```

## The script (L0) — key flags

`scripts/dispatch_task_to_agent.sh --help-for-agents` for the full contract.

* `--task-dir DIR` (required) — the folder; brief defaults to `DIR/TASK.md`.
* `--window S:W` — target (default `ubertmux-nested:fable`).
* `--model` / `--effort` / `--rc-name` / `--handle` — for a **fresh launch**
  (defaults `claude-fable-5` / `high` / `ubertmux-fable` / `ubertmux:fable`).
* `--no-clear` — reuse the agent's context instead of `/clear`ing it (e.g. a
  follow-up task that builds on the last one).
* `--force` — override the pre-send draft guard (rare; you accept clobbering a
  pending draft in the box).
* `--dry-run` — print the plan, touch nothing. **Always dry-run an unfamiliar
  target first.**

Exit codes: `0` dispatched · `2` bad args · `3` agent-busy / not-ready /
verify-fail · `4` tmux error / first-run modal blocks the launch (resolve the
modal by hand — never auto-Enter a trust prompt — then re-run).

## Discipline (don't skip)

* **Never clobber a busy agent.** The script aborts on a mid-run spinner or a
  real pending draft; heed it. `/clear` throws away context — only on an *idle*
  reused agent, and only when the new task is genuinely fresh.
* **Pointer, not paste.** The brief goes in as `@<path>`; keep the tmux message
  small (verified sends collapse/large-paste-mismatch past ~500 chars).
* **The folder is the contract.** Read from `TASK.md`/`in/`/`misc/`, write to
  `out/`/`out-meta/`. State this in every brief so the agent can't misread it.
* **Servant framing.** You're delegating to a peer helper — give it enough
  context to disagree with you, not just execute.

## See also

* `agent-tasks/README.md` — the desk + in/out data contract.
* `scripts/dispatch_task_to_agent.sh` (`.README.md`, `.DEV_NOTES.md`) — the driver.
* `scripts/spawn_task_session.sh` — session-level analog (dedicated + Remote Control).
* `skills/dispatch-helper` + `briefs/` — subagent (context-isolation) analog.
* `skills/delegate-or-spawn` — the inline / route / spawn decision.
* `docs/design/build-the-loop-dont-be-the-loop.md`,
  `docs/design/manager-context-economy-inline-route-or-spawn-delegation-ladder.md` — the why.
