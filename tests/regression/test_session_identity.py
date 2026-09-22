"""
tests/regression/test_session_identity.py
Regression test for A16 & K1: Verifies that session-initiate is accepted ONLY from Jicofo/focus
and that incoming peer P2P session-initiate stanzas cannot overwrite the session identity.
"""

import pytest
from webrtc_bridge.jitsi_signaling import JitsiSignalingSession


@pytest.mark.asyncio
async def test_session_identity_protected_from_p2p_overwrites():
    session = JitsiSignalingSession(xmpp_client_domain="meet.jitsi")
    sent_stanzas = []

    async def mock_send(stanza: str) -> None:
        sent_stanzas.append(stanza)

    session._send_raw = mock_send

    # 1. Incoming legitimate session-initiate from Jicofo focus
    focus_initiate = (
        '<iq from="focus@auth.meet.jitsi/focus" id="iq_focus_1" type="set">'
        '<jingle xmlns="urn:xmpp:jingle:1" action="session-initiate" sid="session_focus_123">'
        '<content name="0"><description xmlns="urn:xmpp:jingle:apps:rtp:1" media="audio"/></content>'
        '</jingle>'
        '</iq>'
    )
    await session._route_incoming_stanza(focus_initiate)

    assert session.jicofo_jid == "focus@auth.meet.jitsi/focus"
    assert session.jingle_sid == "session_focus_123"

    # 2. Incoming rogue P2P session-initiate from a regular browser peer in the room
    p2p_initiate = (
        '<iq from="testroom@muc.meet.jitsi/browser_user_789" id="iq_peer_2" type="set">'
        '<jingle xmlns="urn:xmpp:jingle:1" action="session-initiate" sid="session_p2p_999">'
        '<content name="0"><description xmlns="urn:xmpp:jingle:apps:rtp:1" media="audio"/></content>'
        '</jingle>'
        '</iq>'
    )
    await session._route_incoming_stanza(p2p_initiate)

    # Verify session identity remains locked to Jicofo
    assert session.jicofo_jid == "focus@auth.meet.jitsi/focus"
    assert session.jingle_sid == "session_focus_123"

    # Verify error IQ was returned to the peer
    assert any('type="error"' in s and 'id="iq_peer_2"' in s for s in sent_stanzas)


if __name__ == "__main__":
    pytest.main([__file__])