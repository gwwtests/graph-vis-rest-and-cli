#!/usr/bin/env bash
# dispatch_task_to_agent.sh — hand a FOLDER-shaped task to a STANDING helper
# agent living in a tmux window (default: de:fable at de-tutor:de-fable). It
# ENSURES the right agent is running in the window, optionally /clear's a reused
# idle agent, then verified-sends a short brief POINTER (never the whole brief
# inline — the agent reads the file).
#
# ADOPTED 2026-07-19 from CLIAI uberclaude-gw's fable-dispatch pattern, retargeted
# to this repo's de:fable. See scripts/dispatch_task_to_agent.sh.DEV_NOTES.md for
# the adaptation log.
#
# VENDORED SEND CHAIN — do NOT de-duplicate. This driver calls the NATIVE sibling
# scripts/tmux_send_verified.sh (deps: tmux_send_line.sh, ghost_strip.py) and maps
# its exit-5 = real-draft-guard -> BUSY. The agents-tmux-comms plugin ships a
# same-named tool whose exit-5 means PASTE_COLLAPSED; swapping to it would silently
# mislabel a busy agent. Keep the three vendored scripts as a self-contained copy.
#
# This is the L0 driver behind the skill
# plugins/modes/_shared/skills/dispatch-task-to-fable-helper (L1) and the
# agent-tasks/ desk convention (agent-tasks/README.md).
#
# See: agent-tasks/README.md
#      plugins/modes/_shared/skills/dispatch-task-to-fable-helper/SKILL.md
#      this file's .README.md (usage) + .DEV_NOTES.md (rationale)
#
# Usage:
#   scripts/dispatch_task_to_agent.sh --task-dir DIR [--window SESS:WIN]
#       [--brief FILE] [--rc-name N] [--model M] [--effort E] [--handle H]
#       [--from H] [--socket S] [--cwd DIR] [--no-clear] [--force] [--wait SEC]
#       [--dry-run]
#
# Exit codes: 0 dispatched · 2 bad args · 3 agent-busy / not-ready / verify-fail
#   · 4 tmux error / first-run modal blocks launch.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$HERE/.." && pwd)"

usage() { sed -n '2,36p' "$0"; }

if [[ "${1:-}" == "--help-for-agents" ]]; then
  cat <<'EOF'
dispatch_task_to_agent.sh — CONTRACT (for agents)
PURPOSE: hand a folder-shaped task (agent-tasks/YYMMDD-slug/) to a STANDING
  helper agent in a tmux window (default de:fable). Ensures the agent is up
  (launches fable if the window is empty/shell), guards against clobbering a busy
  agent, /clear's a reused idle agent, then verified-sends a short brief POINTER.
INVOKE: scripts/dispatch_task_to_agent.sh --task-dir agent-tasks/YYMMDD-slug
  --task-dir DIR   REQUIRED. The task folder (must contain the brief).
  --window S:W     target window (default de-tutor:de-fable).
  --brief FILE     brief file (default <task-dir>/TASK.md).
  --rc-name N      Remote Control name for a fresh launch (default de-fable).
  --model M        model for a fresh launch (default claude-fable-5).
  --effort E       effort for a fresh launch (default high).
  --handle H       identity handle the agent should sign as (default de:fable).
  --from H         dispatcher handle the pointer is signed with (default de:tutor).
  --cwd DIR        cwd for a fresh launch (default repo root).
  --no-clear       do NOT /clear a reused agent (default: clear an idle reuse).
  --force          send the brief even past the draft guard (passes --force down).
  --wait SEC       readiness poll seconds for a fresh launch (default 25).
  --dry-run        print the plan, touch nothing.
RETURNS (stdout last line): "DISPATCHED window=<w> brief=<f>" on success, else a
  "BUSY ..."/"NOT-READY ..."/"MODAL ..." line (exit 3/4). The agent reads the
  brief itself; nothing large is pasted into the pane.
GUARANTEES: never blind-clobbers a busy agent; never answers a first-run trust
  modal; always passes -L <socket>; verified send (aborts on a real pending draft).
EOF
  exit 0
fi

# ---- defaults -------------------------------------------------------------
TASK_DIR="" ; WINDOW="graphvis-mgr:fable" ; BRIEF="" ; RC_NAME="graphvis-fable"
MODEL="claude-fable-5" ; EFFORT="high" ; HANDLE="graphvis:fable" ; FROM="graphvis:mgr"
SOCKET="default" ; CWD="$REPO_ROOT" ; DO_CLEAR=1 ; FORCE=0 ; WAIT=25 ; DRY=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --task-dir) TASK_DIR="${2:?}"; shift 2;;
    --window)   WINDOW="${2:?}"; shift 2;;
    --brief)    BRIEF="${2:?}"; shift 2;;
    --rc-name)  RC_NAME="${2:?}"; shift 2;;
    --model)    MODEL="${2:?}"; shift 2;;
    --effort)   EFFORT="${2:?}"; shift 2;;
    --handle)   HANDLE="${2:?}"; shift 2;;
    --from)     FROM="${2:?}"; shift 2;;
    --socket)   SOCKET="${2:?}"; shift 2;;
    --cwd)      CWD="${2:?}"; shift 2;;
    --no-clear) DO_CLEAR=0; shift;;
    --force)    FORCE=1; shift;;
    --wait)     WAIT="${2:?}"; shift 2;;
    --dry-run)  DRY=1; shift;;
    -h|--help)  usage; exit 0;;
    -*) echo "unknown flag: $1" >&2; usage; exit 2;;
    *)  echo "unexpected arg: $1" >&2; exit 2;;
  esac
done

[[ -n "$TASK_DIR" ]] || { echo "ERROR: --task-dir required" >&2; usage; exit 2; }
[[ -d "$TASK_DIR" ]] || { echo "ERROR: --task-dir not a dir: $TASK_DIR" >&2; exit 2; }
[[ -n "$BRIEF" ]] || BRIEF="$TASK_DIR/TASK.md"
[[ -f "$BRIEF" ]] || { echo "ERROR: brief not found: $BRIEF (create TASK.md or pass --brief)" >&2; exit 2; }
[[ -d "$CWD" ]] || { echo "ERROR: --cwd not a dir: $CWD" >&2; exit 2; }

# session:window -> parts (split on the LAST colon so session names may contain none)
SESSION="${WINDOW%:*}" ; WIN="${WINDOW##*:}"
[[ -n "$SESSION" && -n "$WIN" && "$SESSION" != "$WIN" ]] || {
  echo "ERROR: --window must be SESSION:WINDOW (got '$WINDOW')" >&2; exit 2; }
TARGET="$SESSION:$WIN.0"    # pane 0 of the window

# absolute brief path for the pointer (so @path resolves regardless of agent cwd)
BRIEF_ABS="$(cd "$(dirname "$BRIEF")" && pwd)/$(basename "$BRIEF")"
TASK_ABS="$(cd "$TASK_DIR" && pwd)"

tmux_cap() { tmux -L "$SOCKET" capture-pane -p -t "$TARGET" 2>/dev/null || true; }

# The claudeadsp alias does NOT expand under send-keys, so emit the expanded
# skip-perms pair. Run claude INSIDE bash (`; exec "$SHELL"`) so the window
# SURVIVES a claude exit (drops to a shell instead of the window dying).
launch_cmd() {
  # shellcheck disable=SC2016  # $SHELL must stay LITERAL — it expands in the target window's shell, not here
  printf 'claude --allow-dangerously-skip-permissions --dangerously-skip-permissions --remote-control %s --model %s --effort %s ; exec "$SHELL"' \
    "$RC_NAME" "$MODEL" "$EFFORT"
}

# The brief POINTER — kept SINGLE-PATH and short. This repo's abs paths are
# ~115 chars; a two-path pointer approaches the TUI paste-collapse threshold
# (~500B) and the native verified-send has no auto-file-pointer, so a collapse
# would fail verification (exit 3). The brief itself (TASK.md) names in//out/.
pointer_msg() {
  printf '(%s): You are (%s), a standing high-effort helper. Your task brief: @%s . Read it in FULL (it names your in/ + out/ dirs under %s), then begin. Sign back as "(%s):".' \
    "$FROM" "$HANDLE" "$BRIEF_ABS" "$TASK_ABS" "$HANDLE"
}

# ---- dry-run --------------------------------------------------------------
if [[ $DRY -eq 1 ]]; then
  echo "[dry-run] socket=$SOCKET window=$SESSION:$WIN target=$TARGET"
  echo "[dry-run] brief=$BRIEF_ABS  task_dir=$TASK_ABS  handle=$HANDLE  from=$FROM"
  echo "[dry-run] if window missing -> new-window + launch: $(launch_cmd)"
  echo "[dry-run] if reused idle agent & clear -> verified-send '/clear'"
  echo "[dry-run] verified-send pointer -> $(pointer_msg)"
  echo "DRY-RUN window=$SESSION:$WIN brief=$BRIEF_ABS"
  exit 0
fi

tmux -L "$SOCKET" has-session -t "$SESSION" 2>/dev/null || {
  echo "ERROR: session '$SESSION' not found on -L $SOCKET (create the inner session first)" >&2; exit 4; }

# ---- ensure the window + a live agent -------------------------------------
window_exists() {
  tmux -L "$SOCKET" list-windows -t "$SESSION" -F '#{window_name}' 2>/dev/null \
    | grep -qxF "$WIN"
}

launch_here() {   # (re)launch fable in the (already-existing) window
  tmux -L "$SOCKET" send-keys -t "$TARGET" -l "$(launch_cmd)"
  tmux -L "$SOCKET" send-keys -t "$TARGET" Enter
}

poll_ready() {    # 0 ready · 1 modal · 2 timeout
  local left="$WAIT" cap
  while [[ $left -gt 0 ]]; do
    sleep 2; left=$((left-2))
    cap="$(tmux_cap)"
    grep -qiE 'Enter to confirm|Enter to select|❯ 1\.|to navigate|allow external|Do you trust' <<<"$cap" && return 1
    grep -qiE 'Remote Control active|for shortcuts|❯' <<<"$cap" && return 0
  done
  return 2
}

FRESH=0
if ! window_exists; then
  echo "window $SESSION:$WIN missing -> creating + launching fable ($MODEL/$EFFORT, rc=$RC_NAME)"
  tmux -L "$SOCKET" new-window -t "$SESSION" -n "$WIN" -c "$CWD" \
    || { echo "ERROR: could not create window" >&2; exit 4; }
  sleep 1
  launch_here
  FRESH=1
else
  # Liveness by FOREGROUND PROCESS, not by a glyph: a bare shell prompt (starship
  # etc.) can render a `❯`, which would falsely read as a live TUI and cause the
  # brief to be typed into a shell. claude runs as node/claude; an idle window
  # sits on the shell (the `; exec "$SHELL"` fallback).
  pcmd="$(tmux -L "$SOCKET" display-message -p -t "$TARGET" '#{pane_current_command}' 2>/dev/null || true)"
  if [[ -z "$pcmd" || "$pcmd" =~ ^-?(bash|zsh|fish|sh|dash|ash|tcsh|csh)$ ]]; then
    echo "window $SESSION:$WIN exists but foreground is a shell ('${pcmd:-?}') -> (re)launching fable"
    launch_here
    FRESH=1
  else
    echo "window $SESSION:$WIN exists; foreground='$pcmd' -> reusing the running agent"
  fi
fi

if [[ $FRESH -eq 1 ]]; then
  case "$(poll_ready; echo $?)" in
    1) echo "---- pane ----"; tmux_cap | tail -n 16
       echo "MODAL window=$SESSION:$WIN reason=first-run-modal (resolve it yourself — do NOT auto-Enter a trust prompt — then re-run)"; exit 4;;
    2) echo "NOT-READY window=$SESSION:$WIN reason=not-ready-in-${WAIT}s (check the pane)"; exit 3;;
  esac
fi

# ---- guard: never clobber a BUSY agent ------------------------------------
cap="$(tmux_cap)"
if grep -qiE 'esc to interrupt|tokens · esc|Running…|✳|⏵⏸|Thinking…|Cerebrating' <<<"$cap"; then
  echo "---- pane ----"; tmux_cap | tail -n 8
  echo "BUSY window=$SESSION:$WIN reason=agent-mid-run (retry when idle, or attach and check)"; exit 3
fi

# ---- reuse: /clear an idle agent so the new task starts fresh --------------
if [[ $FRESH -eq 0 && $DO_CLEAR -eq 1 ]]; then
  echo "reusing existing agent -> /clear to start the task fresh"
  clr_args=(-L "$SOCKET" -t "$TARGET")
  [[ $FORCE -eq 1 ]] && clr_args+=(--force)
  if "$HERE/tmux_send_verified.sh" "${clr_args[@]}" -- "/clear"; then
    sleep 2   # let the clear settle
  else
    rc=$?
    [[ $rc -eq 5 ]] && { echo "BUSY window=$SESSION:$WIN reason=real-draft-in-box (won't /clear over it; --force to override)"; exit 3; }
    echo "WARN: /clear verify returned $rc — check the pane" >&2
  fi
fi

# ---- hand off the brief POINTER (verified) --------------------------------
MSG="$(pointer_msg)"

snd_args=(-L "$SOCKET" -t "$TARGET")
[[ $FORCE -eq 1 ]] && snd_args+=(--force)
if "$HERE/tmux_send_verified.sh" "${snd_args[@]}" -- "$MSG"; then
  echo "DISPATCHED window=$SESSION:$WIN brief=$BRIEF_ABS"
  exit 0
else
  rc=$?
  [[ $rc -eq 5 ]] && { echo "BUSY window=$SESSION:$WIN reason=real-draft-in-box (nothing sent; --force to override)"; exit 3; }
  echo "VERIFY-FAIL window=$SESSION:$WIN rc=$rc (brief pointer not confirmed in box; check the pane / send by hand)"; exit 3
fi
