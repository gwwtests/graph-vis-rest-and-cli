# TASK — v0.5.0 review → implementable improvement roadmap

**Dispatched by:** `(graphvis:mgr)` — the effort manager for this repo (reports to `ubertmux-adm`).
**You are:** `(graphvis:fable)` — `claude-fable-5`, high effort. The **sole reviewer/architect/judge** for this pass.
**Date:** 2026-07-19 · **Mode:** **propose + judge, don't build.** Design docs only. Do **NOT** edit live code, do **NOT** create branches, do **NOT** run mutating git. Read-only on the repo except your own `out/` + `out-meta/`.
**Your cwd** is the live repo root (`graph-vis-rest-and-cli`, working v0.5.0). Explore it freely, read-only.

---

## Goal (one sentence)

Review the working v0.5.0 graph-vis server + CLI + WebUI, and produce a **prioritized, implementable improvement roadmap** — where each top improvement is scoped tightly enough that one opus agent can implement it on its own `feat/*` branch — **plus a reasoned judgment on whether/how to wire in the `tracking/ttl` fleet-topology graph as a live data source.**

---

## Why this exists (the compass — read before proposing)

This effort (`00-effort-tracking-doc.md`) has a clear north star: a **live, collaborative graph web-UI viewable across browsers**, with **programmatic CLI/agent access** as the ⭐ key feature (agents drive/annotate a shared graph). v0.5.0 already delivers a lot of this. So the review's job is **not** to redesign from scratch — it is to find **the highest-leverage next improvements** to an already-working tool, and to name honestly what is **not worth building yet.**

Every proposal you make MUST be triaged into one of two buckets (this triage is a required section):

* **BUILD-NOW** — improves the core value (live collab graph + CLI/agent API + robustness/correctness) at good leverage-per-effort. Rank by leverage/effort.
* **DEFER** — intellectually interesting but doesn't move the core value now. Naming these honestly is as valuable as the build list.

The deliverable preference from Greg is **implemented branches > a design-only doc.** Your roadmap is the input the opus implementation team will build from — so **scope each BUILD-NOW item as a buildable unit** (see Deliverables).

---

## Context — read these first (all under `in/`, symlinks to live files)

1. **`in/00-effort-tracking-doc.md`** — the effort's vision, status, integration candidates, constraints. Read first.
2. **`in/AGENTS.md`** — the repo's own architecture doc: REST/WS API table, hooks, extensions, converters, multi-client collab, read-only mode, CLI reference. The single best map of what exists.
3. **`in/FUTURE_WORK.md`** — the repo's **own backlog** (SVG export, CLI subscribe mode, rich node/edge content, click-event monitoring, pre-loaded click actions, mindmap/expand-collapse). Weigh these; they are candidate BUILD-NOW items but you are not bound to them — propose better ones if you see them.
4. **`in/graph-vis-server.py`** (635 L), **`in/graph-vis-cli.py`** (791 L), **`in/index.html`** (1073 L) — the three core artifacts. Read for real (correctness, robustness, security, API/UX gaps). The full test suite is in `tests/` (your cwd) — read it to see what is and isn't covered.
5. **`in/docs/`** — design + plan docs (hooks, extensions, transport protocol, screenshot/dom).

### Integration candidate (JUDGE THIS — it is a required deliverable, not optional)

The effort tracking doc calls out wiring the **fleet-topology RDF graph** in as a **real live data source**:

* **`in/fleet_topology_tree.py`** (+ `.README.md`) — a pure renderer that reads `tracking/ttl/*.ttl` and prints tree / json / jsonl / **ttl** / **mermaid** / **graphviz**. Note: this app already **ingests** mermaid, dot, ttl, jsonl. So there is a plausible pipe: `fleet_topology_tree.py -F jsonl | graph-vis-cli.py`.
* **`in/fleet-schema.ttl`** — the fleet ontology (coordination edges: coordinates / hasManager / manages / servesWorkstream / Lead, plus live-session nodes).
* **`in/fleet-topology-declared.ttl`** — the human-owned declared coordination layer (sample data). (Live machine-captured sessions are intentionally NOT provided here — PII gate.)

**Judge:** is wiring this in as a live source worth doing now, and if so, **what is the thinnest valuable slice** (e.g. a one-shot `fleet_topology_tree.py -F jsonl | cli` recipe + doc? a `--watch` live-refresh loop? a dedicated adapter endpoint?) — vs. DEFER with reasons. Ground the judgment in what already exists (the converters + CLI load path), not a green field.

---

## Deliverables — write ONLY to `out/fable/` and `out-meta/`

Write these files to **`out/fable/`**:

1. **`01-review.md`** — the review proper. Strengths; then **concrete findings** grouped as *correctness/bugs · robustness/error-handling · security · API/UX gaps · test coverage gaps · docs drift*. Every finding: file:line where possible, why it matters, severity. Be specific and honest — this is the value.
2. **`02-architecture-assessment.md`** — the shape of the system (server / store / WS / CLI / converters / extensions / frontend). Where the seams are good, where they'll strain as it grows (esp. toward the live-collab + agent-API north star: concurrency, persistence, auth/multi-graph, event model). Keep it decision-oriented.
3. **`03-improvement-roadmap.md`** — **THE key deliverable.** A BUILD-NOW / DEFER triage. For **each BUILD-NOW item**, a scoped mini-spec an opus agent can implement solo on a `feat/<slug>` branch:
   * `slug` (kebab, → `feat/<slug>`), one-line title, leverage/effort rank
   * problem + proposed change (concrete)
   * **likely files to touch**
   * **acceptance test / command** the implementer (and I) can run to verify it works
   * dependencies on other items (so I can order/parallelize)
   * rough size (S/M/L)
   Order the list so I can pick the top N to dispatch in parallel. Aim for **~5–8 well-scoped BUILD-NOW items** (quality over quantity) + a DEFER list with one-line reasons.
4. **`04-fleet-ttl-integration-judgment.md`** — the required integration judgment (above): build-now-thin-slice vs defer, with reasoning and, if build, the scoped mini-spec (same shape as a roadmap item).

Write to **`out-meta/`**:

* `fable-sources-read.md` — what you actually read (files, key line ranges) so I can trust coverage.
* `fable-self-assessment.md` — confidence per deliverable, what you didn't get to, where you'd want a second opinion.

---

## Return protocol

* When done, update **`STATUS.md`** (in this task dir) to `delivered` with a one-line summary + the file list.
* Then verified-send ONE short line to me at `graphvis-mgr:0.0` (socket `default`), prefixed `(graphvis:fable):`, e.g.:
  `(graphvis:fable): delivered — review+roadmap+ttl-judgment in out/fable/, N build-now items. STATUS updated.`
* Keep the tmux line small (pointer, not paste). I read the files.

## Constraints

* **Propose, don't build.** No edits outside `out/` + `out-meta/` + `STATUS.md`. No branches, no commits, no server mutations.
* **No `pip install`** — use `uv run --with` if you need to execute anything (you mostly won't; this is a read+reason task).
* **PII gate** — the `in/` fleet TTL is design-layer sample only; do not go hunting live captures elsewhere.
* **Ground every claim in the code.** file:line beats hand-waving. I will spot-check a headline finding before dispatching the build team — peer-verify beats grade-your-own-work.
* **Scope discipline on the roadmap** — a BUILD-NOW item that can't be stated as a solo-implementable branch with an acceptance test is really a DEFER or needs splitting. Prefer fewer, sharper items.
