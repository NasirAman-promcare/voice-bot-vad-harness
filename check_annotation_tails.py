"""
check_annotation_tails.py

Question: your VADs all release speech 200 ms or so BEFORE the annotated end of
each segment. Is that the models letting go early, or does the ground truth
itself include trailing silence?

This measures it directly. For every annotated speech segment it walks backwards
from the annotated end and finds the last frame that is clearly above the clip's
own noise floor. The distance between that frame and the annotated end is the
segment's "tail padding".

    tail padding ~= 0 ms     -> annotation is tight; the VADs really do release early
    tail padding ~= 200 ms   -> the annotation includes silence; subtract it from
                                the measured hangover before judging the models

Run from the repo root:
    python check_annotation_tails.py
    python check_annotation_tails.py --clips 80      (default 60)
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

FRAME = 160          # 10 ms at 16 kHz, matching the scoring grid
ABOVE_FLOOR_DB = 12  # "clearly speech" = this much above the clip's noise floor
TAIL_WINDOW_MS = 250 # window reported in the second column


def read_wav(path: str):
    """soundfile if available (it is, in the corpus requirements), else scipy."""
    try:
        import soundfile as sf
        x, sr = sf.read(path, dtype="float32")
    except Exception:
        from scipy.io import wavfile
        sr, raw = wavfile.read(path)
        x = raw.astype(np.float32)
        if np.issubdtype(raw.dtype, np.integer):
            x /= float(np.iinfo(raw.dtype).max)
    if x.ndim > 1:
        x = x.mean(axis=1)
    return x, sr


def frame_db(x: np.ndarray) -> np.ndarray:
    n = len(x) // FRAME
    if n == 0:
        return np.array([])
    f = x[: n * FRAME].reshape(n, FRAME)
    return 20.0 * np.log10(np.sqrt((f ** 2).mean(axis=1)) + 1e-10)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--clips", type=int, default=60)
    ap.add_argument("--manifest", default="corpus/manifest.json")
    args = ap.parse_args()

    raw = json.load(open(args.manifest, encoding="utf-8"))
    clips = raw["clips"] if isinstance(raw, dict) and "clips" in raw else raw

    pads, tail_drops, per_category, missing = [], [], {}, 0
    used = 0
    for c in clips:
        if used >= args.clips:
            break
        segs = c.get("speech_segments") or []
        if not segs:
            continue
        path = c.get("clip_path") or f"corpus/audio/{c['clip_id']}"
        if not Path(path).is_file():
            missing += 1
            continue
        x, sr = read_wav(path)
        if sr != 16000:
            continue
        db = frame_db(x)
        if db.size == 0:
            continue
        floor = float(np.percentile(db, 10))       # this clip's own quiet level
        used += 1
        for s, e in segs:
            i0, i1 = s // FRAME, min(e // FRAME, len(db))
            if i1 - i0 < 3:
                continue
            body = db[i0:i1]
            loud = np.where(body > floor + ABOVE_FLOOR_DB)[0]
            if loud.size == 0:
                continue
            pad_ms = (len(body) - 1 - loud[-1]) * 10.0        # annotated end - last loud frame
            w = max(1, TAIL_WINDOW_MS // 10)
            drop_db = float(body[-w:].mean() - body[:-w].mean()) if len(body) > w else 0.0
            pads.append(pad_ms)
            tail_drops.append(drop_db)
            per_category.setdefault(c["category"], []).append(pad_ms)

    if not pads:
        print("No segments measured. Is corpus/audio present? "
              f"({missing} clips had no audio file on disk)")
        return

    pads_arr = np.array(pads)
    print(f"Measured {len(pads)} speech segments across {used} clips"
          + (f"  ({missing} clips skipped: audio file not found)" if missing else ""))
    print()
    print(f"  Trailing silence inside the annotated segments (tail padding):")
    print(f"     median {np.median(pads_arr):6.0f} ms   mean {pads_arr.mean():6.0f} ms"
          f"   90th pct {np.percentile(pads_arr, 90):6.0f} ms")
    print(f"  Energy of the last {TAIL_WINDOW_MS} ms vs the rest of the segment:"
          f" {np.mean(tail_drops):+.1f} dB")
    print()
    print("  By category (median tail padding):")
    for cat, v in sorted(per_category.items(), key=lambda kv: -float(np.median(kv[1]))):
        print(f"     {cat:30s} {np.median(v):5.0f} ms   (n={len(v)})")

    med = float(np.median(pads_arr))
    print()
    print("  How to read this:")
    if med < 50:
        print("     Annotation is tight. The negative hangover is real VAD behaviour;")
        print("     your endpointer must absorb all of it.")
    else:
        print(f"     The ground truth carries about {med:.0f} ms of trailing silence, so roughly")
        print(f"     that much of every VAD's negative hangover is annotation, not the model.")
        print(f"     Corrected hangover  ~=  measured + {med:.0f} ms. Example:")
        for name, ms in (("ten_vad", -204.1), ("firered_vad", -235.6), ("webrtc_vad_mode0", -16.8)):
            print(f"       {name:18s} {ms:7.1f} ms  ->  {ms + med:+7.1f} ms")


if __name__ == "__main__":
    main()
