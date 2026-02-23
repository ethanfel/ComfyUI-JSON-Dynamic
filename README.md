<p align="center">
  <svg xmlns="http://www.w3.org/2000/svg" width="460" height="90" viewBox="0 0 460 90">
    <defs>
      <linearGradient id="bg" x1="0%" y1="0%" x2="100%" y2="100%">
        <stop offset="0%" style="stop-color:#1a1a2e" />
        <stop offset="100%" style="stop-color:#16213e" />
      </linearGradient>
      <linearGradient id="accent" x1="0%" y1="0%" x2="100%" y2="0%">
        <stop offset="0%" style="stop-color:#2b9348" />
        <stop offset="100%" style="stop-color:#0f3460" />
      </linearGradient>
    </defs>
    <rect width="460" height="90" rx="14" fill="url(#bg)" />
    <rect x="20" y="65" width="420" height="3" rx="1.5" fill="url(#accent)" opacity="0.6" />
    <text x="230" y="32" text-anchor="middle" fill="#2b9348" font-family="monospace" font-size="12" font-weight="bold">{ Dynamic }</text>
    <text x="230" y="54" text-anchor="middle" fill="#eee" font-family="sans-serif" font-size="20" font-weight="bold">ComfyUI JSON Dynamic Loader</text>
    <text x="230" y="82" text-anchor="middle" fill="#888" font-family="sans-serif" font-size="10">Auto-discover JSON keys as typed output slots</text>
  </svg>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/License-Apache_2.0-blue.svg" alt="License" />
  <img src="https://img.shields.io/badge/ComfyUI-Custom%20Node-purple" alt="ComfyUI" />
</p>

A single ComfyUI node that reads any JSON file and **automatically creates output slots** for every key it finds. No hardcoded outputs &mdash; when your JSON structure changes, just click Refresh.

## Features

- **Auto-discovery** &mdash; reads JSON keys and exposes them as named outputs
- **Type detection** &mdash; `INT`, `FLOAT`, `STRING` types with colored connectors
- **Batch support** &mdash; `sequence_number` input for `batch_data` arrays
- **Connection-safe refresh** &mdash; adding new keys preserves existing links
- **Workflow persistence** &mdash; keys, types, and connections survive save/reload

## Installation

### ComfyUI Manager
Search for **JSON Dynamic Loader** in the ComfyUI Manager registry.

### Manual
```bash
cd ComfyUI/custom_nodes/
git clone https://github.com/ethanfel/ComfyUI-JSON-Dynamic.git
# Restart ComfyUI
```

## Usage

1. Add **JSON Dynamic Loader** node to your workflow
2. Enter a `json_path` and `sequence_number`
3. Click **Refresh Outputs**
4. Outputs appear named after your JSON keys with correct types
5. Connect to downstream nodes

<p align="center">
<svg xmlns="http://www.w3.org/2000/svg" width="500" height="240" viewBox="0 0 500 240">
  <defs>
    <linearGradient id="dynBg" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" style="stop-color:#353545" />
      <stop offset="100%" style="stop-color:#252535" />
    </linearGradient>
  </defs>
  <rect x="20" y="10" width="240" height="220" rx="10" fill="url(#dynBg)" stroke="#2b9348" stroke-width="2" />
  <rect x="20" y="10" width="240" height="28" rx="10" fill="#2b9348" />
  <rect x="20" y="28" width="240" height="10" fill="#2b9348" />
  <text x="140" y="31" text-anchor="middle" fill="#fff" font-family="sans-serif" font-size="13" font-weight="bold">JSON Dynamic Loader</text>
  <text x="35" y="60" fill="#ccc" font-family="monospace" font-size="10">json_path: /data/prompt.json</text>
  <text x="35" y="78" fill="#ccc" font-family="monospace" font-size="10">sequence_number: 1</text>
  <rect x="45" y="88" width="190" height="24" rx="5" fill="#2b9348" opacity="0.3" stroke="#2b9348" stroke-width="1"/>
  <text x="140" y="104" text-anchor="middle" fill="#2b9348" font-family="sans-serif" font-size="11" font-weight="bold">Refresh Outputs</text>
  <circle cx="260" cy="130" r="5" fill="#6bcb77"/>
  <text x="245" y="134" text-anchor="end" fill="#ccc" font-family="monospace" font-size="10">general_prompt</text>
  <circle cx="260" cy="150" r="5" fill="#6bcb77"/>
  <text x="245" y="154" text-anchor="end" fill="#ccc" font-family="monospace" font-size="10">negative</text>
  <circle cx="260" cy="170" r="5" fill="#4d96ff"/>
  <text x="245" y="174" text-anchor="end" fill="#ccc" font-family="monospace" font-size="10">seed</text>
  <circle cx="260" cy="190" r="5" fill="#ff6b6b"/>
  <text x="245" y="194" text-anchor="end" fill="#ccc" font-family="monospace" font-size="10">flf</text>
  <circle cx="260" cy="210" r="5" fill="#6bcb77"/>
  <text x="245" y="214" text-anchor="end" fill="#ccc" font-family="monospace" font-size="10">camera</text>
  <line x1="265" y1="130" x2="340" y2="130" stroke="#6bcb77" stroke-width="1.5"/>
  <line x1="265" y1="170" x2="340" y2="165" stroke="#4d96ff" stroke-width="1.5"/>
  <rect x="340" y="115" width="140" height="65" rx="8" fill="url(#dynBg)" stroke="#555" stroke-width="1.5" />
  <text x="410" y="137" text-anchor="middle" fill="#aaa" font-family="sans-serif" font-size="11">KSampler</text>
  <circle cx="340" cy="130" r="4" fill="#6bcb77"/>
  <text x="350" y="150" fill="#777" font-family="monospace" font-size="9">positive</text>
  <circle cx="340" cy="165" r="4" fill="#4d96ff"/>
  <text x="350" y="170" fill="#777" font-family="monospace" font-size="9">seed</text>
</svg>
</p>

## Type Handling

| JSON type | Output type | Connector |
|:---|:---|:---|
| `42` (integer) | `INT` | Blue |
| `3.14` (float) | `FLOAT` | Teal |
| `"hello"` (string) | `STRING` | Pink |
| `true` / `false` | `STRING` (`"true"` / `"false"`) | Pink |

## JSON Format

### Flat JSON (single segment)

For simple use cases, the node reads keys directly from the root object. The `sequence_number` input is ignored.

```json
{
  "general_prompt": "A cinematic scene...",
  "seed": 42,
  "flf": 0.5,
  "camera": "pan_left"
}
```

### Batch JSON (multiple segments)

For multi-shot workflows, wrap entries in a `batch_data` array. Each entry is a **segment** representing one shot/scene with its own settings. The `sequence_number` input selects which segment to read.

```json
{
  "batch_data": [
    {
      "sequence_number": 1,
      "general_prompt": "Wide establishing shot of a city",
      "seed": 42,
      "camera": "static",
      "flf": 0.0
    },
    {
      "sequence_number": 2,
      "general_prompt": "Close-up of the protagonist",
      "seed": 108,
      "camera": "pan_left",
      "flf": 0.5,
      "my_custom_key": "only on this segment"
    },
    {
      "sequence_number": 3,
      "general_prompt": "Aerial drone shot over rooftops",
      "seed": 77,
      "camera": "zoom_in",
      "flf": 0.8
    }
  ]
}
```

### Segment lookup

The node resolves which segment to read using this logic:

1. **Match by `sequence_number` field** &mdash; scans `batch_data` for an entry whose `sequence_number` matches the input
2. **Fallback to array index** &mdash; if no match is found, uses `sequence_number - 1` as the array index (clamped to bounds)
3. **No `batch_data`** &mdash; reads keys from the root object directly

This means segments don't need to be in order and can have gaps (e.g. 1, 5, 10). Each segment can have different keys &mdash; click **Refresh Outputs** after changing `sequence_number` if the keys differ between segments.

<p align="center">
<svg xmlns="http://www.w3.org/2000/svg" width="520" height="200" viewBox="0 0 520 200">
  <defs>
    <linearGradient id="segBg" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" style="stop-color:#2d2d3d" />
      <stop offset="100%" style="stop-color:#1e1e2e" />
    </linearGradient>
  </defs>

  <!-- JSON file -->
  <rect x="10" y="10" width="160" height="180" rx="8" fill="url(#segBg)" stroke="#0f3460" stroke-width="1.5" />
  <text x="90" y="30" text-anchor="middle" fill="#0f3460" font-family="monospace" font-size="11" font-weight="bold">batch_data[]</text>

  <!-- Segment boxes -->
  <rect x="22" y="42" width="136" height="38" rx="5" fill="#1a1a2e" stroke="#555" stroke-width="1" />
  <text x="90" y="56" text-anchor="middle" fill="#6bcb77" font-family="monospace" font-size="9">seq 1: city, seed=42</text>
  <text x="90" y="70" text-anchor="middle" fill="#888" font-family="monospace" font-size="8">camera=static, flf=0.0</text>

  <rect x="22" y="86" width="136" height="38" rx="5" fill="#1a1a2e" stroke="#2b9348" stroke-width="2" />
  <text x="90" y="100" text-anchor="middle" fill="#2b9348" font-family="monospace" font-size="9">seq 2: close-up, seed=108</text>
  <text x="90" y="114" text-anchor="middle" fill="#888" font-family="monospace" font-size="8">camera=pan_left, flf=0.5</text>

  <rect x="22" y="130" width="136" height="38" rx="5" fill="#1a1a2e" stroke="#555" stroke-width="1" />
  <text x="90" y="144" text-anchor="middle" fill="#6bcb77" font-family="monospace" font-size="9">seq 3: aerial, seed=77</text>
  <text x="90" y="158" text-anchor="middle" fill="#888" font-family="monospace" font-size="8">camera=zoom_in, flf=0.8</text>

  <!-- Arrow -->
  <line x1="170" y1="105" x2="210" y2="105" stroke="#2b9348" stroke-width="2" marker-end="url(#segArrow)"/>
  <defs><marker id="segArrow" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto"><polygon points="0 0, 8 3, 0 6" fill="#2b9348"/></marker></defs>
  <text x="190" y="95" text-anchor="middle" fill="#2b9348" font-family="monospace" font-size="9">seq=2</text>

  <!-- Node -->
  <rect x="210" y="60" width="180" height="90" rx="8" fill="url(#segBg)" stroke="#2b9348" stroke-width="2" />
  <rect x="210" y="60" width="180" height="22" rx="8" fill="#2b9348" />
  <rect x="210" y="74" width="180" height="8" fill="#2b9348" />
  <text x="300" y="77" text-anchor="middle" fill="#fff" font-family="sans-serif" font-size="10" font-weight="bold">JSON Dynamic Loader</text>

  <circle cx="390" cy="100" r="4" fill="#6bcb77"/>
  <text x="380" y="103" text-anchor="end" fill="#ccc" font-family="monospace" font-size="9">general_prompt</text>
  <circle cx="390" cy="116" r="4" fill="#4d96ff"/>
  <text x="380" y="119" text-anchor="end" fill="#ccc" font-family="monospace" font-size="9">seed</text>
  <circle cx="390" cy="132" r="4" fill="#6bcb77"/>
  <text x="380" y="135" text-anchor="end" fill="#ccc" font-family="monospace" font-size="9">camera</text>

  <!-- Output values -->
  <line x1="394" y1="100" x2="420" y2="100" stroke="#6bcb77" stroke-width="1"/>
  <text x="425" y="103" fill="#888" font-family="monospace" font-size="9">"Close-up of the protagonist"</text>
  <line x1="394" y1="116" x2="420" y2="116" stroke="#4d96ff" stroke-width="1"/>
  <text x="425" y="119" fill="#888" font-family="monospace" font-size="9">108</text>
  <line x1="394" y1="132" x2="420" y2="132" stroke="#6bcb77" stroke-width="1"/>
  <text x="425" y="135" fill="#888" font-family="monospace" font-size="9">"pan_left"</text>
</svg>
</p>

## License

[Apache 2.0](LICENSE)
