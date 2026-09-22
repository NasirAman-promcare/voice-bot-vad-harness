"""
tests/regression/test_accept_no_whitespace.py
Regression test for F1: Verifies that session-accept Jingle XML contains no whitespace-only
text nodes or tails that cause Jicofo parser drops.
"""

import xml.etree.ElementTree as ET
import pytest
from webrtc_bridge.jingle_sdp_translator import sdp_answer_to_jingle_accept


def test_session_accept_contains_no_whitespace_text_nodes():
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

    sdp_answer = (
        "v=0\r\n"
        "o=- 12345 2 IN IP4 0.0.0.0\r\n"
        "s=-\r\n"
        "t=0 0\r\n"
        "m=audio 9 UDP/TLS/RTP/SAVPF 111\r\n"
        "c=IN IP4 0.0.0.0\r\n"
        "a=mid:0\r\n"
        "a=rtcp-mux\r\n"
        "a=ice-ufrag:ans_u\r\n"
        "a=ice-pwd:ans_p\r\n"
        "a=fingerprint:sha-256 AA:BB:CC\r\n"
        "a=setup:active\r\n"
        "a=sendrecv\r\n"
        "a=rtpmap:111 opus/48000/2\r\n"
    )

    accept_xml = sdp_answer_to_jingle_accept(sdp_answer, offer_iq)

    # Parse and inspect each node
    root = ET.fromstring(accept_xml)

    # Check for whitespace-only text or tail in all XML elements
    for elem in root.iter():
        if elem.text is not None and elem.text != "":
            assert elem.text.strip() != "", f"Whitespace-only text in <{elem.tag}>"
        if elem.tail is not None and elem.tail != "":
            assert elem.tail.strip() != "", f"Whitespace-only tail in <{elem.tag}>"


if __name__ == "__main__":
    pytest.main([__file__])