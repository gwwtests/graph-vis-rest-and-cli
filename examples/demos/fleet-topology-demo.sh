#!/bin/bash
# Demo: fleet-topology view using the synthetic fixture (no external tools).
# Adapts examples/fleet-topology-sample.jsonl via fleetjsonl2graph, then loads
# it into a graph-vis server so you can see kind-based styling + drift.
set -euo pipefail
cd "$(dirname "$0")/../.."

PORT="${GRAPH_VIS_PORT:-7849}"
OUT="$(mktemp -t fleet-demo-XXXX.jsonl)"
DRIFT="${1:-}"   # pass --drift to also render drift findings

python3 scripts/converters/fleetjsonl2graph/fleetjsonl2graph.py $DRIFT \
  examples/fleet-topology-sample.jsonl > "$OUT"

echo "Adapted fleet JSONL → $OUT"
echo "Starting graph-vis server on port $PORT ..."
echo "Once it is up (open http://localhost:$PORT), load the graph with:"
echo "    GRAPH_VIS_PORT=$PORT ./graph-vis-cli.py \"clear\""
echo "    GRAPH_VIS_PORT=$PORT ./graph-vis-cli.py -l $OUT \"g\""
echo
exec env GRAPH_VIS_PORT="$PORT" ./graph-vis-server.py
