import os


class AnyType(str):
    """Universal connector type that matches any ComfyUI type."""
    def __ne__(self, __value: object) -> bool:
        return False

any_type = AnyType("*")


class JDL_PathJoin:
    """Joins 1-6 path segments using os.path.join."""

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "segment_1": ("STRING", {"default": "", "multiline": False}),
            },
            "optional": {
                "segment_2": ("STRING", {"default": "", "multiline": False}),
                "segment_3": ("STRING", {"default": "", "multiline": False}),
                "segment_4": ("STRING", {"default": "", "multiline": False}),
                "segment_5": ("STRING", {"default": "", "multiline": False}),
                "segment_6": ("STRING", {"default": "", "multiline": False}),
            },
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("path",)
    FUNCTION = "join_path"
    CATEGORY = "JSON Dynamic/string"

    def join_path(self, segment_1, segment_2="", segment_3="", segment_4="",
                  segment_5="", segment_6=""):
        segments = [s for s in [segment_1, segment_2, segment_3, segment_4,
                                segment_5, segment_6] if s]
        if not segments:
            return ("",)
        return (os.path.normpath(os.path.join(*segments)),)


class JDL_StringFormat:
    """Python format-string templating with up to 8 inputs."""

    @classmethod
    def INPUT_TYPES(s):
        optional = {}
        for i in range(8):
            optional[f"v{i}"] = (any_type, {"default": ""})
        return {
            "required": {
                "template": ("STRING", {"default": "{0}/{1}", "multiline": False}),
            },
            "optional": optional,
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("string",)
    FUNCTION = "format_string"
    CATEGORY = "JSON Dynamic/string"

    def format_string(self, template, **kwargs):
        values = []
        for i in range(8):
            values.append(kwargs.get(f"v{i}", ""))
        try:
            result = template.format(*values)
        except (IndexError, KeyError, ValueError) as e:
            result = f"[format error: {e}]"
        return (result,)


class JDL_StringExtract:
    """Extracts substrings via split, between-delimiters, or filename decomposition."""

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "text": ("STRING", {"default": "", "multiline": False}),
                "mode": (["split_take", "between", "filename_parts"],),
            },
            "optional": {
                "delimiter": ("STRING", {"default": "/", "multiline": False}),
                "index": ("INT", {"default": -1, "min": -999, "max": 999}),
                "delimiter_2": ("STRING", {"default": "", "multiline": False}),
            },
        }

    RETURN_TYPES = ("STRING", "STRING", "STRING", "STRING")
    RETURN_NAMES = ("result", "dirname", "basename", "extension")
    FUNCTION = "extract"
    CATEGORY = "JSON Dynamic/string"

    def extract(self, text, mode, delimiter="/", index=-1, delimiter_2=""):
        dirname = os.path.dirname(text)
        full_basename = os.path.basename(text)
        name, ext = os.path.splitext(full_basename)
        extension = ext.lstrip(".")

        if mode == "split_take":
            parts = text.split(delimiter)
            try:
                result = parts[index]
            except IndexError:
                result = ""
        elif mode == "between":
            result = ""
            start = text.find(delimiter)
            if start != -1:
                start += len(delimiter)
                if delimiter_2:
                    end = text.find(delimiter_2, start)
                    if end != -1:
                        result = text[start:end]
                    else:
                        result = text[start:]
                else:
                    result = text[start:]
        else:  # filename_parts
            result = name

        return (result, dirname, name, extension)


class JDL_StringSwitch:
    """Boolean-based string selection with built-in defaults."""

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "condition": ("BOOLEAN", {"default": True}),
            },
            "optional": {
                "on_true": (any_type,),
                "on_false": (any_type,),
                "default_true": ("STRING", {"default": "", "multiline": False}),
                "default_false": ("STRING", {"default": "", "multiline": False}),
            },
        }

    RETURN_TYPES = (any_type,)
    RETURN_NAMES = ("result",)
    FUNCTION = "switch"
    CATEGORY = "JSON Dynamic/string"

    def switch(self, condition, on_true=None, on_false=None,
               default_true="", default_false=""):
        if condition:
            return (on_true if on_true is not None else default_true,)
        else:
            return (on_false if on_false is not None else default_false,)


class JDL_DependencyPassthrough:
    """Passes data through unchanged. Set 'order' in the JS widget to auto-wire
    execution order between passthrough nodes (1 → 2 → 3 → 4)."""

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "data": (any_type,),
            },
            "optional": {
                "wait_for": (any_type,),
            },
        }

    RETURN_TYPES = (any_type,)
    RETURN_NAMES = ("data",)
    FUNCTION = "passthrough"
    CATEGORY = "JSON Dynamic/flow"

    def passthrough(self, data, wait_for=None):
        return (data,)


NODE_CLASS_MAPPINGS = {
    "JDL_PathJoin": JDL_PathJoin,
    "JDL_StringFormat": JDL_StringFormat,
    "JDL_StringExtract": JDL_StringExtract,
    "JDL_StringSwitch": JDL_StringSwitch,
    "JDL_DependencyPassthrough": JDL_DependencyPassthrough,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "JDL_PathJoin": "Path Join",
    "JDL_StringFormat": "String Format",
    "JDL_StringExtract": "String Extract",
    "JDL_StringSwitch": "String Switch",
    "JDL_DependencyPassthrough": "Ordered Passthrough",
}
