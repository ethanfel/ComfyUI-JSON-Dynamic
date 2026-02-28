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

            // Do NOT remove default outputs synchronously here.
            // During graph loading, ComfyUI creates all nodes (firing onNodeCreated)
            // before configuring them. Other nodes (e.g. Kijai Set/Get) may resolve
            // links to our outputs during their configure step. If we remove outputs
            // here, those nodes find no output slot and error out.
            //
            // Instead, defer cleanup: for loaded workflows onConfigure sets _configured
            // before this runs; for new nodes the defaults are cleaned up.
            this._configured = false;

            // Add Refresh button
            this.addWidget("button", "Refresh Outputs", null, () => {
                this.refreshDynamicOutputs();
            });

            queueMicrotask(() => {
                if (!this._configured) {
                    // New node (not loading) — remove the 32 Python default outputs
                    while (this.outputs.length > 0) {
                        this.removeOutput(0);
                    }
                    this.setSize(this.computeSize());
                    app.graph?.setDirtyCanvas(true, true);
                }
            });
        };

        nodeType.prototype.refreshDynamicOutputs = async function () {
            const pathWidget = this.widgets?.find(w => w.name === "json_path");
            const seqWidget = this.widgets?.find(w => w.name === "sequence_number");
            if (!pathWidget?.value) return;

            try {
                const resp = await api.fetchApi(
                    `/json_dynamic/get_keys?path=${encodeURIComponent(pathWidget.value)}&sequence_number=${seqWidget?.value || 1}`
                );
                const data = await resp.json();
                const { keys, types } = data;

                // If the file wasn't found, keep existing outputs and links intact
                if (data.error === "file_not_found") {
                    console.warn("[JSONDynamicLoader] File not found, keeping existing outputs:", pathWidget.value);
                    return;
                }

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
                        slot.label = key;
                        newOutputs.push(slot);
                        delete oldSlots[key];
                    } else {
                        // New key — create a fresh slot
                        newOutputs.push({ name: key, label: key, type: type, links: null });
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
            this._configured = true;

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

            if (keys.length > 0) {
                for (let i = 0; i < this.outputs.length && i < keys.length; i++) {
                    this.outputs[i].name = keys[i].trim();
                    this.outputs[i].label = keys[i].trim();
                    if (types[i]) this.outputs[i].type = types[i];
                }
                while (this.outputs.length > keys.length) {
                    this.removeOutput(this.outputs.length - 1);
                }
            } else if (this.outputs.length > 0) {
                // Widget values empty but serialized outputs exist — sync widgets
                // from the outputs LiteGraph already restored (fallback).
                if (okWidget) okWidget.value = this.outputs.map(o => o.name).join(",");
                if (otWidget) otWidget.value = this.outputs.map(o => o.type).join(",");
            }

            this.setSize(this.computeSize());
        };
    },
});
