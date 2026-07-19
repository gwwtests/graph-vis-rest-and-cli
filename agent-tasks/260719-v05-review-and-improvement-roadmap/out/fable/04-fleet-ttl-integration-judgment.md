# 04 — Fleet-TTL Integration Judgment

**Author:** (graphvis:fable) · 2026-07-19
**Question:** wire `tracking/ttl` fleet-topology (via `fleet_topology_tree.py`) into graph-vis as a live data source — build now, and if so what's the thinnest valuable slice?

## Verdict: **BUILD-NOW — the thin slice (one-shot adapter + recipe + demo). DEFER live-refresh and any dedicated endpoint.**

## Grounding — what already connects (verified by reading both codebases)

The pipe is *almost* free because both sides already speak JSONL:

* `fleet_topology_tree.py -F jsonl` emits one JSON object per line: `{"type":"node", ...}`, `{"type":"edge", ...}`, `{"type":"drift", ...}` (`render_jsonl`, fleet script :315–320; node/edge shapes from `_model_nodes_edges` :263–303).
* `graph-vis-cli.py -l file.jsonl` loads JSONL **directly** (no converter subprocess — cli:367–369, `_process_jsonl_lines` cli:471–500), passing unknown fields through as vis-network extras and **silently skipping unknown `type` values** — so `"drift"` lines are harmlessly ignored today.

Three concrete mismatches (this is the entire integration gap):

1. **Edges carry `rel`, not `label`** (fleet :271 `{"rel":"oversees","from":lead,"to":...}`) → CLI loads them with empty labels; `rel` rides along as an invisible extra. One rename fixes the whole visual.
2. **Nodes carry `kind`** (`lead`/`coord`/`session`/`manager`/`subteam`/`worker`/`terminated`/`workstream`) and status flags (`alive`, `stale`, `uncovered`) → passed through unused, though they're perfect styling drivers (color/shape per kind — instantly readable topology).
3. **`drift` records are dropped** — acceptable for v1 (they're annotations, not topology).

Also relevant: the `.ttl` route (`fleet_topology_tree.py -F ttl` → CLI ttl2graph) is **currently broken** by finding F6 (uv-shebang bypass, no system rdflib) — one more reason the JSONL route is the right slice, and why roadmap item #3 is a sibling fix rather than a blocker.

## Why build now (and why only the thin slice)

* **It's the effort's own stated integration candidate** with a real recurring consumer: fleet agents/managers already render this graph for sanity checks; a live shared web view is its natural evolution (the tracking doc says exactly this).
* **Leverage/effort is exceptional:** the gap is a ~40-line field-mapping adapter plus documentation. It also *exercises* the product exactly along the north-star axis (agent-produced graph → shared browser view) and will surface real UX feedback (e.g. layout quality on tree-ish graphs) cheaply.
* **Why not more:** a `--watch` live loop today would be clear+reload every N seconds — flicker, layout reset, and it papers over missing primitives (diffing needs #2's rev/resync thinking; persistence #6; SSE #5 for the reverse direction). A dedicated server-side adapter endpoint would couple this repo to uberclaude-gw's schema — wrong direction; keep the fleet-specific knowledge in a converter-shaped script at the boundary, like every other format.
* **PII gate respected:** the renderer unions declared + captured layers from `tracking/ttl/`; the recipe must document testing against the **declared sample** (`fleet-topology.ttl` + `schema.ttl`) and note that rendering captured live-session data into a *shared* browser view is the operator's call (the graph-vis server may be LAN-visible — cross-ref F16).

## Mini-spec — `feat/fleet-jsonl-adapter` (Size S)

* **Slug:** `feat/fleet-jsonl-adapter` · rank: wave-2, independent of all other items.
* **Problem:** `fleet_topology_tree.py -F jsonl` output loads into graph-vis with no labels and no styling; no documented recipe exists.
* **Change:**
  1. New converter-style script `scripts/converters/fleetjsonl2graph/fleetjsonl2graph.py` (stdlib, stdin→stdout, README per repo convention): maps `rel`→`label`; maps `kind`→vis styling (suggested: lead=gold box, coord=blue ellipse, session=green dot, manager=purple, subteam/workstream=gray box, worker=teal, terminated=red ✕); `stale:true`/`alive:false` → dashed border/muted color; `drift` lines → either skipped (default) or `--drift` flag renders them as red annotation nodes attached to their subject. Output: graph-vis JSONL (`{"type":"node"|"edge", ...}` with styling extras) — i.e. it's JSONL→JSONL enrichment, loadable via `-l` or `+++jsonl`.
  2. Recipe doc `docs/recipes/fleet-topology-live-view.md`: one-shot pipeline
     ```bash
     fleet_topology_tree.py -F jsonl | fleetjsonl2graph.py > /tmp/claude/fleet.jsonl
     ./graph-vis-cli.py "clear" -l /tmp/claude/fleet.jsonl
     ```
     plus a crude-but-honest refresh loop (`watch`/`while sleep 30`) documented as interim until DEFER items land, plus the PII note above.
  3. Demo `examples/demos/fleet-topology-demo.sh` using a **committed synthetic fixture** `examples/fleet-topology-sample.jsonl` (derived from the declared-layer sample shapes, fictional names) so the demo runs without uberclaude-gw present.
* **Likely files:** `scripts/converters/fleetjsonl2graph/` (new: script + README + `tests/` or `tests/test_fleetjsonl2graph.py` in repo tests dir), `examples/fleet-topology-sample.jsonl`, `examples/demos/fleet-topology-demo.sh`, `docs/recipes/fleet-topology-live-view.md`, `AGENTS.md` (converter table row).
* **Acceptance:**
  ```bash
  PYTHONPATH=. pytest tests/test_fleetjsonl2graph.py -v -p no:playwright --noconftest
  ./graph-vis-server.py & sleep 2
  ./graph-vis-cli.py "clear" -l <(python3 scripts/converters/fleetjsonl2graph/fleetjsonl2graph.py < examples/fleet-topology-sample.jsonl) "g" \
    | grep -q "nodes"   # labels present: grep an expected edge label e.g. "coordinates"
  ```
  (If process-substitution is awkward for `-l`, write to a temp file — implementer's choice; the test must assert edges carry non-empty labels and nodes carry color/shape extras.)
* **Dependencies:** none hard. Sibling fix #3 (`feat/converter-shebang-exec`) restores the alternative `.ttl` route. Future value multiplies with #6 (persistence) and #5 (SSE) — see DEFER.

## DEFERRED follow-ons (named so they aren't forgotten)

* **`--watch` live refresh** — needs diff-application (add/remove deltas, not clear+reload) to avoid layout resets; design it after #2 (rev) exists and after the one-shot slice teaches us the real refresh cadence. A "clear+reload" watch mode is documented in the recipe as an honest interim.
* **Reverse direction** (browser clicks on fleet nodes → agent actions, e.g. "focus this session") — blocked on click-event broadcast, which is blocked on #5 (SSE).
* **Dedicated `/api/sources/fleet` adapter endpoint** — wrong coupling direction; revisit only if the one-shot recipe proves too clunky in daily use.
* **Rendering the captured/live layer routinely** — operator/PII decision, not an engineering task; the recipe documents the boundary.
