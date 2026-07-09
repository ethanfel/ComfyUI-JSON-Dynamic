import pytest
import torch

from fast_saver import FastAbsoluteSaver


def _save_args(tmp_path, *, save_format="png", latent=None, save_latent=True):
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
        "save_latent": save_latent,
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


def test_png_save_latent_false_skips_sidecar_but_keeps_passthrough(tmp_path):
    saver = FastAbsoluteSaver()
    latent = {"samples": torch.ones((1, 1, 2, 2))}

    result = saver.save_images_fast(**_save_args(tmp_path, latent=latent, save_latent=False))

    assert not (tmp_path / "frame_0000.latent").exists()
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


def test_hw_cpu_fallback_maps_to_valid_same_container_formats():
    import fast_saver as fs

    # Every fallback target exists and keeps the same container extension.
    for hw, cpu in fs._HW_CPU_FALLBACK.items():
        assert hw in fs.VIDEO_FORMATS, hw
        assert cpu in fs.VIDEO_FORMATS, cpu
        assert fs.VIDEO_FORMATS[hw]["ext"] == fs.VIDEO_FORMATS[cpu]["ext"], hw

    # Every hardware (nvenc) format must define a CPU fallback.
    for name in fs.VIDEO_FORMATS:
        if "nvenc" in name:
            assert name in fs._HW_CPU_FALLBACK, name


def test_get_ffmpeg_prefers_binary_with_required_encoder(monkeypatch):
    import fast_saver as fs

    monkeypatch.setattr(fs, "_existing_ffmpeg_paths", lambda: ["/static/ffmpeg", "/nvenc/ffmpeg"])
    monkeypatch.setattr(fs, "_ffmpeg_has_encoder",
                        lambda p, e: p == "/nvenc/ffmpeg" and e == "av1_nvenc")

    # Required encoder lives in the lower-priority binary -> that one wins.
    assert fs._get_ffmpeg("av1_nvenc") == "/nvenc/ffmpeg"
    # No requirement -> highest-priority existing binary.
    assert fs._get_ffmpeg() == "/static/ffmpeg"
    # Required encoder available nowhere -> default binary (caller handles fallback).
    assert fs._get_ffmpeg("h264_nvenc") == "/static/ffmpeg"
