import { app } from "../../scripts/app.js";

const FORMAT_WIDGETS = {
    "png":            [],
    "webp":           ["webp_lossless", "webp_quality", "webp_method"],
    "mp4":            ["video_fps", "video_crf", "video_pixel_format"],
    "h265-mp4":       ["video_fps", "video_crf", "video_pixel_format"],
    "av1-mp4":        ["video_fps", "video_crf", "video_pixel_format"],
    "webm":           ["video_fps", "video_crf", "video_pixel_format"],
    "gif":            ["video_fps", "gif_dither"],
    "ffv1-mkv":       ["video_fps", "video_pixel_format"],
    "prores-mov":     ["video_fps", "prores_profile"],
    "nvenc_h264-mp4": ["video_fps", "video_pixel_format", "video_bitrate"],
    "nvenc_hevc-mp4": ["video_fps", "video_pixel_format", "video_bitrate"],
    "nvenc_av1-mp4":  ["video_fps", "video_pixel_format", "video_bitrate"],
};

const FORMAT_PIX_FMTS = {
    "mp4":            ["yuv420p", "yuv444p"],
    "h265-mp4":       ["yuv420p", "yuv444p", "yuv420p10le"],
    "av1-mp4":        ["yuv420p", "yuv420p10le"],
    "webm":           ["yuv420p", "yuv444p", "yuv420p10le"],
    "ffv1-mkv":       ["yuv420p", "yuv422p", "yuv444p", "rgb24", "bgra"],
    "nvenc_h264-mp4": ["yuv420p", "yuv444p"],
    "nvenc_hevc-mp4": ["yuv420p", "yuv444p", "yuv420p10le"],
    "nvenc_av1-mp4":  ["yuv420p", "yuv420p10le"],
};

const ALL_MANAGED = [
    "webp_lossless", "webp_quality", "webp_method",
    "video_fps", "video_crf", "video_pixel_format",
    "video_bitrate", "prores_profile", "gif_dither",
];

function hideWidget(node, widget) {
    if (widget.origType === undefined) widget.origType = widget.type;
    widget.type = "hidden";
    widget.computeSize = () => [0, -4];
}

function showWidget(node, widget) {
    if (widget.origType !== undefined) {
        widget.type = widget.origType;
        delete widget.origType;
        delete widget.computeSize;
    }
}

function updateVisibility(node) {
    const formatWidget = node.widgets?.find(w => w.name === "save_format");
    if (!formatWidget) return;

    const format = formatWidget.value;
    const visible = new Set(FORMAT_WIDGETS[format] || []);

    for (const name of ALL_MANAGED) {
        const w = node.widgets?.find(w => w.name === name);
        if (!w) continue;
        if (visible.has(name)) {
            showWidget(node, w);
        } else {
            hideWidget(node, w);
        }
    }

    // Update pixel format combo options
    const pixWidget = node.widgets?.find(w => w.name === "video_pixel_format");
    if (pixWidget && FORMAT_PIX_FMTS[format]) {
        const opts = FORMAT_PIX_FMTS[format];
        pixWidget.options.values = opts;
        if (!opts.includes(pixWidget.value)) {
            pixWidget.value = opts[0];
        }
    }

    node.setSize(node.computeSize());
    app.graph?.setDirtyCanvas(true, true);
}

app.registerExtension({
    name: "fast.absolute.saver.visibility",

    async beforeRegisterNodeDef(nodeType, nodeData, app) {
        if (nodeData.name !== "FastAbsoluteSaver") return;

        const origOnNodeCreated = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            origOnNodeCreated?.apply(this, arguments);

            const formatWidget = this.widgets?.find(w => w.name === "save_format");
            if (formatWidget) {
                const origCallback = formatWidget.callback;
                formatWidget.callback = (...args) => {
                    origCallback?.apply(formatWidget, args);
                    updateVisibility(this);
                };
            }

            // Defer initial update so all widgets exist
            queueMicrotask(() => updateVisibility(this));
        };

        const origOnConfigure = nodeType.prototype.onConfigure;
        nodeType.prototype.onConfigure = function (info) {
            origOnConfigure?.apply(this, arguments);
            queueMicrotask(() => updateVisibility(this));
        };
    },
});
