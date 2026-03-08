#!/bin/bash
# Capture tutorial screenshots by running the server + headless chromium
# Usage: ./docs/tutorial/capture-screenshots.sh
set -e
cd "$(dirname "$0")/../.."

PORT=7853
SCREENSHOT_DIR="docs/tutorial/screenshots"
CLI="./graph-vis-cli.py"
SERVER="./graph-vis-server.py"
HOST="127.0.0.1"
export GRAPH_VIS_PORT="$PORT"
export GRAPH_VIS_HOST="$HOST"

mkdir -p "$SCREENSHOT_DIR"

cleanup() {
    echo "Cleaning up..."
    [ -n "$CHROME_PID" ] && kill "$CHROME_PID" 2>/dev/null || true
    [ -n "$SERVER_PID" ] && kill "$SERVER_PID" 2>/dev/null || true
    wait 2>/dev/null
}
trap cleanup EXIT

wait_for_server() {
    for i in $(seq 1 30); do
        curl -s "http://$HOST:$PORT/api/graph" >/dev/null 2>&1 && return 0
        sleep 0.3
    done
    echo "ERROR: Server failed to start" >&2
    exit 1
}

wait_for_browser() {
    for i in $(seq 1 30); do
        local result=$(curl -s "http://$HOST:$PORT/api/dom" 2>/dev/null)
        if echo "$result" | python3 -c "import sys,json; d=json.load(sys.stdin); sys.exit(0 if 'viewport' in d else 1)" 2>/dev/null; then
            return 0
        fi
        sleep 0.5
    done
    echo "ERROR: Browser failed to connect" >&2
    exit 1
}

take_screenshot() {
    local name="$1"
    local extra_params="${2:-}"
    sleep 1.5  # let physics settle
    local url="http://$HOST:$PORT/api/screenshot?hide_ui=true&padding=0.15&background=white${extra_params}"
    curl -s "$url" -o "$SCREENSHOT_DIR/${name}.png"
    echo "  Captured: $name.png ($(wc -c < "$SCREENSHOT_DIR/${name}.png") bytes)"
}

start_server() {
    local ext_args="$@"
    # Kill any previous
    [ -n "$CHROME_PID" ] && kill "$CHROME_PID" 2>/dev/null || true
    [ -n "$SERVER_PID" ] && kill "$SERVER_PID" 2>/dev/null || true
    wait 2>/dev/null
    sleep 0.5

    echo "Starting server${ext_args:+ with extensions: $ext_args}..."
    $SERVER --port "$PORT" --host "$HOST" $ext_args &
    SERVER_PID=$!
    wait_for_server

    echo "Starting headless chromium..."
    with-x11 chromium --headless=new --disable-gpu --no-sandbox \
        --window-size=1200,800 \
        "http://$HOST:$PORT/" &
    CHROME_PID=$!
    wait_for_browser
    echo "  Browser connected."
}

clear_graph() {
    curl -s -X POST "http://$HOST:$PORT/api/clear" >/dev/null
    sleep 0.3
}

load_jsonl() {
    local file="$1"
    echo "$CLI" -l "$file"
    $CLI -l "$file" 2>/dev/null
    sleep 0.5
}

add_triplets() {
    # Read triplets from args: "A knows B" "B likes C"
    for triplet in "$@"; do
        echo "$triplet" | $CLI 2>/dev/null
    done
    sleep 0.3
}

########################################################################
# SECTION 1: Basic triplets
########################################################################
echo ""
echo "=== Section 1: Basic Triplets ==="
start_server

echo "  Adding basic triplets..."
add_triplets "Alice knows Bob" "Bob likes Charlie" "Charlie emails David" "David calls Alice"
take_screenshot "01-basic-triplets"

########################################################################
# SECTION 2: Labelless edges (2 words)
########################################################################
echo ""
echo "=== Section 2: Labelless Edges ==="
clear_graph
add_triplets "Server Client" "Server Database" "Client Browser" "Database Backup"
take_screenshot "02-labelless-edges"

########################################################################
# SECTION 3: Styled graph from JSONL
########################################################################
echo ""
echo "=== Section 3: Styled JSONL Graph ==="
clear_graph
load_jsonl "examples/styled-graph.jsonl"
take_screenshot "03-styled-graph"

########################################################################
# SECTION 4: Mind map (collapsed — only root visible)
########################################################################
echo ""
echo "=== Section 4: Mind Map (collapsed) ==="
clear_graph
load_jsonl "examples/mindmap.jsonl"
take_screenshot "04-mindmap-collapsed"

########################################################################
# SECTION 5: Styled hooks demo
########################################################################
echo ""
echo "=== Section 5: Styled Hooks Demo ==="
clear_graph
load_jsonl "examples/styled-hooks.jsonl"
take_screenshot "05-styled-hooks"

########################################################################
# SECTION 6: Color spawner extension
########################################################################
echo ""
echo "=== Section 6: Color Spawner Extension ==="
start_server "--ext color-spawner.js --ext color-spawner.css"
sleep 2
take_screenshot "06-color-spawner"

########################################################################
# SECTION 7: Sum propagation extension
########################################################################
echo ""
echo "=== Section 7: Sum Propagation Extension ==="
start_server "--ext sum-propagation.js --ext sum-propagation.css"
sleep 2
take_screenshot "07-sum-propagation"

########################################################################
# SECTION 8: Shortest path extension
########################################################################
echo ""
echo "=== Section 8: Shortest Path Extension ==="
start_server "--ext shortest-path.js --ext shortest-path.css"
sleep 2
take_screenshot "08-shortest-path"

########################################################################
# SECTION 9: Delete on doubleclick extension
########################################################################
echo ""
echo "=== Section 9: Delete Extension ==="
start_server "--ext delete-on-doubleclick.js"
add_triplets "Alice knows Bob" "Bob likes Charlie" "Charlie emails David"
take_screenshot "09-delete-extension"

########################################################################
# SECTION 10: Random graph extension
########################################################################
echo ""
echo "=== Section 10: Random Graph Extension ==="
start_server "--ext random-graph.js"
sleep 2
take_screenshot "10-random-graph"

echo ""
echo "=== All screenshots captured! ==="
ls -la "$SCREENSHOT_DIR"/*.png
