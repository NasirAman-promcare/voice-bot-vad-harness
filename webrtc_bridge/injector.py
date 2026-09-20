"""
webrtc_bridge/injector.py

One Job:
    Implement `WebRTCJitsiAudioInjector`, the concrete WebRTC audio injection driver
    satisfying `bots.speaker_bot.IJitsiAudioInjector` via structural subtyping (duck typing).
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
    ssl_verify: bool
    jingle_debug_log_path: str


def load_bridge_config(config_path: Union[str, Path] = "webrtc_bridge/bridge_config.yaml") -> BridgeConfig:
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
        ssl_verify=bool(raw.get("ssl_verify", False)),
        jingle_debug_log_path=str(raw["jingle_debug_log_path"]).strip(),
    )


class WebRTCJitsiAudioInjector:
    """Concrete WebRTC media injector satisfying `bots.speaker_bot.IJitsiAudioInjector`."""

    def __init__(
        self,
        config_path: Union[str, Path] = "webrtc_bridge/bridge_config.yaml",
        config: Optional[BridgeConfig] = None,
    ) -> None:
        self.config = config or load_bridge_config(config_path)
        self.is_connected = False
        self.current_room: Optional[str] = None
        self.bridge_url: Optional[str] = None

        self._signaling: Optional[JitsiSignalingSession] = None
        self._media_session: Optional[BridgeMediaSession] = None

    def connect_and_join(self, room_id: str, bridge_url: str) -> None:
        if not room_id or not room_id.strip():
            raise InjectorConnectionError("Cannot connect: room_id is empty.")
        if not bridge_url or not bridge_url.strip():
            raise InjectorConnectionError("Cannot connect: bridge_url is empty.")

        if self.is_connected and self.current_room == room_id:
            logger.info("Injector already connected to room '%s'", room_id)
            return

        if self.is_connected:
            self.disconnect()

        target_room = room_id.strip()
        self.current_room = target_room
        self.bridge_url = bridge_url.strip()

        logger.info(
            "Connecting WebRTCJitsiAudioInjector to room '%s' via bridge '%s'",
            self.current_room,
            self.bridge_url,
        )

        try:
            self._media_session = BridgeMediaSession(
                role="sendonly",
                outgoing_track=None,
                ice_gather_timeout_s=self.config.ice_gather_timeout_s,
                dtls_handshake_timeout_s=self.config.dtls_handshake_timeout_s,
            )

            self._signaling = JitsiSignalingSession(
                xmpp_client_domain=self.config.xmpp_client_domain,
                muc_room_domain_prefix=self.config.muc_room_domain_prefix,
                ssl_verify=self.config.ssl_verify,
                jingle_debug_log_path=self.config.jingle_debug_log_path,
            )

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

            raw_offer_xml = self._media_session._run_sync(
                self._signaling.wait_for_offer(timeout_s=self.config.dtls_handshake_timeout_s),
                timeout=self.config.dtls_handshake_timeout_s + 2.0,
            )

            sdp_offer = jingle_offer_to_sdp(raw_offer_xml)
            sdp_answer = self._media_session.answer_offer(sdp_offer)

            session_accept_xml = sdp_answer_to_jingle_accept(
                sdp_answer_str=sdp_answer,
                session_initiate_iq=raw_offer_xml,
            )

            self._media_session._run_sync(
                self._signaling.send_answer(session_accept_xml),
                timeout=5.0,
            )

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
            logger.info("WebRTCJitsiAudioInjector joined room '%s' (SSRC: %d)", self.current_room, ssrc)

        except Exception as exc:
            logger.error("Failed to connect and join Jitsi conference: %s", exc, exc_info=True)
            self.disconnect()
            raise InjectorConnectionError(
                f"Failed to join Jitsi room '{target_room}': {exc}"
            ) from exc

    def play_audio_file(self, audio_path: Union[str, Path], sample_rate_hz: int = 16000) -> None:
        if not self.is_connected or self._media_session is None:
            raise InjectorStateError(
                "Cannot play audio file: WebRTCJitsiAudioInjector is not connected to a room. "
                "Call connect_and_join() first."
            )

        target_path = Path(audio_path)
        logger.debug("Injecting audio clip '%s' into microphone track", target_path.name)

        try:
            clip_track = ManifestClipTrack(
                audio_path=target_path,
                sample_rate_hz=sample_rate_hz,
            )

            self._media_session.replace_outgoing_track(clip_track)

            timeout_s = clip_track.duration_seconds + 10.0
            finished = clip_track.done_event.wait(timeout=timeout_s)

            if not finished:
                logger.warning("Audio playback timed out after %.2fs for clip '%s'", timeout_s, target_path.name)

            logger.debug("Finished streaming audio clip '%s'", target_path.name)

        except Exception as exc:
            logger.error("Error during playback of clip '%s': %s", target_path.name, exc)
            raise InjectorPlaybackError(f"Failed to stream clip '{target_path.name}': {exc}") from exc

    def disconnect(self) -> None:
        if not self.is_connected and self._signaling is None and self._media_session is None:
            return

        logger.info("Disconnecting WebRTCJitsiAudioInjector...")

        if self._signaling is not None:
            try:
                if self._media_session is not None:
                    self._media_session._run_sync(self._signaling.disconnect(), timeout=3.0)
            except Exception as exc:
                logger.debug("Notice disconnecting signaling: %s", exc)
            finally:
                self._signaling = None

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
