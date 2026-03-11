#!/usr/bin/env python3
"""CDP helper: evaluate JS in a Chromium tab via Chrome DevTools Protocol.

Usage:
    python3 cdp_eval.py <CDP_PORT> <JS_EXPRESSION>

Example:
    python3 cdp_eval.py 9222 "window.graphVis.nodes.length"
"""
import json
import subprocess
import sys
import urllib.request


def cdp_eval(port: int, expression: str) -> dict:
    """Evaluate JS in the first tab of a Chromium instance at the given CDP port."""
    # Get the WS debugger URL for the first tab
    with urllib.request.urlopen(f"http://localhost:{port}/json") as resp:
        tabs = json.loads(resp.read())
    ws_url = tabs[0]["webSocketDebuggerUrl"]

    # Build the CDP Runtime.evaluate message
    msg = json.dumps({
        "id": 1,
        "method": "Runtime.evaluate",
        "params": {
            "expression": expression,
            "returnByValue": True,
            "awaitPromise": True,
        },
    })

    # Send via websocat and read one response
    proc = subprocess.run(
        ["websocat", "-n1", ws_url],
        input=msg, capture_output=True, text=True, timeout=10,
    )
    result = json.loads(proc.stdout)
    return result.get("result", {}).get("result", {})


def main():
    if len(sys.argv) < 3:
        print(f"Usage: {sys.argv[0]} <CDP_PORT> <JS_EXPRESSION>", file=sys.stderr)
        sys.exit(1)
    port = int(sys.argv[1])
    expr = sys.argv[2]
    result = cdp_eval(port, expr)
    if result.get("type") == "object":
        print(json.dumps(result.get("value"), indent=2))
    elif result.get("type") == "undefined":
        print("undefined")
    else:
        print(result.get("value", result.get("description", str(result))))


if __name__ == "__main__":
    main()
