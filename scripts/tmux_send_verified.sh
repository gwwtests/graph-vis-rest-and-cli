#!/usr/bin/env bash
# tmux_send_verified.sh — send text to a tmux pane, VERIFY it landed
# in the input box, then send Enter.
#
# Predicted-prompt safety (see
# docs/design/claude-tui-predicted-prompt-vs-typed-prompt-pitfall.md):
#   * A dim/faint ANSI "❯ <text>" line is a PREDICTED ghost (empty box) —
#     safe to type over; typing clears it.
#   * A normal-intensity "❯ <text>" line is a REAL pending draft — typing
#     over it MERGES into one corrupted command on Enter. We must NOT.
# So the verify step alone (which captures plain -p AFTER typing, when our
# own keystrokes have already cleared any ghost) cannot tell these apart
# BEFORE the fact. A PRE-send guard (Step 0) captures -e and aborts on a
# real draft. This is exactly the manual check the medic-agent did on
# 2026-06-20 that saved Greg's "(Greg) TODO:" draft in the adm box.
#
# Flow:
#   0. PRE-send: capture -e, classify the "❯" line; ABORT (exit 5) if a
#      REAL (non-ghost, non-empty) draft is already present  [skip w/ --force]
#   1. tmux_send_line.sh --no-enter <text>     # send just the text
#   2. sleep rand(0.37, 0.97)s                  # let buffer settle
#   3. capture-pane -p, extract last "❯ ..." line
#   4. strip both expected and observed to [a-zA-Z0-9], lowercase
#   5. assert observed CONTAINS expected (default) OR EQUALS (--strict)
#   6. send Enter on PASS; abort+report on FAIL
#
# Usage:
#   tmux_send_verified.sh [-L socket] [-t target] [--strict] [--force] [--send-anyway] [--gateway] -- "<text>"
#
# Gateway mode (opt-in: --gateway, or UBERCLAUDE_SEND_VIA_GATEWAY=1): DELEGATE to
# the marketplace gateway (CLIAI/claude-via-tmux-skills agents-tmux-comms) — the
# canonical chokepoint with the paste-collapse integrity gate, auto-.0 addressing,
# bare-numeric warn, handle-lint, and a Ctrl+G editor flow. Default is OFF (native
# path below) so live-fleet behavior is unchanged until adoption is flipped (a
# coordinated follow-up). In gateway mode the exit codes are the GATEWAY's.
#
# Exit codes (NATIVE path):
#   0  — text verified, Enter sent
#   2  — bad arguments
#   3  — verification FAILED (Enter NOT sent unless --send-anyway)
#   4  — capture failed
#   5  — PRE-send guard: target box already holds a real draft (nothing typed)
#
# Note: only matches text that is plausibly typeable. For sending
# control sequences, multi-line input, or anything where the verify
# round-trip would be wrong, use tmux_send_line.sh directly.

set -euo pipefail

SOCKET=""
TARGET=""
STRICT=0
SEND_ANYWAY=0
FORCE=0
PMIN="0.37"
PMAX="0.97"
# Opt-in delegation to the marketplace gateway (collision-safe chokepoint).
# Default OFF (native path) to avoid changing live-fleet behavior unilaterally;
# enable per-call with --gateway or globally with UBERCLAUDE_SEND_VIA_GATEWAY=1.
USE_GATEWAY=0
[[ -n "${UBERCLAUDE_SEND_VIA_GATEWAY:-}" ]] && USE_GATEWAY=1

while [[ $# -gt 0 ]]; do
    case "$1" in
        -L|--socket)        SOCKET="$2"; shift 2 ;;
        -t|--target)        TARGET="$2"; shift 2 ;;
        --strict)           STRICT=1; shift ;;
        --send-anyway)      SEND_ANYWAY=1; shift ;;
        --force)            FORCE=1; shift ;;
        --gateway)          USE_GATEWAY=1; shift ;;
        --no-gateway)       USE_GATEWAY=0; shift ;;
        -p|--pause)         IFS=',' read -r PMIN PMAX <<< "$2"; shift 2 ;;
        -h|--help)
            sed -n '2,39p' "$0"
            exit 0
            ;;
        --) shift; break ;;
        -*) echo "unknown flag: $1" >&2; exit 2 ;;
        *)  break ;;
    esac
done

if [[ $# -ne 1 ]]; then
    echo "usage: $(basename "$0") [-L SOCK] [-t TGT] [--strict] [--force] [--send-anyway] -- <text>" >&2
    exit 2
fi
TEXT="$1"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SEND_LINE="$SCRIPT_DIR/tmux_send_line.sh"
[[ -x "$SEND_LINE" ]] || { echo "error: $SEND_LINE missing" >&2; exit 2; }

# Multi-pane addressing convention (pane-0 = lead): auto-append .0 to a bare
# {session}:{window} target so a send can't land on a SUB-AGENT pane instead of
# the lead. Identical semantics to tmux_send_claude_msg.py (CLIAI/claude-via-
# tmux-skills): target has ':' and no '.' -> append '.0'; an explicit .{pane}
# passes through unchanged (idempotent — a normalized target already has a '.').
# Ref: FUTURE_WORK/2026-06-29--multipane-addressing-auto-pane0-default.md
if [[ -n "$TARGET" && "$TARGET" == *:* && "$TARGET" != *.* ]]; then
    TARGET="${TARGET}.0"
fi

tmux_args=()
[[ -n "$SOCKET" ]] && tmux_args+=( -L "$SOCKET" )
target_args=()
[[ -n "$TARGET" ]] && target_args+=( -t "$TARGET" )

export TMUX=""

# --- optional delegation to the marketplace gateway (collision-safe chokepoint) ---
# CLIAI/claude-via-tmux-skills `agents-tmux-comms` ships the canonical send tool with
# the paste-collapse INTEGRITY GATE, auto-`.0` addressing, bare-numeric warn,
# handle-lint, and a Ctrl+G editor flow. When opted-in we DEFER to it rather than
# diverge (the apex lead's "don't-fork" gate). NOTE: in gateway mode the exit codes
# are the GATEWAY's (0 ok / 1 human-deferred / 2 args / 3 verify / 4 capture /
# 5 blocked-timeout / 6 editor) — see its `--help-for-agents`. `--force` is kept on
# the NATIVE path (the gateway has no "type over a real draft" override).
resolve_gateway() {
    local base="${HOME}/.claude/plugins/cache/claude-via-tmux-skills/agents-tmux-comms"
    [[ -d "$base" ]] || return 1
    local d tool
    while IFS= read -r d; do
        tool="$base/$d/tools/tmux-send-claude-msg/tmux_send_claude_msg.py"
        [[ -f "$tool" ]] && { printf '%s\n' "$tool"; return 0; }
    done < <(find "$base" -mindepth 1 -maxdepth 1 -type d -printf '%f\n' 2>/dev/null | sort -V -r)
    return 1
}

if (( USE_GATEWAY )) && (( ! FORCE )); then
    if gw=$(resolve_gateway); then
        gw_args=()
        [[ -n "$SOCKET" ]] && gw_args+=( -L "$SOCKET" )
        [[ -n "$TARGET" ]] && gw_args+=( -t "$TARGET" )
        (( STRICT ))      && gw_args+=( --strict )
        (( SEND_ANYWAY )) && gw_args+=( --send-anyway )
        gw_args+=( --pause "${PMIN},${PMAX}" )
        exec python3 "$gw" "${gw_args[@]}" -- "$TEXT"
    fi
    echo "warn: gateway requested but no cached tmux_send_claude_msg.py found; using native path" >&2
elif (( USE_GATEWAY )) && (( FORCE )); then
    echo "note: --force is not delegated to the gateway (no draft-override); using native path" >&2
fi

# Helper: normalise = strip non-alnum, lowercase
normalise() {
    python3 -c '
import sys, re
print(re.sub(r"[^a-zA-Z0-9]", "", sys.stdin.read()).lower())'
}

# Helper: detect a REAL (non-ghost) draft already in the input box.
# Input: capture-pane -p -e output (ANSI preserved) on stdin.
# Delegates to the CANONICAL analyzer scripts/ghost_strip.py (single source of
# truth, shared with pane_state_classifier.py + tmux_send_if_available.sh) so the
# SGR/predicted-ghost logic is not duplicated. Prints the real pending-draft text
# (caller aborts on non-empty); prints nothing for an empty box or a dim ghost.
# Migrated 2026-06-21 from a duplicated inline SGR walker that mis-read the
# cursor-mid-ghost case (returned a stray char -> false exit-5); locked by the
# tests/ghost_strip/ cursor-mid-ghost regression fixture (af2ce4c).
detect_real_draft() {
    "$SCRIPT_DIR/ghost_strip.py" - | python3 -c '
import sys, json
d = json.load(sys.stdin)
if d.get("has_real_text"):
    print(d["real_text"].strip())'
}

# Step 0: PRE-send draft guard — never type over a real pending draft.
if (( ! FORCE )); then
    pre=$(tmux "${tmux_args[@]}" capture-pane -p -e "${target_args[@]}" -S -20 2>/dev/null) || {
        echo "error: pre-send capture-pane failed" >&2
        exit 4
    }
    draft=$(printf '%s' "$pre" | detect_real_draft)
    if [[ -n "$draft" ]]; then
        {
            echo "ABORT: target input box already holds a REAL draft — nothing typed."
            echo "  draft: $draft"
            echo "  (dim 'ghost' predictions are ignored; this is normal-intensity text.)"
            echo "  Clear the box, or re-run with --force to type over it intentionally,"
            echo "  or use tmux_send_line.sh directly."
        } >&2
        exit 5
    fi
fi

# Step 1: send text (no Enter)
"$SEND_LINE" ${SOCKET:+-L "$SOCKET"} ${TARGET:+-t "$TARGET"} --no-enter -- "$TEXT"

# Step 2: settle pause
DELAY=$(python3 -c "import random,sys; print(random.uniform(float(sys.argv[1]), float(sys.argv[2])))" "$PMIN" "$PMAX")
sleep "$DELAY"

# Step 3: capture last few lines, find input-box line(s) — they live
# bracketed by ─ lines and start with "❯ "
captured=$(tmux "${tmux_args[@]}" capture-pane -p "${target_args[@]}" -S -20 2>/dev/null) || {
    echo "error: capture-pane failed" >&2
    exit 4
}

# Extract the joined input-box content. Strategy: find the LAST line
# starting with the "❯" glyph (Claude TUI input prompt) and slurp it
# plus any continuation lines (typically indented two spaces) until
# we hit a ─-only line or a status-line marker.
observed=$(echo "$captured" | python3 -c '
import sys
lines = sys.stdin.read().splitlines()
# Find the last "❯" line
last = None
for i, ln in enumerate(lines):
    if "❯" in ln:
        last = i
if last is None:
    print(""); sys.exit(0)
# Slurp the prompt line + continuation lines
buf = [lines[last]]
for ln in lines[last+1:]:
    if not ln.strip():
        continue
    if set(ln.strip()) <= set("─━╌╍"):
        break
    if ln.lstrip().startswith("⏵") or "bypass permissions" in ln:
        break
    buf.append(ln)
print(" ".join(buf))
')

# Step 4: normalise both
expected_norm=$(printf '%s' "$TEXT"     | normalise)
observed_norm=$(printf '%s' "$observed" | normalise)

# Step 5: assert
ok=0
if (( STRICT )); then
    [[ "$observed_norm" == "$expected_norm" ]] && ok=1
else
    [[ "$observed_norm" == *"$expected_norm"* ]] && ok=1
fi

if (( ok )); then
    # Step 6: send Enter
    tmux "${tmux_args[@]}" send-keys "${target_args[@]}" Enter
    echo "verified+sent: target=${SOCKET:-(default)} ${TARGET:-(current)}  bytes_text=${#TEXT}"
    exit 0
fi

# FAIL path
{
    echo "FAIL: verification mismatch"
    echo "  expected (norm): $expected_norm"
    echo "  observed (norm): $observed_norm"
    echo "  observed (raw):  $observed"
} >&2

if (( SEND_ANYWAY )); then
    echo "  --send-anyway set; sending Enter regardless" >&2
    tmux "${tmux_args[@]}" send-keys "${target_args[@]}" Enter
    exit 0
fi

exit 3
