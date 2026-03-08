(function(gv) {
    'use strict';

    var sourceId = null;
    var weightPopup = null;

    // ── Dijkstra ────────────────────────────────────────────────────────

    function dijkstra(src) {
        var nodeIds = gv.nodes.getIds();
        var dist = {};
        var prev = {};
        var visited = {};

        nodeIds.forEach(function(id) {
            dist[id] = Infinity;
            prev[id] = null;
        });
        dist[src] = 0;

        while (true) {
            var u = null;
            var uDist = Infinity;
            nodeIds.forEach(function(id) {
                if (!visited[id] && dist[id] < uDist) {
                    u = id;
                    uDist = dist[id];
                }
            });
            if (u === null) break;
            visited[u] = true;

            gv.edges.get().forEach(function(edge) {
                var neighbor = null;
                if (edge.from === u) neighbor = edge.to;
                else if (edge.to === u) neighbor = edge.from;
                if (neighbor === null || visited[neighbor]) return;

                var w = (edge.weight != null) ? edge.weight : 1;
                var alt = dist[u] + w;
                if (alt < dist[neighbor]) {
                    dist[neighbor] = alt;
                    prev[neighbor] = u;
                }
            });
        }

        return { dist: dist, prev: prev };
    }

    function getTreeEdgeIds(prev) {
        var treeEdgeIds = {};
        var allEdges = gv.edges.get();
        for (var nodeId in prev) {
            var p = prev[nodeId];
            if (p === null) continue;
            allEdges.forEach(function(edge) {
                if ((edge.from === p && edge.to === nodeId) ||
                    (edge.to === p && edge.from === nodeId)) {
                    treeEdgeIds[edge.id] = true;
                }
            });
        }
        return treeEdgeIds;
    }

    // ── Visualization update ────────────────────────────────────────────

    function applyResults() {
        if (sourceId === null) return;
        var result = dijkstra(sourceId);
        var treeEdgeIds = getTreeEdgeIds(result.prev);

        // Update node labels
        gv.nodes.get().forEach(function(node) {
            var d = result.dist[node.id];
            var distStr = (d === Infinity) ? '\u221e' : String(d);
            var baseName = (node._spName != null) ? node._spName : node.label;
            var update = {
                id: node.id,
                label: baseName + '\n(d=' + distStr + ')',
                _spName: baseName
            };
            if (node.id === sourceId) {
                update.borderWidth = 4;
                update.color = { border: '#FFD700' };
            } else {
                update.borderWidth = 1;
                update.color = { border: '#2B7CE9' };
            }
            gv.nodes.update(update);
        });

        // Update edge styles
        gv.edges.get().forEach(function(edge) {
            var onTree = !!treeEdgeIds[edge.id];
            gv.edges.update({
                id: edge.id,
                width: onTree ? 4 : 1,
                color: { color: onTree ? '#4CAF50' : '#848484' }
            });
        });

        // Collect tree edge id list
        var treeList = [];
        for (var eid in treeEdgeIds) treeList.push(eid);

        gv.sendEvent('ext:shortest-path:path-computed', {
            source: sourceId,
            distances: result.dist,
            tree_edges: treeList
        });
    }

    // ── Random graph generation ─────────────────────────────────────────

    function randomInt(min, max) {
        return Math.floor(Math.random() * (max - min + 1)) + min;
    }

    function generateRandomGraph(nodeCount, edgeTarget) {
        nodeCount = nodeCount || 6;
        edgeTarget = edgeTarget || 10;

        gv.nodes.clear();
        gv.edges.clear();

        var labels = [];
        for (var i = 0; i < nodeCount; i++) {
            var label = String.fromCharCode(65 + i);
            labels.push(label);
            gv.nodes.add({ id: label, label: label });
        }

        // Random spanning tree for connectivity
        var inTree = [labels[0]];
        var remaining = labels.slice(1);
        // Shuffle remaining
        for (var j = remaining.length - 1; j > 0; j--) {
            var k = randomInt(0, j);
            var tmp = remaining[j];
            remaining[j] = remaining[k];
            remaining[k] = tmp;
        }

        var edgeSet = {};
        var edgeCount = 0;

        remaining.forEach(function(node) {
            var from = inTree[randomInt(0, inTree.length - 1)];
            var w = randomInt(1, 10);
            var edgeKey = from < node ? from + '-' + node : node + '-' + from;
            var edgeId = from + '-' + node + '-' + edgeCount;
            gv.edges.add({
                id: edgeId,
                from: from,
                to: node,
                label: String(w),
                weight: w
            });
            edgeSet[edgeKey] = true;
            edgeCount++;
            inTree.push(node);
        });

        // Extra edges
        var attempts = 0;
        while (edgeCount < edgeTarget && attempts < 200) {
            attempts++;
            var a = labels[randomInt(0, labels.length - 1)];
            var b = labels[randomInt(0, labels.length - 1)];
            if (a === b) continue;
            var ek = a < b ? a + '-' + b : b + '-' + a;
            if (edgeSet[ek]) continue;
            edgeSet[ek] = true;
            var w2 = randomInt(1, 10);
            var eid = a + '-' + b + '-' + edgeCount;
            gv.edges.add({
                id: eid,
                from: a,
                to: b,
                label: String(w2),
                weight: w2
            });
            edgeCount++;
        }

        sourceId = labels[0];
    }

    // ── Edge weight popup ───────────────────────────────────────────────

    function removeWeightPopup() {
        if (weightPopup) {
            weightPopup.parentNode.removeChild(weightPopup);
            weightPopup = null;
        }
    }

    function showWeightPopup(edgeId) {
        removeWeightPopup();

        var edge = gv.edges.get(edgeId);
        if (!edge) return;

        // Compute midpoint in DOM coords
        var fromPos = gv.network.getPosition(edge.from);
        var toPos = gv.network.getPosition(edge.to);
        var midCanvas = {
            x: (fromPos.x + toPos.x) / 2,
            y: (fromPos.y + toPos.y) / 2
        };
        var midDom = gv.network.canvasToDOM(midCanvas);

        var popup = document.createElement('div');
        popup.className = 'sp-weight-popup';
        popup.style.left = midDom.x + 'px';
        popup.style.top = midDom.y + 'px';

        var lbl = document.createElement('label');
        lbl.textContent = 'Weight:';

        var input = document.createElement('input');
        input.type = 'number';
        input.min = '1';
        input.max = '99';
        input.value = String(edge.weight || 1);

        var okBtn = document.createElement('button');
        okBtn.className = 'sp-ok';
        okBtn.textContent = 'OK';

        var cancelBtn = document.createElement('button');
        cancelBtn.className = 'sp-cancel';
        cancelBtn.textContent = 'Cancel';

        okBtn.addEventListener('click', function() {
            var newWeight = parseInt(input.value, 10);
            if (isNaN(newWeight) || newWeight < 1) newWeight = 1;
            gv.edges.update({
                id: edgeId,
                label: String(newWeight),
                weight: newWeight
            });
            gv.sendEvent('ext:shortest-path:weight-changed', {
                edgeId: edgeId,
                weight: newWeight
            });
            removeWeightPopup();
            applyResults();
        });

        cancelBtn.addEventListener('click', function() {
            removeWeightPopup();
        });

        input.addEventListener('keydown', function(e) {
            if (e.key === 'Enter') okBtn.click();
            if (e.key === 'Escape') cancelBtn.click();
        });

        popup.appendChild(lbl);
        popup.appendChild(input);
        popup.appendChild(okBtn);
        popup.appendChild(cancelBtn);
        gv.container.appendChild(popup);
        weightPopup = popup;

        input.focus();
        input.select();
    }

    // ── Control panel ───────────────────────────────────────────────────

    function buildControls() {
        var panel = document.createElement('div');
        panel.className = 'sp-controls';

        var srcLabel = document.createElement('span');
        srcLabel.className = 'sp-source-label';
        srcLabel.textContent = 'Source:';

        var srcValue = document.createElement('span');
        srcValue.className = 'sp-source-value';
        srcValue.id = 'sp-source-display';
        srcValue.textContent = sourceId || '-';

        var hint = document.createElement('span');
        hint.className = 'sp-hint';
        hint.textContent = '(Shift+click node)';

        var randomizeBtn = document.createElement('button');
        randomizeBtn.textContent = 'Randomize Weights';
        randomizeBtn.addEventListener('click', function() {
            randomizeWeights();
        });

        var newGraphBtn = document.createElement('button');
        newGraphBtn.textContent = 'New Random Graph';
        newGraphBtn.addEventListener('click', function() {
            generateRandomGraph(6, 10);
            applyResults();
            updateSourceDisplay();
        });

        panel.appendChild(srcLabel);
        panel.appendChild(srcValue);
        panel.appendChild(hint);
        panel.appendChild(randomizeBtn);
        panel.appendChild(newGraphBtn);
        gv.container.appendChild(panel);
    }

    function updateSourceDisplay() {
        var el = document.getElementById('sp-source-display');
        if (el) el.textContent = sourceId || '-';
    }

    // ── Actions ─────────────────────────────────────────────────────────

    function randomizeWeights() {
        gv.edges.get().forEach(function(edge) {
            var w = randomInt(1, 10);
            gv.edges.update({
                id: edge.id,
                label: String(w),
                weight: w
            });
        });
        applyResults();
    }

    function setSource(nodeId) {
        if (!gv.nodes.get(nodeId)) return;
        sourceId = nodeId;
        updateSourceDisplay();
        applyResults();
    }

    // ── Event listeners ─────────────────────────────────────────────────

    gv.network.on('selectEdge', function(params) {
        if (!params.edges || params.edges.length === 0) return;
        showWeightPopup(params.edges[0]);
    });

    gv.network.on('click', function(params) {
        // Shift+click on a node sets it as source
        if (params.event && params.event.srcEvent && params.event.srcEvent.shiftKey) {
            if (params.nodes && params.nodes.length > 0) {
                setSource(params.nodes[0]);
                return;
            }
        }
        // Click elsewhere dismisses popup (if not on popup itself)
        if (weightPopup && params.nodes.length === 0 && params.edges.length === 0) {
            removeWeightPopup();
        }
    });

    // ── Commands ─────────────────────────────────────────────────────────

    gv.onCommand('ext:shortest-path:set-source', function(data) {
        if (data && data.node) setSource(data.node);
    });

    gv.onCommand('ext:shortest-path:randomize-weights', function() {
        randomizeWeights();
    });

    gv.onCommand('ext:shortest-path:new-graph', function(data) {
        var n = (data && data.nodes) || 6;
        var e = (data && data.edges) || 10;
        generateRandomGraph(n, e);
        applyResults();
        updateSourceDisplay();
    });

    // ── Init ─────────────────────────────────────────────────────────────

    generateRandomGraph(6, 10);
    buildControls();
    applyResults();

    console.log('[shortest-path] loaded');

})(window.graphVis);
