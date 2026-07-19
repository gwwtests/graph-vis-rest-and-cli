# fable — self-assessment

## Confidence per deliverable

* **01-review.md — HIGH.** All three core artifacts read line-by-line; the two headline findings (F1 read-only WS bypass, F6 uv-shebang bypass breaking TTL) are **empirically verified**, not just read. F2 (broken CDN fallback) is verified by mechanism (dynamically-inserted scripts are async; inline app script runs at parse time) but not by an actual offline browser run — I'd rate it 90% and the acceptance test in roadmap #7 settles it. F18 (title-prop XSS) is explicitly flagged as needs-verification against vis-network 10.
* **02-architecture-assessment.md — HIGH** on the strain diagnosis (dual interpreter, role-less WS, no rev, no persistence — all directly evidenced); **MEDIUM** on the SSE-over-WS recommendation — it's a judgment call trading a second transport for stdlib-CLI simplicity; a reviewer could reasonably prefer a WS hello/role handshake instead.
* **03-improvement-roadmap.md — HIGH** on problem selection and ranking; **MEDIUM** on size estimates (S/M are read-based, not prototyped — #5 SSE and #6 persistence are the most likely to grow; both have crisp fallback scopes). File-lists are from actual line refs, so touch-surface should be accurate. Wave-1 parallelism claim checked against file overlap.
* **04-fleet-ttl-integration-judgment.md — HIGH** on the verdict and the field-mismatch analysis (`rel` vs `label`, `kind` unused, `drift` skipped — all from reading both sides' code). **MEDIUM** on one detail: I did NOT run `fleet_topology_tree.py` (PII gate — it unions the captured live layer), so the exact emitted field set for edge cases (workstream nodes, manager subtrees) is from `_model_nodes_edges` reading only. The committed synthetic fixture in the mini-spec de-risks this.

## What I didn't get to

* Reading converter implementations beyond headers (trusted their per-converter test suites).
* Reading `docs/design/*` bodies — a finding could theoretically be a documented known-limitation (I found no hint of that for the HIGH findings).
* Running the test suite (read-only task; suite is claimed green in repo docs).
* Any browser-level verification (F2 offline behavior, F19 silent-403 UX, vis-network title-tooltip semantics).
* Frontend performance at scale (large-graph physics behavior) — not assessed at all.

## Where I'd want a second opinion before dispatch

1. **Roadmap #1 policy choice:** should visual toggles (`toggle_node`/`toggle_style`) still relay in read-only mode? I recommend yes (view-state, and FUTURE_WORK §2 says hooks "still work for exploration") — but it's Greg's call; it changes the read-only *definition*.
2. **SSE vs WS-role-handshake** for subscribe (#5) — my SSE pick optimizes for the stdlib CLI; if Greg foresees non-Python subscribers preferring WS, decide before dispatch since it shapes the ConnectionManager.
3. **#8's add-edge auto-create** is a behavior change to a public endpoint (dangling-edge 200s become node-creating 200s) — sanity-check no existing extension/e2e relies on dangling edges.
4. **Spot-check invitation:** F1 reproduces in <1 min: set `server_flags["read_only"]=True` under TestClient, send the WS action from `01-review.md`, GET `/api/graph`.

## Process notes

* Constraint compliance: no repo edits outside `out/`+`out-meta/`+`STATUS.md`; no branches/commits; nothing run against a live server; no `pip install` (uv only); captured fleet layer untouched.
* One task-brief nit: TASK.md says CLI is 791 L / index.html 1073 L — confirmed exactly; server is 635 L — confirmed.
