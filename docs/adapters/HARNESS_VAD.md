# Harness VAD adapter

The lab's first voice activity detector (FR-0.7-04). It wraps an existing harness VAD, never a copy. The owner named WebRTC VAD in mode 2 with 20 ms frames, registry name `webrtc_vad_mode2` (docs/approvals/WP-0.7.md, question 1). The code is in `aqis_lab/adapters/harness_vad.py` (class `HarnessVADAdapter`, event-log component `vad`). The runner task is `harness-vad`: every clip, mode `batch`.

## Why this VAD
From the harness's own VADs (PLAN.md, finding 8):
- **WebRTC VAD** (`vad_adapters/webrtc_vad_adapter.py`, package `webrtcvad-wheels` 2.0.14, MIT, fixed-point C) has x86_64 and aarch64 wheels for Python 3.13, so it runs on all three machines.
- **TEN VAD** has a library for Linux x86_64 only, so it cannot run on the Arm Oracle VM.
- **FireRedVAD** needs torch and downloaded weights, which are not in the lab's CPU lock.

## How the harness is used
- `open()` imports `vad_adapters.adapter_registry` from this repository. The repository root is put on the import path, so it works from any folder. A `vad_adapters` package imported from anywhere else is refused (`harness-vad-not-found`).
- It takes the adapter with `get_adapter("webrtc_vad_mode2", frame_size_samples=320)`. That call also runs the harness's own conformance check. An adapter with another ID or frame size is refused (`harness-vad-mismatch`).
- No file under `vad_adapters/` is copied or changed. A test checks that the imported module is under `vad_adapters/` and that `git diff` of the harness paths is empty.

## Frames and segments
- Each clip (16 kHz mono 16-bit) is cut into whole 20 ms frames by the harness's `chunk_audio_stream`. The harness drops a shorter tail. The adapter keeps that rule and records the dropped samples in `dropped_tail_samples`.
- The harness's decision for each frame is used as it is: no smoothing and no hangover.
- A run of speech frames becomes one segment:
  - a `speech_start` event at the start of its first speech frame;
  - a `speech_end` event at the end of its last speech frame.
  - A run that reaches the last whole frame ends at that frame's end.
- Each event's `audio_time_s` is that boundary in seconds. A clip with no speech frame gives no event and no segment.
- In real-speed use (the streaming steps `start_clip`, `feed` and `finish_clip`), a part-frame is dropped in the same way, so streaming gives the same segments as the whole clip.

## Result row fields
After `clip_id`, `run_card_id`, `task` and `task_version`:

| Field | Meaning |
| --- | --- |
| `segments` | `[start_s, end_s]` pairs, in order |
| `speech_s` | Total length of the segments, in seconds |
| `frames` | Whole 20 ms frames decided |
| `speech_frames` | Frames the harness called speech |
| `dropped_tail_samples` | Samples after the last whole frame, dropped by the harness's rule |

Rows repeat byte for byte on every machine: WebRTC VAD is fixed-point code.

## Run card
The `model` block: family `harness-vad`, name `webrtc_vad_mode2`, version `webrtcvad-wheels 2.0.14`, checksum null. The harness code itself is identified by the run card's git commit. Settings:

| Setting | Value |
| --- | --- |
| `mode` | 2 |
| `frame_size_samples` | 320 |
| `registry_name` | `webrtc_vad_mode2` |
| `harness_module` | `vad_adapters.webrtc_vad_adapter` |
| `segmentation` | `raw frame transitions (no smoothing)` |
| `tail` | `dropped (harness chunk_audio_stream)` |

The run card's normaliser is null: a VAD produces no text.

## Not in scope
Scoring VAD decisions against a reference comes in a later phase.
