---
title: tmux_send_verified.sh — user docs
captured_on: 2026-06-20
summary: Send text to a tmux pane — abort if a real draft is already there (Step 0 guard), else verify it landed in the input box (immune to Claude TUI predicted prompts) and send Enter.
related:
  - scripts/tmux_send_verified.sh.DEV_NOTES.md
  - scripts/tmux_send_line.sh
  - docs/design/claude-tui-predicted-prompt-vs-typed-prompt-pitfall.md
---

# `tmux_send_verified.sh`

Like `tmux_send_line.sh`, but with a roundtrip verify before Enter.

Use this when the target pane is **not yours** (other agent, user
session, etc.) and a predicted prompt or pending draft would
corrupt the message if you fired blind.

## Usage

```bash
tmux_send_verified.sh [-L SOCK] [-t TGT] [--strict] [--force] [--send-anyway] [-p MIN,MAX] -- "<text>"
```

| Flag | Default | Effect |
|------|---------|--------|
| `-L SOCK`        | (default socket) | tmux server |
| `-t TGT`         | current pane     | pane target |
| `--strict`       | off (contains)   | require exact normalised-alnum match |
| `--force`        | off              | skip the Step 0 pre-send draft guard — type even if a real draft is present |
| `--send-anyway`  | off              | on verify-fail, send Enter regardless and exit 0 (use with care) |
| `-p MIN,MAX`     | `0.37,0.97`      | settle-pause range (seconds) before verify |
| `--`             | —                | terminator before the text argument |

## Flow

0. **PRE-send guard:** `capture-pane -p -e`, classify the last `❯ …` line.
   A **dim/faint** line is a predicted ghost (empty box) → proceed; a
   **normal-intensity** line is a real pending draft → **abort exit 5,
   nothing typed** (override with `--force`). This is the check that
   `(medic-agent)` had to do by hand on 2026-06-20 to save Greg's draft.
1. `tmux_send_line.sh --no-enter` sends just the text.
2. Sleep `rand(MIN, MAX)` seconds — predicted prompts vanish, real
   input settles.
3. `capture-pane`, extract last `❯ …` line (+ continuations).
4. Normalise both expected and observed to `[a-z0-9]` lowercase.
5. Assert observed contains (default) or equals (`--strict`) expected.
6. PASS → send Enter. FAIL → abort and report.

## Examples

```bash
# Cross-agent intro (high-stakes — verify):
tmux_send_verified.sh -L default -t tmux_session_snapshot:0 -- \
    "(uberclaude-Kestrel): brief follow-up question..."

# Strict mode — any prior content fails the check:
tmux_send_verified.sh --strict -L default -t somesess:0 -- "ls -la"

# Override pause range (faster):
tmux_send_verified.sh -p 0.2,0.5 -L ubertmux -t :0 -- "echo hi"
```

## Exit codes

* `0` — verified and Enter sent (or `--send-anyway` triggered)
* `2` — bad arguments
* `3` — verification mismatch; Enter NOT sent (unless `--send-anyway`)
* `4` — capture-pane failed
* `5` — pre-send guard: target box already holds a real draft, nothing typed (override with `--force`)

## When to use this vs `tmux_send_line.sh`

| Situation | Script |
|-----------|--------|
| Your own pane, definitely empty | `tmux_send_line.sh` |
| Just observed-empty via capture, low-stakes | `tmux_send_line.sh` |
| Cross-agent / cross-user channel | `tmux_send_verified.sh` |
| Anything that runs commands on a `bash` prompt | `tmux_send_verified.sh` |
| Multi-line / control sequences / non-typeable | `tmux_send_line.sh` (verify won't work) |

## Caveat — large pastes collapse to a placeholder (verify mismatches)

When the text is large enough, Claude Code treats the send as a
clipboard paste and **collapses it to `[Pasted text #N +X lines]`** in the
input box. The text DID land, but the read-back sees the placeholder, not
the literal characters, so the verify step **mismatches** — exit `3`, and
you may reflexively reach for `--send-anyway`. To avoid this:

* Keep verified sends **small/typed** (under ~500 chars) so the literal
  text stays capture-confirmable; for longer content, **split into chunks**
  (each verified) or write it to a file and send a short pointer.
* For a deliberate large paste you intend to submit by hand: press **Enter**
  to send it, or **`Ctrl+G`** to open it in `$EDITOR` first (terminal editor
  only — check `echo $EDITOR`; `vim` here works, a GUI `$EDITOR` does not).

A follow-up TODO (see `.DEV_NOTES.md`) is to make the verifier recognise the
paste placeholder as a valid "landed" signal instead of failing.

## See also

* `docs/design/inter-agent-tmux-communication-protocol.md` — §Send size
  (paste-collapse) for the full handling.
* `docs/design/claude-tui-predicted-prompt-vs-typed-prompt-pitfall.md`
  — the full rationale.
* `scripts/tmux_send_line.sh` — underlying primitive.
