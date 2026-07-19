# 01 — v0.5.0 Review

**Reviewer:** (graphvis:fable) · claude-fable-5 · 2026-07-19
**Scope:** `graph-vis-server.py` (635 L), `graph-vis-cli.py` (791 L), `static/index.html` (1073 L), `tests/` (~410 tests), `e2e/`, `docs/`, converters, `FUTURE_WORK.md`, `AGENTS.md`.
**Method:** full read of the three core artifacts + tests; two headline findings verified empirically (marked ✅ VERIFIED — reproduction included).

---

## Strengths (what v0.5.0 genuinely gets right)

* **The architecture is the right shape for the north star.** REST for mutations → in-memory store → WS broadcast to all browsers is exactly the "any source mutates, everyone sees it" model the effort wants. The mutation flow diagram in `AGENTS.md` matches the code.
* **The CLI is a real agent API.** Stdlib-only client, pipe-first default, positional commands, `-l`/`-s` file round-trips, multiline format blocks (`+++jsonl` etc.) — this is genuinely scriptable, and the 2/3-bare-words shorthand is agent-ergonomic.
* **The converter suite is disciplined.** 10 converters, each a standalone CLI + importable library, each with its own test file (converter tests are the bulk of the ~410-test suite). The lossless-JSONL / lossy-others distinction is documented and honest.
* **Hooks + extensions are a well-designed extensibility seam.** Declarative `on_click`/`on_doubleClick` actions in data, `window.graphVis` extension API, namespaced `ext:<name>:<event>` transport — all documented in `docs/design/` and demonstrated by working examples/demos.
* **The docs are unusually close to the code.** `AGENTS.md`'s API table matches the implemented endpoints; README-per-script convention is followed; QA procedure (`qa/multi-client-collaboration-qa.md`) shows real 3-browser verification was done.
* **Server-side store sync for hook actions** (`_apply_action_to_store`, server:444) — the insight that browser-local actions must be replayed into the store so late-joining clients get correct state is the hard part of multi-client sync, and it's mostly there (see F5 for the gap).

---

## Findings

Severity: **HIGH** = breaks a core promise (collab correctness, agent usability, security) · **MED** = real but survivable · **LOW** = polish.

### A. Correctness / bugs

**F1 · HIGH · Read-only mode is bypassable via WebSocket `action` events** — ✅ VERIFIED
`require_writable()` guards only the REST endpoints (server:34–37, applied at 276, 285, 296, 305, 313, 363). The WS handler (server:524–533) accepts `{"event":"action", ...}` from **any** WS client and calls `_apply_action_to_store()` (server:444) with **no read-only check** — and `add_node`/`remove_node`/`add_edge`/`remove_edge` actions are full mutations. Verified against a live TestClient: REST `add-node` → 403, then the same node added via WS action → present in `/api/graph`.
Reproduction: `out-meta/` notes; script at scratchpad `verify_readonly_bypass.py`. Essence:
```python
server_flags["read_only"] = True
client.post("/api/add-node", ...)          # → 403 ✓
ws.send_json({"event":"action","data":{"action":"add_node","id":"Sneaky"}})
client.get("/api/graph")                   # → Sneaky is in the store ✗
```
Why it matters: read-only mode is advertised (`AGENTS.md`, `FUTURE_WORK.md` §2 "✅ COMPLETED") as "block all mutations". Any WS client (websocat, a script, another browser) mutates anyway — and the mutation is *persisted and rebroadcast*.

**F2 · HIGH · Local vis-network fallback cannot work — offline page is dead**
`index.html:5–7` loads vis-network from CDN with `onerror="loadLocalFallback()"`; the fallback (index.html:123–127) appends a `<script>` element, which browsers load **asynchronously**. The main inline script (index.html:505, `new vis.DataSet()`) executes during parsing, *before* the fallback arrives → `ReferenceError: vis is not defined`, and no code ever re-runs `init()`. The CSS fallback (line 8–10) is fine; the JS one is structurally broken. `static/deps/` exists precisely for this and is never effectively used.
Why it matters: offline/air-gapped/Tailscale-without-internet use — a stated deployment mode — renders a blank page.

**F3 · HIGH · No state re-sync after WS reconnect → silently stale graph**
On WS close the frontend retries every 2 s (index.html:431–435) but **never re-fetches `/api/graph`** on reconnect. Every event during the outage (or a server restart) is lost; the browser keeps rendering a diverged graph with a green "connected" dot. For the live-collab north star this is the worst kind of failure: silent, persistent inconsistency.

**F4 · MED · Snapshot-then-subscribe race at startup**
`init()` (index.html:1039–1068) fetches the graph snapshot **then** calls `connectWebSocket()`. Mutations landing between snapshot and WS-open are lost until manual reload. Same root cause as F3 (no revision/sequence marker on events; no "sync" protocol). Fix both together.

**F5 · MED · `toggle_style` is never applied to the server store**
Frontend executes and relays 8 action types (index.html:767–855, incl. `toggle_style` at 805–820); `_apply_action_to_store` (server:444–502) handles only 7 — `toggle_style` is missing. A relayed `toggle_style` reaches other live browsers but never the store, so late-joining clients get pre-toggle styling. `AGENTS.md` documents all 8 as supported. (Also: the styled-hooks example uses it — `examples/styled-hooks.jsonl`.)

**F6 · HIGH · CLI `.ttl`/`.n3` load AND store are broken on machines without system rdflib** — ✅ VERIFIED
The CLI runs converters as `[sys.executable, script]` (cli:385–388, 429–432, 661–664), which **bypasses the uv shebang**. `ttl2graph.py` and `graph2ttl.py` declare `rdflib` via PEP 723 (`ttl2graph.py:1–5`) and have no fallback. Verified: `python3 -c "import rdflib"` → `ModuleNotFoundError` on this workstation → `Load x.ttl`, `store x.ttl`, and `+++ttl` blocks all fail with "Converter error". The other converters survive only because they're stdlib.
Why it matters: TTL is the ingest format for the fleet-topology integration; the documented `-l examples/web-of-knowledge.ttl` flow does not work.

**F7 · MED · `add-edge` never auto-creates endpoint nodes → dangling edges**
`GraphStore.add_edge` (server:97–107) stores edges without checking node existence; `add_triplet` (server:112) does auto-create. The CLI's documented 2-bare-words shorthand ("`Alice Bob`" → labelless edge, cli:560–571) therefore produces an **invisible** edge on an empty graph (vis-network won't render an edge whose endpoints don't exist), and `/api/graph` snapshots can contain edges referencing absent nodes. Either auto-create endpoints (recommended, consistent with triplets) or reject with 422.

**F8 · MED · `ws_command` assumes `active_connections[0]` is a browser**
server:167–186 sends `capture-screenshot`/`get-dom`/`set-ui` to the *first* WS connection. Any non-browser WS client (websocat per the QA doc, a future `--subscribe` CLI) that connected first will never respond → 10–15 s hang → 503, even though a real browser is connected. This is a latent blocker for the CLI-subscribe roadmap item.

**F9 · LOW · Edge-ID scheme allows silent overwrites and ambiguous IDs**
Auto-ID `f"{from}-{label}-{to}"` / `f"{from}--{to}"` (server:99–103): re-adding the same triplet silently replaces (acceptable idempotency), but IDs are ambiguous when node names contain `-`, and parallel edges with the same label are impossible without explicit ids.

### B. Robustness / error handling

**F10 · HIGH (for agents) · CLI always exits 0, even on total failure**
`GraphClient._request` (cli:84–86) catches `URLError`, prints to stderr, returns `None`; every command then silently no-ops; `main()` has no error accounting. `echo "Alice knows Bob" | ./graph-vis-cli.py` against a dead server → exit 0. Agents and shell scripts (`&&`, `set -e`) cannot detect failure. Same for 403-in-read-only: printed as raw `HTTP Error 403`, exit 0.

**F11 · MED · CLI has no request timeout** — `urlopen` at cli:74 has no `timeout` (screenshot's 20 s at cli:122 is the only one). A hung server hangs the CLI/agent forever.

**F12 · MED · Malformed input crashes the CLI with tracebacks**
`_load_intermediate` does bare `int()` on the converter header (cli:457); `_process_jsonl_lines` does bare `json.loads` and `obj["id"]` (cli:479–489). One bad JSONL line = uncaught exception mid-load (partial load, no summary). Should skip-with-warning and count errors.

**F13 · MED · Zero logging in the server** — no access/mutation/WS-connect logging; WS parse errors swallowed silently (server:543–544). Debugging a live multi-client session is guesswork. Even a `--verbose` uvicorn-logger integration would help.

**F14 · LOW · Serial broadcast** — `ConnectionManager.broadcast` awaits each client in turn (server:148–154); one slow client delays all others *and* the HTTP response of the mutating request. Fine at 3 clients; use `asyncio.gather` when convenient.

**F15 · LOW · Misc**: `remove-edge` broadcasts even when nothing was removed (server:303–308); `do_ui` prints "UI hidden." even on 503 (cli:343–353); `/api/screenshot` doesn't validate `format` and `b64decode` can raise → 500 (server:407–416).

### C. Security

**F16 · MED · No authentication anywhere; default bind `0.0.0.0`** (server:584). Anyone on the LAN can mutate, clear, screenshot, and toggle UI of every connected browser. Acceptable for a trusted-LAN tool, but the north star (agents + humans sharing a graph over Tailscale) deserves at least an optional shared token (`GRAPH_VIS_TOKEN`) on mutations + WS.

**F17 · MED · No Origin check on `/ws` → cross-site WebSocket access**
REST POSTs are implicitly protected by CORS preflight (JSON content-type, no CORS headers configured), but WebSockets are exempt from CORS. Any web page open in any browser on a machine that can reach the server may connect to `/ws` and, via F1's `action` events, mutate the graph (and read all relayed traffic). Checking `Origin` against the server's own host (or the token from F16) closes this.

**F18 · LOW · Unvalidated extras flow into vis-network** — arbitrary JSON props on nodes/edges are stored and rebroadcast (server:277, 298); vis-network's `title` prop historically renders as an HTML tooltip → potential stored XSS from any client able to add nodes. Needs a quick check against vis-network 10 semantics; sanitize or whitelist if confirmed.

### D. API / UX gaps

**F19 · MED · Browser gives no feedback when mutations fail** — none of the `api.*` fetch results are checked (index.html:132–196; input flow 956–976). In read-only mode typing a triplet does nothing, silently (403 swallowed). One toast/status-line would fix all of these at once.

**F20 · MED · `-l FILE -s OUT` from a terminal unexpectedly enters the REPL** — cli:772–776: with no commands and a TTY stdin, `args.repl` is force-set after load/store. The doc example ("Load file, store result", cli:13) implies one-shot. Store-then-REPL surprises scripts run interactively.

**F21 · LOW · Server `--help` can't be discovered from the CLI ecosystem**: `graph/g` prints the whole node/edge list with no size cap (cli:296–306) — unusable on large graphs; no `--json` output mode for `g`/`list` (agents must parse pretty-print or call REST themselves).

**F22 · LOW · No `--version`** on either binary despite `VERSION` file existing (v0.5.0 commit 2510ea2).

### E. Test coverage gaps

**F23 · HIGH-value gap · Read-only mode has zero tests.** No test sets `server_flags["read_only"]` (grep across `tests/` — no hits). The one completed FUTURE_WORK feature is untested, and F1 proves the gap is load-bearing.

**F24 · HIGH-value gap · The WS `action` relay path and `_apply_action_to_store` (≈60 lines, server:444–546) have zero tests.** `tests/test_ws.py` covers broadcast-on-REST only. This is the most intricate logic in the server (toggle cascade semantics, store/browser dual implementation) and the place where F1/F5 live.

**F25 · MED gaps**: no tests for `--ext` extension loading/validation (server:614–633); no CLI error-path tests (server down, converter failure, malformed JSONL, exit codes); no tests for `ws_command` (screenshot/dom happy path with a fake browser WS client); e2e (4 tests) doesn't cover reconnect or read-only.

### F. Docs drift

**F26 · LOW** — server `--help` epilog (server:578–581) says `GRAPH_VIS_INPUT_MODE` default is `multiline`; actual default is `minimal` (server:590–592, `AGENTS.md` agrees on minimal). Epilog also omits `GRAPH_VIS_HOST` and `GRAPH_VIS_READ_ONLY`.
**F27 · LOW** — effort tracking doc (`in/00-effort-tracking-doc.md:38`) describes v0.5.0 as "REST + unix-socket + SSE/WebSocket"; the repo has no unix-socket and no SSE. Drift in the tracking layer, not the repo — but worth correcting so the mgr's mental model matches (SSE appears in this roadmap as a *proposed* item).
**F28 · LOW** — `AGENTS.md` documents `toggle_style` as fully supported (Action Types table) — true in-browser, false server-side until F5 is fixed.

---

## Summary table

| # | Sev | Area | One-liner |
|---|-----|------|-----------|
| F1 | HIGH | security/correctness | WS `action` events bypass read-only (✅ verified) |
| F2 | HIGH | correctness | Local vis-network fallback never works — offline = blank page |
| F3 | HIGH | correctness | No re-sync after WS reconnect → silent stale graph |
| F6 | HIGH | correctness | `.ttl` load/store broken: converters run with `sys.executable`, uv shebang bypassed (✅ verified) |
| F10 | HIGH | agents | CLI exits 0 on every failure |
| F4 | MED | correctness | Snapshot fetched before WS subscribe (startup race) |
| F5 | MED | correctness | `toggle_style` missing from `_apply_action_to_store` |
| F7 | MED | correctness | add-edge allows dangling edges; 2-word CLI shorthand invisible on empty graph |
| F8 | MED | robustness | `ws_command` → `active_connections[0]` assumes browser |
| F11–F13 | MED | robustness | No CLI timeout · CLI crashes on malformed input · zero server logging |
| F16–F17 | MED | security | No auth, `0.0.0.0` default · no WS Origin check |
| F19–F20 | MED | UX | Silent mutation failures in browser · `-l -s` drops into REPL |
| F23–F25 | — | tests | Read-only, action-relay, error paths untested |
| F9, F14, F15, F18, F21, F22, F26–F28 | LOW | — | See above |
