"""Audio input and output for the registry and the pack builder: strict WAV reading, canonical WAV writing, exact FLAC decoding.

CAPABILITIES:
  CAP-PACK-002: read_wav() and wav_info() parse RIFF/WAVE files strictly (PCM only, every chunk bounded, any extra chunks skipped); canonical_wav() writes the 44-byte-header 16-bit PCM form every pack clip uses; flac_info() reads a FLAC STREAMINFO block; decode_flac() decodes FLAC with soundfile and proves the samples exact against the encoder's STREAMINFO MD5; require_working_format() rejects anything that is not 16 kHz mono 16-bit [tests: test_FR_0_4_03_all_clips_16k_mono_pcm16, test_FR_0_4_03_flac_decode_checked_against_streaminfo_md5, test_FR_0_4_03_rejects_source_in_other_format, test_FR_0_4_03_wav_reader_rejects_malformed_files]
INPUTS AND OUTPUTS: file bytes in; AudioInfo, sample bytes (16-bit little-endian) or canonical WAV bytes out;
  AudioFormatError naming the file and the problem.
CONTRACTS: phase 0 working format (16 kHz, mono, 16-bit PCM WAV; docs/specs/phase-0/00-PHASE-0-OVERVIEW.md).
INVARIANTS:
  - Never converts: a source in another format is an error, never resampled, remixed or requantised.
  - decode_flac() never returns samples whose MD5 differs from the STREAMINFO MD5, and refuses a FLAC file
    without an MD5, because its decoding could not be proven exact.
  - canonical_wav() output depends only on the samples and the format, so equal samples give equal bytes.
NOT IN SCOPE:
  - Mixing and excerpts (aqis_lab/packs/mix.py); reading archives (aqis_lab/registry/fetch.py).
CHANGE LOG:
  2026-09-27 WP-0.4 FR-0.4-03 created.
"""
import hashlib
import io
import struct
from dataclasses import dataclass

import numpy as np
import soundfile

WORKING_RATE = 16000
WORKING_CHANNELS = 1
WORKING_BITS = 16
WAV_HEADER_BYTES = 44
PCM_FORMAT_TAG = 1


class AudioFormatError(ValueError):
    """An audio file is malformed or not in the format required."""


@dataclass(frozen=True)
class AudioInfo:
    """Format facts of an audio file; data_offset and data_bytes locate the sample data of a WAV file."""
    sample_rate_hz: int
    channels: int
    bits: int
    n_samples: int
    data_offset: int = 0
    data_bytes: int = 0


def _chunks(data, where):
    if len(data) < 12 or data[0:4] != b"RIFF" or data[8:12] != b"WAVE":
        raise AudioFormatError(f"{where}: not a RIFF/WAVE file")
    riff_size = struct.unpack_from("<I", data, 4)[0]
    if riff_size + 8 != len(data):
        raise AudioFormatError(f"{where}: RIFF size field says {riff_size + 8} bytes, the file has {len(data)}")
    pos = 12
    while pos < len(data):
        if pos + 8 > len(data):
            raise AudioFormatError(f"{where}: truncated chunk header at byte {pos}")
        chunk_id = data[pos:pos + 4]
        size = struct.unpack_from("<I", data, pos + 4)[0]
        start = pos + 8
        end = start + size
        if end > len(data):
            raise AudioFormatError(f"{where}: chunk {chunk_id!r} at byte {pos} runs past the end of the file")
        yield chunk_id, start, size
        pos = end + (size & 1)


def wav_info(data, where="audio"):
    """AudioInfo of a WAV file given as bytes; raises AudioFormatError unless it is a well-formed PCM WAV."""
    fmt = None
    found_data = None
    for chunk_id, start, size in _chunks(data, where):
        if chunk_id == b"fmt ":
            if fmt is not None:
                raise AudioFormatError(f"{where}: more than one fmt chunk")
            if size < 16:
                raise AudioFormatError(f"{where}: fmt chunk of {size} bytes is too short")
            fmt = struct.unpack_from("<HHIIHH", data, start)
        elif chunk_id == b"data":
            if found_data is not None:
                raise AudioFormatError(f"{where}: more than one data chunk")
            found_data = (start, size)
    if fmt is None:
        raise AudioFormatError(f"{where}: no fmt chunk")
    if found_data is None:
        raise AudioFormatError(f"{where}: no data chunk")
    tag, channels, rate, byte_rate, block_align, bits = fmt
    if tag != PCM_FORMAT_TAG:
        raise AudioFormatError(f"{where}: format tag {tag} is not PCM (1)")
    if channels < 1 or rate < 1 or bits not in (8, 16, 24, 32):
        raise AudioFormatError(f"{where}: invalid format ({channels} channels, {rate} Hz, {bits} bits)")
    if block_align != channels * bits // 8 or byte_rate != rate * block_align:
        raise AudioFormatError(f"{where}: inconsistent fmt chunk (block align {block_align}, byte rate {byte_rate})")
    start, size = found_data
    if size % block_align:
        raise AudioFormatError(f"{where}: data chunk of {size} bytes is not a whole number of frames")
    return AudioInfo(rate, channels, bits, size // block_align, start, size)


def require_working_format(info, where):
    """Raise AudioFormatError unless info is 16 kHz, mono, 16-bit; the message names the actual format."""
    if (info.sample_rate_hz, info.channels, info.bits) != (WORKING_RATE, WORKING_CHANNELS, WORKING_BITS):
        raise AudioFormatError(
            f"{where}: is {info.sample_rate_hz} Hz, {info.channels} channel(s), {info.bits}-bit; the lab needs "
            f"16000 Hz, 1 channel, 16-bit PCM WAV (convert with: ffmpeg -i <input> -ac 1 -ar 16000 "
            f"-sample_fmt s16 <output>.wav)")


def read_wav(data, where="audio"):
    """(AudioInfo, int16 samples) of a 16 kHz mono 16-bit PCM WAV file given as bytes."""
    info = wav_info(data, where)
    require_working_format(info, where)
    samples = np.frombuffer(data, dtype="<i2", count=info.n_samples, offset=info.data_offset)
    return info, samples.astype(np.int16)


def canonical_wav(samples):
    """Canonical WAV bytes (44-byte header, 16 kHz mono 16-bit PCM) of an int16 sample array."""
    array = np.asarray(samples)
    if array.dtype != np.int16 or array.ndim != 1:
        raise AudioFormatError(f"canonical_wav needs a one-dimensional int16 array, got {array.dtype} {array.shape}")
    payload = array.astype("<i2").tobytes()
    block_align = WORKING_CHANNELS * WORKING_BITS // 8
    header = b"RIFF" + struct.pack("<I", 36 + len(payload)) + b"WAVE" + b"fmt " + struct.pack(
        "<IHHIIHH", 16, PCM_FORMAT_TAG, WORKING_CHANNELS, WORKING_RATE, WORKING_RATE * block_align, block_align,
        WORKING_BITS) + b"data" + struct.pack("<I", len(payload))
    return header + payload


def flac_info(data, where="audio"):
    """(AudioInfo, STREAMINFO MD5 bytes) of a FLAC file given as bytes (header only)."""
    if len(data) < 42 or data[0:4] != b"fLaC":
        raise AudioFormatError(f"{where}: not a FLAC file")
    block_type = data[4] & 0x7F
    length = int.from_bytes(data[5:8], "big")
    if block_type != 0 or length != 34:
        raise AudioFormatError(f"{where}: the first metadata block is not a 34-byte STREAMINFO block")
    streaminfo = data[8:42]
    packed = int.from_bytes(streaminfo[10:18], "big")
    rate = packed >> 44
    channels = ((packed >> 41) & 0x7) + 1
    bits = ((packed >> 36) & 0x1F) + 1
    total = packed & ((1 << 36) - 1)
    if rate < 1:
        raise AudioFormatError(f"{where}: STREAMINFO sample rate is 0")
    return AudioInfo(rate, channels, bits, total), bytes(streaminfo[18:34])


def decode_flac(data, where="audio"):
    """(AudioInfo, int16 samples) of a 16 kHz mono 16-bit FLAC file, proven exact by its STREAMINFO MD5."""
    info, md5 = flac_info(data, where)
    require_working_format(info, where)
    if md5 == bytes(16):
        raise AudioFormatError(f"{where}: FLAC file has no MD5 signature, so exact decoding cannot be proven")
    try:
        samples, rate = soundfile.read(io.BytesIO(data), dtype="int16", always_2d=False)
    except (RuntimeError, soundfile.LibsndfileError) as exc:
        raise AudioFormatError(f"{where}: FLAC decoding failed: {exc}") from exc
    samples = np.ascontiguousarray(samples, dtype=np.int16)
    if rate != info.sample_rate_hz or samples.ndim != 1 or samples.shape[0] != info.n_samples:
        raise AudioFormatError(f"{where}: decoder returned {samples.shape} samples at {rate} Hz, STREAMINFO says "
                               f"{info.n_samples} at {info.sample_rate_hz} Hz")
    if hashlib.md5(samples.astype("<i2").tobytes()).digest() != md5:
        raise AudioFormatError(f"{where}: decoded samples do not match the FLAC STREAMINFO MD5")
    return info, samples
