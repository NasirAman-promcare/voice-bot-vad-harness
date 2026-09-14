"""
bots package initialization.

Exposes the Tier 2 Jitsi Live Pipeline bots:
  - SpeakerBot: plays individual manifest clips and reports verbatim marker offsets.
  - ListenerBot: ingests, timestamps, decodes, resamples (16kHz), and tracks sequence loss.
"""

from bots.listener_bot import (
    AudioStreamEvent,
    CapturedStreamData,
    ListenerBot,
    ListenerBotError,
    PacketDiagnostic,
)
from bots.speaker_bot import (
    AudioPlaybackError,
    ClipFileNotFoundError,
    DefaultJitsiAudioInjector,
    IJitsiAudioInjector,
    PlaybackMetadata,
    RoomJoinError,
    SpeakerBot,
    SpeakerBotError,
)

__all__ = [
    # Listener Bot
    "AudioStreamEvent",
    "CapturedStreamData",
    "ListenerBot",
    "ListenerBotError",
    "PacketDiagnostic",
    # Speaker Bot
    "AudioPlaybackError",
    "ClipFileNotFoundError",
    "DefaultJitsiAudioInjector",
    "IJitsiAudioInjector",
    "PlaybackMetadata",
    "RoomJoinError",
    "SpeakerBot",
    "SpeakerBotError",
]