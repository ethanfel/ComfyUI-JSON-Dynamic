import { app } from "../../scripts/app.js";

const NODE_TYPE = "JDL_DependencyPassthrough";
const WAIT_FOR_INPUT = "wait_for";
const CHAIN_COLOR = "#4ea6f7";
const CHAIN_COLOR_DIM = "#2a5a8a";

/** Find the input slot index for wait_for on a node. */
function getWaitForSlot(node) {
    if (!node.inputs) return -1;
    for (let i = 0; i < node.inputs.length; i++) {
        if (node.inputs[i].name === WAIT_FOR_INPUT) return i;
    }
    return -1;
}

/** Get all JDL_DependencyPassthrough nodes in the graph sorted by order. */
function getSortedPassthroughNodes(graph) {
    const nodes = [];
    for (const node of graph._nodes || []) {
        if (node.type === NODE_TYPE) {
            const orderW = node.widgets?.find(w => w.name === "order");
            nodes.push({ node, order: orderW ? orderW.value : 0 });
        }
    }
    nodes.sort((a, b) => a.order - b.order || a.node.id - b.node.id);
    return nodes;
}

/** Remove all links connected to the wait_for input of a node. */
function clearWaitForLinks(node, graph) {
    const slot = getWaitForSlot(node);
    if (slot < 0) return;
    const input = node.inputs[slot];
    if (input && input.link != null) {
        graph.removeLink(input.link);
    }
}

/**
 * Rewire all passthrough nodes: connect each node's data output (slot 0)
 * to the next-order node's wait_for input.
 */
function rewireAll(graph) {
    if (!graph || graph._rewiring) return;
    graph._rewiring = true;
    graph._prevNodeMap = null; // invalidate rendering cache
    try {
        const sorted = getSortedPassthroughNodes(graph);

        // Clear all wait_for links first
        for (const { node } of sorted) {
            clearWaitForLinks(node, graph);
        }

        // Connect consecutive pairs
        for (let i = 0; i < sorted.length - 1; i++) {
            const srcNode = sorted[i].node;
            const dstNode = sorted[i + 1].node;
            const dstSlot = getWaitForSlot(dstNode);
            if (dstSlot < 0) continue;
            // output slot 0 = data output
            srcNode.connect(0, dstNode, dstSlot);
        }

        graph.setDirtyCanvas(true, true);
    } finally {
        graph._rewiring = false;
    }
}

/**
 * Build a map from node id to its predecessor in the sorted chain.
 * Cached per graph and invalidated when rewireAll runs.
 */
function getPrevNodeMap(graph) {
    if (graph._prevNodeMap) return graph._prevNodeMap;
    const sorted = getSortedPassthroughNodes(graph);
    const map = new Map();
    for (let i = 1; i < sorted.length; i++) {
        map.set(sorted[i].node.id, sorted[i - 1]);
    }
    graph._prevNodeMap = map;
    return map;
}

app.registerExtension({
    name: "jdl.dependency.passthrough",

    async beforeRegisterNodeDef(nodeType, nodeData, appInstance) {
        if (nodeData.name !== NODE_TYPE) return;

        // --- onNodeCreated: add order widget, hide wait_for ---
        const origOnNodeCreated = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            origOnNodeCreated?.apply(this, arguments);

            // Add order widget
            this.addWidget("number", "order", 1, (v) => {
                // Clamp to 1-99
                const clamped = Math.max(1, Math.min(99, Math.round(v)));
                const orderW = this.widgets?.find(w => w.name === "order");
                if (orderW && orderW.value !== clamped) orderW.value = clamped;
                // Rewire after order changes
                if (this.graph) rewireAll(this.graph);
            }, { min: 1, max: 99, step: 1, precision: 0 });

            // Hide the wait_for input visually
            this._hideWaitFor();

            this.setSize(this.computeSize());
        };

        // --- Helper to hide wait_for slot ---
        nodeType.prototype._hideWaitFor = function () {
            const slot = getWaitForSlot(this);
            if (slot >= 0 && this.inputs[slot]) {
                this.inputs[slot].hidden = true;
            }
        };

        // --- onConfigure: restore order widget from saved data ---
        const origOnConfigure = nodeType.prototype.onConfigure;
        nodeType.prototype.onConfigure = function (info) {
            origOnConfigure?.apply(this, arguments);

            // Restore order widget value from serialized widget values
            const orderW = this.widgets?.find(w => w.name === "order");
            if (orderW && info.widgets_values) {
                const orderIdx = this.widgets.indexOf(orderW);
                if (orderIdx >= 0 && orderIdx < info.widgets_values.length) {
                    const v = info.widgets_values[orderIdx];
                    if (typeof v === "number") {
                        orderW.value = Math.max(1, Math.min(99, Math.round(v)));
                    }
                }
            }

            this._hideWaitFor();
        };

        // --- onAdded: rewire when node is placed on graph ---
        const origOnAdded = nodeType.prototype.onAdded;
        nodeType.prototype.onAdded = function (graph) {
            origOnAdded?.apply(this, arguments);
            this._hideWaitFor();
            // Defer to let graph settle
            queueMicrotask(() => {
                if (this.graph) rewireAll(this.graph);
            });
        };

        // --- onRemoved: rewire remaining nodes ---
        const origOnRemoved = nodeType.prototype.onRemoved;
        nodeType.prototype.onRemoved = function () {
            const graph = this.graph;
            origOnRemoved?.apply(this, arguments);
            if (graph) {
                queueMicrotask(() => rewireAll(graph));
            }
        };

        // --- onConnectionsChange: prevent manual wait_for edits ---
        const origOnConnectionsChange = nodeType.prototype.onConnectionsChange;
        nodeType.prototype.onConnectionsChange = function (type, slotIndex, isConnected, linkInfo, ioSlot) {
            origOnConnectionsChange?.apply(this, arguments);
            if (this.graph?._rewiring) return;

            // If user manually disconnected/connected the wait_for slot, re-enforce auto wiring
            if (type === LiteGraph.INPUT) {
                const waitSlot = getWaitForSlot(this);
                if (slotIndex === waitSlot) {
                    queueMicrotask(() => {
                        if (this.graph) rewireAll(this.graph);
                    });
                }
            }
        };

        // --- onDrawForeground: draw chain visualization ---
        const origOnDrawForeground = nodeType.prototype.onDrawForeground;
        nodeType.prototype.onDrawForeground = function (ctx) {
            origOnDrawForeground?.apply(this, arguments);
            if (!this.graph || this.flags?.collapsed) return;

            const orderW = this.widgets?.find(w => w.name === "order");
            if (!orderW) return;

            // Draw order badge in top-right corner
            const orderNum = orderW.value;
            ctx.save();
            const badgeX = this.size[0] - 28;
            const badgeY = -LiteGraph.NODE_TITLE_HEIGHT + 4;
            const badgeW = 24;
            const badgeH = LiteGraph.NODE_TITLE_HEIGHT - 8;
            const radius = 4;

            // Rounded rect background
            ctx.fillStyle = CHAIN_COLOR;
            ctx.beginPath();
            ctx.roundRect(badgeX, badgeY, badgeW, badgeH, radius);
            ctx.fill();

            // Order number text
            ctx.fillStyle = "#fff";
            ctx.font = "bold 11px sans-serif";
            ctx.textAlign = "center";
            ctx.textBaseline = "middle";
            ctx.fillText(orderNum, badgeX + badgeW / 2, badgeY + badgeH / 2);
            ctx.restore();

            // Draw dashed chain line from previous-order node
            const prevMap = getPrevNodeMap(this.graph);
            const prev = prevMap.get(this.id);
            if (!prev) return;

            const srcNode = prev.node;
            // Calculate connection points in graph space, then convert to local
            const srcX = srcNode.pos[0] + srcNode.size[0] / 2;
            const srcY = srcNode.pos[1] + srcNode.size[1];
            const dstX = this.pos[0] + this.size[0] / 2;
            const dstY = this.pos[1] + 10;

            // Convert to local coords (this node's space)
            const localSrcX = srcX - this.pos[0];
            const localSrcY = srcY - this.pos[1];
            const localDstX = dstX - this.pos[0];
            const localDstY = dstY - this.pos[1];

            ctx.save();
            ctx.strokeStyle = CHAIN_COLOR_DIM;
            ctx.lineWidth = 2;
            ctx.setLineDash([6, 4]);
            ctx.globalAlpha = 0.6;
            ctx.beginPath();
            ctx.moveTo(localSrcX, localSrcY);

            // Curved line for better visual
            const midY = (localSrcY + localDstY) / 2;
            ctx.bezierCurveTo(
                localSrcX, midY,
                localDstX, midY,
                localDstX, localDstY
            );
            ctx.stroke();

            // Draw a small arrow at the destination
            ctx.setLineDash([]);
            ctx.globalAlpha = 0.8;
            ctx.fillStyle = CHAIN_COLOR_DIM;
            ctx.beginPath();
            ctx.moveTo(localDstX, localDstY);
            ctx.lineTo(localDstX - 5, localDstY - 8);
            ctx.lineTo(localDstX + 5, localDstY - 8);
            ctx.closePath();
            ctx.fill();
            ctx.restore();
        };
    },

    /** After the full graph is configured (workflow load), rewire everything. */
    async setup(appInstance) {
        function hookGraph(graph) {
            if (!graph || graph._passthroughHooked) return;
            graph._passthroughHooked = true;
            const origAfterConfigure = graph.onAfterConfigure;
            graph.onAfterConfigure = function () {
                origAfterConfigure?.apply(this, arguments);
                queueMicrotask(() => {
                    for (const node of graph._nodes || []) {
                        if (node.type === NODE_TYPE) {
                            node._hideWaitFor?.();
                        }
                    }
                    rewireAll(graph);
                });
            };
        }

        // Hook now if graph exists, otherwise poll briefly until it does
        if (app.graph) {
            hookGraph(app.graph);
        } else {
            let attempts = 0;
            const interval = setInterval(() => {
                if (app.graph) {
                    clearInterval(interval);
                    hookGraph(app.graph);
                } else if (++attempts > 50) {
                    clearInterval(interval);
                }
            }, 100);
        }
    },
});
