# Multi-Client Collaboration QA Procedure

**Date:** 2026-03-11
**Status:** All tests PASSED (1 bug found and fixed during QA)

## Prerequisites

* Chromium with CDP (Chrome DevTools Protocol) support
* `websocat` for WebSocket communication
* `websockets` Python package (for CDP screenshots)
* `curl` for REST API calls
* The `qa/cdp_eval.py` helper script

## Setup

### 1. Start the server

```bash
./graph-vis-server.py
# Verify it's running
curl -s http://localhost:7849/api/graph | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'{len(d[\"nodes\"])} nodes')"
```

### 2. Launch 3 Chromium instances with CDP

Each instance uses a separate user profile and a unique CDP debugging port:

```bash
mkdir -p /tmp/claude/qa-chromium/{profile1,profile2,profile3}

chromium --remote-debugging-port=9222 \
         --user-data-dir=/tmp/claude/qa-chromium/profile1 \
         --window-size=800,600 --window-position=0,0 \
         "http://localhost:7849" &

chromium --remote-debugging-port=9223 \
         --user-data-dir=/tmp/claude/qa-chromium/profile2 \
         --window-size=800,600 --window-position=810,0 \
         "http://localhost:7849" &

chromium --remote-debugging-port=9224 \
         --user-data-dir=/tmp/claude/qa-chromium/profile3 \
         --window-size=800,600 --window-position=400,400 \
         "http://localhost:7849" &
```

### 3. Verify CDP connections

```bash
for port in 9222 9223 9224; do
    echo -n "CDP $port: "
    curl -s http://localhost:$port/json/version | python3 -c \
        "import sys,json; print(json.load(sys.stdin).get('Browser','FAIL'))"
done
```

### 4. Clear graph for clean state

```bash
curl -s -X POST http://localhost:7849/api/clear
```

## CDP Helper

The `qa/cdp_eval.py` script executes JavaScript in a browser tab via CDP:

```bash
# Check node count in browser on port 9222
python3 qa/cdp_eval.py 9222 "window.graphVis.nodes.length"

# Execute async API call
python3 qa/cdp_eval.py 9222 "
(async () => {
    await window.graphVis.api.addTriplet('A', 'knows', 'B');
    return 'done';
})()
"
```

## Test Procedure

### Test 1: REST API → All Browsers Sync

**Action:** Add a triplet via REST API.
**Expect:** All 3 browsers show 2 nodes immediately.

```bash
curl -s -X POST http://localhost:7849/api/add-triplet \
  -H 'Content-Type: application/json' \
  -d '{"subject":"Alice","predicate":"knows","object":"Bob"}'
sleep 1
for port in 9222 9223 9224; do
  echo "Browser $port: $(python3 qa/cdp_eval.py $port 'window.graphVis.nodes.length') nodes"
done
```

**Result:** PASSED — All 3 browsers showed 2 nodes.

### Test 2: CLI → All Browsers Sync

**Action:** Add a triplet via the CLI tool.
**Expect:** All browsers update to 4 nodes.

```bash
echo "Charlie friends Dave" | ./graph-vis-cli.py
sleep 1
for port in 9222 9223 9224; do
  echo "Browser $port: $(python3 qa/cdp_eval.py $port 'window.graphVis.nodes.length') nodes"
done
```

**Result:** PASSED — All 3 browsers showed 4 nodes, 2 edges.

### Test 3: Browser 1 JS API → Browsers 2 & 3 Sync

**Action:** Call `api.addTriplet()` from Browser 1's JS context.
**Expect:** Browsers 2 and 3 also receive the new triplet.

```bash
python3 qa/cdp_eval.py 9222 "
(async () => {
    await window.graphVis.api.addTriplet('Eve', 'likes', 'Frank');
    return 'sent';
})()
"
sleep 1
for port in 9222 9223 9224; do
  echo "Browser $port: $(python3 qa/cdp_eval.py $port 'window.graphVis.nodes.length') nodes"
done
```

**Result:** PASSED — All 3 browsers showed 6 nodes.

### Test 4: Clear via REST → All Browsers Clear

**Action:** POST to `/api/clear`.
**Expect:** All browsers show 0 nodes, 0 edges.

```bash
curl -s -X POST http://localhost:7849/api/clear
sleep 1
for port in 9222 9223 9224; do
  n=$(python3 qa/cdp_eval.py $port "window.graphVis.nodes.length")
  e=$(python3 qa/cdp_eval.py $port "window.graphVis.edges.length")
  echo "Browser $port: $n nodes, $e edges"
done
```

**Result:** PASSED — All browsers cleared.

### Test 5: Hook Action (add_node) → Broadcast to Others

**Action:** Execute `executeAction({action:'add_node', ...})` in Browser 1.
**Expect:** Browsers 2 & 3 receive the node. Server store updated.

```bash
python3 qa/cdp_eval.py 9222 "
window.graphVis.executeAction({action:'add_node', id:'HookNode1', label:'From Hook'});
'done'
"
sleep 1
for port in 9222 9223 9224; do
  echo "Browser $port: $(python3 qa/cdp_eval.py $port 'window.graphVis.nodes.length') nodes"
done
curl -s http://localhost:7849/api/graph | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'Server: {len(d[\"nodes\"])} nodes')"
```

**Result:** PASSED — All 3 browsers showed 1 node. Server store confirmed.

### Test 6: Hook add_edge from Browser 2 → Others Sync

**Action:** Add node + edge via hook actions from Browser 2.
**Expect:** All browsers and server show 2 nodes, 1 edge.

```bash
python3 qa/cdp_eval.py 9223 "
window.graphVis.executeAction({action:'add_node', id:'HookNode2', label:'From B2'});
window.graphVis.executeAction({action:'add_edge', from:'HookNode1', to:'HookNode2', label:'linked'});
'done'
"
```

**Result:** PASSED — 2 nodes, 1 edge across all.

### Test 7: Hook remove_node with Cascade Edge Removal

**Action:** Remove a node that has connected edges via hook action from Browser 3.
**Expect:** Node AND connected edges removed on all browsers and server.

```bash
python3 qa/cdp_eval.py 9224 "
window.graphVis.executeAction({action:'remove_node', id:'HookNode1'});
'done'
"
```

**Result:** PASSED (after bug fix) — 1 node, 0 edges across all.

**Bug found:** The original `remove_node` hook action only called `nodes.remove(id)` without
removing connected edges. Fixed by adding `network.getConnectedEdges()` cascade removal.

### Test 8: toggle_node Visibility Sync

**Action:** Toggle a node's visibility from Browser 2, verify all browsers reflect it.

```bash
# Setup
python3 qa/cdp_eval.py 9222 "
(async () => {
    await window.graphVis.api.addTriplet('Root', 'has', 'Child1');
    return 'loaded';
})()
"
sleep 1

# Toggle hide from Browser 2
python3 qa/cdp_eval.py 9223 "
window.graphVis.executeAction({action:'toggle_node', id:'Child1'});
'toggled'
"
sleep 1

for port in 9222 9223 9224; do
  echo "Browser $port: Child1 hidden=$(python3 qa/cdp_eval.py $port "JSON.stringify(window.graphVis.nodes.get('Child1')?.hidden)")"
done
```

**Result:** PASSED — `hidden=true` on all 3 browsers after toggle, `hidden=false` after toggle back.

### Test 9: Restyle Action Sync

**Action:** Restyle a node's color from Browser 3.
**Expect:** All browsers show the new color.

```bash
python3 qa/cdp_eval.py 9224 "
window.graphVis.executeAction({action:'restyle', id:'Root', color:{background:'#FF0000',border:'#AA0000'}});
'restyled'
"
sleep 1
for port in 9222 9223 9224; do
  echo "Browser $port: $(python3 qa/cdp_eval.py $port "JSON.stringify(window.graphVis.nodes.get('Root')?.color)")"
done
```

**Result:** PASSED — `{"background":"#FF0000","border":"#AA0000"}` on all 3.

### Test 10: Read-Only Mode Endpoint

**Action:** Check `/api/read-only` returns current state.

```bash
curl -s http://localhost:7849/api/read-only
```

**Result:** PASSED — `{"read_only":false}`.

### Test 11: Server Store Consistency for New Clients

**Action:** Verify `GET /api/graph` includes visual state (colors, hidden flags).
**Expect:** Restyle colors and toggle states persisted in server store.

```bash
curl -s http://localhost:7849/api/graph | python3 -m json.tool
```

**Result:** PASSED — Server returned nodes with `color` and `hidden`/`physics` properties intact.

### Test 12: Concurrent Rapid Mutations from 4 Sources

**Action:** Fire mutations simultaneously from all 3 browsers + CLI.
**Expect:** All end up with identical node/edge counts.

```bash
curl -s -X POST http://localhost:7849/api/clear > /dev/null
sleep 1

python3 qa/cdp_eval.py 9222 "(async()=>{await window.graphVis.api.addTriplet('B1_A','from','Browser1'); await window.graphVis.api.addTriplet('B1_B','from','Browser1'); return 'done'})()" &
python3 qa/cdp_eval.py 9223 "(async()=>{await window.graphVis.api.addTriplet('B2_A','from','Browser2'); await window.graphVis.api.addTriplet('B2_B','from','Browser2'); return 'done'})()" &
python3 qa/cdp_eval.py 9224 "(async()=>{await window.graphVis.api.addTriplet('B3_A','from','Browser3'); await window.graphVis.api.addTriplet('B3_B','from','Browser3'); return 'done'})()" &
echo "CLI_A knows CLI_B" | ./graph-vis-cli.py &
wait
sleep 2

server=$(curl -s http://localhost:7849/api/graph | python3 -c "import sys,json; print(len(json.load(sys.stdin)['nodes']))")
echo "Server: $server nodes"
for port in 9222 9223 9224; do
  echo "Browser $port: $(python3 qa/cdp_eval.py $port 'window.graphVis.nodes.length') nodes"
done
```

**Result:** PASSED — All showed 11 nodes. Server and all browsers perfectly consistent.

## Taking Screenshots via CDP

To capture browser screenshots for documentation:

```python
import asyncio, json, base64, urllib.request, websockets

async def screenshot(port, filename):
    with urllib.request.urlopen(f'http://localhost:{port}/json') as r:
        ws_url = json.loads(r.read())[0]['webSocketDebuggerUrl']
    async with websockets.connect(ws_url, max_size=2**24) as ws:
        await ws.send(json.dumps({
            'id': 1, 'method': 'Page.captureScreenshot',
            'params': {'format': 'png'}
        }))
        resp = json.loads(await ws.recv())
        with open(filename, 'wb') as f:
            f.write(base64.b64decode(resp['result']['data']))

asyncio.run(asyncio.gather(
    screenshot(9222, 'qa/qa-screenshot-browser1.png'),
    screenshot(9223, 'qa/qa-screenshot-browser2.png'),
    screenshot(9224, 'qa/qa-screenshot-browser3.png'),
))
```

## Cleanup

```bash
# Close Chromium instances (by user data dir to be specific)
for port in 9222 9223 9224; do
    kill $(lsof -ti:$port) 2>/dev/null
done
rm -rf /tmp/claude/qa-chromium
```

## Summary

| Test | Source → Target | Result |
|------|----------------|--------|
| 1 | REST API → 3 browsers | PASSED |
| 2 | CLI → 3 browsers | PASSED |
| 3 | Browser 1 JS → Browsers 2,3 | PASSED |
| 4 | REST clear → 3 browsers | PASSED |
| 5 | Hook add_node (B1) → B2,B3 + server | PASSED |
| 6 | Hook add_edge (B2) → B1,B3 + server | PASSED |
| 7 | Hook remove_node cascade (B3) → B1,B2 + server | PASSED (bug fixed) |
| 8 | Hook toggle_node visibility → all | PASSED |
| 9 | Hook restyle color → all | PASSED |
| 10 | Read-only mode check | PASSED |
| 11 | Server store has visual state for new clients | PASSED |
| 12 | Concurrent mutations from 4 sources | PASSED |

### Bug Found and Fixed

**remove_node hook action missing cascade edge removal:**
The `remove_node` case in `executeAction()` only called `nodes.remove(id)` without
removing connected edges. The server store correctly cascade-removed edges, but other
browsers retained orphaned edges. Fixed by adding `network.getConnectedEdges()` before
removing the node.

### Architecture Confirmed

```
Browser A ──WS──┐
Browser B ──WS──┤── FastAPI server ──── CLI / curl
Browser C ──WS──┘

Mutation flow:
  Any source → REST API → server store update → WS broadcast to ALL browsers

Hook action flow:
  Browser X executes locally → WS {event:"action"} → server
    ├── updates store (mutations, toggles, restyles)
    └── relays to all OTHER browsers → they execute the same action
```
