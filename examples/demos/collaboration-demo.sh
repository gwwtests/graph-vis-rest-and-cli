#!/usr/bin/env bash
# Collaboration demo: shows multi-client real-time sync
#
# Opens 2 browser windows and feeds triplets with delays so you can
# watch nodes appear across both browsers simultaneously.
#
# Usage: ./examples/demos/collaboration-demo.sh
set -euo pipefail
cd "$(dirname "$0")/../.."

PORT=${GRAPH_VIS_PORT:-7849}
URL="http://localhost:${PORT}"

echo "=== Multi-Client Collaboration Demo ==="
echo ""

# Check if server is running
if ! curl -sf "${URL}/api/graph" >/dev/null 2>&1; then
    echo "Starting server..."
    ./graph-vis-server.py &
    SERVER_PID=$!
    sleep 2
    echo "Server started (PID ${SERVER_PID})"
else
    echo "Server already running on port ${PORT}"
    SERVER_PID=""
fi

# Clear existing graph
curl -sf -X POST "${URL}/api/clear" >/dev/null
echo "Graph cleared."
echo ""

# Open two browser windows if possible
if command -v xdg-open >/dev/null 2>&1; then
    echo "Opening two browser windows..."
    xdg-open "${URL}" 2>/dev/null &
    sleep 1
    xdg-open "${URL}" 2>/dev/null &
    sleep 2
    echo "Both windows open. Watch them sync!"
    echo ""
fi

echo "Adding nodes from CLI (watch both browsers update)..."
echo ""

add_triplet() {
    echo "$1 $2 $3" | ./graph-vis-cli.py
    sleep 1.5
}

# Build a knowledge graph about collaboration
add_triplet "Collaboration" enables "RealTimeSync"
add_triplet "Collaboration" requires "WebSocket"
add_triplet "Collaboration" supports "MultipleBrowsers"

add_triplet "WebSocket" broadcasts "Events"
add_triplet "Events" update "AllClients"

add_triplet "REST_API" handles "Mutations"
add_triplet "Mutations" trigger "Broadcast"
add_triplet "Broadcast" reaches "AllClients"

add_triplet "CLI" sends "Mutations"
add_triplet "Browser" sends "Mutations"
add_triplet "curl" sends "Mutations"

add_triplet "HookActions" relay_via "WebSocket"
add_triplet "HookActions" include "ToggleNode"
add_triplet "HookActions" include "Restyle"
add_triplet "HookActions" include "AddRemove"

echo ""
echo "=== Demo complete! ==="
echo "Graph: $(curl -sf "${URL}/api/graph" | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'{len(d[\"nodes\"])} nodes, {len(d[\"edges\"])} edges')")"
echo ""
echo "Try:"
echo "  - Type a triplet in one browser's text box (click Min → Multi first)"
echo "  - Watch it appear in the other browser"
echo "  - Add more from CLI: echo 'NewNode connects OtherNode' | ./graph-vis-cli.py"
echo ""

if [ -n "${SERVER_PID}" ]; then
    echo "Server running as PID ${SERVER_PID}. Press Ctrl+C to stop."
    wait "${SERVER_PID}"
fi
