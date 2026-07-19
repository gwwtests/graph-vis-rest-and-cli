# Review Guide — v0.5.0 review→improve cycle (8 implemented feat/* branches)

**Author:** `(graphvis:mgr)` · 2026-07-19 · reports to `ubertmux-adm`
**Base:** all branches cut from `master` @ `2510ea2` (v0.5.0). **Nothing pushed; master untouched.**
**Source review:** `../fable/{01-review,02-architecture-assessment,03-improvement-roadmap,04-fleet-ttl-integration-judgment}.md` (Fable 5). This guide is the manager's synthesis of the 8 implementations.

---

## TL;DR

A Fable 5 review of v0.5.0 produced a triaged roadmap (8 BUILD-NOW + a fleet-TTL thin-slice + a DEFER list). A team of 8 opus agents each implemented one item on its own `feat/*` branch in an isolated worktree, with tests. **All 8 landed green.** Manager independently re-ran 2 suites (ws-write-protection 58, collab-resync 49) — matched the self-reports. Branches are ready for human review/merge.

---

## The 8 branches

| # | Branch | Size | Tests (reported) | What it does |
|---|--------|------|------|--------------|
| 1 | `feat/ws-write-protection` | S | 65 pass | Enforce `--read-only` on the WS action path (was bypassable — finding **F1**); optional `GRAPH_VIS_TOKEN` bearer/`?token=` auth; WS `Origin` check; new `GET /api/config`. |
| 2 | `feat/collab-resync` | S | 49 pass | Monotonic `store.rev` in every mutation + broadcast + `/api/graph`; browser connects WS-first, buffers, resyncs on (re)connect with viewport preserved. Kills silent divergence (**F3/F4**). |
| 3 | `feat/cli-hardening` | S | 56 pass | (a) run converters via their uv shebangs not `sys.executable` — unbreaks the `.ttl` path (**F6**); (b) real exit codes (0/1/2), request `--timeout`, `--json` output, non-interactive `-l/-s` no longer drops into REPL (**F10/F11/F20/F21**). |
| 4 | `feat/sse-subscribe` | M | 9+60 pass | `GET /api/events` SSE stream (bounded queue, heartbeat) + CLI `--subscribe [--format jsonl\|human]` (stdlib). The agent-reactive foundation (FUTURE_WORK §1). |
| 5 | `feat/server-persistence` | M | 52 pass | `--load` at boot + debounced atomic JSONL `--autosave`; graphs survive restart. Live restart round-trip verified. |
| 6 | `feat/store-action-parity` | S | 11 pass | Server-side `toggle_style` (late joiners saw wrong style — **F5**); `add_edge` auto-creates endpoint nodes (**F24**); table-driven action contract test. |
| 7 | `feat/vis-local-fallback` | S | e2e 4/5 | Offline vis-network fallback actually boots the app (**F2**); new offline-CDN e2e test passes. **Also fixed the e2e harness, which was broken on master** (see Cross-cutting). |
| 8 | `feat/fleet-jsonl-adapter` | S | 15 pass | `fleetjsonl2graph` converter (rel→label, kind→styling) + recipe doc + synthetic demo — wires the fleet-topology graph into graph-vis (roadmap #9 / TTL judgment). New files only. |

Sizes/numbers per each agent's report; #3 bundles roadmap items #3+#4 (both edit the CLI) as two commits.

---

## Reviewer setup (do this first — tests won't run otherwise)

1. **Python deps** come via `uv` (PEP 723); system python lacks fastapi. Run tests as:
   ```bash
   PYTHONPATH=. uv run --with fastapi --with 'uvicorn[standard]' --with websockets \
     --with httpx --with pytest --with pytest-asyncio \
     pytest tests/... -p no:playwright
   ```
2. **Gitignored import symlinks.** `tests/conftest.py` does `from graph_vis_server import app`, but `graph_vis_server.py`/`graph_vis_cli.py` are **gitignored symlinks** absent in fresh checkouts. Recreate before running tests:
   ```bash
   ln -sf graph-vis-server.py graph_vis_server.py
   ln -sf graph-vis-cli.py graph_vis_cli.py
   ```
   → **Recommended follow-up (not built, to keep branches scoped):** either commit these two symlinks or have `conftest.py` create them at import — it would unbreak `pytest` for every fresh clone. Left as a small master-level fix because 4 branches already touch `conftest.py`.

---

## Recommended merge order (minimizes rebase pain)

File-overlap map: **server** edited by 1,2,4,5,6 · **index.html** by 1,2,6,7 · **cli** by 3,4 · `conftest.py` by 1,2,4 · `AGENTS.md` by 6 branches (mechanical).

* **Wave A — independent, merge in any order, no rebase:**
  * `feat/fleet-jsonl-adapter` (new files + 1 AGENTS row)
  * `feat/cli-hardening` (only the CLI; shares CLI with #4 — merge this before #4)
* **Wave B — the server mutation/WS path, merge sequentially and rebase each onto the last:**
  1. `feat/collab-resync` **first** — it introduces the `broadcast_mutation()`/`rev` refactor that the others' broadcast lines sit on (per the fable roadmap's "merge #2 first").
  2. `feat/ws-write-protection` — gates the same mutation + action-relay path; rebase onto (1).
  3. `feat/store-action-parity` — also edits `_apply_action_to_store`; rebase.
  4. `feat/server-persistence` — adds `trigger_autosave()` on the broadcast path (additive); rebase.
  5. `feat/sse-subscribe` — adds `sse_fan_out()` hooks (localized, low collision) + CLI; rebase. SSE payload forwards `rev` verbatim, so it already composes with (1).
* **Wave C — last:** `feat/vis-local-fallback` — wraps the whole `index.html` inline script in `startApp()`; rebase so the Wave-B index.html edits (1,2,6) land **inside** the wrapper. Mechanically simple but broad in that file.

The index.html cluster (1,2,6,7) is where real conflicts live; everything else is additive/mechanical. AGENTS.md conflicts throughout are trivial.

---

## Cross-cutting findings the implementation surfaced (beyond the fable review)

* **e2e was 100% broken on master** — `e2e/test_e2e.py` imported `graph_vis_server` (hyphen-filename `ModuleNotFoundError`) so the server subprocess died and every test hit `ERR_CONNECTION_REFUSED`; also the default `minimal` input-mode hid the UI. `feat/vis-local-fallback` fixes both (commits after the fix are separable — a reviewer can cherry-pick the two e2e-harness commits to master to unbreak e2e independently of the vis change). The remaining e2e failure `test_delete_node_via_modal` is pre-existing/out-of-scope (needs the `delete-on-doubleclick.js` extension, not loaded by default).
* **Gitignored test symlinks** (above) — a repo-hygiene gap every agent hit.
* **CLI exec-order gotcha** — `cli "clear" -l file` clears *after* load (documented order: connect→load→commands); the fleet recipe documents running `clear` as its own step before `-l`.

---

## What was NOT built (DEFER) — see `../fable/03-improvement-roadmap.md` §DEFER

Click-event broadcast (blocked on SSE — now unblocked by #4, promote next), pre-loaded click actions / mindmap (already ~expressible via hooks), SVG export, rich node/edge content (do as an extension), bulk-load endpoint, server-authoritative actions (large cut; #6's contract test holds the risk), multi-graph rooms / per-user auth, CRDT/op-log, frontend bundler. The fleet **`--watch` live-refresh** and **reverse-direction** (browser→agent) follow-ons are deferred pending diff-application (#2) and click-broadcast.

---

## Provenance

* Fable review + roadmap: `../fable/` (this task dir). Kit adoption + this review live on branch `design/v05-review-and-roadmap`.
* Manager independent verification: re-ran `feat/ws-write-protection` (58 passed) and `feat/collab-resync` (49 passed) suites from clean worktrees — matched reports. Spot-checked review findings F1 + F6 against code before dispatching (both confirmed).
