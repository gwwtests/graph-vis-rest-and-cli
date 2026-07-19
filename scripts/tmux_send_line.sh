#!/usr/bin/env bash
# tmux_send_line.sh — send a text line to a tmux pane with a randomised
# pause before Enter, so the input buffer settles and we don't race the
# receiving program.
#
# Usage:
#   tmux_send_line.sh [-L socket] [-t target] [--no-enter] [-p MIN,MAX] -- "<text>"
#
# Defaults:
#   pause range = 0.37 0.98   (seconds, uniform)
#
# Examples:
#   tmux_send_line.sh -L ubertmux -t :0.0 -- "/btw status?"
#   tmux_send_line.sh -L default -t tmux_session_snapshot:0 -- \
#       "(uberclaude-Kestrel): hello, design observed; thank you."
#
# Why the random pause?
#   * Some receivers debounce; sending Enter immediately after text can
#     drop the last keystroke.
#   * Randomisation (vs fixed 0.5s) avoids accidental harmonic patterns
#     that paste-detectors flag as machine input.
#
# Identity convention:
#   Wire format (canonical) is `(uberclaude-<fantasy>): <msg>` — two
#   tokens joined by a hyphen, inside parens. Same form for first
#   contact and subsequent lines.
#   The `(name=(firstname=..., familyname=...))` notation in the
#   source design prompt is the SPEC of how the name is composed,
#   NOT what you literally type.
#   See docs/design/inter-agent-tmux-communication-protocol.md.

set -euo pipefail

SOCKET=""
TARGET=""
NO_ENTER=0
PMIN="0.37"
PMAX="0.98"

while [[ $# -gt 0 ]]; do
    case "$1" in
        -L|--socket) SOCKET="$2"; shift 2 ;;
        -t|--target) TARGET="$2"; shift 2 ;;
        --no-enter)  NO_ENTER=1; shift ;;
        -p|--pause)  IFS=',' read -r PMIN PMAX <<< "$2"; shift 2 ;;
        -h|--help)
            sed -n '2,30p' "$0"
            exit 0
            ;;
        --) shift; break ;;
        -*) echo "unknown flag: $1" >&2; exit 2 ;;
        *)  break ;;
    esac
done

if [[ $# -ne 1 ]]; then
    echo "usage: $(basename "$0") [-L SOCKET] [-t TARGET] [--no-enter] [-p MIN,MAX] -- <text>" >&2
    exit 2
fi
TEXT="$1"

tmux_args=()
[[ -n "$SOCKET" ]] && tmux_args+=( -L "$SOCKET" )

# Always scrub $TMUX so we don't talk to the inherited server.
export TMUX=""

tmux "${tmux_args[@]}" send-keys ${TARGET:+-t "$TARGET"} -- "$TEXT"

if (( NO_ENTER == 0 )); then
    # Random pause in [PMIN, PMAX). Use python3 (stdlib only) for portable randf.
    DELAY=$(python3 -c "import random,sys; print(random.uniform(float(sys.argv[1]), float(sys.argv[2])))" "$PMIN" "$PMAX")
    sleep "$DELAY"
    tmux "${tmux_args[@]}" send-keys ${TARGET:+-t "$TARGET"} Enter
fi
