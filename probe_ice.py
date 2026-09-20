#!/usr/bin/env python3
"""
probe_ice.py -- standalone single-bot ICE diagnostic for the Jitsi WebRTC bridge.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
import time
from pathlib import Path

logging.basicConfig(
    level=logging.DEBUG,
    stream=sys.stdout,
    format="%(asctime)s %(levelname)-5s [%(name)s] %(message)s",
)
for noisy in ("websockets", "websockets.client", "asyncio", "urllib3", "charset_normalizer"):
    logging.getLogger(noisy).setLevel(logging.WARNING)
logging.getLogger("aioice").setLevel(logging.DEBUG)
logging.getLogger("aiortc").setLevel(logging.DEBUG)

log = logging.getLogger("probe")

from webrtc_bridge.injector import load_bridge_config
from webrtc_bridge.jingle_sdp_translator import (
    jingle_offer_to_sdp,
    parse_transport_info_candidates,
    sdp_answer_to_jingle_accept,
)
from webrtc_bridge.jitsi_signaling import JitsiSignalingSession
from webrtc_bridge.media_session import BridgeMediaSession


def banner(title: str) -> None:
    print("\n" + "=" * 78, flush=True)
    print(f"  {title}", flush=True)
    print("=" * 78, flush=True)


def dump_ice_internals(media_session, label: str) -> None:
    """Reach into aiortc/aioice private state and print what ICE actually has."""
    pc = getattr(media_session, "_pc", None)
    if pc is None:
        print(f"[{label}] no RTCPeerConnection", flush=True)
        return

    print(
        f"[{label}] signalingState={pc.signalingState} "
        f"iceGatheringState={pc.iceGatheringState} "
        f"iceConnectionState={pc.iceConnectionState} "
        f"connectionState={pc.connectionState}",
        flush=True,
    )

    seen = set()
    for tcv in pc.getTransceivers():
        try:
            ice = tcv.receiver.transport.transport
        except Exception as exc:
            print(f"  mid={tcv.mid}: cannot reach ICE transport: {exc}", flush=True)
            continue

        if id(ice) in seen:
            continue
        seen.add(id(ice))

        conn = getattr(ice, "_connection", None)
        if conn is None:
            print(f"  mid={tcv.mid}: RTCIceTransport has no _connection", flush=True)
            continue

        print(f"  --- ICE transport (mid={tcv.mid}) state={ice.state} ---", flush=True)
        print(
            f"      role: ice_controlling={getattr(conn, 'ice_controlling', '?')}",
            flush=True,
        )
        print(
            f"      local  ufrag={getattr(conn, 'local_username', '?')!r} "
            f"pwd={getattr(conn, 'local_password', '?')!r}",
            flush=True,
        )
        print(
            f"      remote ufrag={getattr(conn, 'remote_username', '?')!r} "
            f"pwd={getattr(conn, 'remote_password', '?')!r}",
            flush=True,
        )

        locals_ = list(getattr(conn, "local_candidates", []) or [])
        remotes = list(getattr(conn, "remote_candidates", []) or [])
        print(f"      LOCAL candidates ({len(locals_)}):", flush=True)
        for c in locals_:
            print(f"        {c.type:6s} {c.host}:{c.port} prio={c.priority}", flush=True)
        print(f"      REMOTE candidates ({len(remotes)}):", flush=True)
        if not remotes:
            print("        *** NONE -- ICE has nothing to check against ***", flush=True)
        for c in remotes:
            print(f"        {c.type:6s} {c.host}:{c.port} prio={c.priority}", flush=True)

        eoc = getattr(conn, "_remote_candidates_end", None)
        print(f"      remote_candidates_end={eoc}", flush=True)

        pairs = list(getattr(conn, "_check_list", []) or [])
        print(f"      CHECK LIST ({len(pairs)} pairs):", flush=True)
        for p in pairs:
            try:
                lc, rc = p.local_candidate, p.remote_candidate
                print(
                    f"        {p.state} "
                    f"{lc.host}:{lc.port} -> {rc.host}:{rc.port} "
                    f"({lc.type}/{rc.type})",
                    flush=True,
                )
            except Exception:
                print(f"        {p!r}", flush=True)
        if not pairs:
            print("        *** EMPTY -- no pairs were ever formed ***", flush=True)


async def main(role: str, deadline_s: float) -> None:
    cfg = load_bridge_config("webrtc_bridge/bridge_config.yaml")
    room = "vad-benchmark-eval-room-01"
    bridge_url = "wss://vad-jitsi-nasir.duckdns.org/xmpp-websocket"
    display_name = (
        cfg.listener_display_name if role == "listener" else cfg.speaker_display_name
    ) + "-PROBE"

    media = BridgeMediaSession(
        role="recvonly" if role == "listener" else "sendonly",
        outgoing_track=None,
        ice_gather_timeout_s=cfg.ice_gather_timeout_s,
        dtls_handshake_timeout_s=cfg.dtls_handshake_timeout_s,
    )

    sig = JitsiSignalingSession(
        xmpp_client_domain=cfg.xmpp_client_domain,
        muc_room_domain_prefix=cfg.muc_room_domain_prefix,
        ssl_verify=cfg.ssl_verify,
        jingle_debug_log_path=Path("/tmp/probe_stanzas.log"),
    )

    trickle_count = {"stanzas": 0, "candidates": 0}

    def on_transport_info(raw_xml: str) -> None:
        trickle_count["stanzas"] += 1
        banner(f"TRICKLE transport-info #{trickle_count['stanzas']}")
        print(raw_xml, flush=True)
        cands = parse_transport_info_candidates(raw_xml)
        print(f"--> parsed {len(cands)} candidates from this stanza", flush=True)
        for mid, c in cands:
            trickle_count["candidates"] += 1
            print(f"    mid={mid!r} {c.type} {c.ip}:{c.port} prio={c.priority}", flush=True)
            media.add_remote_candidate(mid, c)

    sig.set_transport_info_callback(on_transport_info)

    banner("1. JOINING MUC")
    await sig.connect(
        bridge_url=bridge_url,
        room_id=room,
        display_name=display_name,
        timeout_s=30.0,
    )
    print("MUC join OK", flush=True)

    banner("2. RAW session-initiate FROM JICOFO")
    raw_offer = await sig.wait_for_offer(timeout_s=30.0)
    print(raw_offer, flush=True)

    banner("3. TRANSLATED SDP OFFER (fed to aiortc)")
    sdp_offer = jingle_offer_to_sdp(raw_offer)
    print(sdp_offer, flush=True)

    banner("4. aiortc SDP ANSWER")
    sdp_answer = await media.async_answer_offer(sdp_offer)
    print(sdp_answer, flush=True)

    dump_ice_internals(media, "after setRemoteDescription+createAnswer")

    banner("5. session-accept SENT TO JICOFO")
    accept_xml = sdp_answer_to_jingle_accept(
        sdp_answer_str=sdp_answer,
        session_initiate_iq=raw_offer,
    )
    print(accept_xml, flush=True)
    await sig.send_answer(accept_xml)
    print("session-accept transmitted", flush=True)

    banner("6. POLLING ICE STATE")
    started = time.monotonic()
    while time.monotonic() - started < deadline_s:
        await asyncio.sleep(2.0)
        elapsed = time.monotonic() - started
        dump_ice_internals(media, f"t+{elapsed:.0f}s")
        pc = media._pc
        if pc is not None and pc.iceConnectionState in ("connected", "completed", "failed"):
            print(f"\n*** ICE resolved: {pc.iceConnectionState} ***", flush=True)
            break

    banner("7. SUMMARY")
    print(
        f"trickle stanzas received : {trickle_count['stanzas']}\n"
        f"trickle candidates parsed: {trickle_count['candidates']}",
        flush=True,
    )
    dump_ice_internals(media, "final")
    print("\nStanza log written to /tmp/probe_stanzas.log", flush=True)

    try:
        await sig.disconnect()
    except Exception:
        pass
    media.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--role", choices=["listener", "speaker"], default="listener")
    ap.add_argument("--deadline", type=float, default=40.0)
    args = ap.parse_args()
    asyncio.run(main(args.role, args.deadline))
