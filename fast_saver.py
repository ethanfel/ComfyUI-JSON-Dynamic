import os
import platform
import torch
import numpy as np
from PIL import Image
from PIL.PngImagePlugin import PngInfo
import concurrent.futures
import re
import time
import glob
import json
import subprocess
import shutil
import stat
import tempfile
import urllib.request
import zipfile
import tarfile

_NODE_DIR = os.path.dirname(os.path.abspath(__file__))
_FFMPEG_DIR = os.path.join(_NODE_DIR, "ffmpeg_bin")


def _get_ffmpeg():
    """Find or download a ffmpeg binary. Search order:
    1. Bundled binary in this node's ffmpeg_bin/ folder
    2. imageio_ffmpeg (shipped by VideoHelperSuite)
    3. System PATH
    4. Auto-download a static build into ffmpeg_bin/
    """
    system = platform.system()
    exe_name = "ffmpeg.exe" if system == "Windows" else "ffmpeg"
    local_bin = os.path.join(_FFMPEG_DIR, exe_name)

    # 1. Already downloaded
    if os.path.isfile(local_bin):
        return local_bin

    # 2. imageio_ffmpeg
    try:
        import imageio_ffmpeg
        path = imageio_ffmpeg.get_ffmpeg_exe()
        if path and os.path.isfile(path):
            return path
    except Exception:
        pass

    # 3. System PATH
    system_bin = shutil.which("ffmpeg")
    if system_bin:
        return system_bin

    # 4. Auto-download static build
    print("xx- FastSaver: ffmpeg not found. Downloading static build...")
    os.makedirs(_FFMPEG_DIR, exist_ok=True)

    urls = {
        ("Linux", "x86_64"):  "https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz",
        ("Linux", "aarch64"): "https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-arm64-static.tar.xz",
        ("Windows", "AMD64"): "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip",
    }

    machine = platform.machine()
    key = (system, machine)
    url = urls.get(key)
    if not url:
        raise RuntimeError(
            f"No automatic ffmpeg download available for {system}/{machine}. "
            f"Please install ffmpeg manually or place a binary in {_FFMPEG_DIR}"
        )

    archive_path = os.path.join(_FFMPEG_DIR, "ffmpeg_archive")
    try:
        urllib.request.urlretrieve(url, archive_path)

        if url.endswith(".tar.xz"):
            with tarfile.open(archive_path, "r:xz") as tar:
                for member in tar.getmembers():
                    if member.name.endswith("/ffmpeg") and member.isfile():
                        member.name = exe_name
                        tar.extract(member, _FFMPEG_DIR)
                        break
        elif url.endswith(".zip"):
            with zipfile.ZipFile(archive_path, "r") as zf:
                for name in zf.namelist():
                    if name.endswith("bin/ffmpeg.exe"):
                        data = zf.read(name)
                        with open(local_bin, "wb") as f:
                            f.write(data)
                        break
    finally:
        if os.path.exists(archive_path):
            os.remove(archive_path)

    if not os.path.isfile(local_bin):
        raise RuntimeError(f"Failed to extract ffmpeg to {local_bin}")

    # Make executable on Linux/Mac
    if system != "Windows":
        os.chmod(local_bin, os.stat(local_bin).st_mode | stat.S_IEXEC)

    print(f"xx- FastSaver: ffmpeg downloaded to {local_bin}")
    return local_bin

class FastAbsoluteSaver:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "images": ("IMAGE", ),
                "output_path": ("STRING", {"default": "D:\\Datasets\\Sharp_Output"}),
                "filename_prefix": ("STRING", {"default": "frame"}),

                # --- FORMAT SWITCH ---
                "save_format": (["png", "webp", "mp4", "webm"], ),

                # --- NAMING CONTROL ---
                "use_timestamp": ("BOOLEAN", {"default": False, "label": "Add Timestamp (Unique)"}),
                "auto_increment": ("BOOLEAN", {"default": True, "label": "Auto-Increment Counter (Scan Folder)"}),
                "counter_digits": ("INT", {"default": 4, "min": 1, "max": 12, "step": 1, "label": "Number Padding (000X)"}),
                "filename_with_score": ("BOOLEAN", {"default": False, "label": "Append Score to Filename"}),

                # --- METADATA & WORKFLOW ---
                "metadata_key": ("STRING", {"default": "sharpness_score"}),
                "save_workflow_metadata": ("BOOLEAN", {"default": False, "label": "Save ComfyUI Workflow (Graph)"}),
                "save_metadata_png": ("BOOLEAN", {"default": False, "label": "Embed Workflow in PNG (sidecar or first file)"}),

                # --- PERFORMANCE ---
                "max_threads": ("INT", {"default": 0, "min": 0, "max": 128, "step": 1, "label": "Max Threads (0=Auto)"}),

                # --- WEBP SPECIFIC ---
                "webp_lossless": ("BOOLEAN", {"default": True, "label": "WebP Lossless"}),
                "webp_quality": ("INT", {"default": 100, "min": 0, "max": 100, "step": 1}),
                "webp_method": ("INT", {"default": 4, "min": 0, "max": 6, "step": 1}),

                # --- VIDEO SPECIFIC ---
                "video_fps": ("INT", {"default": 24, "min": 1, "max": 120, "step": 1, "label": "Video FPS"}),
                "video_crf": ("INT", {"default": 18, "min": 0, "max": 51, "step": 1, "label": "Video CRF (0=Lossless, 51=Worst)"}),
                "video_pixel_format": (["yuv420p", "yuv444p"], {"label": "Pixel Format"}),
            },
            "optional": {
                "scores_info": ("STRING", {"forceInput": True}),
            },
            # Hidden inputs used to capture the workflow graph
            "hidden": {"prompt": "PROMPT", "extra_pnginfo": "EXTRA_PNGINFO"},
        }

    RETURN_TYPES = ()
    FUNCTION = "save_images_fast"
    OUTPUT_NODE = True
    CATEGORY = "utils/io"

    def parse_info(self, info_str, batch_size):
        if not info_str:
            # No scores connected - return None for scores to indicate "not provided"
            return ([0]*batch_size, None)
        matches = re.findall(r"F:(\d+).*?Score:\s*(\d+(\.\d+)?)", info_str)
        frames = []
        scores = []
        for m in matches:
            try:
                frames.append(int(m[0]))
                scores.append(float(m[1]))
            except ValueError:
                pass
        if len(frames) < batch_size:
            missing = batch_size - len(frames)
            frames.extend([0] * missing)
            scores.extend([0.0] * missing)
        return frames[:batch_size], scores[:batch_size]

    def get_start_index(self, output_path, prefix):
        # Scans the directory ONCE to find the highest existing number.
        print(f"xx- FastSaver: Scanning folder for existing '{prefix}' files...")
        files = glob.glob(os.path.join(output_path, f"{prefix}*.*"))

        max_idx = 0
        # Check specifically for prefix_NUMBER pattern to avoid confusing timestamps
        pattern = re.compile(rf"{re.escape(prefix)}_(\d+)")

        for f in files:
            fname = os.path.basename(f)
            match = pattern.match(fname)
            if match:
                try:
                    val = int(match.group(1))
                    if val > max_idx:
                        max_idx = val
                except ValueError:
                    continue
        print(f"xx- FastSaver: Found highest index {max_idx}. Starting at {max_idx + 1}")
        return max_idx + 1

    def _save_sidecar_png(self, img, png_path, score, key_name, prompt_data, extra_data):
        """Save a metadata-carrying PNG sidecar next to a non-PNG export."""
        meta = PngInfo()
        if score is not None:
            meta.add_text(key_name, str(score))
        meta.add_text("software", "ComfyUI_FastAbsoluteSaver")
        workflow_json = json.dumps(extra_data.get("workflow", {})) if extra_data else "{}"
        prompt_json = json.dumps(prompt_data) if prompt_data else "{}"
        meta.add_text("prompt", prompt_json)
        meta.add_text("workflow", workflow_json)
        img.save(png_path, format="PNG", pnginfo=meta, compress_level=1)

    def save_single_image(self, img_array, full_path, score, key_name, fmt, lossless, quality, method,
                          save_workflow, prompt_data, extra_data, force_png_metadata=False):
        try:
            img = Image.fromarray(img_array)

            # --- METADATA PREPARATION ---
            meta_png = PngInfo()

            if fmt == "png":
                if score is not None:
                    meta_png.add_text(key_name, str(score))
                meta_png.add_text("software", "ComfyUI_Parallel_Node")

            # ComfyUI Workflow Metadata (if requested, or forced via sidecar toggle for first PNG)
            if (save_workflow or force_png_metadata) and fmt == "png":
                workflow_json = json.dumps(extra_data.get("workflow", {})) if extra_data else "{}"
                prompt_json = json.dumps(prompt_data) if prompt_data else "{}"
                meta_png.add_text("prompt", prompt_json)
                meta_png.add_text("workflow", workflow_json)

            # --- SAVING ---
            if fmt == "png":
                img.save(full_path, format="PNG", pnginfo=meta_png, compress_level=1)

            elif fmt == "webp":
                img.save(full_path, format="WEBP", lossless=lossless, quality=quality, method=method)

            return True
        except Exception as e:
            print(f"xx- Error saving {full_path}: {e}")
            return False

    def save_video(self, frames_np, output_path, filename_prefix, use_timestamp, fps, crf, pixel_format, video_format,
                   auto_increment=False, counter_digits=4,
                   scores_list=None, metadata_key="sharpness_score", save_workflow=False, prompt_data=None, extra_data=None):
        """Save image batch as a video file using ffmpeg. frames_np is a list/array of uint8 numpy arrays."""
        ffmpeg_path = _get_ffmpeg()

        ext = ".mp4" if video_format == "mp4" else ".webm"
        if use_timestamp:
            ts_str = f"_{int(time.time())}"
            out_file = os.path.join(output_path, f"{filename_prefix}{ts_str}{ext}")
        elif auto_increment:
            start_idx = self.get_start_index(output_path, filename_prefix)
            fmt_str = f"{{:0{counter_digits}d}}"
            out_file = os.path.join(output_path, f"{filename_prefix}_{fmt_str.format(start_idx)}{ext}")
        else:
            out_file = os.path.join(output_path, f"{filename_prefix}{ext}")

        batch_size = len(frames_np)
        h, w = frames_np[0].shape[0], frames_np[0].shape[1]

        # --- BUILD METADATA FILE (avoids arg-too-long for large workflows) ---
        meta_lines = [";FFMETADATA1"]
        meta_lines.append("software=ComfyUI_FastAbsoluteSaver")

        if scores_list:
            avg_score = sum(scores_list) / len(scores_list)
            meta_lines.append(f"{metadata_key}_avg={avg_score:.2f}")
            meta_lines.append(f"{metadata_key}_all={','.join(f'{s:.2f}' for s in scores_list)}")

        if save_workflow:
            if prompt_data:
                # Escape ffmetadata special chars: =, ;, #, \ and newlines
                prompt_str = json.dumps(prompt_data).replace("\\", "\\\\").replace("=", "\\=").replace(";", "\\;").replace("#", "\\#").replace("\n", "\\\n")
                meta_lines.append(f"prompt={prompt_str}")
            if extra_data:
                workflow = extra_data.get("workflow", {})
                if workflow:
                    workflow_str = json.dumps(workflow).replace("\\", "\\\\").replace("=", "\\=").replace(";", "\\;").replace("#", "\\#").replace("\n", "\\\n")
                    meta_lines.append(f"workflow={workflow_str}")

        self._meta_tmpfile = tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8")
        self._meta_tmpfile.write("\n".join(meta_lines))
        self._meta_tmpfile.close()
        meta_file = self._meta_tmpfile.name

        if video_format == "mp4":
            codec = "libx264"
            cmd = [
                ffmpeg_path, "-y",
                "-f", "rawvideo", "-pix_fmt", "rgb24",
                "-s", f"{w}x{h}", "-r", str(fps),
                "-i", "-",
                "-i", meta_file, "-map_metadata", "1",
                "-c:v", codec, "-crf", str(crf),
                "-pix_fmt", pixel_format,
                "-movflags", "+faststart",
                out_file
            ]
        else:  # webm
            codec = "libvpx-vp9"
            cmd = [
                ffmpeg_path, "-y",
                "-f", "rawvideo", "-pix_fmt", "rgb24",
                "-s", f"{w}x{h}", "-r", str(fps),
                "-i", "-",
                "-i", meta_file, "-map_metadata", "1",
                "-c:v", codec, "-crf", str(crf), "-b:v", "0",
                "-pix_fmt", pixel_format,
                out_file
            ]

        print(f"xx- FastSaver: Encoding {batch_size} frames to {out_file} ({codec}, crf={crf}, {fps}fps)...")

        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            for frame in frames_np:
                proc.stdin.write(frame.tobytes())
            proc.stdin.close()
        except BrokenPipeError:
            pass
        stderr = proc.stderr.read()
        proc.wait()

        # Clean up metadata temp file
        try:
            os.remove(meta_file)
        except OSError:
            pass

        if proc.returncode != 0:
            raise RuntimeError(f"ffmpeg failed: {stderr.decode()}")

        print(f"xx- FastSaver: Video saved to {out_file}")
        return out_file

    def save_images_fast(self, images, output_path, filename_prefix, save_format, use_timestamp, auto_increment, counter_digits,
                         max_threads, filename_with_score, metadata_key, save_workflow_metadata, save_metadata_png,
                         webp_lossless, webp_quality, webp_method,
                         video_fps, video_crf, video_pixel_format,
                         scores_info=None, prompt=None, extra_pnginfo=None):

        output_path = output_path.strip('"')
        if not os.path.exists(output_path):
            try:
                os.makedirs(output_path, exist_ok=True)
            except OSError:
                raise ValueError(f"Could not create directory: {output_path}")

        if images is None or len(images) == 0:
            raise ValueError("No images provided to FastAbsoluteSaver.")

        # Batch GPU->CPU transfer once (avoids N individual sync transfers)
        images_np = (255.0 * images.cpu().numpy()).clip(0, 255).astype(np.uint8)
        batch_size = len(images_np)

        # --- VIDEO PATH (check early, before image-specific logic) ---
        if save_format in ("mp4", "webm"):
            _, scores_list = self.parse_info(scores_info, batch_size)
            out_file = self.save_video(images_np, output_path, filename_prefix, use_timestamp,
                            video_fps, video_crf, video_pixel_format, save_format,
                            auto_increment=auto_increment, counter_digits=counter_digits,
                            scores_list=scores_list, metadata_key=metadata_key,
                            save_workflow=save_workflow_metadata, prompt_data=prompt,
                            extra_data=extra_pnginfo)
            # Save metadata sidecar PNG next to the video file
            if save_metadata_png:
                png_path = os.path.splitext(out_file)[0] + ".png"
                img = Image.fromarray(images_np[0])
                avg_score = (sum(scores_list) / len(scores_list)) if scores_list else None
                self._save_sidecar_png(img, png_path, avg_score, metadata_key, prompt, extra_pnginfo)
                print(f"xx- FastSaver: Metadata PNG sidecar saved to {png_path}")
            return {"ui": {"images": []}}

        if max_threads == 0:
            max_threads = os.cpu_count() or 4

        frame_indices, scores_list = self.parse_info(scores_info, batch_size)

        # --- INDEX LOGIC ---
        start_counter = 0
        using_real_frames = any(idx > 0 for idx in frame_indices)

        if auto_increment and not use_timestamp and not using_real_frames:
            start_counter = self.get_start_index(output_path, filename_prefix)

        ts_str = f"_{int(time.time())}" if use_timestamp else ""

        print(f"xx- FastSaver: Saving {batch_size} images to {output_path}...")

        first_image_path = None

        with concurrent.futures.ThreadPoolExecutor(max_workers=max_threads) as executor:
            futures = []

            for i, img_array in enumerate(images_np):
                real_frame_num = frame_indices[i]
                current_score = scores_list[i] if scores_list else None

                if real_frame_num > 0:
                    number_part = real_frame_num
                else:
                    number_part = start_counter + i

                fmt_str = f"{{:0{counter_digits}d}}"
                number_str = fmt_str.format(number_part)

                base_name = f"{filename_prefix}{ts_str}_{number_str}"

                if filename_with_score and current_score is not None:
                    base_name += f"_{int(current_score)}"

                ext = ".webp" if save_format == "webp" else ".png"
                full_path = os.path.join(output_path, f"{base_name}{ext}")

                if i == 0:
                    first_image_path = full_path

                # For PNG sequences: embed workflow metadata in the first file only
                force_meta = (save_metadata_png and save_format == "png" and i == 0)

                futures.append(executor.submit(
                    self.save_single_image,
                    img_array, full_path, current_score, metadata_key,
                    save_format, webp_lossless, webp_quality, webp_method,
                    save_workflow_metadata, prompt, extra_pnginfo,
                    force_png_metadata=force_meta
                ))

            concurrent.futures.wait(futures)

        # Save a single metadata sidecar PNG using the first image (skip for PNG sequences - handled above)
        if save_metadata_png and save_format != "png" and first_image_path is not None:
            png_path = os.path.splitext(first_image_path)[0] + ".png"
            img = Image.fromarray(images_np[0])
            first_score = scores_list[0] if scores_list else None
            self._save_sidecar_png(img, png_path, first_score, metadata_key, prompt, extra_pnginfo)
            print(f"xx- FastSaver: Metadata PNG sidecar saved to {png_path}")

        return {"ui": {"images": []}}


NODE_CLASS_MAPPINGS = {
    "FastAbsoluteSaver": FastAbsoluteSaver,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "FastAbsoluteSaver": "Fast Absolute Saver (Metadata)",
}
