(function(gv) {
    'use strict';

    var counter = 0;
    var overlays = {}; // nodeId -> overlay DOM element

    function randomHex() {
        var hex = '#';
        for (var i = 0; i < 6; i++) {
            hex += '0123456789ABCDEF'[Math.floor(Math.random() * 16)];
        }
        return hex;
    }

    function nextId() {
        counter++;
        return 'spawner-' + counter;
    }

    function createOverlay(nodeId, parentId) {
        var color = randomHex();
        var overlay = document.createElement('div');
        overlay.className = 'color-spawner-overlay';
        overlay.dataset.nodeId = nodeId;

        var input = document.createElement('input');
        input.type = 'text';
        input.value = color;
        input.style.borderColor = color;

        input.addEventListener('input', function() {
            var val = input.value.trim();
            if (/^#[0-9A-Fa-f]{6}$/.test(val)) {
                input.style.borderColor = val;
            }
        });

        var btn = document.createElement('button');
        btn.textContent = 'New';
        btn.addEventListener('click', function() {
            spawnChild(nodeId, input.value.trim());
        });

        overlay.appendChild(input);
        overlay.appendChild(btn);
        gv.container.appendChild(overlay);
        overlays[nodeId] = overlay;

        updateOverlayPosition(nodeId);
    }

    function updateOverlayPosition(nodeId) {
        var overlay = overlays[nodeId];
        if (!overlay) return;
        try {
            var canvasPos = gv.network.getPosition(nodeId);
            var domPos = gv.network.canvasToDOM(canvasPos);
            overlay.style.left = domPos.x + 'px';
            overlay.style.top = domPos.y + 'px';
            overlay.style.display = '';
        } catch (e) {
            overlay.style.display = 'none';
        }
    }

    function updateAllOverlays() {
        for (var nodeId in overlays) {
            updateOverlayPosition(nodeId);
        }
    }

    function spawnChild(parentId, hexColor) {
        if (!/^#[0-9A-Fa-f]{6}$/.test(hexColor)) {
            hexColor = '#CCCCCC';
        }

        var childId = nextId();
        var childLabel = 'Node ' + counter;

        gv.nodes.add({
            id: childId,
            label: childLabel,
            color: {
                background: hexColor,
                border: hexColor,
                highlight: { background: hexColor, border: hexColor }
            },
            font: { color: isLight(hexColor) ? '#000' : '#fff' }
        });

        gv.edges.add({
            from: parentId,
            to: childId
        });

        gv.sendEvent('ext:color-spawner:node-created', {
            id: childId,
            color: hexColor,
            parent: parentId
        });

        createOverlay(childId, parentId);
    }

    function isLight(hex) {
        var r = parseInt(hex.slice(1, 3), 16);
        var g = parseInt(hex.slice(3, 5), 16);
        var b = parseInt(hex.slice(5, 7), 16);
        return (r * 299 + g * 587 + b * 114) / 1000 > 140;
    }

    // Create root spawner node
    var rootId = nextId(); // spawner-1
    gv.nodes.add({
        id: rootId,
        label: 'Spawner',
        color: {
            background: '#FFFFFF',
            border: '#AAAAAA',
            highlight: { background: '#F5F5F5', border: '#888888' }
        },
        font: { color: '#333' }
    });

    createOverlay(rootId, null);

    // Reposition overlays on draw (handles drag, zoom, pan)
    gv.network.on('afterDrawing', updateAllOverlays);

    console.log('[color-spawner] loaded');

})(window.graphVis);
