(function(gv) {
    'use strict';

    function randomInt(min, max) {
        return Math.floor(Math.random() * (max - min + 1)) + min;
    }

    function generateRandomGraph(nodeCount, edgeTarget, clearFirst) {
        nodeCount = nodeCount || 6;
        edgeTarget = edgeTarget || 10;
        if (clearFirst !== false) {
            gv.nodes.clear();
            gv.edges.clear();
        }

        var labels = [];
        for (var i = 0; i < nodeCount; i++) {
            var label = String.fromCharCode(65 + (i % 26));
            if (i >= 26) label += String(Math.floor(i / 26));
            labels.push(label);
            gv.nodes.add({ id: label, label: label });
        }

        // Random spanning tree for connectivity
        var inTree = [labels[0]];
        var remaining = labels.slice(1);
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
            var edgeKey = from < node ? from + '-' + node : node + '-' + from;
            var edgeId = 'rg-' + edgeCount;
            gv.edges.add({
                id: edgeId,
                from: from,
                to: node
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
            var eid = 'rg-' + edgeCount;
            gv.edges.add({
                id: eid,
                from: a,
                to: b
            });
            edgeCount++;
        }

        gv.sendEvent('ext:random-graph:generated', {
            nodeCount: gv.nodes.length,
            edgeCount: gv.edges.length
        });
    }

    // ── Floating button ─────────────────────────────────────────────────

    var btn = document.createElement('button');
    btn.textContent = 'Random';
    btn.style.cssText =
        'position:absolute;top:12px;right:12px;z-index:55;' +
        'padding:5px 12px;font-size:12px;background:#4CAF50;color:#fff;' +
        'border:none;border-radius:4px;cursor:pointer;font-family:sans-serif;' +
        'box-shadow:0 1px 4px rgba(0,0,0,0.15);';
    btn.addEventListener('mouseenter', function() {
        btn.style.background = '#45a049';
    });
    btn.addEventListener('mouseleave', function() {
        btn.style.background = '#4CAF50';
    });
    btn.addEventListener('click', function() {
        generateRandomGraph(6, 10, true);
    });
    gv.container.appendChild(btn);

    // ── Command ─────────────────────────────────────────────────────────

    gv.onCommand('ext:random-graph:generate', function(data) {
        var n = (data && data.nodes) || 6;
        var e = (data && data.edges) || 10;
        var clear = (data && data.clear !== undefined) ? data.clear : true;
        generateRandomGraph(n, e, clear);
    });

    console.log('[random-graph] loaded');

})(window.graphVis);
