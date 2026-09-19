"""
webrtc_bridge package initialization.

Exposes the public interface and typed exceptions for the Direct WebRTC
Participant Bridge subsystem (Tier 2 live Jitsi pipeline).
"""

from webrtc_bridge.injector import (
    BridgeConfig,
    InjectorConnectionError,
    InjectorError,
    InjectorPlaybackError,
    InjectorStateError,
    WebRTCJitsiAudioInjector,
    load_bridge_config,
)
from webrtc_bridge.jingle_sdp_translator import (
    JingleSessionMismatchError,
    JingleTranslationError,
    JingleXMLMalformedError,
    build_source_add_stanza,
    jingle_offer_to_sdp,
    sdp_answer_to_jingle_accept,
)
from webrtc_bridge.jitsi_signaling import (
    JingleOfferTimeoutError,
    MUCConflictError,
    MUCJoinError,
    SASLAuthenticationError,
    SignalingConnectionError,
    SignalingError,
)
from webrtc_bridge.media_session import (
    AIORTCConformanceError,
    DTLSHandshakeTimeoutError,
    ICEConnectionFailedError,
    ICEConnectionTimeoutError,
    MediaSessionError,
    MediaSessionNegotiationError,
    MediaSessionStateError,
)
from webrtc_bridge.outgoing_clip_track import (
    AudioFileDecodeError,
    ClipTrackFileNotFoundError,
    ManifestClipTrack,
    OutgoingClipTrackError,
    SampleRateMismatchError,
)
from webrtc_bridge.raw_rtp_tap import (
    InvalidReceiverError,
    RawRtpTap,
    RawRtpTapError,
)

# Lazy/conditional export of JitsiListenerBridge (File 32)
try:
    from webrtc_bridge.listener_bridge import JitsiListenerBridge
except ImportError:
    JitsiListenerBridge = None  # type: ignore[assignment, misc]

__all__ = [
    # Top-Level Seams & Config
    "WebRTCJitsiAudioInjector",
    "JitsiListenerBridge",
    "BridgeConfig",
    "load_bridge_config",
    # Core Helpers
    "ManifestClipTrack",
    "RawRtpTap",
    "jingle_offer_to_sdp",
    "sdp_answer_to_jingle_accept",
    "build_source_add_stanza",
    # Injector Exceptions
    "InjectorError",
    "InjectorStateError",
    "InjectorConnectionError",
    "InjectorPlaybackError",
    # Signaling Exceptions
    "SignalingError",
    "SignalingConnectionError",
    "SASLAuthenticationError",
    "MUCJoinError",
    "MUCConflictError",
    "JingleOfferTimeoutError",
    # Translation Exceptions
    "JingleTranslationError",
    "JingleXMLMalformedError",
    "JingleSessionMismatchError",
    # Media Session Exceptions
    "MediaSessionError",
    "AIORTCConformanceError",
    "MediaSessionStateError",
    "MediaSessionNegotiationError",
    "ICEConnectionTimeoutError",
    "DTLSHandshakeTimeoutError",
    "ICEConnectionFailedError",
    # Track Exceptions
    "OutgoingClipTrackError",
    "ClipTrackFileNotFoundError",
    "SampleRateMismatchError",
    "AudioFileDecodeError",
    # Tap Exceptions
    "RawRtpTapError",
    "InvalidReceiverError",
]