#!/bin/bash
# Demo: interactive color spawner with HTML overlays
cd "$(dirname "$0")/../.."
exec ./graph-vis-server.py --ext color-spawner.js --ext color-spawner.css "$@"
