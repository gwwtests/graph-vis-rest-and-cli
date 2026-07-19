---
title: dispatch_task_to_agent.sh — user docs
captured_on: 2026-07-19
summary: Hand a folder-shaped task (agent-tasks/YYMMDD-slug/) to a standing helper agent in a tmux window — ensure the agent is up, /clear a reused idle one, verified-send a short brief pointer.
related:
  - scripts/dispatch_task_to_agent.sh.DEV_NOTES.md
  - skills/dispatch-task-to-fable-helper/SKILL.md
  - agent-tasks/README.md
  - scripts/spawn_task_session.sh
  - scripts/tmux_send_verified.sh
---

# `dispatch_task_to_agent.sh`

L0 driver behind `skills/dispatch-task-to-fable-helper`. Hands a **folder-shaped
task** to a **standing helper agent** in a tmux window (default: the fable helper
at `ubertmux-nested:fable`) and gets file deliverables back.

## What it does

1. Validates the task folder + brief (`--task-dir DIR`, brief defaults to
   `DIR/TASK.md`).
2. **Ensures the agent is up** in the target window:
   * window missing → `new-window` + launch `claude --model … --effort … \
     --remote-control … ` (skip-perms, expanded; run inside bash so the window
     survives a claude exit) → poll for readiness / first-run modal.
   * window present but no claude TUI (dropped to a shell) → relaunch in place.
   * window present with a claude TUI → reuse it.
3. **Guards** against clobbering: aborts if the agent is **mid-run** (spinner) or
   the input box holds a **real pending draft** (via `tmux_send_verified.sh`'s
   Step-0 guard).
4. On a **reused idle** agent: verified-sends `/clear` (skip with `--no-clear`).
5. **Verified-sends a short brief POINTER** — `(ubertmux-adm): You are (handle) …
   read @<brief> … write to <dir>/out/ …` — never the whole brief inline.

## Usage

```bash
# dry-run first (prints the plan, touches nothing)
scripts/dispatch_task_to_agent.sh --task-dir agent-tasks/260719-my-task --dry-run

# real dispatch (fable defaults)
scripts/dispatch_task_to_agent.sh --task-dir agent-tasks/260719-my-task

# follow-up that keeps the agent's context (no /clear)
scripts/dispatch_task_to_agent.sh --task-dir agent-tasks/260720-followup --no-clear

# a different standing helper (e.g. a codex or opus window you keep)
scripts/dispatch_task_to_agent.sh --task-dir agent-tasks/260719-x \
  --window ubertmux-nested:opus-helper --model claude-opus-4-8 --rc-name ubertmux-opus \
  --handle ubertmux:opus
```

| Flag | Default | Effect |
|------|---------|--------|
| `--task-dir DIR` | (required) | the task folder (must hold the brief) |
| `--window S:W`   | `ubertmux-nested:fable` | target session:window |
| `--brief FILE`   | `<task-dir>/TASK.md` | the brief file |
| `--rc-name N`    | `ubertmux-fable` | Remote Control name (fresh launch) |
| `--model M`      | `claude-fable-5` | model (fresh launch) |
| `--effort E`     | `high` | effort (fresh launch) |
| `--handle H`     | `ubertmux:fable` | identity handle the agent signs as |
| `--cwd DIR`      | repo root | cwd (fresh launch) |
| `--no-clear`     | off (clears) | reuse the agent's context, don't `/clear` |
| `--force`        | off | override the draft guard (passed to the send) |
| `--wait SEC`     | `25` | readiness poll seconds (fresh launch) |
| `--socket S`     | `default` | tmux `-L` socket |
| `--dry-run`      | off | print the plan, touch nothing |

## Exit codes

* `0` — dispatched (brief pointer verified + Enter sent)
* `2` — bad arguments / missing task-dir or brief
* `3` — agent busy (mid-run / real draft), not-ready in time, or verify-fail
* `4` — tmux error (no session / can't create window) or a first-run modal
  blocks the launch (resolve it by hand — do **not** auto-Enter a trust
  prompt — then re-run)

## Notes

* Always passes `-L <socket>` (never bare `tmux`).
* Never answers a first-run trust/permission modal for you.
* The `claudeadsp` alias can't expand under `send-keys`, so the skip-perms pair
  is emitted expanded (same as `spawn_task_session.sh`).
* Keep the brief a *file*; the pointer sent into the pane stays small so the
  verified send doesn't trip the large-paste-collapse mismatch (~500 chars).
