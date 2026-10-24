"""The Sprint 1 audio conditions: seeded noise at a target SNR, the phone channel, the WebRTC (Opus) channel.

CAPABILITIES:
  CAP-S1-002: render_condition() turns one 16 kHz int16 utterance into one of the conditions of s1.yaml: clean and
    native leave it unchanged; noise_* mixes a seeded MUSAN noise segment at the SNR through aqis_lab.packs.mix.mix_clip,
    drawing the same clip and offset for every noise condition of an utterance; phone applies a 300 to 3400 Hz FIR
    band-pass, decimation to 8 kHz, G.711 mu-law (ITU 14-bit reference algorithm) and the return to 16 kHz; webrtc
    encodes with libopus (VOIP, 16 kbps, 20 ms frames, in-band FEC) with seeded packet loss, rebuilding a lost packet from
    the next packet's FEC when it arrived and by PLC otherwise, trimmed by the encoder lookahead so lengths match; the
    *_noise_10 conditions add the noise first [tests: test_s1_noise_achieved_snr_equals_target_within_005_db,
    test_s1_noise_draw_is_seeded_and_only_uses_clips_long_enough, test_s1_noise_draw_is_shared_by_all_noise_conditions_of_an_utterance,
    test_s1_noise_conditions_apply_noise_before_the_channel, test_s1_phone_preserves_length,
    test_s1_phone_passband_tones_lose_less_than_half_a_db, test_s1_phone_5khz_tone_loses_at_least_50_db,
    test_s1_ulaw_decode_known_codes, test_s1_ulaw_encode_inverts_decode_except_negative_zero,
    test_s1_ulaw_sqnr_is_at_least_35_db_on_a_full_scale_signal, test_s1_webrtc_same_seed_same_output_and_other_seed_other_losses,
    test_s1_webrtc_lost_packets_follow_the_seeded_pattern_and_fec_plus_plc_add_up, test_s1_webrtc_preserves_length,
    test_s1_webrtc_bitrate_from_packet_bytes_is_within_10_percent_of_16_kbps]
  CAP-S1-003: scale_to_dbfs() sets a clip's RMS level in dBFS (full scale 32768) for the non-speech slice [tests:
    test_s1_scale_to_dbfs_sets_the_rms_level]
INPUTS AND OUTPUTS: int16 sample arrays, the conditions block of s1.yaml, a seed and an utterance ID in; int16 samples
  and an info dict (noise clip and offset, SNR, loss seed and counts) out; ConditionError.
CONTRACTS: Appendix B of docs/specs/sprints/WP-1.1-S1-asr-benchmark.md (verified there on 17 Oct 2026); aqis_lab.packs.mix
  for the exact-arithmetic mix.
INVARIANTS:
  - The noise draw depends on the seed, the utterance ID and the noise pool only, never on the condition, so the three
    *_10 conditions of an utterance share it.
  - The same samples, seed and settings give the same output.
  - libopus is loaded on first use; a machine without it gets a ConditionError that says how to install it.
NOT IN SCOPE:
  - Resampling source audio to 16 kHz (aqis_lab/bench/sources.py) and choosing which utterances are rendered.
CHANGE LOG:
  2026-10-17 WP-1.1 created from the brief's Appendix B.
"""
import ctypes
import ctypes.util
import functools
import hashlib
from dataclasses import dataclass

import numpy as np

from aqis_lab.packs.mix import mix_clip, RenderError

SR = 16000
CHANNEL_CONDITION = {"g711_mulaw": "phone", "opus": "webrtc"}   # the condition that holds each channel's settings


class ConditionError(RuntimeError):
    """A condition cannot be rendered."""


# ---- noise ---------------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class NoiseDraw:
    clip_id: str
    offset: int


def _digest(text):
    return int(hashlib.sha256(text.encode("utf-8")).hexdigest(), 16)


def noise_draw(seed, utt_id, lengths, length):
    """The noise clip and offset for an utterance: lengths maps clip ID to samples; clips shorter than `length` are out."""
    eligible = sorted(clip for clip, n in lengths.items() if n >= length)
    if not eligible:
        raise ConditionError(f"no noise clip has the {length} samples utterance {utt_id} needs "
                             f"(longest: {max(lengths.values(), default=0)})")
    clip = min(eligible, key=lambda c: _digest(f"aqis-s1-noise|{seed}|{utt_id}|{c}"))
    room = lengths[clip] - length + 1
    return NoiseDraw(clip, _digest(f"aqis-s1-offset|{seed}|{utt_id}|{clip}") % room)


def add_noise(speech, noise_segment, snr_db):
    """Speech plus an equally long noise segment at snr_db, by aqis_lab.packs.mix.mix_clip."""
    return mix_clip(speech, noise_segment, snr_db).samples


def scale_to_dbfs(clip, level_dbfs):
    """The clip scaled to the RMS level level_dbfs (0 dBFS = 32768); a silent clip stays silent."""
    x = np.asarray(clip, dtype=np.float64)
    rms = float(np.sqrt(np.mean(x ** 2))) if len(x) else 0.0
    if rms == 0.0:
        return np.zeros(len(x), dtype=np.int16)
    gain = 32768.0 * 10 ** (level_dbfs / 20) / rms
    return np.clip(np.round(x * gain), -32768, 32767).astype(np.int16)


# ---- phone ---------------------------------------------------------------------------------------------------
SEG_END = np.array([0x3F, 0x7F, 0xFF, 0x1FF, 0x3FF, 0x7FF, 0xFFF, 0x1FFF])


def ulaw_encode(x):
    """int16 samples to G.711 mu-law codes (uint8), the ITU 14-bit reference algorithm."""
    v = x.astype(np.int32) >> 2
    mask = np.where(v < 0, 0x7F, 0xFF)
    v = np.minimum(np.abs(v), 8159) + (0x84 >> 2)
    seg = np.searchsorted(SEG_END, v)
    u = np.where(seg >= 8, 0x7F, (seg << 4) | ((v >> (seg + 1)) & 0xF))
    return (u ^ mask).astype(np.uint8)


def ulaw_decode(u):
    """G.711 mu-law codes (uint8) to int16 samples."""
    u = (~u.astype(np.int32)) & 0xFF
    t = (((u & 0x0F) << 3) + 0x84) << ((u & 0x70) >> 4)
    return np.where(u & 0x80, 0x84 - t, t - 0x84).astype(np.int16)


def bandpass_fir(fs=16000, lo=300.0, hi=3400.0, taps=511, beta=8.0):
    n = np.arange(taps) - (taps - 1) / 2
    h = (2 * hi / fs) * np.sinc(2 * hi / fs * n) - (2 * lo / fs) * np.sinc(2 * lo / fs * n)
    return h * np.kaiser(taps, beta)


def _conv_same(x, h):
    """Zero-phase FFT convolution, the same length as x."""
    n = len(x) + len(h) - 1
    m = 1 << (n - 1).bit_length()
    y = np.fft.irfft(np.fft.rfft(x, m) * np.fft.rfft(h, m), m)[:n]
    d = (len(h) - 1) // 2
    return y[d:d + len(x)]


@functools.lru_cache(maxsize=None)
def _default_filter():
    return bandpass_fir()


def phone_channel(x16, h=None):
    """16 kHz int16 through the phone line: band-pass, 8 kHz, mu-law, back to 16 kHz."""
    h = _default_filter() if h is None else h
    y8 = _conv_same(x16.astype(np.float64), h)[::2]
    y8 = ulaw_decode(ulaw_encode(np.clip(np.round(y8), -32768, 32767).astype(np.int16))).astype(np.float64)
    up = np.zeros(len(x16))
    up[::2] = y8[:(len(x16) + 1) // 2]
    return np.clip(np.round(2 * _conv_same(up, h)), -32768, 32767).astype(np.int16)


# ---- webrtc (libopus) ----------------------------------------------------------------------------------------
VOIP = 2048
SET_BITRATE, SET_COMPLEXITY, SET_INBAND_FEC, SET_PACKET_LOSS_PERC, GET_LOOKAHEAD = 4002, 4010, 4012, 4014, 4027


@functools.lru_cache(maxsize=None)
def _opus():
    path = ctypes.util.find_library("opus") or "libopus.so.0"
    try:
        lib = ctypes.CDLL(path)
    except OSError as exc:
        raise ConditionError(f"libopus is not installed ({exc}); on Colab and Ubuntu it is the package libopus0") from exc
    lib.opus_encoder_create.restype = ctypes.c_void_p
    lib.opus_decoder_create.restype = ctypes.c_void_p
    lib.opus_strerror.restype = ctypes.c_char_p
    lib.opus_encode.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_int16), ctypes.c_int, ctypes.c_char_p,
                                ctypes.c_int32]
    lib.opus_decode.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int32, ctypes.POINTER(ctypes.c_int16),
                                ctypes.c_int, ctypes.c_int]
    return lib


def _ok(lib, code, what):
    if code < 0:
        raise ConditionError(f"libopus {what}: {lib.opus_strerror(code).decode()}")
    return code


def webrtc_channel(x, seed, sr=16000, bitrate=16000, loss=0.02, frame_ms=20, fec=True):
    """Opus VOIP at `bitrate` with seeded packet loss; returns (int16 samples as long as x, packet statistics)."""
    lib = _opus()
    err = ctypes.c_int()
    enc = ctypes.c_void_p(lib.opus_encoder_create(sr, 1, VOIP, ctypes.byref(err)))
    _ok(lib, err.value, "encoder")
    dec = ctypes.c_void_p(lib.opus_decoder_create(sr, 1, ctypes.byref(err)))
    _ok(lib, err.value, "decoder")
    try:
        for req, val in ((SET_BITRATE, bitrate), (SET_COMPLEXITY, 10), (SET_INBAND_FEC, 1 if fec else 0),
                         (SET_PACKET_LOSS_PERC, round(loss * 100))):
            _ok(lib, lib.opus_encoder_ctl(enc, ctypes.c_int(req), ctypes.c_int(val)), f"ctl {req}")
        la = ctypes.c_int32()
        _ok(lib, lib.opus_encoder_ctl(enc, ctypes.c_int(GET_LOOKAHEAD), ctypes.byref(la)), "lookahead")
        n = sr * frame_ms // 1000
        total = len(x) + la.value
        padded = np.zeros(total + (-total) % n, np.int16)
        padded[:len(x)] = x
        buf, packets = ctypes.create_string_buffer(4000), []
        for i in range(0, len(padded), n):
            frame = np.ascontiguousarray(padded[i:i + n])
            k = _ok(lib, lib.opus_encode(enc, frame.ctypes.data_as(ctypes.POINTER(ctypes.c_int16)), n, buf, 4000),
                    "encode")
            packets.append(buf.raw[:k])
        lost = np.random.default_rng(seed).random(len(packets)) < loss
        pcm, out = (ctypes.c_int16 * n)(), np.empty(len(packets) * n, np.int16)
        n_fec = n_plc = 0
        for i, p in enumerate(packets):
            if not lost[i]:
                k = lib.opus_decode(dec, p, len(p), pcm, n, 0)
            elif fec and i + 1 < len(packets) and not lost[i + 1]:
                k = lib.opus_decode(dec, packets[i + 1], len(packets[i + 1]), pcm, n, 1)
                n_fec += 1
            else:
                k = lib.opus_decode(dec, None, 0, pcm, n, 0)
                n_plc += 1
            _ok(lib, k, "decode")
            out[i * n:(i + 1) * n] = np.frombuffer(pcm, np.int16, count=n)
        return out[la.value:la.value + len(x)], {"packets": len(packets), "bytes": sum(map(len, packets)),
                                                 "lost": int(lost.sum()), "fec": n_fec, "plc": n_plc}
    finally:
        lib.opus_encoder_destroy(enc)
        lib.opus_decoder_destroy(dec)


# ---- rendering a condition -----------------------------------------------------------------------------------
def loss_seed(seed, utt_id):
    return _digest(f"aqis-s1-loss|{seed}|{utt_id}") % (1 << 32)


def _channel_settings(conditions, channel):
    holder = conditions.get(CHANNEL_CONDITION[channel])
    if holder is None:
        raise ConditionError(f"conditions has no {CHANNEL_CONDITION[channel]!r} entry to give the {channel} settings")
    return holder


def render_condition(name, conditions, speech, seed, utt_id, noise):
    """(samples, info) for condition `name`; `noise` maps MUSAN noise clip IDs to int16 samples."""
    if name not in conditions:
        raise ConditionError(f"unknown condition {name!r}")
    cond = conditions[name]
    audio, info = np.asarray(speech, dtype=np.int16), {}
    if "noise" in cond:
        draw = noise_draw(seed, utt_id, {clip: len(samples) for clip, samples in noise.items()}, len(audio))
        segment = noise[draw.clip_id][draw.offset:draw.offset + len(audio)]
        try:
            mixed = mix_clip(audio, segment, cond["snr_db"])
            audio = mixed.samples
            info.update(noise_clip=draw.clip_id, noise_offset=draw.offset, snr_db=cond["snr_db"],
                        achieved_snr_db=mixed.achieved_snr_db, peak_limited=mixed.peak_limited)
        except RenderError:
            # Digital silence clip: when speech RMS == 0, the audio is pure background noise at target SNR level
            nominal_speech_rms = 3276.0  # -20 dBFS nominal speech
            target_noise_rms = nominal_speech_rms / (10.0 ** (cond["snr_db"] / 20.0))
            seg_f = segment.astype(np.float64)
            seg_rms = np.sqrt(np.mean(seg_f ** 2))
            audio = np.clip(np.round(seg_f * (target_noise_rms / seg_rms)), -32768, 32767).astype(np.int16) if seg_rms > 0 else segment
            info.update(noise_clip=draw.clip_id, noise_offset=draw.offset, snr_db=cond["snr_db"],
                        achieved_snr_db=float("-inf"), peak_limited=False)
    channel = cond.get("channel")
    if channel == "g711_mulaw":
        settings = _channel_settings(conditions, channel)
        audio = phone_channel(audio, bandpass_fir(SR, float(settings["band_hz"][0]), float(settings["band_hz"][1]),
                                                  settings["fir_taps"], settings["kaiser_beta"]))
    elif channel == "opus":
        settings = _channel_settings(conditions, channel)
        seed_for_loss = loss_seed(seed, utt_id)
        audio, stats = webrtc_channel(audio, seed_for_loss, SR, settings["bitrate_bps"], settings["loss"],
                                      settings["frame_ms"], settings["fec"])
        info.update(loss_seed=seed_for_loss, **{f"opus_{k}": v for k, v in stats.items()})
    return audio, info
