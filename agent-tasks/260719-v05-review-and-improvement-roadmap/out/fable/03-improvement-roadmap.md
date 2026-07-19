# 03 — Improvement Roadmap (BUILD-NOW / DEFER triage)

**Author:** (graphvis:fable) · 2026-07-19
**Contract:** each BUILD-NOW item is solo-implementable by one opus agent on `feat/<slug>`, with a runnable acceptance check. F-numbers reference `01-review.md`. Dispatch order = list order; the **Parallel dispatch guide** at the bottom shows what can run concurrently.

---

## BUILD-NOW (8 items, ranked by leverage ÷ effort)

### 1. `feat/ws-write-protection` — enforce read-only + optional token on the WS path
**Size S · leverage: makes an advertised guarantee true · fixes F1, F17, part of F16**

* **Problem:** WS `action` events mutate the store even in `--read-only` (✅ verified); `/ws` has no Origin check, so any web page reachable to the host can mutate cross-site.
* **Change:**
  * In the WS handler (server:524–533): if `server_flags["read_only"]`, drop mutation actions (`add_node`, `remove_node`, `add_edge`, `remove_edge`, `restyle`) — do not apply, do not relay; optionally reply `{"error":"read-only"}`. Decide + document whether visual toggles (`toggle_node`/`toggle_edge`/`toggle_style`) still relay (recommend: yes, they're view-state; document it).
  * Add optional `GRAPH_VIS_TOKEN` (env + `--token`): when set, require `Authorization: Bearer <t>` on mutation REST endpoints and `?token=<t>` on `/ws` connect (403/close otherwise). When unset, behavior unchanged.
  * Check WS `Origin` header: if present and not same-host (or in `GRAPH_VIS_ALLOWED_ORIGINS`), reject. Frontend passes token from a `/api/config` field or query param — keep minimal: same-origin browsers get it via a small `GET /api/config` (returns `{token_required: bool}`; the human pastes token into a prompt only when required).
* **Files:** `graph-vis-server.py` (WS handler, arg parsing), `static/index.html` (WS connect URL, optional token prompt), `tests/test_ws.py`, `tests/test_api.py`, `AGENTS.md`.
* **Acceptance:**
  ```bash
  PYTHONPATH=. pytest tests/test_ws.py tests/test_api.py -v -p no:playwright -k "read_only or token or origin"
  # must include: WS action in read-only does NOT appear in /api/graph (regression test for F1)
  ```
* **Deps:** none.

### 2. `feat/collab-resync` — revision counter + reconnect/startup resync
**Size S · leverage: silent-divergence class of bugs eliminated · fixes F3, F4**

* **Problem:** browser fetches snapshot before subscribing, and never re-fetches after WS reconnect → silently stale graphs.
* **Change:**
  * Server: add `store.rev` (int, incremented on every mutation incl. WS-relayed actions); include `"rev"` in every broadcast event and in `GET /api/graph`.
  * Frontend: connect WS **first**, buffer incoming events; then fetch snapshot; apply snapshot, then replay buffered events with `rev >` snapshot rev. On `ws.onopen` after a disconnect: re-fetch snapshot and reconcile (simplest correct: clear DataSets + reload, preserving viewport via `network.getViewPosition`/`moveTo`). If an incoming event's `rev` skips a number, trigger the same resync.
* **Files:** `graph-vis-server.py` (store + broadcast + `/api/graph`), `static/index.html` (`init()`, `connectWebSocket`, `handleWsEvent`), `tests/test_api.py` (rev increments), `tests/test_ws.py` (rev in events), `e2e/test_e2e.py` (optional: kill/restart server, assert graph reappears).
* **Acceptance:**
  ```bash
  PYTHONPATH=. pytest tests/ -v -p no:playwright -k "rev or resync"
  # manual/e2e: start server, open browser, stop server, mutate nothing, restart with --load, browser shows reloaded graph within ~4s
  ```
* **Deps:** none (merge before or after #1; touches different server regions, minor conflict risk in index.html with #1).

### 3. `feat/converter-shebang-exec` — run converters via their shebangs, not `sys.executable`
**Size S · leverage: unbreaks the whole TTL path, prerequisite for fleet integration · fixes F6**

* **Problem:** CLI invokes converters with `[sys.executable, script]` (cli:385, 429, 661), bypassing PEP 723 uv shebangs → `.ttl`/`.n3` load/store fails wherever rdflib isn't in system python (✅ verified on this workstation).
* **Change:** single helper `run_converter(script_path, argv, input_text)` used by all three call sites: if the script is executable, run `[script_path, ...]` directly (shebang: `uv run` resolves deps); else fall back to `[sys.executable, script_path, ...]`. Propagate stderr on failure. Bump timeout to 60 s for first-run uv resolution; print a one-line "resolving deps via uv…" hint on slow start (optional).
* **Files:** `graph-vis-cli.py` (do_Load, do_store, `_flush_converter`), `tests/test_cli.py` (mock-level test that the invocation prefers the script itself; a skipif-uv-missing integration test loading `examples/web-of-knowledge.ttl`).
* **Acceptance:**
  ```bash
  python3 -c "import rdflib" 2>&1 | grep -q ModuleNotFoundError  # precondition on this machine
  ./graph-vis-server.py & sleep 2
  ./graph-vis-cli.py -l examples/web-of-knowledge.ttl "g" | grep -q "nodes"   # loads via uv shebang
  ./graph-vis-cli.py "store /tmp/claude/out.ttl" && head -3 /tmp/claude/out.ttl
  ```
* **Deps:** none.

### 4. `feat/cli-agent-ergonomics` — exit codes, timeouts, and `--json` output
**Size S · leverage: agents are first-class users and currently fly blind · fixes F10, F11, F20, F21 (partial)**

* **Problem:** CLI exits 0 on every failure; no request timeout (hangs forever); `-l X -s Y` from a TTY drops into the REPL; no machine-readable output for `g`/`list`.
* **Change:**
  * `GraphClient._request`: `timeout=` (default 10 s, `--timeout` flag + `GRAPH_VIS_TIMEOUT` env); distinguish HTTP errors (print status + detail body, e.g. the 403 read-only message) from connection errors.
  * Track failures on the REPL/client (counter); `main()` exits 1 if any command/load/store failed, 2 on connect-refused for *all* requests. Document codes in the docstring.
  * Non-interactive mode: `-l`/`-s` without commands and without `--repl` should NOT enter the REPL — run steps and exit (keep REPL only for explicit `--repl` or bare TTY invocation with no work to do).
  * Add `--json` flag: `graph`/`list` emit the raw `/api/graph` JSON (or JSONL lines) to stdout for piping.
* **Files:** `graph-vis-cli.py`, `tests/test_cli.py` (exit-code tests with a dead port; `--json` shape test), `graph-vis-cli.README.md`.
* **Acceptance:**
  ```bash
  echo "Alice knows Bob" | GRAPH_VIS_PORT=1 ./graph-vis-cli.py; test $? -ne 0
  ./graph-vis-cli.py --json "g" | python3 -c "import sys,json; json.load(sys.stdin)"
  PYTHONPATH=. pytest tests/test_cli.py -v -p no:playwright --noconftest
  ```
* **Deps:** none. (Coordinate with #3 — both touch `graph-vis-cli.py`; dispatch to the same agent or sequence them.)

### 5. `feat/sse-subscribe` — server-sent-events stream + CLI `--subscribe`
**Size M · leverage: ⭐ FUTURE_WORK §1, the agent-reactive foundation · designed around F8**

* **Problem:** no way to observe graph changes from the CLI/scripts; a stdlib WS client is impractical, and letting subscribers join `/ws` would break `ws_command`'s browser assumption (F8).
* **Change:**
  * Server: `GET /api/events` — SSE endpoint (`text/event-stream`). Each broadcast event is also written to all SSE subscribers (`data: {"event":...,"data":...,"rev":...}\n\n`). Implement as an `asyncio.Queue` per subscriber registered in the ConnectionManager (or a sibling `SseManager`); heartbeat comment every 15 s; drop-on-slow (bounded queue) so one stuck consumer can't leak memory. Keep `/ws` untouched (browsers only).
  * CLI: `--subscribe [--format jsonl|human]` — stdlib `urllib.request` streaming read loop, printing one event per line (jsonl = raw; human = `+ node Alice`, `- edge A-knows-B`, …). Runs after `-l`/commands; Ctrl-C exits 0. `--subscribe` implies no REPL.
* **Files:** `graph-vis-server.py` (SSE endpoint, broadcast fan-out), `graph-vis-cli.py` (subscribe loop, formatting), `tests/test_api.py`/new `tests/test_sse.py` (TestClient streaming: mutate → event received), `tests/test_cli.py` (formatting unit tests), `AGENTS.md`, `graph-vis-cli.README.md`, `FUTURE_WORK.md` (§1 → done).
* **Acceptance:**
  ```bash
  PYTHONPATH=. pytest tests/test_sse.py -v -p no:playwright
  # live: ./graph-vis-server.py &  ./graph-vis-cli.py --subscribe --format jsonl > /tmp/claude/ev.jsonl &
  #       echo "Alice knows Bob" | ./graph-vis-cli.py && sleep 1 && grep -q add-triplet /tmp/claude/ev.jsonl
  ```
* **Deps:** benefits from #2's `rev` (include it if merged; not blocking). Unlocks DEFER item "click-event-broadcast".

### 6. `feat/server-persistence` — `--load` at boot + debounced JSONL autosave
**Size M · leverage: graphs stop being process-lifetime · addresses arch strain §4**

* **Problem:** server restart loses everything; graphs are becoming worth keeping (fleet topology, annotation sessions).
* **Change:**
  * `--load FILE` (repeatable, env `GRAPH_VIS_LOAD`): at startup parse JSONL (same node/edge/triplet semantics as the CLI's `_process_jsonl_lines` — implement server-side, no HTTP) into the store. Non-JSONL formats: out of scope (users convert first).
  * `--autosave FILE` (env `GRAPH_VIS_AUTOSAVE`): on every mutation (REST + WS actions), schedule a debounced (~2 s) async write of lossless JSONL (reuse `graph2jsonl` logic — import it or re-emit inline; it's stdlib). Atomic write (tmp + rename). `--autosave` alone implies `--load` of the same file if it exists (the obvious "just persist" mode).
* **Files:** `graph-vis-server.py` (arg parsing, loader, debounced saver hooked into broadcast path), new `tests/test_persistence.py` (load-at-boot via store inspection; autosave file appears + round-trips), `AGENTS.md`.
* **Acceptance:**
  ```bash
  PYTHONPATH=. pytest tests/test_persistence.py -v -p no:playwright
  # live: ./graph-vis-server.py --autosave /tmp/claude/g.jsonl &  echo "A b C" | ./graph-vis-cli.py
  #       kill server; restart same cmd; curl -s :7849/api/graph | grep -q '"A"'
  ```
* **Deps:** none hard; pairs naturally with #2 (rev could persist too — optional).

### 7. `feat/vis-local-fallback` — make the offline fallback actually boot the app
**Size S · leverage: offline/air-gapped deployments work · fixes F2**

* **Problem:** CDN failure leaves `vis` undefined when the inline script runs; the dynamically-appended fallback loads too late; app is dead offline.
* **Change:** restructure boot: wrap all vis-dependent code in a `startApp()` invoked by a tiny loader that (a) checks `window.vis` after the CDN tag, (b) if missing, injects the local script and calls `startApp()` from its `onload`, (c) surfaces a visible error only if both fail. Simplest robust form: `<script>` CDN → `<script>if(!window.vis)document.write('<script src="/static/deps/vis-network.min.js"><\/script>')</script>` → app script (document.write of a script during parsing IS synchronous — ugly but bulletproof); or the async-loader + `startApp()` refactor (cleaner, slightly larger diff). Implementer's choice; must keep zero build tooling. Verify `static/deps/vis-network.min.js` is actually the full standalone UMD build.
* **Files:** `static/index.html`, `e2e/test_e2e.py` (new test: load page with CDN blocked — e.g. Chrome `--host-resolver-rules="MAP cdnjs.cloudflare.com 127.0.0.1"` — assert canvas renders and a triplet can be added).
* **Acceptance:**
  ```bash
  ./manage test   # e2e including new offline test
  ```
* **Deps:** none. Conflicts (same file) with #1/#2's index.html edits — dispatch after they merge, or accept a small rebase.

### 8. `feat/store-action-parity` — `toggle_style` in the store + a JS/py action contract test
**Size S · leverage: closes the known divergence and fences future ones · fixes F5, F24, part of F7**

* **Problem:** `_apply_action_to_store` misses `toggle_style` (late-joiners see wrong styles); the dual JS/python action interpreters have zero shared tests; add-edge permits dangling edges.
* **Change:**
  * Implement `toggle_style` server-side (store `_original_style` on the item, swap like index.html:805–820).
  * Auto-create missing endpoint nodes in `GraphStore.add_edge` (matching `add_triplet` semantics) — fixes the invisible 2-word-shorthand edge; broadcast the created nodes (extend the `add-edge` event payload with `"nodes":[...]`, frontend applies them like `add-triplet` does).
  * New `tests/test_actions.py`: table-driven — for each documented action type, apply via WS relay and assert resulting `/api/graph` state (this is the store side of the contract; note in the test docstring that index.html implements the same semantics — full JS-side automation stays in e2e).
* **Files:** `graph-vis-server.py` (`_apply_action_to_store`, `GraphStore.add_edge`, add-edge endpoint payload), `static/index.html` (handle `nodes` in add-edge event), `tests/test_actions.py`, `AGENTS.md` (add-edge auto-create note).
* **Acceptance:**
  ```bash
  PYTHONPATH=. pytest tests/test_actions.py -v -p no:playwright
  # includes: relay toggle_style via WS → new TestClient GET /api/graph reflects toggled style
  # includes: POST /api/add-edge {"from":"X","to":"Y"} → nodes X,Y exist in /api/graph
  ```
* **Deps:** merge after #1 (both edit the WS handler region).

---

## Fleet-TTL integration item

**#9 `feat/fleet-jsonl-adapter` (Size S)** — judged BUILD-NOW as a thin slice; full mini-spec in `04-fleet-ttl-integration-judgment.md`. Depends on nothing above (works today via the CLI JSONL path); `--watch` variants benefit from #6/#5.

---

## Parallel dispatch guide

* **Wave 1 (fully parallel, 5 agents):** #1, #2, #3+#4 (one agent, same file), #5, #6
* **Wave 2 (after wave 1 merges):** #7 (index.html rebased), #8 (after #1), #9 (anytime; independent repo surface)
* Merge order within wave 1 is flexible; #1 and #2 both touch `index.html` lightly — merge #2 first (bigger frontend diff), rebase #1.

---

## DEFER (with one-line reasons)

| Candidate | Reason to defer |
|---|---|
| **Click-event broadcast** (FUTURE_WORK §4) | S-sized and valuable, but depends on #5 (SSE) — promote to build immediately next cycle once #5 merges. |
| **Pre-loaded click actions** (FW §5) | Already ~expressible via `on_click` hooks + `add_node`/`toggle_node` actions (see `examples/mindmap.jsonl`); revisit only if hooks prove insufficient. |
| **Mindmap / expand-collapse** (FW §6) | Same — `examples/mindmap.jsonl` already demonstrates it; polish belongs after click monitoring exists. |
| **SVG export** (FW §0) | Pure exploration; raster screenshot works; no current consumer of vector output. |
| **Rich node/edge content** (FW §3) | Should be prototyped as an *extension* (images/links via extras already pass through), not core; no concrete use case yet. |
| **Bulk-load REST endpoint** | Current per-edge POST loading is fine at present graph sizes (~10²); revisit at >10³ edges or if fleet graphs grow. |
| **Server-authoritative actions** (kill the dual interpreter) | Right long-term (arch §1) but a large cut across server+frontend; #8's contract test contains the risk meanwhile. |
| **Multi-graph rooms / per-user identity & permissions** | No current use case; ripples through every endpoint, CLI, frontend; token (#1) covers today's trust needs. |
| **Op-log / CRDT sync** | Single-server in-memory store + rev resync (#2) is sufficient conflict handling at this scale. |
| **WS client in CLI (instead of SSE)** | Would require a non-stdlib dep or a hand-rolled WS impl; SSE delivers the same value cheaper. |
| **Frontend modularization / bundler** | index.html is still navigable; zero-build is a feature; split into plain JS files only when it next grows materially. |
| **Logging/observability overhaul** (F13) | Fold minimal mutation+WS logging into whichever wave-1 item touches the server first (suggest #1); a dedicated item isn't warranted. |
| **Docs-drift fixes** (F26–F28) | One-line fixes; fold into the items touching those files (#1 → AGENTS.md read-only note; #3/#4 → CLI README; #6 → server epilog). |
