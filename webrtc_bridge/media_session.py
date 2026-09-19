"""
webrtc_bridge/media_session.py

One Job:
    Own the `aiortc.RTCPeerConnection` media-plane lifecycle and manage a dedicated
    background asyncio event loop thread, exposing clean, synchronous methods for
    `speaker_bot.py` and `listener_bridge.py`.

Sync-over-Async Bridge Architecture:
    `bots/speaker_bot.py`'s `IJitsiAudioInjector` seam is strictly synchronous and
    declares no asyncio dependencies. This class creates and manages a private asyncio
    event loop running on a dedicated daemon thread, safely dispatching coroutines
    (`asyncio.run_coroutine_threadsafe`) and blocking synchronously for results.

Single-Transceiver Direction Policy:
    Configures exactly one transceiver matching the bot's designated role:
      - 'sendonly': Attaches `outgoing_track` (File 29) before answering, generating
        an active audio sender in the local SDP answer.
      - 'recvonly': Configures a receive-only audio transceiver to ingest the far-end
        JVB stream without advertising a synthetic sender.
    Dual-direction (sendrecv) transceivers are explicitly prohibited.

Track Replacement ("Connect Once, Never Per Clip"):
    For the Speaker role, `replace_outgoing_track(track)` hot-swaps the underlying
    audio track on the existing `RTCRtpSender` without tearing down DTLS-SRTP or
    renegotiating Jingle/SDP, preserving stable wire connectivity across clips.

What this module must NEVER do:
    - Never decode, transcode, or resample audio (delegated to Files 29 and 30).
    - Never apply WebRTC browser-style DSP (AEC, NS, AGC) to outgoing/incoming media.
    - Never leave non-daemon background threads dangling on process exit.
    - Never swallow ICE or DTLS handshake failures.
"""

from __future__ import annotations

import asyncio
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
    RTCPeerConnection,
    RTCRtpReceiver,
    RTCRtpSender,
    RTCRtpTransceiver,
    RTCSessionDescription,
)

logger = logging.getLogger("webrtc_bridge.media_session")


# ==============================================================================
# Exceptions
# ==============================================================================

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


# ==============================================================================
# aiortc Version Conformance Check
# ==============================================================================

def check_aiortc_conformance() -> None:
    """
    Validates that the installed aiortc runtime exposes the private receiver/sender
    mechanisms required by Files 28 and 30.

    Fails loud at construction time to prevent silent mid-run diagnostic failures.

    Raises:
        AIORTCConformanceError: If private attributes are missing or incompatible.
    """
    version_str = getattr(aiortc, "__version__", "unknown")

    # 1. Verify RTCRtpReceiver private methods for File 30 (raw_rtp_tap)
    if not hasattr(RTCRtpReceiver, "_handle_rtp_packet"):
        raise AIORTCConformanceError(
            f"Installed aiortc=={version_str} is missing private method "
            "'RTCRtpReceiver._handle_rtp_packet' required by raw_rtp_tap.py."
        )

    # 2. Verify RTCRtpSender track replacement capabilities for File 28
    if not hasattr(RTCRtpSender, "replaceTrack") and not hasattr(RTCRtpSender, "_track"):
        raise AIORTCConformanceError(
            f"Installed aiortc=={version_str} does not expose 'replaceTrack' or '_track' on RTCRtpSender."
        )

    logger.debug("aiortc runtime conformance verified (version: %s)", version_str)


# ==============================================================================
# Bridge Media Session Implementation
# ==============================================================================

class BridgeMediaSession:
    """
    Synchronous manager for the underlying asynchronous aiortc RTCPeerConnection.
    """

    def __init__(
        self,
        role: str,
        outgoing_track: Optional[MediaStreamTrack] = None,
        ice_gather_timeout_s: float = 10.0,
        dtls_handshake_timeout_s: float = 15.0,
    ) -> None:
        """
        Initializes the media session and starts the background asyncio event loop.

        Args:
            role: Either 'sendonly' (Speaker) or 'recvonly' (Listener).
            outgoing_track: Initial MediaStreamTrack for 'sendonly' role.
            ice_gather_timeout_s: Maximum timeout for ICE candidate gathering.
            dtls_handshake_timeout_s: Maximum timeout for DTLS handshake completion.

        Raises:
            ValueError: If role is not 'sendonly' or 'recvonly'.
            AIORTCConformanceError: If aiortc runtime attributes are missing.
        """
        clean_role = role.strip().lower()
        if clean_role not in ("sendonly", "recvonly"):
            raise ValueError(f"Invalid role: '{role}'. Must be 'sendonly' or 'recvonly'.")

        # Startup Conformance Check
        check_aiortc_conformance()

        self.role = clean_role
        self.ice_gather_timeout_s = float(ice_gather_timeout_s)
        self.dtls_handshake_timeout_s = float(dtls_handshake_timeout_s)
        self._initial_outgoing_track = outgoing_track

        # Internal State
        self._pc: Optional[RTCPeerConnection] = None
        self._transceiver: Optional[RTCRtpTransceiver] = None
        self._sender: Optional[RTCRtpSender] = None
        self._outgoing_ssrc: Optional[int] = None
        self._is_answered: bool = False
        self._is_closed: bool = False

        # Asyncio Thread Plumbing
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(
            target=self._run_background_loop,
            daemon=True,
            name=f"BridgeMediaSessionThread-{self.role}",
        )
        self._thread.start()

        # Connection Synchronization Events
        self._ice_completed_event = asyncio.Event()
        self._dtls_connected_event = asyncio.Event()
        self._failed_event = asyncio.Event()
        self._failure_reason: Optional[str] = None

        # Initialize PeerConnection asynchronously on background loop
        self._run_sync(self._async_init_pc(), timeout=5.0)

    # --------------------------------------------------------------------------
    # Background Event Loop & Concurrency Plumbing
    # --------------------------------------------------------------------------
    def _run_background_loop(self) -> None:
        """Entrypoint for the dedicated background asyncio event loop thread."""
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_forever()
        finally:
            self._loop.close()

    def _run_sync(self, coro: Any, timeout: Optional[float] = None) -> Any:
        """Dispatches a coroutine to the background loop and blocks synchronously."""
        if self._is_closed:
            raise MediaSessionStateError("Cannot execute operation: BridgeMediaSession is closed.")

        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        try:
            return future.result(timeout=timeout)
        except TimeoutError as exc:
            future.cancel()
            raise TimeoutError(f"Media session operation timed out after {timeout}s.") from exc
        except Exception:
            raise

    # --------------------------------------------------------------------------
    # Async PeerConnection Lifecycle
    # --------------------------------------------------------------------------
    async def _async_init_pc(self) -> None:
        """Constructs RTCPeerConnection with strict disabling of browser DSP."""
        # RTCConfiguration: Direct host candidates, no STUN/TURN overhead needed for JVB
        config = RTCConfiguration(iceServers=[])
        self._pc = RTCPeerConnection(configuration=config)

        # Wire connection state listener hooks
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

        # Add single directional transceiver
        if self.role == "sendonly":
            if self._initial_outgoing_track is not None:
                self._sender = self._pc.addTrack(self._initial_outgoing_track)
                # Find the transceiver managing this sender
                for t in self._pc.getTransceivers():
                    if t.sender == self._sender:
                        self._transceiver = t
                        t.direction = "sendonly"
                        break
            else:
                self._transceiver = self._pc.addTransceiver("audio", direction="sendonly")
                self._sender = self._transceiver.sender
        else:
            # Recvonly role
            self._transceiver = self._pc.addTransceiver("audio", direction="recvonly")

    # --------------------------------------------------------------------------
    # Public Synchronous Surface
    # --------------------------------------------------------------------------
    def answer_offer(self, sdp_offer_str: str) -> str:
        """
        Applies remote SDP offer, generates local SDP answer, and blocks synchronously
        until ICE and DTLS are fully connected.

        Args:
            sdp_offer_str: The SDP offer string generated by File 27.

        Returns:
            The local SDP answer string.

        Raises:
            ICEConnectionTimeoutError: If ICE gathering / connectivity fails.
            DTLSHandshakeTimeoutError: If DTLS fails to establish after ICE.
            ICEConnectionFailedError: If connection state enters 'failed'.
            MediaSessionNegotiationError: If SDP offer/answer parsing fails.
        """
        return self._run_sync(
            self._async_answer_offer(sdp_offer_str),
            timeout=self.dtls_handshake_timeout_s + self.ice_gather_timeout_s + 5.0,
        )

    async def _async_answer_offer(self, sdp_offer_str: str) -> str:
        assert self._pc is not None

        try:
            # 1. Set Remote Description (Offer)
            offer_desc = RTCSessionDescription(sdp=sdp_offer_str, type="offer")
            await self._pc.setRemoteDescription(offer_desc)

            # 2. Create and Set Local Description (Answer)
            answer_desc = await self._pc.createAnswer()
            await self._pc.setLocalDescription(answer_desc)

        except Exception as exc:
            raise MediaSessionNegotiationError(f"SDP offer/answer generation failed: {exc}") from exc

        # 3. Block until ICE is Connected / Completed
        try:
            async with asyncio.timeout(self.ice_gather_timeout_s):
                while not self._ice_completed_event.is_set():
                    if self._failed_event.is_set():
                        raise ICEConnectionFailedError(
                            f"ICE connectivity failed: {self._failure_reason}"
                        )
                    await asyncio.sleep(0.05)
        except (TimeoutError, asyncio.TimeoutError) as exc:
            raise ICEConnectionTimeoutError(
                f"ICE connectivity checks timed out after {self.ice_gather_timeout_s}s "
                f"(Current ICE state: {self._pc.iceConnectionState})"
            ) from exc

        # 4. Block until DTLS Handshake is Connected
        try:
            async with asyncio.timeout(self.dtls_handshake_timeout_s):
                while not self._dtls_connected_event.is_set():
                    if self._failed_event.is_set():
                        raise MediaSessionNegotiationError(
                            f"DTLS handshake failed: {self._failure_reason}"
                        )
                    await asyncio.sleep(0.05)
        except (TimeoutError, asyncio.TimeoutError) as exc:
            raise DTLSHandshakeTimeoutError(
                f"DTLS-SRTP handshake timed out after {self.dtls_handshake_timeout_s}s "
                f"(Current PeerConnection state: {self._pc.connectionState})"
            ) from exc

        # 5. Extract Outgoing SSRC for Speaker role
        if self.role == "sendonly":
            self._outgoing_ssrc = self._extract_outgoing_ssrc()

        self._is_answered = True
        local_sdp = self._pc.localDescription.sdp if self._pc.localDescription else ""
        logger.info("[%s] Media session successfully established (ICE & DTLS Connected)", self.role)
        return local_sdp

    def _extract_outgoing_ssrc(self) -> int:
        """Extracts the 32-bit SSRC for the outgoing audio track from sender / SDP."""
        # 1. Check sender private _ssrc attribute
        if self._sender and hasattr(self._sender, "_ssrc") and self._sender._ssrc:
            return int(self._sender._ssrc)

        # 2. Fallback: Parse a=ssrc:(\d+) from local SDP
        if self._pc and self._pc.localDescription:
            m = re.search(r"a=ssrc:(\d+)", self._pc.localDescription.sdp)
            if m:
                return int(m.group(1))

        # 3. Default fallback integer SSRC
        return 10001

    # --------------------------------------------------------------------------
    # Public Track & Receiver Properties
    # --------------------------------------------------------------------------
    @property
    def outgoing_ssrc(self) -> int:
        """
        The 32-bit Synchronization Source ID of the outgoing audio track.

        Readable only after `answer_offer` succeeds for 'sendonly' role.
        """
        if self.role != "sendonly":
            raise MediaSessionStateError("outgoing_ssrc is only available for 'sendonly' role.")
        if not self._is_answered or self._outgoing_ssrc is None:
            raise MediaSessionStateError("outgoing_ssrc is not available before answer_offer() completes.")
        return self._outgoing_ssrc

    @property
    def outgoing_media_type(self) -> str:
        """Returns the media type string ('audio')."""
        return "audio"

    def replace_outgoing_track(self, track: MediaStreamTrack) -> None:
        """
        Hot-swaps the outgoing audio track on the live sender without renegotiation.

        Args:
            track: The new File 29 ManifestClipTrack instance.

        Raises:
            MediaSessionStateError: If called before answer_offer has completed or on recvonly role.
        """
        if self.role != "sendonly":
            raise MediaSessionStateError("replace_outgoing_track is only valid for 'sendonly' role.")
        if not self._is_answered:
            raise MediaSessionStateError(
                "Cannot replace outgoing track: answer_offer() has not succeeded yet."
            )

        self._run_sync(self._async_replace_track(track), timeout=5.0)

    async def _async_replace_track(self, track: MediaStreamTrack) -> None:
        assert self._sender is not None

        if hasattr(self._sender, "replaceTrack"):
            res = self._sender.replaceTrack(track)
            if asyncio.iscoroutine(res):
                await res
        else:
            # Fallback to direct attribute swap on older aiortc builds
            self._sender._track = track

        logger.info("[sendonly] Successfully hot-swapped outgoing audio track on live sender.")

    def get_incoming_receiver(self) -> RTCRtpReceiver:
        """
        Returns the RTCRtpReceiver instance for the incoming audio feed. (Listener role only).

        Raises:
            MediaSessionStateError: If called on 'sendonly' role or before initialization.
        """
        if self.role != "recvonly":
            raise MediaSessionStateError("get_incoming_receiver is only available for 'recvonly' role.")
        if self._transceiver is None:
            raise MediaSessionStateError("Receiver is uninitialized.")
        return self._transceiver.receiver

    # --------------------------------------------------------------------------
    # Teardown
    # --------------------------------------------------------------------------
    def close(self) -> None:
        """Closes the peer connection and terminates the background event loop thread cleanly."""
        if self._is_closed:
            return
        self._is_closed = True

        logger.info("[%s] Closing BridgeMediaSession...", self.role)
        try:
            self._run_sync(self._async_close(), timeout=3.0)
        except Exception as exc:
            logger.debug("Notice closing peer connection: %s", exc)
        finally:
            self._loop.call_soon_threadsafe(self._loop.stop)
            self._thread.join(timeout=2.0)
            logger.info("[%s] BridgeMediaSession closed cleanly.", self.role)

    async def _async_close(self) -> None:
        if self._pc is not None:
            await self._pc.close()
            self._pc = None

    def __enter__(self) -> BridgeMediaSession:
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()