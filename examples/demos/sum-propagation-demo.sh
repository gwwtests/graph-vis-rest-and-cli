#!/bin/bash
# Demo: tree with sum propagation from children to parents
cd "$(dirname "$0")/../.."
exec ./graph-vis-server.py --ext sum-propagation.js --ext sum-propagation.css "$@"
