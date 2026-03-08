#!/bin/bash
# Demo: backward-compatible delete-on-doubleclick behavior via extension
cd "$(dirname "$0")/../.."
exec ./graph-vis-server.py --ext delete-on-doubleclick.js "$@"
