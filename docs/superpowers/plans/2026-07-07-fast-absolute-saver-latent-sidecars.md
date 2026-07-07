# Fast Absolute Saver Latent Sidecars Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Save unmodified optional latents next to `FastAbsoluteSaver` media outputs and load them back by absolute path.

**Architecture:** Keep latent save/load behavior in `fast_saver.py` beside the existing saver node. Add small helpers for sidecar path derivation and direct `torch.save`/`torch.load` persistence so media naming and latent naming stay coupled.

**Tech Stack:** Python 3.10+, PyTorch, pytest, existing ComfyUI node mapping conventions.

---

### Task 1: Latent Sidecar Tests

**Files:**
- Create: `tests/test_fast_saver_latent.py`
- Modify: `fast_saver.py`

- [ ] **Step 1: Write the failing tests**

```python
import torch

from fast_saver import FastAbsoluteSaver


def test_png_save_writes_matching_latent_sidecar(tmp_path):
    saver = FastAbsoluteSaver()
    images = torch.zeros((1, 2, 2, 3), dtype=torch.float32)
    latent = {"samples": torch.arange(4, dtype=torch.float32).reshape(1, 1, 2, 2), "keep": {"value": 7}}

    saver.save_images_fast(
        images=images,
        output_path=str(tmp_path),
        filename_prefix="frame",
        save_format="png",
        use_timestamp=False,
        auto_increment=False,
        counter_digits=4,
        max_threads=1,
        filename_with_score=False,
        metadata_key="sharpness_score",
        save_workflow_metadata=False,
        save_metadata_png=False,
        webp_lossless=True,
        webp_quality=100,
        webp_method=4,
        video_fps=24,
        video_crf=18,
        video_pixel_format="yuv420p",
        video_bitrate=10,
        prores_profile="hq",
        gif_dither="sierra2_4a",
        latent=latent,
    )

    latent_path = tmp_path / "frame_0000.latent"
    loaded = torch.load(latent_path, map_location="cpu", weights_only=False)
    assert torch.equal(loaded["samples"], latent["samples"])
    assert loaded["keep"] == {"value": 7}


def test_video_save_writes_latent_sidecar_next_to_video(tmp_path):
    saver = FastAbsoluteSaver()
    images = torch.zeros((2, 2, 2, 3), dtype=torch.float32)
    latent = {"samples": torch.arange(8, dtype=torch.float32).reshape(2, 1, 2, 2)}
    video_path = tmp_path / "clip_0001.mp4"

    def fake_save_video(*args, **kwargs):
        video_path.write_bytes(b"video")
        return str(video_path)

    saver.save_video = fake_save_video
    saver.save_images_fast(
        images=images,
        output_path=str(tmp_path),
        filename_prefix="clip",
        save_format="mp4",
        use_timestamp=False,
        auto_increment=False,
        counter_digits=4,
        max_threads=1,
        filename_with_score=False,
        metadata_key="sharpness_score",
        save_workflow_metadata=False,
        save_metadata_png=False,
        webp_lossless=True,
        webp_quality=100,
        webp_method=4,
        video_fps=24,
        video_crf=18,
        video_pixel_format="yuv420p",
        video_bitrate=10,
        prores_profile="hq",
        gif_dither="sierra2_4a",
        latent=latent,
    )

    loaded = torch.load(tmp_path / "clip_0001.latent", map_location="cpu", weights_only=False)
    assert torch.equal(loaded["samples"], latent["samples"])


def test_load_latent_absolute_round_trips_saved_object(tmp_path):
    from fast_saver import JDL_LoadLatentAbsolute

    path = tmp_path / "sample.latent"
    latent = {"samples": torch.ones((1, 4, 8, 8)), "noise_mask": torch.zeros((1, 1, 8, 8))}
    torch.save(latent, path)

    loaded, = JDL_LoadLatentAbsolute().load_latent(str(path))

    assert torch.equal(loaded["samples"], latent["samples"])
    assert torch.equal(loaded["noise_mask"], latent["noise_mask"])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_fast_saver_latent.py -q`

Expected: tests fail because `latent` is not an accepted input and `JDL_LoadLatentAbsolute` does not exist.

- [ ] **Step 3: Implement minimal production code**

Add `latent` to `FastAbsoluteSaver.INPUT_TYPES()["optional"]`, accept it in `save_images_fast`, save `.latent` sidecars with `torch.save`, and register `JDL_LoadLatentAbsolute`.

- [ ] **Step 4: Run focused tests**

Run: `python -m pytest tests/test_fast_saver_latent.py -q`

Expected: both tests pass.

- [ ] **Step 5: Run broader verification**

Run: `python -m pytest tests/test_fast_saver_latent.py -q && python -m compileall fast_saver.py image_preview.py string_utils.py json_loader_dynamic.py`

Expected: pytest passes and compileall reports no syntax errors.
