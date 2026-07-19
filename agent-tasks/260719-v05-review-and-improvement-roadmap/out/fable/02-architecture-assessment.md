# 02 — Architecture Assessment

**Reviewer:** (graphvis:fable) · 2026-07-19 · decision-oriented; cross-references findings in `01-review.md` (F-numbers).

## The shape of the system

```
                 REST (mutations, snapshot)          WS (events, actions, cmd/resp)
  CLI/agents ──────────────┐                                ┌────────── Browser × N
  curl/scripts ────────────┤                                │   vis-network DataSets
                           ▼                                ▼   hooks + extensions
                    FastAPI app ── GraphStore (dicts) ── ConnectionManager
                           │              ▲                     │
     converters (subproc) ─┘              └── _apply_action_to_store (WS relay)
```

Six components: **server** (FastAPI, single process, single asyncio loop), **store** (two dicts, no versioning), **WS layer** (broadcast + action relay + command/response), **CLI** (stdlib REPL/pipe client), **converters** (10 standalone subprocess scripts), **frontend** (one 1073-line HTML file: vis-network + hooks + extension loader).

## Seams that are good — keep them

* **REST-mutates / WS-notifies split.** One writer path (`store` methods), one fan-out path (`manager.broadcast`). Every mutation source — browser input, CLI, curl, hook relay — converges on the same store before anyone hears about it. This is the correct spine for the collab north star; don't let features route around it.
* **Converters as subprocess CLIs with a tiny intermediate format.** Isolation of dependencies (rdflib only in the two TTL scripts), independent testability (~340 of the ~410 tests), and the CLI stays stdlib-only. The `Vn En` + `from to label` intermediate is crude but has earned its keep. The only flaw is the *invocation* (`sys.executable` bypasses uv shebangs — F6), not the seam.
* **Extension mechanism.** `window.graphVis` + namespaced `ext:` WS events is a real plugin API with five working extensions and demo scripts. It absorbed features (delete-modal) that would otherwise have bloated core. Rich-node-content ambitions (FUTURE_WORK §3) should land as extensions, not core.
* **Hooks as data.** `on_click` arrays inside node JSON keep interactivity declarative, serializable, and lossless through graph2jsonl. The mindmap/expand-collapse ambitions (FUTURE_WORK §5–6) are mostly *already expressible* here.

## Seams that will strain — and when

**1. The dual action interpreter (will strain immediately).**
Hook actions are implemented twice: `executeAction` in JS (index.html:767) and `_apply_action_to_store` in Python (server:444). They have already diverged (`toggle_style` — F5), and every new action type must be written twice with identical cascade semantics (see the twin toggle_node edge-cascade loops, index.html:776–789 vs server:478–489). **Decision:** accept the duplication but fence it with a shared contract test (same action sequence → same resulting graph state, pytest driving both store and a headless DataSet-equivalent), or move to server-authoritative actions (browser sends intent, server applies + broadcasts result). Server-authoritative is the eventual right answer for the agent north star (agents then get action semantics for free via REST), but it's a bigger cut — the contract test is the build-now move.

**2. The event model has no notion of "since when" (strains at 2+ real users).**
Events carry no revision/sequence number; a client that misses one event can only recover by full re-fetch — and today it never does (F3/F4). A monotonically increasing `rev` on the store, stamped into every broadcast plus `/api/graph`, makes staleness *detectable*; "refetch-on-reconnect + refetch-on-gap" makes it *recoverable*. That's sufficient for this tool's scale for a long time. Op-log replay, offline merge, CRDTs: firmly out of scope — the single-server in-memory store IS the conflict resolution.

**3. WS connections are role-less (strains the moment CLI-subscribe ships).**
`ws_command` sends browser-only commands to `active_connections[0]` (F8); the action relay trusts every socket equally (F1). There's no handshake distinguishing *browser* / *subscriber* / *controller*. Two escape paths: (a) add a hello message + role registry on `/ws`; (b) give subscribers a different transport entirely — **SSE** (`GET /api/events`). SSE is the better move: it keeps `/ws` browsers-only by convention, is trivially consumable from the stdlib CLI (urllib streaming) and `curl`, and sidesteps writing a WS client without dependencies. Recommended: SSE for outbound event streaming; `/ws` remains the browser channel.

**4. Persistence: the store is a process lifetime (strains at first accidental Ctrl-C).**
Everything dies with the process; the CLI's `store`/`Load` is manual compensation. For a tool whose graphs are increasingly *worth keeping* (fleet topology, shared annotation sessions), snapshot persistence — `--load FILE` at boot + debounced JSONL autosave — is cheap because graph2jsonl is already lossless. A database is unjustified; a JSONL file is greppable, diffable, git-able, and matches the converter ecosystem.

**5. Trust model: none (strains the moment the bind address isn't a trusted LAN).**
No auth, no WS origin check, read-only enforced on only one of two mutation paths (F1, F16, F17). The tool's honest posture today is "anyone who can reach the port owns the graph." That posture is fine *if stated*, but read-only mode currently promises more than it delivers. Minimum viable trust: enforce read-only on the WS path (bug fix), optional `GRAPH_VIS_TOKEN` shared secret on mutations + WS connect, and an Origin allow-list. Multi-user identity, per-user permissions, multi-graph rooms: DEFER — no current use case needs them, and rooms would ripple through every endpoint, the CLI, and the frontend.

**6. The frontend monolith (strains slowly; tolerable).**
1073 lines of inline JS in one HTML file: HighlightManager, WS client, action executor, screenshot rig, input modes, extension loader. It's still navigable and has zero build tooling — a genuine virtue for this project. Don't introduce a bundler; do consider splitting into `/static/js/*.js` modules loaded by plain `<script>` tags when the file next grows materially. Not build-now.

## Consequences for the roadmap

Ordered by architectural leverage:

1. **Close the WS trust gap** (F1 + F17 + optional token) — makes the existing read-only promise true; prerequisite for exposing the server beyond localhost.
2. **Introduce `rev` + resync protocol** (F3/F4) — the smallest change that makes multi-client state *provably* convergent.
3. **SSE event stream** — unlocks CLI subscribe (FUTURE_WORK §1) and click monitoring (§4) without touching the role-less-WS problem.
4. **Fix converter invocation** (F6) — restores the TTL path; hard prerequisite for the fleet-topology integration (see `04-…judgment.md`).
5. **Snapshot persistence** — turns the server from a demo into a tool you can trust with real graphs.
6. **Agent-grade CLI errors** (F10/F11) — exit codes + timeouts; agents are first-class users and currently fly blind.

Everything else in `FUTURE_WORK.md` (SVG export, rich nodes, pre-loaded actions, mindmap) builds *on top of* these and should wait behind them.
