# Fast Absolute Saver Latent Sidecars Design

## Goal

Add an optional `latent` input to `FastAbsoluteSaver` that saves the unmodified latent object next to the generated media, and add an absolute-path latent loader that can read those sidecars back into ComfyUI.

## Behavior

- `FastAbsoluteSaver` accepts an optional `latent` input of type `LATENT`.
- When `latent` is connected, the saver writes a sidecar file with the exact media base name and `.latent` extension.
- Video outputs produce one sidecar: `clip.mp4` writes `clip.latent`.
- Image sequence outputs write a sidecar for each saved image. Each sidecar stores the full connected latent object unchanged rather than slicing per frame.
- The latent is persisted with `torch.save` as provided. The saver must not prune keys, convert tensors, detach tensors, clone tensors, or strip metadata.
- A new `Load Latent Absolute` node accepts an absolute path and returns a `LATENT`.
- Missing or invalid latent files raise clear errors rather than silently blocking downstream nodes.

## Files

- `fast_saver.py` owns the saver and the new absolute latent load node.
- `tests/test_fast_saver_latent.py` covers sidecar naming, exact object persistence, and absolute loading.

## Performance Notes

The implementation should keep the current fast batch image conversion path. Any performance improvement should be low risk and localized, such as reusing output path decisions for media and sidecars rather than recomputing or guessing names after save.
