"""WP-0.4 FR-0.4-03: the working audio format, strict WAV reading and exact FLAC decoding (aqis_lab/packs/audio.py)."""
import hashlib
import struct
import wave
import io

import numpy as np
import pytest

from aqis_packs_testutil import flac_bytes, list_chunk, seeded_noise, tone, wav_bytes
from aqis_lab.packs import audio


def test_FR_0_4_03_all_clips_16k_mono_pcm16():
    samples = seeded_noise(1234, seed=3)
    data = audio.canonical_wav(samples)
    # read back with the standard library, independently of the lab's reader
    with wave.open(io.BytesIO(data)) as w:
        assert (w.getframerate(), w.getnchannels(), w.getsampwidth(), w.getnframes()) == (16000, 1, 2, 1234)
        assert w.readframes(1234) == samples.astype("<i2").tobytes()
    assert len(data) == 44 + 2 * 1234
    assert data[:4] == b"RIFF" and data[8:16] == b"WAVEfmt " and data[36:40] == b"data"
    info, back = audio.read_wav(data, "x.wav")
    assert (info.sample_rate_hz, info.channels, info.bits, info.n_samples) == (16000, 1, 16, 1234)
    assert np.array_equal(back, samples)


def test_FR_0_4_03_canonical_wav_drops_extra_chunks_and_keeps_samples():
    samples = tone(800)
    source = wav_bytes(samples, extra_chunk=list_chunk())
    info, back = audio.read_wav(source, "tts.wav")
    assert info.data_offset > 44
    assert audio.canonical_wav(back) == wav_bytes(samples)


def test_FR_0_4_03_flac_decode_checked_against_streaminfo_md5():
    samples = seeded_noise(5000, seed=9)
    data = flac_bytes(samples)
    info, back = audio.decode_flac(data, "u.flac")
    assert info.n_samples == 5000 and np.array_equal(back, samples)
    md5_offset = 8 + 18
    assert data[md5_offset:md5_offset + 16] == hashlib.md5(samples.astype("<i2").tobytes()).digest()
    wrong = bytearray(data)
    wrong[md5_offset] ^= 0xFF
    with pytest.raises(audio.AudioFormatError, match="do not match the FLAC STREAMINFO MD5"):
        audio.decode_flac(bytes(wrong), "u.flac")
    unsigned = bytearray(data)
    unsigned[md5_offset:md5_offset + 16] = bytes(16)
    with pytest.raises(audio.AudioFormatError, match="no MD5 signature"):
        audio.decode_flac(bytes(unsigned), "u.flac")


@pytest.mark.parametrize("rate,channels,bits", [(48000, 1, 16), (16000, 2, 16), (16000, 1, 8), (8000, 1, 16)])
def test_FR_0_4_03_rejects_source_in_other_format(rate, channels, bits):
    samples = tone(1600 * channels)
    data = wav_bytes(samples, rate=rate, channels=channels, bits=bits)
    with pytest.raises(audio.AudioFormatError) as info:
        audio.read_wav(data, "other.wav")
    text = str(info.value)
    assert "other.wav" in text and f"{rate} Hz" in text and "ffmpeg" in text
    if (rate, channels, bits) != (16000, 1, 8):
        with pytest.raises(audio.AudioFormatError, match="16000 Hz, 1 channel, 16-bit"):
            audio.decode_flac(flac_bytes(tone(1600), rate=rate) if channels == 1 else _stereo_flac(), "o.flac")


def _stereo_flac():
    import soundfile
    buf = io.BytesIO()
    soundfile.write(buf, np.zeros((100, 2), dtype=np.int16), 16000, format="FLAC", subtype="PCM_16")
    return buf.getvalue()


def test_FR_0_4_03_wav_reader_rejects_malformed_files():
    good = wav_bytes(tone(100))
    cases = [
        ("not a RIFF", b"RIFX" + good[4:]),
        ("RIFF size", good[:4] + struct.pack("<I", 5) + good[8:]),
        ("runs past the end", good[:40] + struct.pack("<I", 10 ** 6) + good[44:]),
        ("not PCM", good[:20] + struct.pack("<H", 3) + good[22:]),
        ("whole number of frames", good[:40] + struct.pack("<I", 199) + good[44:]),  # 199 bytes + pad byte
    ]
    for expected, data in cases:
        with pytest.raises(audio.AudioFormatError, match=expected):
            audio.wav_info(data, "bad.wav")
    no_data = b"RIFF" + struct.pack("<I", 4 + 24) + good[8:36]
    with pytest.raises(audio.AudioFormatError, match="no data chunk"):
        audio.wav_info(no_data, "bad.wav")
    with pytest.raises(audio.AudioFormatError, match="not a FLAC file"):
        audio.decode_flac(good, "bad.flac")
    with pytest.raises(audio.AudioFormatError, match="int16"):
        audio.canonical_wav(np.zeros(4, dtype=np.int32))
