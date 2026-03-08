#!/bin/bash
# Demo: expandable mind map using core hooks (load mindmap.jsonl via CLI)
cd "$(dirname "$0")/../.."
echo "Starting server... Load the mindmap with:"
echo "  ./graph-vis-cli.py -l examples/mindmap.jsonl"
exec ./graph-vis-server.py "$@"
