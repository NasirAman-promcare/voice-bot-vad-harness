# Tier 2 Network Description

- Date: 2026-10-03
- Jitsi Meet Server: Oracle Cloud VM.Standard.A1.Flex (4 OCPUs, 24 GB RAM, Ubuntu 24.04 LTS), ashburn region (`https://vad-jitsi-nasir.duckdns.org/`).
- Jitsi Version: Docker Jitsi Meet (`ghcr.io/jitsi/web:unstable`, `ghcr.io/jitsi/jvb:unstable`).
- Speaker and Listener Bots: Executed on Google Colab (x86_64 host).
- Network Path: WebRTC stream over public internet via WebSocket bridge (`wss://vad-jitsi-nasir.duckdns.org/xmpp-websocket`) to Oracle Jitsi Videobridge.
- TURN Relay: No TURN relay (direct host/STUN ICE connection over port 10000/udp).
- Start Time: 2026-10-03 07:59:07 UTC
- End Time: 2026-10-03 11:34:53 UTC
- Impairment: None on network route (packet loss tested on benchmark packet-loss corpus category).
- Transport Protocol: Opus 16 kHz, 20 ms packet frames.
- Run Execution: Clean run with today's harness across all 6 operating points (ten_vad, firered_vad, webrtc_vad_mode0..3) over all 229 clips.
