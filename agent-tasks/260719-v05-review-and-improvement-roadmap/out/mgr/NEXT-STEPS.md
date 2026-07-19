# NEXT STEPS / RESUME NOTES — graph-vis review→improve effort

**For:** `ubertmux-adm` work-line notes · **From:** `(graphvis:mgr)` · 2026-07-19
**State:** review→implement cycle CLOSED. 8 `feat/*` branches on `master@2510ea2`, all green, nothing pushed. This file = what remains, ordered by what to do first.

---

## A. Immediate next action (human/opus, one focused session)

**Review + merge the 8 branches** per `REVIEW_GUIDE.md` merge order:
* **Wave A (independent, merge anytime):** `feat/cli-hardening`, `feat/fleet-jsonl-adapter`
* **Wave B (server mutation/WS path — sequential, rebase each):** `feat/collab-resync` → `feat/ws-write-protection` → `feat/store-action-parity` → `feat/server-persistence` → `feat/sse-subscribe`
* **Wave C (last, rebase to absorb the index.html edits):** `feat/vis-local-fallback`

Real conflicts live only in the `static/index.html` cluster (1,2,6,7) and the server broadcast/action path; everything else is additive. `AGENTS.md` conflicts throughout are trivial.

## B. Small repo-hygiene fixes (NOT built, to keep branches scoped — do on master)

1. **Gitignored test symlinks** — `tests/conftest.py` imports `graph_vis_server`, a gitignored symlink absent in fresh clones. Commit the two symlinks OR have `conftest.py` create them at import. Unblocks `pytest` for every clone. (Left unbuilt because 4 branches touch `conftest.py`.)
2. **Cherry-pick the e2e-harness fixes to master** — e2e was 100% broken on master (hyphen-filename import + default `minimal` input-mode hides UI). The two fix commits are separable on `feat/vis-local-fallback` and can land on master independently of the vis change.
3. **Pre-existing e2e failure** `test_delete_node_via_modal` — needs the `delete-on-doubleclick.js` extension (not loaded by default). Decide: load it in that test, or mark xfail.

## C. Post-merge housekeeping

* Bump `VERSION` → `v0.6.0`; run the full suite on merged master.
* Update `FUTURE_WORK.md`: §1 (CLI subscribe) now DONE via SSE; §2 (read-only) already done. Reflect new state.

## D. Next-cycle BUILD candidates (were DEFER, now unblocked / high-value)

* **Click-event broadcast** (FUTURE_WORK §4) — was blocked on SSE; **now unblocked by `feat/sse-subscribe`**. Promote to BUILD next cycle. Enables browser-click → agent reactions.
* **Fleet `--watch` live-refresh** — the fleet adapter shipped as a one-shot; live refresh needs diff-application (add/remove deltas, not clear+reload), which the `rev` counter from `feat/collab-resync` now makes feasible. Pairs with `feat/server-persistence`.
* **Reverse direction** (browser click on a fleet node → agent action, e.g. "focus this session") — blocked on click-event broadcast above.

## E. Longer-horizon DEFER (named in `../fable/03-improvement-roadmap.md`, not yet warranted)

Server-authoritative actions (kill the dual JS/py interpreter — large cut; `feat/store-action-parity`'s contract test holds the risk meanwhile) · multi-graph rooms + per-user identity/permissions · CRDT/op-log sync · SVG vector export · rich node/edge content (prototype as an extension) · bulk-load REST endpoint (only at >10³ edges) · frontend modularization/bundler (zero-build is a feature) · dedicated `/api/sources/fleet` endpoint (wrong coupling direction).

## Pointers

* Branches: `git branch --list 'feat/*'` in `~/github/gwwtests/graph-vis-rest-and-cli`.
* Full review: `agent-tasks/260719-v05-review-and-improvement-roadmap/out/fable/` + `out/mgr/REVIEW_GUIDE.md` (all on branch `design/v05-review-and-roadmap`).
* The fable helper window `graphvis-mgr:fable` is left standing for a follow-up dispatch (re-use the kit: `scripts/dispatch_task_to_agent.sh`).
