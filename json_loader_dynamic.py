import json
import os
import logging
from typing import Any

logger = logging.getLogger(__name__)

KEY_BATCH_DATA = "batch_data"
MAX_DYNAMIC_OUTPUTS = 32


class AnyType(str):
    """Universal connector type that matches any ComfyUI type."""
    def __ne__(self, __value: object) -> bool:
        return False

any_type = AnyType("*")


try:
    from server import PromptServer
    from aiohttp import web
except ImportError:
    PromptServer = None


def read_json_data(json_path: str) -> dict[str, Any]:
    if not os.path.exists(json_path):
        logger.warning(f"File not found at {json_path}")
        return {}
    try:
        with open(json_path, 'r') as f:
            data = json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        logger.warning(f"Error reading {json_path}: {e}")
        return {}
    if not isinstance(data, dict):
        logger.warning(f"Expected dict from {json_path}, got {type(data).__name__}")
        return {}
    return data


def get_batch_item(data: dict[str, Any], sequence_number: int) -> dict[str, Any]:
    """Resolve batch item by sequence_number field, falling back to array index."""
    if KEY_BATCH_DATA in data and isinstance(data[KEY_BATCH_DATA], list) and len(data[KEY_BATCH_DATA]) > 0:
        for item in data[KEY_BATCH_DATA]:
            if int(item.get("sequence_number", 0)) == sequence_number:
                return item
        idx = max(0, min(sequence_number - 1, len(data[KEY_BATCH_DATA]) - 1))
        logger.warning(f"No item with sequence_number={sequence_number}, falling back to index {idx}")
        return data[KEY_BATCH_DATA][idx]
    return data


# --- API Route ---
if PromptServer is not None:
    @PromptServer.instance.routes.get("/json_dynamic/get_keys")
    async def get_keys_route(request):
        json_path = request.query.get("path", "")
        try:
            seq = int(request.query.get("sequence_number", "1"))
        except (ValueError, TypeError):
            seq = 1
        data = read_json_data(json_path)
        target = get_batch_item(data, seq)
        if not data:
            return web.json_response({"keys": [], "types": [], "error": "file_not_found"})
        keys = []
        types = []
        if isinstance(target, dict):
            for k, v in target.items():
                keys.append(k)
                if isinstance(v, bool):
                    types.append("STRING")
                elif isinstance(v, int):
                    types.append("INT")
                elif isinstance(v, float):
                    types.append("FLOAT")
                else:
                    types.append("STRING")
        return web.json_response({"keys": keys, "types": types})


class JSONDynamicLoader:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "json_path": ("STRING", {"default": "", "multiline": False}),
                "sequence_number": ("INT", {"default": 1, "min": 1, "max": 9999}),
            },
            "optional": {
                "output_keys": ("STRING", {"default": ""}),
                "output_types": ("STRING", {"default": ""}),
            },
        }

    RETURN_TYPES = tuple(any_type for _ in range(MAX_DYNAMIC_OUTPUTS))
    RETURN_NAMES = tuple(f"output_{i}" for i in range(MAX_DYNAMIC_OUTPUTS))
    FUNCTION = "load_dynamic"
    CATEGORY = "JSON Dynamic/json"
    OUTPUT_NODE = False

    def load_dynamic(self, json_path, sequence_number, output_keys="", output_types=""):
        data = read_json_data(json_path)
        target = get_batch_item(data, sequence_number)

        keys = [k.strip() for k in output_keys.split(",") if k.strip()] if output_keys else []

        results = []
        for key in keys:
            val = target.get(key, "")
            if isinstance(val, bool):
                results.append(str(val).lower())
            elif isinstance(val, int):
                results.append(val)
            elif isinstance(val, float):
                results.append(val)
            else:
                results.append(str(val))

        while len(results) < MAX_DYNAMIC_OUTPUTS:
            results.append("")

        return tuple(results)


NODE_CLASS_MAPPINGS = {
    "JSONDynamicLoader": JSONDynamicLoader,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "JSONDynamicLoader": "JSON Dynamic Loader",
}
