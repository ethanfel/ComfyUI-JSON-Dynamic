import { app } from "../../scripts/app.js";

app.registerExtension({
    name: "jdl.preview.to.load",

    async beforeRegisterNodeDef(nodeType, nodeData, app) {
        if (nodeData.name !== "JDL_PreviewToLoad") return;

        const origOnNodeCreated = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            origOnNodeCreated?.apply(this, arguments);

            this.addWidget("number", "load_image_node_id", 0, (v) => {}, {
                min: 0,
                max: 99999,
                step: 10,
                precision: 0,
            });

            this.addWidget("button", "Send to Load Image", null, () => {
                const nodeIdWidget = this.widgets?.find(w => w.name === "load_image_node_id");
                if (!nodeIdWidget) return;

                const targetId = Math.round(nodeIdWidget.value);
                const targetNode = app.graph.getNodeById(targetId);
                if (!targetNode) {
                    console.warn("[PreviewToLoad] No node found with ID:", targetId);
                    return;
                }

                const filename = this.last_input_filename;
                if (!filename) {
                    console.warn("[PreviewToLoad] No filename available. Run the workflow first.");
                    return;
                }

                const imageWidget = targetNode.widgets?.find(w => w.name === "image");
                if (!imageWidget) {
                    console.warn("[PreviewToLoad] Target node has no 'image' widget.");
                    return;
                }

                // Add filename to combo options if not already present
                if (imageWidget.options?.values && !imageWidget.options.values.includes(filename)) {
                    imageWidget.options.values.push(filename);
                }

                imageWidget.value = filename;
                if (imageWidget.callback) {
                    imageWidget.callback(filename);
                }

                app.graph.setDirtyCanvas(true, true);
            });

            this.addWidget("text", "channel", "default", () => {});

            this.addWidget("button", "Send to Channel", null, () => {
                const channelWidget = this.widgets?.find(w => w.name === "channel");
                const channel = channelWidget?.value || "default";

                const filename = this.last_input_filename;
                if (!filename) {
                    console.warn("[PreviewToLoad] No filename available. Run the workflow first.");
                    return;
                }

                fetch("/jdl/channel/send", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ channel, filename }),
                })
                .then(r => r.json())
                .then(data => {
                    if (data.ok) {
                        console.log(`[PreviewToLoad] Sent "${filename}" to channel "${channel}"`);
                    } else {
                        console.warn("[PreviewToLoad] Channel send failed:", data.error);
                    }
                })
                .catch(err => console.error("[PreviewToLoad] Channel send error:", err));
            });

            this.setSize(this.computeSize());
        };

        const origOnExecuted = nodeType.prototype.onExecuted;
        nodeType.prototype.onExecuted = function (output) {
            origOnExecuted?.apply(this, arguments);

            if (output?.input_filename?.length) {
                this.last_input_filename = output.input_filename[0];
            }
        };
    },
});
