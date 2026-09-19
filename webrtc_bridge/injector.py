"""
webrtc_bridge/injector.py

One Job:
    Implement `WebRTCJitsiAudioInjector`, the concrete WebRTC audio injection driver
    satisfying `bots.speaker_bot.IJitsiAudioInjector` via structural subtyping (duck typing).
    Composes XMPP signaling (File 26), Jingle-SDP translation (File 27), the WebRTC media
    session (File 28), and the outgoing clip track (File 29) to inject real audio into a
    Jitsi conference room without a browser.

Structural Subtyping & Seam Isolation:
    Satisfies `IJitsiAudioInjector`'s three synchronous methods:
      1. `connect_and_join(room_id, bridge_url)`: Runs full signaling, ICE/DTLS negotiation,
         and source announcement once per process lifetime.
      2. `play_audio_file(audio_path, sample_rate_hz)`: Hot-swaps `ManifestClipTrack` on
         the live sender and blocks synchronously on `done_event` until playback completes.
      3. `disconnect()`: Cleanly tears down Jingle, presence, and peer connection in order.
    Does NOT subclass or import anything from `bots.speaker_bot`.

Single Reader Rule:
    This file is one of exactly two files permitted to read `webrtc_bridge/bridge_config.yaml`
    directly. `room_id` and `bridge_url` are never read from disk here; they are passed
    directly through `connect_and_join` as provided by the orchestrator.

What this module must NEVER do:
    - Never import anything from `bots/` or `config/run_config.yaml`.
    - Never reconnect ICE/DTLS per clip (connect once, reuse for all manifest clips).
    - Never attempt implicit connection on `play_audio_file` if not connected.
    - Never leave partially initialized sessions hanging if connection fails midway.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Union

import yaml

from webrtc_bridge.jingle_sdp_translator import (
    jingle_offer_to_sdp,
    sdp_answer_to_jingle_accept,
)
from webrtc_bridge.jitsi_signaling import JitsiSignalingSession
from webrtc_bridge.media_session import BridgeMediaSession
from webrtc_bridge.outgoing_clip_track import ManifestClipTrack

logger = logging.getLogger("webrtc_bridge.injector")


# ==============================================================================
# Exceptions
# ==============================================================================

class InjectorError(Exception):
    """Base exception for WebRTCJitsiAudioInjector operations."""
    pass


class InjectorStateError(InjectorError):
    """Raised when an operation is invoked in an invalid injector lifecycle state."""
    pass


class InjectorConnectionError(InjectorError):
    """Raised when room connection, signaling, or WebRTC negotiation fails."""
    pass


class InjectorPlaybackError(InjectorError):
    """Raised when audio track injection or playback fails."""
    pass


# ==============================================================================
# Declarative Bridge Configuration Schema & Loader
# ==============================================================================

@dataclass(frozen=True)
class BridgeConfig:
    """Immutable parameters loaded from webrtc_bridge/bridge_config.yaml."""
    speaker_display_name: str
    listener_display_name: str
    xmpp_client_domain: str
    muc_room_domain_prefix: str
    ice_gather_timeout_s: float
    dtls_handshake_timeout_s: float
    xmpp_reconnect_attempts: int
    xmpp_reconnect_backoff_s: float
    opus_bitrate_bps: int
    opus_dtx_enabled: bool
    opus_fec_enabled: bool
    jingle_debug_log_path: str


def load_bridge_config(config_path: Union[str, Path] = "webrtc_bridge/bridge_config.yaml") -> BridgeConfig:
    """
    Parses and validates `webrtc_bridge/bridge_config.yaml`.

    Raises:
        FileNotFoundError: If the configuration file is missing.
        ValueError: If required keys are missing or malformed.
    """
    path = Path(config_path)
    if not path.is_file():
        raise FileNotFoundError(f"Bridge configuration file not found: {path.resolve()}")

    with open(path, mode="r", encoding="utf-8") as f:
        try:
            raw = yaml.safe_load(f)
        except yaml.YAMLError as exc:
            raise ValueError(f"Malformed YAML in '{path}': {exc}") from exc

    if not isinstance(raw, dict):
        raise ValueError(f"Root of bridge configuration '{path}' must be a mapping.")

    required_keys = [
        "speaker_display_name", "listener_display_name", "xmpp_client_domain",
        "muc_room_domain_prefix", "ice_gather_timeout_s", "dtls_handshake_timeout_s",
        "xmpp_reconnect_attempts", "xmpp_reconnect_backoff_s", "opus_bitrate_bps",
        "opus_dtx_enabled", "opus_fec_enabled", "jingle_debug_log_path",
    ]
    missing = [k for k in required_keys if k not in raw]
    if missing:
        raise ValueError(f"Bridge config '{path}' missing required keys: {missing}")

    return BridgeConfig(
        speaker_display_name=str(raw["speaker_display_name"]).strip(),
        listener_display_name=str(raw["listener_display_name"]).strip(),
        xmpp_client_domain=str(raw["xmpp_client_domain"]).strip(),
        muc_room_domain_prefix=str(raw["muc_room_domain_prefix"]).strip(),
        ice_gather_timeout_s=float(raw["ice_gather_timeout_s"]),
        dtls_handshake_timeout_s=float(raw["dtls_handshake_timeout_s"]),
        xmpp_reconnect_attempts=int(raw["xmpp_reconnect_attempts"]),
        xmpp_reconnect_backoff_s=float(raw["xmpp_reconnect_backoff_s"]),
        opus_bitrate_bps=int(raw["opus_bitrate_bps"]),
        opus_dtx_enabled=bool(raw["opus_dtx_enabled"]),
        opus_fec_enabled=bool(raw["opus_fec_enabled"]),
        jingle_debug_log_path=str(raw["jingle_debug_log_path"]).strip(),
    )


# ==============================================================================
# WebRTC Jitsi Audio Injector Implementation
# ==============================================================================

class WebRTCJitsiAudioInjector:
    """
    Concrete WebRTC media injector satisfying `bots.speaker_bot.IJitsiAudioInjector`.
    """

    def __init__(
        self,
        config_path: Union[str, Path] = "webrtc_bridge/bridge_config.yaml",
        config: Optional[BridgeConfig] = None,
    ) -> None:
        """
        Initializes the injector and loads declarative bridge settings.

        Args:
            config_path: Path to bridge_config.yaml.
            config: Optional pre-loaded BridgeConfig instance.
        """
        self.config = config or load_bridge_config(config_path)
        self.is_connected = False
        self.current_room: Optional[str] = None
        self.bridge_url: Optional[str] = None

        self._signaling: Optional[JitsiSignalingSession] = None
        self._media_session: Optional[BridgeMediaSession] = None

    # --------------------------------------------------------------------------
    # IJitsiAudioInjector Protocol Implementation
    # --------------------------------------------------------------------------
    def connect_and_join(self, room_id: str, bridge_url: str) -> None:
        """
        Establishes XMPP signaling, joins the Jitsi room, negotiates Jingle/SDP,
        and establishes DTLS-SRTP to JVB.

        Args:
            room_id: Jitsi room name from orchestrator (e.g. 'vad-benchmark-eval-room-01').
            bridge_url: WebSocket signaling endpoint (e.g. 'wss://vad-jitsi-nasir.duckdns.org/xmpp-websocket').

        Raises:
            InjectorConnectionError: If room join or WebRTC connection fails.
        """
        if not room_id or not room_id.strip():
            raise InjectorConnectionError("Cannot connect: room_id is empty.")
        if not bridge_url or not bridge_url.strip():
            raise InjectorConnectionError("Cannot connect: bridge_url is empty.")

        if self.is_connected and self.current_room == room_id:
            logger.info("Injector already connected to room '%s'", room_id)
            return

        if self.is_connected:
            self.disconnect()

        self.current_room = room_id.strip()
        self.bridge_url = bridge_url.strip()

        logger.info(
            "Connecting WebRTCJitsiAudioInjector to room '%s' via bridge '%s'",
            self.current_room,
            self.bridge_url,
        )

        # Clean teardown safety on partial failure
        try:
            # 1. Initialize Media Session (Starts dedicated background asyncio thread)
            self._media_session = BridgeMediaSession(
                role="sendonly",
                outgoing_track=None,
                ice_gather_timeout_s=self.config.ice_gather_timeout_s,
                dtls_handshake_timeout_s=self.config.dtls_handshake_timeout_s,
            )

            # 2. Initialize XMPP Signaling Session
            self._signaling = JitsiSignalingSession(
                xmpp_client_domain=self.config.xmpp_client_domain,
                muc_room_domain_prefix=self.config.muc_room_domain_prefix,
                jingle_debug_log_path=self.config.jingle_debug_log_path,
            )

            # 3. Connect Signaling & Join MUC (Executed on media session background loop)
            connect_timeout = (
                self.config.ice_gather_timeout_s + self.config.dtls_handshake_timeout_s + 10.0
            )
            self._media_session._run_sync(
                self._signaling.connect(
                    bridge_url=self.bridge_url,
                    room_id=self.current_room,
                    display_name=self.config.speaker_display_name,
                    timeout_s=connect_timeout,
                ),
                timeout=connect_timeout + 2.0,
            )

            # 4. Await Jicofo's Jingle session-initiate Offer
            raw_offer_xml = self._media_session._run_sync(
                self._signaling.wait_for_offer(timeout_s=self.config.dtls_handshake_timeout_s),
                timeout=self.config.dtls_handshake_timeout_s + 2.0,
            )

            # 5. Translate Jingle XML Offer -> SDP Offer (File 27)
            sdp_offer = jingle_offer_to_sdp(raw_offer_xml)

            # 6. Apply Offer & Generate Answer (Blocks synchronously until ICE & DTLS connect)
            sdp_answer = self._media_session.answer_offer(sdp_offer)

            # 7. Translate SDP Answer -> Jingle session-accept IQ (File 27)
            session_accept_xml = sdp_answer_to_jingle_accept(
                sdp_answer_str=sdp_answer,
                session_initiate_iq=raw_offer_xml,
            )

            # 8. Transmit session-accept Answer to Jicofo
            self._media_session._run_sync(
                self._signaling.send_answer(session_accept_xml),
                timeout=5.0,
            )

            # 9. Announce Outgoing Audio Source (SSRC) to MUC / JVB
            ssrc = self._media_session.outgoing_ssrc
            source_name = f"{self.config.speaker_display_name}-a0"
            self._media_session._run_sync(
                self._signaling.announce_source(
                    ssrc=ssrc,
                    media_type=self._media_session.outgoing_media_type,
                    source_name=source_name,
                    muted=False,
                ),
                timeout=5.0,
            )

            self.is_connected = True
            logger.info(
                "WebRTCJitsiAudioInjector successfully joined room '%s' (SSRC: %d)",
                self.current_room,
                ssrc,
            )

        except Exception as exc:
            logger.error("Failed to connect and join Jitsi conference: %s", exc, exc_info=True)
            self.disconnect()
            raise InjectorConnectionError(
                f"Failed to join Jitsi room '{self.current_room}': {exc}"
            ) from exc

    def play_audio_file(self, audio_path: Union[str, Path], sample_rate_hz: int = 16000) -> None:
        """
        Streams exactly one audio clip into the Jitsi room microphone feed.

        Hot-swaps the underlying `ManifestClipTrack` on the live sender without renegotiation
        and blocks synchronously until the audio payload is completely transmitted.

        Args:
            audio_path: Path to the 16kHz mono WAV clip file.
            sample_rate_hz: Sample rate verification value (16000 Hz).

        Raises:
            InjectorStateError: If called when not connected.
            InjectorPlaybackError: If file loading or media playback fails.
        """
        if not self.is_connected or self._media_session is None:
            raise InjectorStateError(
                "Cannot play audio file: WebRTCJitsiAudioInjector is not connected to a room. "
                "Call connect_and_join() first."
            )

        target_path = Path(audio_path)
        logger.debug("Injecting audio clip '%s' into microphone track", target_path.name)

        try:
            # 1. Instantiate ManifestClipTrack (Verifies 16kHz, pre-computes 48kHz upsample)
            clip_track = ManifestClipTrack(
                audio_path=target_path,
                sample_rate_hz=sample_rate_hz,
            )

            # 2. Hot-swap track on existing RTCRtpSender without renegotiating
            self._media_session.replace_outgoing_track(clip_track)

            # 3. Block synchronously until transmission completes
            timeout_s = clip_track.duration_seconds + 10.0
            finished = clip_track.done_event.wait(timeout=timeout_s)

            if not finished:
                logger.warning(
                    "Audio playback timed out after %.2fs for clip '%s'",
                    timeout_s,
                    target_path.name,
                )

            logger.debug("Finished streaming audio clip '%s'", target_path.name)

        except Exception as exc:
            logger.error("Error during playback of clip '%s': %s", target_path.name, exc)
            raise InjectorPlaybackError(
                f"Failed to stream clip '{target_path.name}': {exc}"
            ) from exc

    def disconnect(self) -> None:
        """
        Leaves the Jitsi conference, terminates the Jingle session, and closes
        the WebRTC peer connection and background loop.
        """
        if not self.is_connected and self._signaling is None and self._media_session is None:
            return

        logger.info("Disconnecting WebRTCJitsiAudioInjector from '%s'...", self.current_room)

        # 1. Teardown XMPP Signaling (Sends session-terminate and unavailable presence)
        if self._signaling is not None:
            try:
                if self._media_session is not None:
                    self._media_session._run_sync(self._signaling.disconnect(), timeout=3.0)
            except Exception as exc:
                logger.debug("Notice disconnecting signaling: %s", exc)
            finally:
                self._signaling = None

        # 2. Teardown WebRTC Media Session (Closes RTCPeerConnection and stops thread)
        if self._media_session is not None:
            try:
                self._media_session.close()
            except Exception as exc:
                logger.debug("Notice closing media session: %s", exc)
            finally:
                self._media_session = None

        self.is_connected = False
        self.current_room = None
        self.bridge_url = None
        logger.info("WebRTCJitsiAudioInjector disconnected cleanly.")

    def __enter__(self) -> WebRTCJitsiAudioInjector:
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.disconnect()