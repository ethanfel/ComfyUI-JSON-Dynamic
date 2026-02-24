from .json_loader_dynamic import (
    NODE_CLASS_MAPPINGS as _json_class_mappings,
    NODE_DISPLAY_NAME_MAPPINGS as _json_display_mappings,
)
from .string_utils import (
    NODE_CLASS_MAPPINGS as _string_class_mappings,
    NODE_DISPLAY_NAME_MAPPINGS as _string_display_mappings,
)
from .image_preview import (
    NODE_CLASS_MAPPINGS as _image_class_mappings,
    NODE_DISPLAY_NAME_MAPPINGS as _image_display_mappings,
)

NODE_CLASS_MAPPINGS = {**_json_class_mappings, **_string_class_mappings, **_image_class_mappings}
NODE_DISPLAY_NAME_MAPPINGS = {**_json_display_mappings, **_string_display_mappings, **_image_display_mappings}

WEB_DIRECTORY = "./web"

__all__ = ['NODE_CLASS_MAPPINGS', 'NODE_DISPLAY_NAME_MAPPINGS', 'WEB_DIRECTORY']
