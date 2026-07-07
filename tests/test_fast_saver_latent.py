import pytest
import torch

from fast_saver import FastAbsoluteSaver


def _save_args(tmp_path, *, save_format="png", latent=None):
    return {
        "images": torch.zeros((1, 2, 2, 3), dtype=torch.float32),
        "output_path": str(tmp_path),
        "filename_prefix": "frame",
        "save_format": save_format,
        "use_timestamp": False,
        "auto_increment": False,
        "counter_digits": 4,
        "max_threads": 1,
        "filename_with_score": False,
        "metadata_key": "sharpness_score",
        "save_workflow_metadata": False,
        "save_metadata_png": False,
        "webp_lossless": True,
        "webp_quality": 100,
        "webp_method": 4,
        "video_fps": 24,
        "video_crf": 18,
        "video_pixel_format": "yuv420p",
        "video_bitrate": 10,
        "prores_profile": "hq",
        "gif_dither": "sierra2_4a",
        "latent": latent,
    }


def test_png_save_writes_matching_latent_sidecar(tmp_path):
    saver = FastAbsoluteSaver()
    latent = {
        "samples": torch.arange(4, dtype=torch.float32).reshape(1, 1, 2, 2),
        "keep": {"value": 7},
    }

    saver.save_images_fast(**_save_args(tmp_path, latent=latent))

    loaded = torch.load(tmp_path / "frame_0000.latent", map_location="cpu", weights_only=False)
    assert torch.equal(loaded["samples"], latent["samples"])
    assert loaded["keep"] == {"value": 7}


def test_png_save_returns_latent_passthrough(tmp_path):
    saver = FastAbsoluteSaver()
    latent = {"samples": torch.ones((1, 1, 2, 2))}

    result = saver.save_images_fast(**_save_args(tmp_path, latent=latent))

    assert result["result"] == (latent,)
    assert result["result"][0] is latent


def test_video_save_writes_latent_sidecar_next_to_video(tmp_path):
    saver = FastAbsoluteSaver()
    latent = {"samples": torch.arange(8, dtype=torch.float32).reshape(2, 1, 2, 2)}
    video_path = tmp_path / "clip_0001.mp4"

    def fake_save_video(*args, **kwargs):
        video_path.write_bytes(b"video")
        return str(video_path)

    saver.save_video = fake_save_video
    args = _save_args(tmp_path, save_format="mp4", latent=latent)
    args["images"] = torch.zeros((2, 2, 2, 3), dtype=torch.float32)
    args["filename_prefix"] = "clip"

    saver.save_images_fast(**args)

    loaded = torch.load(tmp_path / "clip_0001.latent", map_location="cpu", weights_only=False)
    assert torch.equal(loaded["samples"], latent["samples"])


def test_load_latent_absolute_round_trips_saved_object(tmp_path):
    from fast_saver import JDL_LoadLatentAbsolute

    path = tmp_path / "sample.latent"
    latent = {
        "samples": torch.ones((1, 4, 8, 8)),
        "noise_mask": torch.zeros((1, 1, 8, 8)),
    }
    torch.save(latent, path)

    loaded, = JDL_LoadLatentAbsolute().load_latent(str(path))

    assert torch.equal(loaded["samples"], latent["samples"])
    assert torch.equal(loaded["noise_mask"], latent["noise_mask"])


def test_load_latent_absolute_rejects_relative_paths():
    from fast_saver import JDL_LoadLatentAbsolute

    with pytest.raises(ValueError, match="absolute"):
        JDL_LoadLatentAbsolute().load_latent("sample.latent")
