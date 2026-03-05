import hashlib
import json
import os
import random

import numpy as np
import torch
from PIL import Image, ImageOps, ImageSequence
from PIL.PngImagePlugin import PngInfo

import folder_paths
import node_helpers
from comfy.cli_args import args
from comfy_execution.graph_utils import ExecutionBlocker

try:
    from server import PromptServer
    from aiohttp import web
except ImportError:
    PromptServer = None

CHANNELS_FILE = os.path.join(os.path.dirname(__file__), "channels.json")


def _read_channels():
    if os.path.exists(CHANNELS_FILE):
        try:
            with open(CHANNELS_FILE, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, ValueError):
            return {}
    return {}


def _write_channels(data):
    with open(CHANNELS_FILE, "w") as f:
        json.dump(data, f, indent=2)


if PromptServer is not None:
    @PromptServer.instance.routes.post("/jdl/channel/send")
    async def channel_send(request):
        body = await request.json()
        channel = body.get("channel", "default")
        filename = body.get("filename", "")
        if not filename:
            return web.json_response({"error": "filename required"}, status=400)
        channels = _read_channels()
        channels[channel] = filename
        _write_channels(channels)
        return web.json_response({"ok": True, "channel": channel, "filename": filename})

    @PromptServer.instance.routes.get("/jdl/channel/receive")
    async def channel_receive(request):
        channel = request.query.get("channel", "default")
        channels = _read_channels()
        filename = channels.get(channel, "")
        return web.json_response({"channel": channel, "filename": filename})

    @PromptServer.instance.routes.get("/jdl/channel/list")
    async def channel_list(request):
        channels = _read_channels()
        return web.json_response({"channels": list(channels.keys())})


class JDL_PreviewToLoad:
    """Previews an image and saves a copy to input/ for use by LoadImage nodes."""

    def __init__(self):
        self.output_dir = folder_paths.get_temp_directory()
        self.type = "temp"
        self.prefix_append = "_temp_" + ''.join(
            random.choice("abcdefghijklmnopqrstupvxyz") for _ in range(5)
        )
        self.compress_level = 1

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "images": ("IMAGE",),
                "filename": ("STRING", {"default": "preview"}),
            },
            "optional": {
                "mask": ("MASK",),
            },
            "hidden": {
                "prompt": "PROMPT",
                "extra_pnginfo": "EXTRA_PNGINFO",
            },
        }

    RETURN_TYPES = ()
    FUNCTION = "preview_and_save"
    OUTPUT_NODE = True
    CATEGORY = "utils/image"

    def preview_and_save(self, images, filename="preview", mask=None, prompt=None, extra_pnginfo=None):
        # Save to temp/ for preview (same as PreviewImage)
        filename_prefix = "ComfyUI" + self.prefix_append
        full_output_folder, fname, counter, subfolder, filename_prefix = (
            folder_paths.get_save_image_path(
                filename_prefix, self.output_dir,
                images[0].shape[1], images[0].shape[0]
            )
        )

        results = []
        for batch_number, image in enumerate(images):
            i = 255.0 * image.cpu().numpy()
            img = Image.fromarray(np.clip(i, 0, 255).astype(np.uint8))

            metadata = None
            if not args.disable_metadata:
                metadata = PngInfo()
                if prompt is not None:
                    metadata.add_text("prompt", json.dumps(prompt))
                if extra_pnginfo is not None:
                    for x in extra_pnginfo:
                        metadata.add_text(x, json.dumps(extra_pnginfo[x]))

            temp_file = f"{fname}_{counter:05}_.png"
            img.save(
                os.path.join(full_output_folder, temp_file),
                pnginfo=metadata, compress_level=self.compress_level,
            )
            results.append({
                "filename": temp_file,
                "subfolder": subfolder,
                "type": self.type,
            })
            counter += 1

        # Save first image to input/ for LoadImage consumption
        input_dir = folder_paths.get_input_directory()
        safe_name = os.path.basename(filename).strip().strip(".")
        if not safe_name:
            safe_name = "preview"
        input_filename = f"{safe_name}.png"

        first_image = 255.0 * images[0].cpu().numpy()
        first_img = Image.fromarray(np.clip(first_image, 0, 255).astype(np.uint8))

        # Embed mask as alpha channel so LoadImage extracts it
        if mask is not None:
            mask_data = mask[0].cpu().numpy() if mask.dim() == 3 else mask.cpu().numpy()
            # LoadImage inverts alpha (mask = 1 - alpha), so save alpha = 1 - mask
            alpha = np.clip((1.0 - mask_data) * 255.0, 0, 255).astype(np.uint8)
            alpha_img = Image.fromarray(alpha)
            if alpha_img.size != first_img.size:
                alpha_img = alpha_img.resize(first_img.size, Image.LANCZOS)
            first_img = first_img.convert("RGBA")
            first_img.putalpha(alpha_img)

        metadata = None
        if not args.disable_metadata:
            metadata = PngInfo()
            if prompt is not None:
                metadata.add_text("prompt", json.dumps(prompt))
            if extra_pnginfo is not None:
                for x in extra_pnginfo:
                    metadata.add_text(x, json.dumps(extra_pnginfo[x]))

        first_img.save(
            os.path.join(input_dir, input_filename),
            pnginfo=metadata, compress_level=4,
        )

        return {"ui": {"images": results, "input_filename": [input_filename]}}


def _load_image_from_path(image_path):
    """Shared helper: load an image file and return (IMAGE tensor, MASK tensor)."""
    img = node_helpers.pillow(Image.open, image_path)

    output_images = []
    output_masks = []
    w, h = None, None

    for i in ImageSequence.Iterator(img):
        i = node_helpers.pillow(ImageOps.exif_transpose, i)

        if i.mode == 'I':
            i = i.point(lambda i: i * (1 / 255))
        frame = i.convert("RGB")

        if len(output_images) == 0:
            w = frame.size[0]
            h = frame.size[1]

        if frame.size[0] != w or frame.size[1] != h:
            continue

        frame_np = np.array(frame).astype(np.float32) / 255.0
        frame_tensor = torch.from_numpy(frame_np)[None,]
        if 'A' in i.getbands():
            mask = np.array(i.getchannel('A')).astype(np.float32) / 255.0
            mask = 1. - torch.from_numpy(mask)
        elif i.mode == 'P' and 'transparency' in i.info:
            mask = np.array(i.convert('RGBA').getchannel('A')).astype(np.float32) / 255.0
            mask = 1. - torch.from_numpy(mask)
        else:
            mask = torch.zeros((64, 64), dtype=torch.float32, device="cpu")
        output_images.append(frame_tensor)
        output_masks.append(mask.unsqueeze(0))

        if img.format == "MPO":
            break

    if len(output_images) > 1:
        output_image = torch.cat(output_images, dim=0)
        output_mask = torch.cat(output_masks, dim=0)
    else:
        output_image = output_images[0]
        output_mask = output_masks[0]

    return (output_image, output_mask)


class JDL_LoadImage:
    """Load an image from the input directory with an active switch to skip downstream execution."""

    @classmethod
    def INPUT_TYPES(s):
        input_dir = folder_paths.get_input_directory()
        files = [f for f in os.listdir(input_dir) if os.path.isfile(os.path.join(input_dir, f))]
        files = folder_paths.filter_files_content_types(files, ["image"])
        return {
            "required": {
                "image": (sorted(files), {"image_upload": True}),
                "active": ("BOOLEAN", {"default": True}),
            },
        }

    RETURN_TYPES = ("IMAGE", "MASK")
    FUNCTION = "load_image"
    CATEGORY = "utils/image"

    def load_image(self, image, active):
        if not active:
            return (ExecutionBlocker(None), ExecutionBlocker(None))

        image_path = folder_paths.get_annotated_filepath(image)
        return _load_image_from_path(image_path)

    @classmethod
    def IS_CHANGED(s, image, active):
        if not active:
            return "inactive"
        image_path = folder_paths.get_annotated_filepath(image)
        m = hashlib.sha256()
        with open(image_path, 'rb') as f:
            m.update(f.read())
        return m.digest().hex()

    @classmethod
    def VALIDATE_INPUTS(s, image, active):
        if not active:
            return True
        if not folder_paths.exists_annotated_filepath(image):
            return "Invalid image file: {}".format(image)
        return True


class JDL_ImageReceiver:
    """Load an image from a named channel (cross-workflow image passing)."""

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "channel": ("STRING", {"default": "default"}),
                "active": ("BOOLEAN", {"default": True}),
            },
        }

    RETURN_TYPES = ("IMAGE", "MASK", "STRING")
    RETURN_NAMES = ("image", "mask", "filename")
    FUNCTION = "receive"
    CATEGORY = "utils/image"

    def receive(self, channel, active):
        if not active:
            return (ExecutionBlocker(None), ExecutionBlocker(None), ExecutionBlocker(None))

        channels = _read_channels()
        filename = channels.get(channel, "")
        if not filename:
            return (ExecutionBlocker(None), ExecutionBlocker(None), ExecutionBlocker(None))

        input_dir = folder_paths.get_input_directory()
        image_path = os.path.join(input_dir, filename)
        if not os.path.isfile(image_path):
            return (ExecutionBlocker(None), ExecutionBlocker(None), ExecutionBlocker(None))

        output_image, output_mask = _load_image_from_path(image_path)
        return (output_image, output_mask, filename)

    @classmethod
    def IS_CHANGED(s, channel, active):
        if not active:
            return "inactive"
        channels = _read_channels()
        filename = channels.get(channel, "")
        return hashlib.sha256(filename.encode()).hexdigest()

    @classmethod
    def VALIDATE_INPUTS(s, channel, active):
        return True


NODE_CLASS_MAPPINGS = {
    "JDL_PreviewToLoad": JDL_PreviewToLoad,
    "JDL_LoadImage": JDL_LoadImage,
    "JDL_ImageReceiver": JDL_ImageReceiver,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "JDL_PreviewToLoad": "Preview to Load Image",
    "JDL_LoadImage": "Load Image (Active Switch)",
    "JDL_ImageReceiver": "Image Receiver (Channel)",
}
