(function(gv) {
    'use strict';

    // -- Modal DOM elements ------------------------------------------------
    var overlay = document.createElement('div');
    overlay.style.cssText =
        'position:fixed;top:0;left:0;width:100%;height:100%;' +
        'background:rgba(0,0,0,0.45);z-index:10000;display:none;' +
        'align-items:center;justify-content:center;';

    var dialog = document.createElement('div');
    dialog.style.cssText =
        'background:#1e1e2e;color:#cdd6f4;border:1px solid #585b70;' +
        'border-radius:10px;padding:24px 32px;min-width:280px;' +
        'text-align:center;font-family:sans-serif;box-shadow:0 8px 32px rgba(0,0,0,0.5);';

    var msg = document.createElement('p');
    msg.style.cssText = 'margin:0 0 20px;font-size:15px;';

    var btnRow = document.createElement('div');
    btnRow.style.cssText = 'display:flex;gap:12px;justify-content:center;';

    var btnConfirm = document.createElement('button');
    btnConfirm.textContent = 'Delete';
    btnConfirm.style.cssText =
        'padding:8px 22px;border:none;border-radius:6px;cursor:pointer;' +
        'font-size:14px;background:#f38ba8;color:#1e1e2e;font-weight:600;';

    var btnCancel = document.createElement('button');
    btnCancel.textContent = 'Cancel';
    btnCancel.style.cssText =
        'padding:8px 22px;border:1px solid #585b70;border-radius:6px;cursor:pointer;' +
        'font-size:14px;background:transparent;color:#cdd6f4;';

    btnRow.appendChild(btnConfirm);
    btnRow.appendChild(btnCancel);
    dialog.appendChild(msg);
    dialog.appendChild(btnRow);
    overlay.appendChild(dialog);
    document.body.appendChild(overlay);

    // -- State -------------------------------------------------------------
    var pendingNodeId = null;

    function showModal(label) {
        msg.textContent = 'Delete vertex ' + label + '?';
        overlay.style.display = 'flex';
    }

    function hideModal() {
        overlay.style.display = 'none';
        pendingNodeId = null;
    }

    // -- Button handlers ---------------------------------------------------
    btnConfirm.addEventListener('click', function() {
        if (pendingNodeId !== null) {
            gv.api.removeNode(pendingNodeId);
        }
        hideModal();
    });

    btnCancel.addEventListener('click', hideModal);

    overlay.addEventListener('click', function(e) {
        if (e.target === overlay) hideModal();
    });

    // -- Keyboard: Escape to cancel, Enter to confirm ----------------------
    document.addEventListener('keydown', function(e) {
        if (overlay.style.display !== 'flex') return;
        if (e.key === 'Escape') { hideModal(); }
        if (e.key === 'Enter')  { btnConfirm.click(); }
    });

    // -- Register doubleClick on vis-network -------------------------------
    gv.network.on('doubleClick', function(params) {
        if (!params.nodes || params.nodes.length === 0) return;

        var nodeId = params.nodes[0];
        var node = gv.nodes.get(nodeId);
        if (!node) return;

        // Yield to hook system if the node defines on_doubleClick actions
        if (node.on_doubleClick && Array.isArray(node.on_doubleClick) && node.on_doubleClick.length > 0) {
            return;
        }

        pendingNodeId = nodeId;
        showModal(node.label || nodeId);
    });

    console.log('[delete-on-doubleclick] loaded');
})(window.graphVis);
