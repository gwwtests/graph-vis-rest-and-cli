# Recipe: live fleet-topology view in graph-vis

Wire the external `fleet_topology_tree.py -F jsonl` renderer into graph-vis via
the `fleetjsonl2graph` adapter, so the fleet topology shows up as a styled,
collaboratively-viewable graph.

> **Prerequisite:** `fleet_topology_tree.py` is an *external* tool (not part of
> this repo). This recipe only needs its `-F jsonl` output. To try the pipeline
> without it, use the committed synthetic fixture
> `examples/fleet-topology-sample.jsonl`.

## One-shot

```bash
# 1. start a graph-vis server (pick an unused port)
GRAPH_VIS_PORT=7849 ./graph-vis-server.py &

# 2. render fleet → adapt → load into graph-vis
fleet_topology_tree.py -F jsonl \
  | python3 scripts/converters/fleetjsonl2graph/fleetjsonl2graph.py > /tmp/fleet.jsonl
./graph-vis-cli.py "clear" ; ./graph-vis-cli.py -l /tmp/fleet.jsonl "g"

# with the synthetic fixture instead of the live renderer:
python3 scripts/converters/fleetjsonl2graph/fleetjsonl2graph.py \
  examples/fleet-topology-sample.jsonl > /tmp/fleet.jsonl
./graph-vis-cli.py "clear" ; ./graph-vis-cli.py -l /tmp/fleet.jsonl "g"

# render drift findings too:
fleet_topology_tree.py -F jsonl \
  | python3 scripts/converters/fleetjsonl2graph/fleetjsonl2graph.py --drift > /tmp/fleet.jsonl
```

> **CLI execution-order gotcha.** `graph-vis-cli.py` always runs `--load` files
> *before* positional commands (`connect → --load → commands`). So a single
> `./graph-vis-cli.py "clear" -l f.jsonl "g"` would load **then** clear, leaving
> an empty graph. Issue `clear` as its **own** invocation *before* the load (as
> above), or just skip it and let `-l` add to the current graph.

## Crude refresh loop (honest interim)

There is no push/subscribe from the fleet renderer yet. Until then, a dumb poll
loop is a fair interim — it re-renders every 30s and replaces the graph:

```bash
while true; do
  fleet_topology_tree.py -F jsonl \
    | python3 scripts/converters/fleetjsonl2graph/fleetjsonl2graph.py > /tmp/fleet.jsonl
  ./graph-vis-cli.py "clear"
  ./graph-vis-cli.py -l /tmp/fleet.jsonl
  sleep 30
done
```

This is intentionally crude: full re-clear + reload each tick (brief flicker, no
diffing, fixed interval). It is documented as a stopgap, not the intended
long-term design — a proper adapter would diff and emit only mutations, or
subscribe to renderer changes.

## PII / privacy note

Fleet JSONL from a live capture can contain operational detail — session names,
server hostnames, working directories, window counts, coordinator/worker
identities. graph-vis binds to `0.0.0.0` by default and is designed for LAN
collaboration, so **rendering captured live-session data into a shared view
makes that data visible to everyone who can reach the server.** Whether that is
acceptable is the operator's call. Consider:

* running the server on `127.0.0.1` (`GRAPH_VIS_HOST=127.0.0.1`) for a private
  view, and/or `--read-only`;
* sanitising or omitting `cwd`/`server`/session-name fields before rendering;
* using the synthetic fixture for demos and screenshots.

Never commit real captured fleet JSONL to this repo — only the synthetic
`examples/fleet-topology-sample.jsonl` (fictional names) is safe to share.
