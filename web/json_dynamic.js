import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

app.registerExtension({
    name: "json.dynamic.loader",

    async beforeRegisterNodeDef(nodeType, nodeData, app) {
        if (nodeData.name !== "JSONDynamicLoader") return;

        const origOnNodeCreated = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            origOnNodeCreated?.apply(this, arguments);

            // Hide internal widgets (managed by JS)
            for (const name of ["output_keys", "output_types"]) {
                const w = this.widgets?.find(w => w.name === name);
                if (w) { w.type = "hidden"; w.computeSize = () => [0, -4]; }
            }

            // Remove all 32 default outputs from Python RETURN_TYPES
            while (this.outputs.length > 0) {
                this.removeOutput(0);
            }

            // Add Refresh button
            this.addWidget("button", "Refresh Outputs", null, () => {
                this.refreshDynamicOutputs();
            });

            this.setSize(this.computeSize());
        };

        nodeType.prototype.refreshDynamicOutputs = async function () {
            const pathWidget = this.widgets?.find(w => w.name === "json_path");
            const seqWidget = this.widgets?.find(w => w.name === "sequence_number");
            if (!pathWidget?.value) return;

            try {
                const resp = await api.fetchApi(
                    `/json_dynamic/get_keys?path=${encodeURIComponent(pathWidget.value)}&sequence_number=${seqWidget?.value || 1}`
                );
                const { keys, types } = await resp.json();

                // Store keys and types in hidden widgets for persistence
                const okWidget = this.widgets?.find(w => w.name === "output_keys");
                if (okWidget) okWidget.value = keys.join(",");
                const otWidget = this.widgets?.find(w => w.name === "output_types");
                if (otWidget) otWidget.value = types.join(",");

                // Build a map of current output names to slot indices
                const oldSlots = {};
                for (let i = 0; i < this.outputs.length; i++) {
                    oldSlots[this.outputs[i].name] = i;
                }

                // Build new outputs, reusing existing slots to preserve links
                const newOutputs = [];
                for (let k = 0; k < keys.length; k++) {
                    const key = keys[k];
                    const type = types[k] || "*";
                    if (key in oldSlots) {
                        // Reuse existing slot object (keeps links intact)
                        const slot = this.outputs[oldSlots[key]];
                        slot.type = type;
                        newOutputs.push(slot);
                        delete oldSlots[key];
                    } else {
                        // New key — create a fresh slot
                        newOutputs.push({ name: key, type: type, links: null });
                    }
                }

                // Disconnect links on slots that are being removed
                for (const name in oldSlots) {
                    const idx = oldSlots[name];
                    if (this.outputs[idx]?.links?.length) {
                        for (const linkId of [...this.outputs[idx].links]) {
                            this.graph?.removeLink(linkId);
                        }
                    }
                }

                // Reassign the outputs array and fix link slot indices
                this.outputs = newOutputs;
                if (this.graph) {
                    for (let i = 0; i < this.outputs.length; i++) {
                        const links = this.outputs[i].links;
                        if (!links) continue;
                        for (const linkId of links) {
                            const link = this.graph.links[linkId];
                            if (link) link.origin_slot = i;
                        }
                    }
                }

                this.setSize(this.computeSize());
                app.graph.setDirtyCanvas(true, true);
            } catch (e) {
                console.error("[JSONDynamicLoader] Refresh failed:", e);
            }
        };

        // Restore state on workflow load
        const origOnConfigure = nodeType.prototype.onConfigure;
        nodeType.prototype.onConfigure = function (info) {
            origOnConfigure?.apply(this, arguments);

            // Hide internal widgets
            for (const name of ["output_keys", "output_types"]) {
                const w = this.widgets?.find(w => w.name === name);
                if (w) { w.type = "hidden"; w.computeSize = () => [0, -4]; }
            }

            const okWidget = this.widgets?.find(w => w.name === "output_keys");
            const otWidget = this.widgets?.find(w => w.name === "output_types");

            const keys = okWidget?.value
                ? okWidget.value.split(",").filter(k => k.trim())
                : [];
            const types = otWidget?.value
                ? otWidget.value.split(",")
                : [];

            // On load, LiteGraph already restored serialized outputs with links.
            // Rename and set types to match stored state (preserves links).
            for (let i = 0; i < this.outputs.length && i < keys.length; i++) {
                this.outputs[i].name = keys[i].trim();
                if (types[i]) this.outputs[i].type = types[i];
            }

            // Remove any extra outputs beyond the key count
            while (this.outputs.length > keys.length) {
                this.removeOutput(this.outputs.length - 1);
            }

            this.setSize(this.computeSize());
        };
    },
});
