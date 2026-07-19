# fleetjsonl2graph

Adapt **fleet-topology JSONL** (as emitted by the external
`fleet_topology_tree.py -F jsonl`) into **graph-vis JSONL** that loads directly
via `graph-vis-cli.py -l` or a `+++jsonl` block.

## Purpose

The fleet renderer emits one JSON object per line describing a
coordinator/session fleet. graph-vis' JSONL loader already reads
`{"type":"node"|"edge"|"triplet"}` lines and passes unknown fields through as
vis-network styling extras — so fleet JSONL *almost* loads as-is. Three gaps
remain, which this thin adapter closes:

1. Fleet **edges** carry `rel` (e.g. `"rel":"oversees"`) instead of `label` →
   they would load with empty labels. This adapter maps `rel` → `label`.
2. Fleet **nodes** carry `kind` (lead/coord/session/manager/subteam/worker/
   terminated/workstream) plus status flags (`alive`/`stale`/`uncovered`/
   `live`). This adapter turns `kind` into vis-network `color`/`shape`, and
   `stale:true` / `alive:false` into a dashed muted border.
3. Fleet **`drift`** records have no graph-vis equivalent. They are **skipped by
   default**; `--drift` renders each as a red annotation node attached (by edge)
   to its `subject`.

Unknown `type` values and unknown node/edge fields are preserved as pass-through
extras, so future fleet fields keep flowing to vis-network without adapter
changes.

## Styling map (`kind` → vis)

| `kind`       | shape   | colour           |
|--------------|---------|------------------|
| `lead`       | box     | gold             |
| `coord`      | ellipse | blue             |
| `session`    | dot     | green            |
| `manager`    | box     | purple           |
| `subteam`    | box     | gray             |
| `workstream` | box     | light gray       |
| `worker`     | dot     | teal             |
| `terminated` | box     | red + `✕` + dashed |
| *(other)*    | dot     | slate (fallback) |

`stale:true` or `alive:false` → dashed muted border. Stale edges → dashed muted line.

## Usage

```bash
# stdin → stdout (pipe-friendly)
cat fleet.jsonl | ./fleetjsonl2graph.py

# from a file
./fleetjsonl2graph.py fleet.jsonl

# also render drift findings as red annotations
./fleetjsonl2graph.py --drift fleet.jsonl

# end-to-end into graph-vis
./fleetjsonl2graph.py examples/fleet-topology-sample.jsonl > /tmp/fleet.jsonl
./graph-vis-cli.py -l /tmp/fleet.jsonl "g"
```

## Library usage

```python
from fleetjsonl2graph import convert, format_jsonl

lines = convert("fleet.jsonl", drift=True)   # list of {"type": ...} dicts
print(format_jsonl(lines))                    # JSONL text
```

`convert(source, drift=False)` accepts a path (str) or a file-like object and
returns nodes first, then edges, then (if `drift=True`) drift annotations.

## Related

* `scripts/converters/jsonl2graph/` — the general JSONL loader this mirrors.
* `docs/recipes/fleet-topology-live-view.md` — one-shot + refresh-loop pipeline.
* `examples/fleet-topology-sample.jsonl` — synthetic fixture.
* `examples/demos/fleet-topology-demo.sh` — demo launcher.
