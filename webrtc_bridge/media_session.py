"""
webrtc_bridge/media_session.py

One Job:
    Own the `aiortc.RTCPeerConnection` media-plane lifecycle and manage a dedicated
    background asyncio event loop thread, exposing clean, synchronous and asynchronous
    methods for `speaker_bot.py` and `listener_bridge.py`.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import logging
import re
import sys
import threading
import time
from typing import Any, Dict, List, Optional, Tuple, Union

import aiortc
from aiortc import (
    MediaStreamTrack,
    RTCConfiguration,
    RTCIceCandidate,      
    RTCIceServer,
    RTCPeerConnection,
    RTCRtpReceiver,
    RTCRtpSender,
    RTCRtpTransceiver,
    RTCSessionDescription,
)

logger = logging.getLogger("webrtc_bridge.media_session")


class MediaSessionError(Exception):
    """Base exception for WebRTC media session operations."""
    pass


class AIORTCConformanceError(MediaSessionError):
    """Raised when the installed aiortc version fails private attribute conformance checks."""
    pass


class MediaSessionStateError(MediaSessionError):
    """Raised when an operation is requested in an invalid session lifecycle state."""
    pass


class MediaSessionNegotiationError(MediaSessionError):
    """Base exception for SDP, ICE, or DTLS negotiation failures."""
    pass


class ICEConnectionTimeoutError(MediaSessionNegotiationError):
    """Raised when ICE connectivity checks fail to complete within the configured timeout."""
    pass


class DTLSHandshakeTimeoutError(MediaSessionNegotiationError):
    """Raised when ICE completes but the DTLS-SRTP handshake fails to establish."""
    pass


class ICEConnectionFailedError(MediaSessionNegotiationError):
    """Raised when an established ICE connection enters the 'failed' or 'disconnected' state."""
    pass


def check_aiortc_conformance() -> None:
    version_str = getattr(aiortc, "__version__", "unknown")
    if not hasattr(RTCRtpReceiver, "_handle_rtp_packet"):
        raise AIORTCConformanceError(
            f"Installed aiortc=={version_str} is missing private method "
            "'RTCRtpReceiver._handle_rtp_packet' required by raw_rtp_tap.py."
        )
    if not hasattr(RTCRtpSender, "replaceTrack") and not hasattr(RTCRtpSender, "_track"):
        raise AIORTCConformanceError(
            f"Installed aiortc=={version_str} does not expose 'replaceTrack' or '_track' on RTCRtpSender."
        )
    logger.debug("aiortc runtime conformance verified (version: %s)", version_str)


class BridgeMediaSession:
    """Synchronous & asynchronous manager for the underlying aiortc RTCPeerConnection."""

    def __init__(
        self,
        role: str,
        outgoing_track: Optional[MediaStreamTrack] = None,
        ice_gather_timeout_s: float = 10.0,
        dtls_handshake_timeout_s: float = 15.0,
    ) -> None:
        clean_role = role.strip().lower()
        if clean_role not in ("sendonly", "recvonly"):
            raise ValueError(f"Invalid role: '{role}'. Must be 'sendonly' or 'recvonly'.")

        check_aiortc_conformance()

        self.role = clean_role
        self.ice_gather_timeout_s = float(ice_gather_timeout_s)
        self.dtls_handshake_timeout_s = float(dtls_handshake_timeout_s)
        self._initial_outgoing_track = outgoing_track

        self._pc: Optional[RTCPeerConnection] = None
        self._transceiver: Optional[RTCRtpTransceiver] = None
        self._sender: Optional[RTCRtpSender] = None
        self._outgoing_ssrc: Optional[int] = None
        self._is_answered: bool = False
        self._is_closed: bool = False

        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(
            target=self._run_background_loop,
            daemon=True,
            name=f"BridgeMediaSessionThread-{self.role}",
        )
        self._thread.start()

        self._ice_completed_event = asyncio.Event()
        self._dtls_connected_event = asyncio.Event()
        self._failed_event = asyncio.Event()
        self._failure_reason: Optional[str] = None

        self._run_sync(self._async_init_pc(), timeout=5.0)

    def _run_background_loop(self) -> None:
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_forever()
        finally:
            self._loop.close()

    def _run_sync(self, coro: Any, timeout: Optional[float] = None) -> Any:
        if self._is_closed or not self._loop.is_running():
            if asyncio.iscoroutine(coro):
                coro.close()
            raise MediaSessionStateError("Cannot execute operation: BridgeMediaSession is closed or loop stopped.")

        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        try:
            return future.result(timeout=timeout)
        except concurrent.futures.TimeoutError as exc:
            if not future.done():
                future.cancel()
                raise TimeoutError(f"Media session operation timed out after {timeout}s.") from exc
            raise
        except Exception:
            raise

    async def _async_init_pc(self) -> None:
        config = RTCConfiguration(
          iceServers=[
              RTCIceServer(urls=["stun:stun.l.google.com:19302"]),
              RTCIceServer(urls=["stun:stun1.l.google.com:19302"]),
          ]
        )
        self._pc = RTCPeerConnection(configuration=config)

        @self._pc.on("connectionstatechange")
        def on_connection_state_change() -> None:
            assert self._pc is not None
            state = self._pc.connectionState
            logger.info("[%s] PeerConnection state changed -> %s", self.role, state)
            if state == "connected":
                self._dtls_connected_event.set()
            elif state in ("failed", "closed"):
                self._failure_reason = f"PeerConnection entered '{state}' state."
                self._failed_event.set()

        @self._pc.on("iceconnectionstatechange")
        def on_ice_state_change() -> None:
            assert self._pc is not None
            ice_state = self._pc.iceConnectionState
            logger.info("[%s] ICE state changed -> %s", self.role, ice_state)
            if ice_state in ("completed", "connected"):
                self._ice_completed_event.set()
            elif ice_state == "failed":
                self._failure_reason = "ICE connectivity checks failed."
                self._failed_event.set()

        if self.role == "sendonly":
            if self._initial_outgoing_track is not None:
                self._sender = self._pc.addTrack(self._initial_outgoing_track)
                for t in self._pc.getTransceivers():
                    if t.sender == self._sender:
                        self._transceiver = t
                        t.direction = "sendonly"
                        break
            else:
                self._transceiver = self._pc.addTransceiver("audio", direction="sendonly")
                self._sender = self._transceiver.sender
        else:
            self._transceiver = self._pc.addTransceiver("audio", direction="recvonly")

    async def async_answer_offer(self, sdp_offer_str: str) -> str:
        """Sets remote offer, creates answer, sets local description, and returns local SDP string."""
        assert self._pc is not None
        try:
            offer_desc = RTCSessionDescription(sdp=sdp_offer_str, type="offer")
            await self._pc.setRemoteDescription(offer_desc)
            answer_desc = await self._pc.createAnswer()
            await self._pc.setLocalDescription(answer_desc)

            # Wait up to 3s for ICE gathering to complete
            try:
                async with asyncio.timeout(3.0):
                    while self._pc.iceGatheringState != "complete":
                        await asyncio.sleep(0.05)
            except (TimeoutError, asyncio.TimeoutError):
                logger.debug("[%s] ICE gathering completed with available candidates", self.role)

            # Signal end of remote candidates so aioice immediately binds the succeeded public candidate pair
            try:
                await self._pc.addIceCandidate(None)
            except Exception:
                pass

        except Exception as exc:
            raise MediaSessionNegotiationError(f"SDP offer/answer generation failed: {exc}") from exc

        local_sdp = self._pc.localDescription.sdp if self._pc.localDescription else ""
        return local_sdp

    async def async_wait_for_connection(self) -> None:
        """Waits for ICE connectivity and DTLS-SRTP handshake to establish after session-accept."""
        assert self._pc is not None
        timeout_s = self.ice_gather_timeout_s

        try:
            async with asyncio.timeout(timeout_s):
                while not self._ice_completed_event.is_set():
                    if self._failed_event.is_set():
                        raise ICEConnectionFailedError(f"ICE connectivity failed: {self._failure_reason}")
                    
                    # If ICE is checking and a pair has already succeeded, notify end of candidates
                    if self._pc.iceConnectionState == "checking":
                        try:
                            await self._pc.addIceCandidate(None)
                        except Exception:
                            pass
                            
                    await asyncio.sleep(0.1)
        except (TimeoutError, asyncio.TimeoutError) as exc:
            raise ICEConnectionTimeoutError(
                f"ICE connectivity checks timed out after {timeout_s}s (Current: {self._pc.iceConnectionState})"
            ) from exc

        try:
            async with asyncio.timeout(self.dtls_handshake_timeout_s):
                while not self._dtls_connected_event.is_set():
                    if self._failed_event.is_set():
                        raise MediaSessionNegotiationError(f"DTLS handshake failed: {self._failure_reason}")
                    await asyncio.sleep(0.05)
        except (TimeoutError, asyncio.TimeoutError) as exc:
            raise DTLSHandshakeTimeoutError(
                f"DTLS-SRTP handshake timed out after {self.dtls_handshake_timeout_s}s (Current: {self._pc.connectionState})"
            ) from exc

        if self.role == "sendonly":
            self._outgoing_ssrc = self._extract_outgoing_ssrc()

        self._is_answered = True
        logger.info("[%s] Media session established (ICE & DTLS Connected)", self.role)

    def wait_for_connection(self) -> None:
        """Synchronous wrapper for async_wait_for_connection."""
        return self._run_sync(
            self.async_wait_for_connection(),
            timeout=self.dtls_handshake_timeout_s + self.ice_gather_timeout_s + 10.0,
        )

    def _extract_outgoing_ssrc(self) -> int:
        if self._sender and hasattr(self._sender, "_ssrc") and self._sender._ssrc:
            return int(self._sender._ssrc)
        if self._pc and self._pc.localDescription:
            m = re.search(r"a=ssrc:(\d+)", self._pc.localDescription.sdp)
            if m:
                return int(m.group(1))
        return 10001

    @property
    def outgoing_ssrc(self) -> int:
        if self.role != "sendonly":
            raise MediaSessionStateError("outgoing_ssrc is only available for 'sendonly' role.")
        if not self._is_answered or self._outgoing_ssrc is None:
            raise MediaSessionStateError("outgoing_ssrc is not available before answer_offer() completes.")
        return self._outgoing_ssrc

    @property
    def outgoing_media_type(self) -> str:
        return "audio"

    def replace_outgoing_track(self, track: MediaStreamTrack) -> None:
        if self.role != "sendonly":
            raise MediaSessionStateError("replace_outgoing_track is only valid for 'sendonly' role.")
        if not self._is_answered:
            raise MediaSessionStateError("Cannot replace outgoing track: answer_offer() has not succeeded yet.")
        self._run_sync(self._async_replace_track(track), timeout=5.0)

    async def _async_replace_track(self, track: MediaStreamTrack) -> None:
        assert self._sender is not None
        if hasattr(self._sender, "replaceTrack"):
            res = self._sender.replaceTrack(track)
            if asyncio.iscoroutine(res):
                await res
        else:
            self._sender._track = track
        logger.info("[sendonly] Successfully hot-swapped outgoing audio track.")

    def get_incoming_receiver(self) -> RTCRtpReceiver:
        if self.role != "recvonly":
            raise MediaSessionStateError("get_incoming_receiver is only available for 'recvonly' role.")
        if self._transceiver is None:
            raise MediaSessionStateError("Receiver is uninitialized.")
        return self._transceiver.receiver

    async def async_add_remote_candidate(self, mid: str, cand: Any) -> None:
        """Adds a remote trickle ICE candidate to the underlying PeerConnection."""
        if self._pc is None:
            return
        try:
            rtc_candidate = RTCIceCandidate(
                component=int(cand.component),
                foundation=cand.foundation,
                ip=cand.ip,
                port=int(cand.port),
                priority=int(cand.priority),
                protocol=cand.protocol.lower(),
                type=cand.type,
                relatedAddress=cand.rel_addr if cand.rel_addr else None,
                relatedPort=int(cand.rel_port) if cand.rel_port else None,
                sdpMid=mid,
                sdpMLineIndex=0 if mid in ("audio", "0") else 1,
                tcpType=cand.tcptype if cand.tcptype else None,
            )
            await self._pc.addIceCandidate(rtc_candidate)
            logger.debug("[%s] Applied remote ICE candidate %s:%s (%s)", self.role, cand.ip, cand.port, cand.type)
        except Exception as exc:
            logger.warning("[%s] Notice applying remote candidate: %s", self.role, exc)

    def add_remote_candidate(self, mid: str, cand: Any) -> None:
        """Synchronous wrapper to apply a remote candidate."""
        if self._loop and self._loop.is_running():
            asyncio.run_coroutine_threadsafe(self.async_add_remote_candidate(mid, cand), self._loop)

    def close(self) -> None:
        if self._is_closed:
            return
        self._is_closed = True

        logger.info("[%s] Closing BridgeMediaSession...", self.role)
        try:
            if self._loop.is_running():
                self._run_sync(self._async_close(), timeout=3.0)
        except Exception as exc:
            logger.debug("Notice closing peer connection: %s", exc)
        finally:
            if self._loop.is_running():
                self._loop.call_soon_threadsafe(self._loop.stop)
            self._thread.join(timeout=2.0)
            logger.info("[%s] BridgeMediaSession closed cleanly.", self.role)

    async def _async_close(self) -> None:
        if self._pc is not None:
            try:
                await self._pc.close()
            except Exception:
                pass
            self._pc = None

    def __enter__(self) -> BridgeMediaSession:
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()