import json
import os
import random

import numpy as np
from PIL import Image
from PIL.PngImagePlugin import PngInfo

import folder_paths
from comfy.cli_args import args


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
            "hidden": {
                "prompt": "PROMPT",
                "extra_pnginfo": "EXTRA_PNGINFO",
            },
        }

    RETURN_TYPES = ()
    FUNCTION = "preview_and_save"
    OUTPUT_NODE = True
    CATEGORY = "utils/image"

    def preview_and_save(self, images, filename="preview", prompt=None, extra_pnginfo=None):
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


NODE_CLASS_MAPPINGS = {
    "JDL_PreviewToLoad": JDL_PreviewToLoad,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "JDL_PreviewToLoad": "Preview to Load Image",
}
