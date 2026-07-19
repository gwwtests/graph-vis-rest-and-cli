# STATUS — v0.5.0 review → improvement roadmap

* **state:** CLOSED — delivered + implemented
* **lead:** (graphvis:mgr) · **reviewer/architect:** (graphvis:fable) claude-fable-5 · **implementers:** 8 opus agents (worktrees)
* **Phase 1 (fable review):** out/fable/{01-review,02-arch,03-roadmap,04-fleet-ttl}.md — 8 BUILD-NOW + fleet thin-slice + DEFER. mgr spot-checked F1+F6 (confirmed).
* **Phase 2 (opus implement):** 8 feat/* branches off master, all tests green. mgr re-ran 2 suites independently (match).
* **Phase 3 (synthesis):** out/mgr/REVIEW_GUIDE.md — branch table, reviewer setup, merge order (waves A/B/C), cross-cutting findings.
* **branches:** feat/{ws-write-protection,collab-resync,cli-hardening,sse-subscribe,server-persistence,store-action-parity,vis-local-fallback,fleet-jsonl-adapter}
* **next (human):** review + merge per REVIEW_GUIDE.md merge order. Recommended follow-up: commit/bootstrap the gitignored test symlinks; cherry-pick e2e-harness fixes to master.
