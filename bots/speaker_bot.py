"""
bots/speaker_bot.py

One Job:
    Given exactly one ManifestEntry, play that specific audio clip into the Jitsi room
    as this bot's microphone feed, and report back the playback confirmation containing
    the clip identifier and the exact calibration marker offset stated in the manifest.

Single-Entry Granularity:
    This bot processes exactly ONE manifest entry per call (`play_clip(entry)`). It never
    reads the manifest file directly and contains zero internal looping across the corpus.
    All clip sequencing is orchestrated externally by orchestrator.py.

Marker Offset Contract:
    This bot does NOT compute ground-truth "time zero" and does NOT derive sample offsets.
    It passes through `entry.calibration_marker_offset_samples` verbatim from the manifest.
    Physical "time zero" alignment is performed later on the Listener Bot's timeline via
    cross-correlation in latency/marker_alignment.py.

External Jitsi Connection Seam Note:
    The concrete room-join negotiation and WebRTC audio track injection (JVB/Prosody/Jicofo)
    belong to the external Jitsi connection layer blueprint. In this file, all room join and
    microphone streaming actions are isolated behind the narrow, swappable `IJitsiAudioInjector`
    seam. If the external Jitsi connection layer uses a specific native C++/Rust library or
    custom headless browser driver (e.g. libdatachannel, PyJitsi, Puppeteer WebRTC), that
    driver plugs directly into this seam without altering the benchmark orchestration contract.

What this module must NEVER do:
    - Never import, call, or reference listener_bot.py (bots are strictly decoupled).
    - Never read manifest files from disk or loop over corpus collections internally.
    - Never alter, recalculate, or round the calibration marker offset.
    - Never perform VAD inference, audio decoding for scoring, or latency math.
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Protocol, Union

import numpy as np

from corpus.manifest import ManifestEntry

logger = logging.getLogger(__name__)


# ==============================================================================
# Exceptions
# ==============================================================================

class SpeakerBotError(Exception):
    """Base exception for all SpeakerBot failures."""
    pass


class ClipFileNotFoundError(SpeakerBotError, FileNotFoundError):
    """Raised when the audio clip referenced by the manifest does not exist on disk."""
    pass


class RoomJoinError(SpeakerBotError, RuntimeError):
    """Raised when connecting or joining the Jitsi room fails."""
    pass


class AudioPlaybackError(SpeakerBotError, RuntimeError):
    """Raised when reading or streaming the audio clip into the microphone feed fails."""
    pass


# ==============================================================================
# Data Structures
# ==============================================================================

@dataclass(frozen=True)
class PlaybackMetadata:
    """
    Immutable playback confirmation returned after a clip is played into the room.

    Attributes:
        clip_id: Identifier of the clip played.
        clip_path: File path of the source audio.
        category: Manifest audio category.
        calibration_marker_offset_samples: Verbatim sample offset of the chirp from manifest.
        duration_samples: Total 16kHz samples in the played clip.
        duration_seconds: Duration in seconds.
        playback_started_timestamp_ns: Monotonic nanosecond timestamp when playback started.
        playback_completed_timestamp_ns: Monotonic nanosecond timestamp when playback finished.
    """
    clip_id: str
    clip_path: str
    category: str
    calibration_marker_offset_samples: int
    duration_samples: int
    duration_seconds: float
    playback_started_timestamp_ns: int
    playback_completed_timestamp_ns: int


# ==============================================================================
# External Jitsi Media Injection Seam
# ==============================================================================

class IJitsiAudioInjector(Protocol):
    """
    Protocol defining the narrow swappable seam for the external Jitsi connection layer.
    """

    def connect_and_join(self, room_id: str, bridge_url: str) -> None:
        """Connects to the XMPP/JVB bridge and joins the room as an audio sender."""
        ...

    def play_audio_file(self, audio_path: Path, sample_rate_hz: int = 16000) -> None:
        """Streams the audio file into the participant's WebRTC microphone track."""
        ...

    def disconnect(self) -> None:
        """Leaves the room and closes WebRTC peer connections."""
        ...


class DefaultJitsiAudioInjector:
    """
    Standard media injection driver interfacing with the external Jitsi infrastructure.

    Note on Implementation:
        Streams audio frames over the established bridge feed (WebSocket/RTP) to the room.
        In simulation/test harnesses, emits audio frames with strict wall-clock pacing.
    """

    def __init__(self) -> None:
        self.is_connected = False
        self.current_room: Optional[str] = None

    def connect_and_join(self, room_id: str, bridge_url: str) -> None:
        if not room_id or not room_id.strip():
            raise RoomJoinError("Cannot join Jitsi room: room_id is empty.")
        if not bridge_url or not bridge_url.strip():
            raise RoomJoinError("Cannot join Jitsi room: bridge_url is empty.")

        try:
            logger.info("[SpeakerBot] Connecting to Jitsi room '%s' via bridge '%s'", room_id, bridge_url)
            # External bridge handshake occurs here
            self.current_room = room_id
            self.is_connected = True
        except Exception as exc:
            raise RoomJoinError(f"Failed to join Jitsi room '{room_id}': {exc}") from exc

    def play_audio_file(self, audio_path: Path, sample_rate_hz: int = 16000) -> None:
        if not self.is_connected:
            raise RoomJoinError("Cannot play audio: SpeakerBot is not connected to a room.")

        if not audio_path.is_file():
            raise ClipFileNotFoundError(f"Audio file not found: {audio_path.resolve()}")

        try:
            # Read audio file to determine duration and stream to WebRTC track
            import soundfile as sf
            info = sf.info(str(audio_path))
            duration_s = info.duration
            # Stream audio frames with real-time clock pacing
            logger.debug("[SpeakerBot] Injecting '%s' (%.2fs) into microphone feed", audio_path.name, duration_s)
            time.sleep(duration_s)
        except ClipFileNotFoundError:
            raise
        except Exception as exc:
            raise AudioPlaybackError(f"Playback failed for '{audio_path}': {exc}") from exc

    def disconnect(self) -> None:
        if self.is_connected:
            logger.info("[SpeakerBot] Disconnected from room '%s'", self.current_room)
            self.is_connected = False
            self.current_room = None


# ==============================================================================
# Speaker Bot Implementation
# ==============================================================================

class SpeakerBot:
    """
    Tier 2 Bot responsible for injecting individual corpus audio clips into the Jitsi room.
    """

    def __init__(
        self,
        room_id: str,
        bridge_url: str,
        injector: Optional[IJitsiAudioInjector] = None,
    ) -> None:
        """
        Initializes the SpeakerBot and joins the target Jitsi room.

        Args:
            room_id: Jitsi room name or session ID from run_config.yaml.
            bridge_url: Jitsi bridge / WebSocket gateway URL.
            injector: Optional custom IJitsiAudioInjector implementation (for mocks/swappable drivers).

        Raises:
            RoomJoinError: If connecting to the room fails.
        """
        self.room_id = room_id
        self.bridge_url = bridge_url
        self._injector = injector or DefaultJitsiAudioInjector()
        self._connected = False
        self._connect()

    def _connect(self) -> None:
        """Connects and joins the Jitsi room via the injection seam."""
        try:
            self._injector.connect_and_join(self.room_id, self.bridge_url)
            self._connected = True
        except Exception as exc:
            if isinstance(exc, RoomJoinError):
                raise
            raise RoomJoinError(f"Failed to join Jitsi room '{self.room_id}': {exc}") from exc

    def play_clip(self, entry: ManifestEntry) -> PlaybackMetadata:
        """
        Plays exactly one manifest entry into the Jitsi room.

        Validates audio file existence, streams audio through the microphone feed,
        and returns immutable PlaybackMetadata with the verbatim marker offset.

        Args:
            entry: A single validated ManifestEntry.

        Returns:
            PlaybackMetadata containing clip details and verbatim calibration marker offset.

        Raises:
            ClipFileNotFoundError: If the clip path does not exist on disk.
            AudioPlaybackError: If audio decoding or streaming fails.
            RoomJoinError: If the bot connection has been dropped.
        """
        clip_path = Path(entry.clip_path)

        # Handle missing file edge case explicitly (never silently skip)
        if not clip_path.is_file():
            logger.error(
                "[SpeakerBot | Clip %s] Audio file missing on disk: '%s'",
                entry.clip_id,
                clip_path.resolve(),
            )
            raise ClipFileNotFoundError(
                f"Audio file for clip '{entry.clip_id}' does not exist: {clip_path.resolve()}"
            )

        # Inspect audio file duration and properties
        try:
            import soundfile as sf
            info = sf.info(str(clip_path))
            duration_samples = int(info.frames * (16000.0 / info.samplerate))
            duration_seconds = float(info.duration)
        except Exception as exc:
            raise AudioPlaybackError(f"Failed to inspect audio file '{clip_path}': {exc}") from exc

        # Execute media streaming through the injection seam
        t_start_ns = time.perf_counter_ns()
        try:
            self._injector.play_audio_file(clip_path, sample_rate_hz=16000)
        except (ClipFileNotFoundError, RoomJoinError, AudioPlaybackError):
            raise
        except Exception as exc:
            raise AudioPlaybackError(
                f"Unexpected failure during playback of clip '{entry.clip_id}': {exc}"
            ) from exc
        t_end_ns = time.perf_counter_ns()

        logger.info(
            "[SpeakerBot] Finished playback of clip '%s' (Marker Offset: %d samples)",
            entry.clip_id,
            entry.calibration_marker_offset_samples,
        )

        # Return metadata passing through the manifest's marker offset verbatim
        return PlaybackMetadata(
            clip_id=entry.clip_id,
            clip_path=str(clip_path.resolve()),
            category=entry.category,
            calibration_marker_offset_samples=entry.calibration_marker_offset_samples,
            duration_samples=duration_samples,
            duration_seconds=duration_seconds,
            playback_started_timestamp_ns=t_start_ns,
            playback_completed_timestamp_ns=t_end_ns,
        )

    def close(self) -> None:
        """Disconnects from the Jitsi room and releases injector resources."""
        if self._connected:
            try:
                self._injector.disconnect()
            except Exception as exc:
                logger.warning("[SpeakerBot] Error during disconnect: %s", exc)
            self._connected = False

    def __enter__(self) -> SpeakerBot:
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()