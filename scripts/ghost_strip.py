#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# ///
"""ghost_strip.py — CANONICAL SGR-aware analysis of a Claude TUI input box.

Single source of truth for "what is in the ❯ input box?" so the three consumers
stop drifting (divergence already caused a real bug — the `[0;2m` reset-then-faint
cursor-ghost leaked as a false real-draft → spurious abort; see
FUTURE_WORK/classifier-full-line-predicted-ghost-misreads-idle-as-unknown.md):

  * pane_state_classifier.has_predicted_ghost  (was: RE_GHOST, missed full-line ghost)
  * tmux_send_if_available.input_has_real_text  (was: a regex dim-strip)
  * tmux_send_verified.detect_real_draft        (the SGR machine ported here)

PREDICTED GHOST vs REAL DRAFT
  A predicted ghost renders DIM (SGR faint, param 2; commonly "[0;2m" = reset
  THEN faint) after the ❯ — the box is EMPTY / available, never block a send.
  REAL typed text renders at normal intensity — a pending draft, never type over.

  We take the LAST ❯ line (the live box; scrollback ❯ lines sit above) and walk
  its SGR runs LEFT-TO-RIGHT (param order matters: "0;2m" = reset → faint ⇒ dim;
  the old "2-then-0" precedence wrongly cleared dim and leaked the ghost). Text in
  a dim run is GHOST; text outside is REAL. The reverse-video cursor (param 7)
  marks the insertion point — its single char is a placeholder (a space in an
  empty/ghost box) and is DISCARDED, so it never reads as a draft even when the
  cursor sits on a ghost's first char.

CLI: ghost_strip.py <ansi.txt|-> -> JSON {has_prompt, real_text, has_real_text,
                                           ghost_text, has_ghost}
Pure funcs: analyze_prompt(ansi) -> PromptAnalysis; has_predicted_ghost(ansi);
            input_real_text(ansi).  No third-party deps (uv inline script).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, asdict
from pathlib import Path

PROMPT = "❯"
_SGR = re.compile(r"\x1b\[([0-9;]*)m")
_CSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")   # any residual CSI escape
_ALNUM = re.compile(r"[A-Za-z0-9]")


@dataclass
class PromptAnalysis:
    has_prompt: bool       # a ❯ input line was found
    real_text: str         # non-dim (non-ghost) visible text after ❯, stripped
    has_real_text: bool    # real_text carries an alphanumeric ⇒ a REAL draft
    ghost_text: str        # dim (ghost/predicted) visible text after ❯, stripped
    has_ghost: bool        # a dim prediction is present (box still empty/available)


def _last_prompt_line(ansi: str, glyph: str = PROMPT) -> str | None:
    found = None
    for ln in ansi.splitlines():
        if glyph in ln:
            found = ln          # keep the LAST one (the live box)
    return found


def _clean(s: str) -> str:
    s = _CSI.sub("", s)            # strip residual CSI (cursor moves, colors)
    s = re.sub(r"\x1b.", "", s)    # strip any other 2-char escape
    return s.replace("\xa0", " ")  # NBSP padding -> space


def analyze_prompt(ansi: str, glyph: str = PROMPT) -> PromptAnalysis:
    """Analyze the LAST input line of an ANSI capture. `glyph` selects the input
    prompt: ❯ (U+276F, Claude — default) or › (U+203A, Codex). Default is byte-
    identical to the pre-glyph behaviour for every existing caller."""
    line = _last_prompt_line(ansi, glyph)
    if line is None:
        return PromptAnalysis(False, "", False, "", False)
    after = line.split(glyph, 1)[1]
    dim = False
    reverse = False           # SGR 7: the input cursor — its char is a placeholder
    real_parts: list[str] = []
    ghost_parts: list[str] = []

    def _stash(seg: str) -> None:
        if dim:
            ghost_parts.append(seg)   # dim => predicted ghost
        elif reverse:
            pass                      # cursor placeholder — neither real nor ghost
        else:
            real_parts.append(seg)    # normal intensity => real typed text

    pos = 0
    for m in _SGR.finditer(after):
        _stash(after[pos:m.start()])
        params = m.group(1).split(";") if m.group(1) else ["0"]
        for p in params:                       # LEFT-TO-RIGHT — order matters
            if p == "2":
                dim = True
            elif p == "7":
                reverse = True
            elif p == "0":
                dim = reverse = False
            elif p == "22":
                dim = False
            elif p == "27":
                reverse = False
        pos = m.end()
    _stash(after[pos:])
    real = _clean("".join(real_parts))
    ghost = _clean("".join(ghost_parts))
    return PromptAnalysis(
        has_prompt=True,
        real_text=real.strip(),
        has_real_text=bool(_ALNUM.search(real)),
        ghost_text=ghost.strip(),
        has_ghost=bool(ghost.strip()),
    )


def has_predicted_ghost(ansi: str | None, glyph: str = PROMPT) -> bool:
    """True iff the box shows a DIM predicted ghost (box still empty)."""
    return bool(ansi) and analyze_prompt(ansi, glyph).has_ghost


def input_real_text(ansi: str | None, glyph: str = PROMPT) -> str:
    """The REAL (non-ghost) pending draft in the box; '' if empty/ghost-only."""
    if not ansi:
        return ""
    a = analyze_prompt(ansi, glyph)
    return a.real_text if a.has_real_text else ""


_AGENT_HELP = """\
ghost_strip.py — canonical SGR analysis of the Claude ❯ input box (one source of
truth; consumers: pane_state_classifier, tmux_send_if_available, tmux_send_verified).
PURE: analyze_prompt(ansi) -> PromptAnalysis(has_prompt, real_text, has_real_text,
  ghost_text, has_ghost); has_predicted_ghost(ansi)->bool; input_real_text(ansi)->str.
RULE: take the LAST ❯ line; walk SGR runs LEFT-TO-RIGHT (0;2m = reset→faint ⇒ DIM).
  DIM text = predicted ghost (box EMPTY/available). Normal-intensity text = REAL
  draft (never type over). The [7m reverse cursor is not dim (its blanked char is a
  space ⇒ not alphanumeric ⇒ not a draft).
CLI: ghost_strip.py <ansi.txt|-> -> JSON. Pass the ANSI (capture-pane -p -e).
"""


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("path", nargs="?", help="ANSI capture file (or - for stdin)")
    ap.add_argument("--help-for-agents", action="store_true")
    args = ap.parse_args()
    if args.help_for_agents:
        print(_AGENT_HELP)
        return 0
    if not args.path:
        ap.error("path is required (or --help-for-agents)")
    ansi = sys.stdin.read() if args.path == "-" else Path(args.path).read_text()
    print(json.dumps(asdict(analyze_prompt(ansi))))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
