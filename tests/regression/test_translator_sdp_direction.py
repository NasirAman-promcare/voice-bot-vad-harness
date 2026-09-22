"""
tests/regression/test_translator_sdp_direction.py
Regression test for F2, F3 & F5: Verifies that m-section direction before a=mid is tracked,
source SSRC is declared for sending media, and rtcp-mux is inside transport.
"""

import xml.etree.ElementTree as ET
import pytest
from webrtc_bridge.jingle_sdp_translator import sdp_answer_to_jingle_accept


def test_translator_handles_direction_before_mid_and_source_ssrc():
    # SDP Answer structure produced by aiortc where a=sendonly appears before a=mid (F2)
    sdp_answer = (
        "v=0\r\n"
        "o=- 99999 2 IN IP4 0.0.0.0\r\n"
        "s=-\r\n"
        "t=0 0\r\n"
        "m=audio 9 UDP/TLS/RTP/SAVPF 111\r\n"
        "c=IN IP4 0.0.0.0\r\n"
        "a=sendonly\r\n"
        "a=mid:0\r\n"
        "a=rtcp-mux\r\n"
        "a=ice-ufrag:test_ufrag\r\n"
        "a=ice-pwd:test_pwd\r\n"
        "a=fingerprint:sha-256 11:22:33:44:55\r\n"
        "a=setup:active\r\n"
        "a=rtpmap:111 opus/48000/2\r\n"
        "a=ssrc:777888 cname:speaker\r\n"
    )

    offer_iq = (
        '<iq from="focus@auth.meet.jitsi/focus" to="client@meet.jitsi/bot" id="off1" type="set">'
        '<jingle xmlns="urn:xmpp:jingle:1" action="session-initiate" sid="sid123">'
        '<content name="0" creator="initiator">'
        '<description xmlns="urn:xmpp:jingle:apps:rtp:1" media="audio">'
        '<payload-type id="111" name="opus" clockrate="48000"/>'
        '</description>'
        '<transport xmlns="urn:xmpp:jingle:transports:ice-udp:1" ufrag="u1" pwd="p1"/>'
        '</content>'
        '</jingle>'
        '</iq>'
    )

    accept_xml = sdp_answer_to_jingle_accept(sdp_answer, offer_iq)
    root = ET.fromstring(accept_xml)

    # 1. Verify direction is mapped to 'responder' (sendonly from answer perspective) (F2)
    content = root.find(".//{urn:xmpp:jingle:1}content")
    assert content is not None
    assert content.attrib.get("senders") == "responder"

    # 2. Verify source SSRC is declared in description (F3)
    source = root.find(".//{urn:xmpp:jingle:apps:rtp:ssma:0}source")
    assert source is not None, "Missing <source> tag in session-accept (F3)"
    assert source.attrib.get("ssrc") == "777888"

    # 3. Verify rtcp-mux is inside transport (F5)
    transport = root.find(".//{urn:xmpp:jingle:transports:ice-udp:1}transport")
    assert transport is not None
    rtcp_mux = transport.find("{urn:xmpp:jingle:transports:ice-udp:1}rtcp-mux")
    assert rtcp_mux is not None, "Missing <rtcp-mux/> inside <transport> (F5)"


if __name__ == "__main__":
    pytest.main([__file__])