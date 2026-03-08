#!/bin/bash
# Demo: interactive Dijkstra shortest path visualization
cd "$(dirname "$0")/../.."
exec ./graph-vis-server.py --ext shortest-path.js --ext shortest-path.css "$@"
