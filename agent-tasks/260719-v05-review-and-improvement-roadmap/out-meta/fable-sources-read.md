# fable — sources actually read (coverage record)

**Read in FULL (every line):**

* `TASK.md` (task dir)
* `in/00-effort-tracking-doc.md` (70 L — vision, status, integration candidates, constraints)
* `in/FUTURE_WORK.md` (206 L — all 7 backlog sections)
* `in/graph-vis-server.py` = `graph-vis-server.py` (635 L)
* `in/graph-vis-cli.py` = `graph-vis-cli.py` (791 L)
* `in/index.html` = `static/index.html` (1073 L)
* `tests/conftest.py` (27 L)

**Read in targeted part (sections / greps, with line refs where used in findings):**

* `fleet_topology_tree.py` — header+docstring+AGENT_HELP (:1–120), `render_jsonl` (:315–320), `_model_nodes_edges` (:263–303), format map (:430), renderer dispatch (:503)
* `fleet_topology_tree.py.README.md` — first 40 L (scope/philosophy, declared-vs-captured union)
* `scripts/converters/jsonl2graph/jsonl2graph.py` — docstring + `convert()` head (:1–60)
* `scripts/converters/ttl2graph/ttl2graph.py` — shebang/PEP723 header (:1–20) — basis of F6
* `scripts/converters/graph2ttl/graph2ttl.py` — header (:1–15)
* `tests/test_api.py`, `tests/test_ws.py`, `tests/test_cli.py`, `tests/test_extensions.py` — full `def test_` inventory (94 names) + grep for `read_only`/`action` coverage (none found → F23/F24)
* `e2e/test_e2e.py` — first 40 L + test inventory (4 tests)
* `qa/multi-client-collaboration-qa.md` — first 50 L (method + tooling; notes websocat as a WS client → feeds F8)
* Repo `AGENTS.md` — full (provided in context)
* Directory listings: `docs/design/`, `docs/plans/`, `examples/`, `examples/demos/`, `scripts/converters/`, `qa/`, `e2e/`; `git log --oneline -15`

**Executed (read-only / scratchpad only):**

* `verify_readonly_bypass.py` (scratchpad) via `uv run --with fastapi…` → **F1 CONFIRMED** (REST 403, WS action mutates store)
* `python3 -c "import rdflib"` → ModuleNotFoundError → **F6 confirmed live** on this workstation
* Various `grep`/`ls`/`wc`/`sed` inspections (no repo mutation; no live server started; no fleet renderer executed — PII gate: did not touch `tracking/ttl` captured layer)

**Explicitly NOT read (and impact):**

* `docs/design/*.md` and `docs/plans/*.md` bodies (titles only) — findings are grounded in code, not design intent; risk: a finding may be a documented known-limitation. Spot-checked none.
* Converter implementations other than jsonl2graph/ttl2graph headers — their ~340 tests pass per repo docs; low risk.
* `in/fleet-schema.ttl` / `in/fleet-topology-declared.ttl` bodies — judgment grounded in the renderer's emitted JSONL shape instead (the actual integration surface).
* `qa/cdp_eval.py`, `manage`, `e2e/Dockerfile`, `docs/tutorial/`.
