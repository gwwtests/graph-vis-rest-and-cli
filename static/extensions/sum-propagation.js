(function(gv) {
    'use strict';

    // -- State ----------------------------------------------------------------
    var counter = 0;
    var parentMap = new Map();   // childId → parentId
    var childrenMap = new Map(); // parentId → [childId, ...]
    var valueMap = new Map();    // nodeId → numeric value
    var nameMap = new Map();     // nodeId → display name
    var overlays = new Map();    // nodeId → DOM element

    // -- Helpers --------------------------------------------------------------

    function nextId() {
        counter++;
        return 'sum-' + counter;
    }

    function nextName() {
        return 'Node ' + counter;
    }

    function getChildren(nodeId) {
        return childrenMap.get(nodeId) || [];
    }

    function isLeaf(nodeId) {
        return getChildren(nodeId).length === 0;
    }

    function computeSum(nodeId) {
        var children = getChildren(nodeId);
        if (children.length === 0) return valueMap.get(nodeId) || 0;
        var s = 0;
        for (var i = 0; i < children.length; i++) {
            s += valueMap.get(children[i]) || 0;
        }
        return s;
    }

    function updateLabel(nodeId) {
        var name = nameMap.get(nodeId) || nodeId;
        var val = valueMap.get(nodeId) || 0;
        gv.nodes.update({ id: nodeId, label: name + ': ' + val });
    }

    function propagateUp(nodeId) {
        var current = nodeId;
        while (current !== undefined) {
            if (!isLeaf(current)) {
                var sum = computeSum(current);
                valueMap.set(current, sum);
                updateLabel(current);
                gv.sendEvent('ext:sum-propagation:sum-updated', { id: current, sum: sum });
            }
            current = parentMap.get(current);
        }
    }

    // -- Overlay management ---------------------------------------------------

    function createOverlay(nodeId) {
        var el = document.createElement('div');
        el.className = 'sum-prop-overlay';
        el.dataset.nodeId = nodeId;

        rebuildOverlayContent(el, nodeId);

        gv.container.appendChild(el);
        overlays.set(nodeId, el);
        return el;
    }

    function rebuildOverlayContent(el, nodeId) {
        el.innerHTML = '';

        if (isLeaf(nodeId)) {
            // Editable number input
            var input = document.createElement('input');
            input.type = 'number';
            input.className = 'sum-prop-input';
            input.value = valueMap.get(nodeId) || 0;
            input.addEventListener('input', function() {
                var v = parseFloat(input.value) || 0;
                valueMap.set(nodeId, v);
                updateLabel(nodeId);
                gv.sendEvent('ext:sum-propagation:value-changed', { id: nodeId, value: v });
                propagateUp(parentMap.get(nodeId));
            });
            // Stop vis-network from grabbing focus/drag
            input.addEventListener('mousedown', function(e) { e.stopPropagation(); });
            input.addEventListener('pointerdown', function(e) { e.stopPropagation(); });
            el.appendChild(input);
        } else {
            // Non-editable sum display
            var span = document.createElement('span');
            span.className = 'sum-prop-value';
            span.textContent = valueMap.get(nodeId) || 0;
            el.appendChild(span);
        }

        // "+" button to add child
        var btn = document.createElement('button');
        btn.className = 'sum-prop-add-btn';
        btn.textContent = '+';
        btn.addEventListener('mousedown', function(e) { e.stopPropagation(); });
        btn.addEventListener('pointerdown', function(e) { e.stopPropagation(); });
        btn.addEventListener('click', function(e) {
            e.stopPropagation();
            addChild(nodeId);
        });
        el.appendChild(btn);
    }

    function refreshOverlay(nodeId) {
        var el = overlays.get(nodeId);
        if (!el) return;
        rebuildOverlayContent(el, nodeId);
    }

    function positionOverlays() {
        overlays.forEach(function(el, nodeId) {
            try {
                var canvasPos = gv.network.getPosition(nodeId);
                var domPos = gv.network.canvasToDOM(canvasPos);
                el.style.left = domPos.x + 'px';
                el.style.top = (domPos.y + 30) + 'px';
            } catch (e) {
                // Node may have been removed
            }
        });
    }

    // -- Node creation --------------------------------------------------------

    function createNode(name, id) {
        valueMap.set(id, 0);
        nameMap.set(id, name);
        gv.nodes.update({ id: id, label: name + ': 0' });
        createOverlay(id);
    }

    function addChild(parentId) {
        var wasLeaf = isLeaf(parentId);

        var childId = nextId();
        var childName = nextName();

        // Set up relationships
        parentMap.set(childId, parentId);
        if (!childrenMap.has(parentId)) {
            childrenMap.set(parentId, []);
        }
        childrenMap.get(parentId).push(childId);

        // Create the child node in vis-network
        gv.nodes.add({ id: childId, label: childName + ': 0' });
        gv.edges.add({ from: parentId, to: childId });

        // Track child state
        valueMap.set(childId, 0);
        nameMap.set(childId, childName);
        createOverlay(childId);

        // If parent was a leaf, convert its overlay to sum display
        if (wasLeaf) {
            refreshOverlay(parentId);
            // Recompute parent sum from children (child starts at 0)
            var sum = computeSum(parentId);
            valueMap.set(parentId, sum);
            updateLabel(parentId);
            gv.sendEvent('ext:sum-propagation:sum-updated', { id: parentId, sum: sum });
            propagateUp(parentMap.get(parentId));
        }

        positionOverlays();
    }

    // -- Initialise -----------------------------------------------------------

    // Create root node
    var rootId = nextId();   // sum-1
    var rootName = 'Root';
    nameMap.set(rootId, rootName);
    valueMap.set(rootId, 0);
    gv.nodes.add({ id: rootId, label: rootName + ': 0' });
    createOverlay(rootId);

    // Position overlays on draw
    gv.network.on('afterDrawing', positionOverlays);

    // Also reposition when network is stabilized or zoomed/dragged
    gv.network.on('zoom', positionOverlays);
    gv.network.on('dragEnd', positionOverlays);

    console.log('[sum-propagation] loaded');
})(window.graphVis);
