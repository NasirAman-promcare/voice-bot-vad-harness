"""
tests/regression/test_iq_replies.py
Regression test for A15 & K3: Verifies that Jingle action stanzas (source-add, source-remove,
session-terminate) receive proper IQ acknowledgments and update session lifecycle state.
"""

import pytest
from webrtc_bridge.jitsi_signaling import JitsiSignalingSession


@pytest.mark.asyncio
async def test_jingle_action_stanzas_are_acknowledged():
    session = JitsiSignalingSession(xmpp_client_domain="meet.jitsi")
    session._is_connected = True
    sent_stanzas = []

    async def mock_send(stanza: str) -> None:
        sent_stanzas.append(stanza)

    session._send_raw = mock_send

    # 1. Test source-add acknowledgment
    source_add_iq = (
        '<iq from="focus@auth.meet.jitsi/focus" id="sa_001" type="set">'
        '<jingle xmlns="urn:xmpp:jingle:1" action="source-add" sid="sid123"/>'
        '</iq>'
    )
    await session._route_incoming_stanza(source_add_iq)
    assert any('type="result"' in s and 'id="sa_001"' in s for s in sent_stanzas)

    # 2. Test source-remove acknowledgment
    source_remove_iq = (
        '<iq from="focus@auth.meet.jitsi/focus" id="sr_002" type="set">'
        '<jingle xmlns="urn:xmpp:jingle:1" action="source-remove" sid="sid123"/>'
        '</iq>'
    )
    await session._route_incoming_stanza(source_remove_iq)
    assert any('type="result"' in s and 'id="sr_002"' in s for s in sent_stanzas)

    # 3. Test session-terminate acknowledgment and state update
    session_term_iq = (
        '<iq from="focus@auth.meet.jitsi/focus" id="st_003" type="set">'
        '<jingle xmlns="urn:xmpp:jingle:1" action="session-terminate" sid="sid123"/>'
        '</iq>'
    )
    await session._route_incoming_stanza(session_term_iq)
    assert any('type="result"' in s and 'id="st_003"' in s for s in sent_stanzas)
    assert session._is_connected is False, "Session must be marked disconnected after session-terminate"


if __name__ == "__main__":
    pytest.main([__file__])