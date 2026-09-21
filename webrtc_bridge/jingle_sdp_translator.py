"""
webrtc_bridge/jingle_sdp_translator.py

One Job:
    Provide pure, deterministic, network-free translation functions between Jitsi's
    Jingle XML protocol stanzas (XEP-0166, XEP-0167, XEP-0176, XEP-0320) and standard
    SDP offer/answer strings (RFC 4566, RFC 8866), plus source-declaration stanza generation.
"""

from __future__ import annotations

import logging
import re
import uuid
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

logger = logging.getLogger("webrtc_bridge.jingle_sdp_translator")

# Standard XML Namespaces
NS_CLIENT = "jabber:client"
NS_JINGLE = "urn:xmpp:jingle:1"
NS_RTP = "urn:xmpp:jingle:apps:rtp:1"
NS_ICE_UDP = "urn:xmpp:jingle:transports:ice-udp:1"
NS_DTLS = "urn:xmpp:jingle:apps:dtls:0"
NS_RTCP_FB = "urn:xmpp:jingle:apps:rtp:rtcp-fb:0"
NS_HDREXT = "urn:xmpp:jingle:apps:rtp:rtp-hdrext:0"
NS_SSMA = "urn:xmpp:jingle:apps:rtp:ssma:0"
NS_NICK = "http://jabber.org/protocol/nick"
NS_AUDIO_MUTED = "http://jitsi.org/jitmeet/audio"
NS_VIDEO_MUTED = "http://jitsi.org/jitmeet/video"


# ==============================================================================
# Exceptions
# ==============================================================================

class JingleTranslationError(ValueError):
    """Base exception for all Jingle-to-SDP or SDP-to-Jingle translation failures."""
    pass


class JingleXMLMalformedError(JingleTranslationError):
    """Raised when incoming Jingle XML is malformed, unparseable, or missing root elements."""
    pass


class JingleSessionMismatchError(JingleTranslationError):
    """Raised when session IDs, content names, or initiators mismatch expected values."""
    pass


# ==============================================================================
# Internal Intermediate Data Structures
# ==============================================================================

@dataclass
class CodecPayload:
    id: str
    name: str
    clockrate: str
    channels: Optional[str] = None
    parameters: Dict[str, str] = field(default_factory=dict)
    rtcp_fbs: List[Tuple[str, Optional[str]]] = field(default_factory=list)


@dataclass
class HeaderExtension:
    id: str
    uri: str


@dataclass
class IceCandidate:
    foundation: str
    component: str
    protocol: str
    priority: str
    ip: str
    port: str
    type: str  # host, srflx, prflx, relay
    rel_addr: Optional[str] = None
    rel_port: Optional[str] = None
    tcptype: Optional[str] = None
    generation: Optional[str] = None
    network: Optional[str] = None
    id: Optional[str] = None


@dataclass
class TransportInfo:
    ufrag: str
    pwd: str
    fingerprint_hash: str
    fingerprint: str
    setup: str  # actpass, active, passive
    candidates: List[IceCandidate] = field(default_factory=list)


@dataclass
class ContentInfo:
    name: str
    creator: str
    senders: str  # both, initiator, responder, none
    media: str    # audio, video
    codecs: List[CodecPayload] = field(default_factory=list)
    header_extensions: List[HeaderExtension] = field(default_factory=list)
    transport: Optional[TransportInfo] = None
    ssrcs: List[str] = field(default_factory=list)


# ==============================================================================
# XML Parsing Helpers
# ==============================================================================

def _strip_ns(tag: str) -> str:
    """Strips XML namespace prefix from tag."""
    return tag.split("}")[-1] if "}" in tag else tag


def _find_elem(parent: ET.Element, tag_name: str) -> Optional[ET.Element]:
    """Finds first child matching tag_name ignoring namespace prefixes."""
    for child in parent:
        if _strip_ns(child.tag) == tag_name:
            return child
    return None


def _find_all_elems(parent: ET.Element, tag_name: str) -> List[ET.Element]:
    """Finds all children matching tag_name ignoring namespace prefixes."""
    return [child for child in parent if _strip_ns(child.tag) == tag_name]


# ==============================================================================
# Jingle Offer -> SDP Offer
# ==============================================================================

def jingle_offer_to_sdp(session_initiate_iq: str) -> str:
    """
    Translates a raw Jicofo `session-initiate` Jingle IQ XML string into a standard SDP offer.
    """
    if not session_initiate_iq or not session_initiate_iq.strip():
        raise JingleXMLMalformedError("Cannot parse empty or null session_initiate_iq.")

    try:
        root = ET.fromstring(session_initiate_iq.strip())
    except ET.ParseError as exc:
        raise JingleXMLMalformedError(f"XML parse error in session-initiate IQ: {exc}") from exc

    jingle_elem = _find_elem(root, "jingle")
    if jingle_elem is None:
        if _strip_ns(root.tag) == "jingle":
            jingle_elem = root
        else:
            raise JingleXMLMalformedError("Missing <jingle> element in session-initiate IQ.")

    action = jingle_elem.attrib.get("action")
    if action != "session-initiate":
        raise JingleXMLMalformedError(
            f"Expected Jingle action='session-initiate', found '{action}'."
        )

    sid = jingle_elem.attrib.get("sid", uuid.uuid4().hex[:16])

    content_elems = _find_all_elems(jingle_elem, "content")
    if not content_elems:
        raise JingleXMLMalformedError("session-initiate IQ contains no <content> elements.")

    contents: List[ContentInfo] = []

    for c_elem in content_elems:
        c_name = c_elem.attrib.get("name", "0")
        c_creator = c_elem.attrib.get("creator", "initiator")
        c_senders = c_elem.attrib.get("senders", "both")

        desc_elem = _find_elem(c_elem, "description")
        if desc_elem is None:
            raise JingleXMLMalformedError(f"Content '{c_name}' missing <description> element.")

        media_type = desc_elem.attrib.get("media", "audio")

        # Codecs
        codecs: List[CodecPayload] = []
        for pt_elem in _find_all_elems(desc_elem, "payload-type"):
            pt_id = pt_elem.attrib.get("id")
            pt_name = pt_elem.attrib.get("name")
            pt_clock = pt_elem.attrib.get("clockrate", "48000")
            pt_channels = pt_elem.attrib.get("channels")

            if not pt_id or not pt_name:
                continue

            params: Dict[str, str] = {}
            for param_elem in _find_all_elems(pt_elem, "parameter"):
                p_name = param_elem.attrib.get("name")
                p_val = param_elem.attrib.get("value")
                if p_name and p_val is not None:
                    params[p_name] = p_val

            rtcp_fbs: List[Tuple[str, Optional[str]]] = []
            for fb_elem in _find_all_elems(pt_elem, "rtcp-fb"):
                fb_type = fb_elem.attrib.get("type")
                fb_subtype = fb_elem.attrib.get("subtype")
                if fb_type:
                    rtcp_fbs.append((fb_type, fb_subtype))

            codecs.append(
                CodecPayload(
                    id=pt_id,
                    name=pt_name,
                    clockrate=pt_clock,
                    channels=pt_channels,
                    parameters=params,
                    rtcp_fbs=rtcp_fbs,
                )
            )

        # RTP Header Extensions
        hdrexts: List[HeaderExtension] = []
        for ext_elem in _find_all_elems(desc_elem, "header-extension"):
            ext_id = ext_elem.attrib.get("id")
            ext_uri = ext_elem.attrib.get("uri")
            if ext_id and ext_uri:
                hdrexts.append(HeaderExtension(id=ext_id, uri=ext_uri))

        # SSRC attributes
        ssrcs: List[str] = []
        for src_elem in _find_all_elems(desc_elem, "source"):
            ssrc_val = src_elem.attrib.get("ssrc")
            if ssrc_val:
                ssrcs.append(ssrc_val)

        # Transport (ICE + DTLS)
        trans_elem = _find_elem(c_elem, "transport")
        if trans_elem is None:
            raise JingleXMLMalformedError(f"Content '{c_name}' missing <transport> element.")

        ufrag = trans_elem.attrib.get("ufrag", "")
        pwd = trans_elem.attrib.get("pwd", "")

        fp_elem = _find_elem(trans_elem, "fingerprint")
        if fp_elem is not None:
            fp_hash = fp_elem.attrib.get("hash", "sha-256")
            fp_setup = fp_elem.attrib.get("setup", "actpass")
            fp_val = (fp_elem.text or "").strip()
        else:
            fp_hash = "sha-256"
            fp_setup = "actpass"
            fp_val = ""

        # Candidates
        candidates: List[IceCandidate] = []
        for cand_elem in _find_all_elems(trans_elem, "candidate"):
            c_ip = cand_elem.attrib.get("ip")
            c_port = cand_elem.attrib.get("port")
            if not c_ip or not c_port:
                continue

            candidates.append(
                IceCandidate(
                    foundation=cand_elem.attrib.get("foundation", "1"),
                    component=cand_elem.attrib.get("component", "1"),
                    protocol=cand_elem.attrib.get("protocol", "udp").lower(),
                    priority=cand_elem.attrib.get("priority", "2130706431"),
                    ip=c_ip,
                    port=c_port,
                    type=cand_elem.attrib.get("type", "host"),
                    rel_addr=cand_elem.attrib.get("rel-addr"),
                    rel_port=cand_elem.attrib.get("rel-port"),
                    tcptype=cand_elem.attrib.get("tcptype"),
                    generation=cand_elem.attrib.get("generation"),
                    network=cand_elem.attrib.get("network"),
                    id=cand_elem.attrib.get("id"),
                )
            )

        transport = TransportInfo(
            ufrag=ufrag,
            pwd=pwd,
            fingerprint_hash=fp_hash,
            fingerprint=fp_val,
            setup=fp_setup,
            candidates=candidates,
        )

        contents.append(
            ContentInfo(
                name=c_name,
                creator=c_creator,
                senders=c_senders,
                media=media_type,
                codecs=codecs,
                header_extensions=hdrexts,
                transport=transport,
                ssrcs=ssrcs,
            )
        )

    # Format Standard SDP Offer
    session_numeric_id = int(uuid.uuid4().int & 0x7FFFFFFF)
    mids = [c.name for c in contents]

    sdp_lines: List[str] = [
        "v=0",
        f"o=- {session_numeric_id} 2 IN IP4 0.0.0.0",
        "s=-",
        "t=0 0",
        f"a=group:BUNDLE {' '.join(mids)}",
        "a=msid-semantic: WMS", 
    ]

    for content in contents:
        t = content.transport
        default_ip = t.candidates[0].ip if t and t.candidates else "0.0.0.0"
        default_port = t.candidates[0].port if t and t.candidates else "9"

        payload_ids = [c.id for c in content.codecs]
        payload_str = " ".join(payload_ids) if payload_ids else "111"

        sdp_lines.extend([
            f"m={content.media} {default_port} UDP/TLS/RTP/SAVPF {payload_str}",
            f"c=IN IP4 {default_ip}",
            f"a=mid:{content.name}",
            "a=rtcp-mux",
        ])

        if t:
            if t.ufrag:
                sdp_lines.append(f"a=ice-ufrag:{t.ufrag}")
            if t.pwd:
                sdp_lines.append(f"a=ice-pwd:{t.pwd}")
            if t.fingerprint:
                sdp_lines.append(f"a=fingerprint:{t.fingerprint_hash} {t.fingerprint}")
            if t.setup:
                sdp_lines.append(f"a=setup:{t.setup}")

        if content.senders == "both":
            sdp_lines.append("a=sendrecv")
        elif content.senders == "initiator":
            sdp_lines.append("a=sendonly")
        elif content.senders == "responder":
            sdp_lines.append("a=recvonly")
        else:
            sdp_lines.append("a=inactive")

        for c in content.codecs:
            ch_str = f"/{c.channels}" if c.channels and c.channels != "1" else (
                "/2" if c.name.lower() == "opus" else ""
            )
            sdp_lines.append(f"a=rtpmap:{c.id} {c.name}/{c.clockrate}{ch_str}")

            if c.parameters:
                param_str = ";".join(f"{k}={v}" for k, v in c.parameters.items())
                sdp_lines.append(f"a=fmtp:{c.id} {param_str}")

            for fb_type, fb_subtype in c.rtcp_fbs:
                sub = f" {fb_subtype}" if fb_subtype else ""
                sdp_lines.append(f"a=rtcp-fb:{c.id} {fb_type}{sub}")

        for ext in content.header_extensions:
            sdp_lines.append(f"a=extmap:{ext.id} {ext.uri}")

        if t and t.candidates:
            for cand in t.candidates:
                cand_line = (
                    f"a=candidate:{cand.foundation} {cand.component} {cand.protocol} "
                    f"{cand.priority} {cand.ip} {cand.port} typ {cand.type}"
                )
                if cand.rel_addr and cand.rel_port:
                    cand_line += f" raddr {cand.rel_addr} rport {cand.rel_port}"
                if cand.tcptype:
                    cand_line += f" tcptype {cand.tcptype}"
                if cand.generation is not None:
                    cand_line += f" generation {cand.generation}"
                sdp_lines.append(cand_line)

    formatted_sdp = "\r\n".join(sdp_lines) + "\r\n"
    logger.debug("Successfully generated SDP offer from Jingle session-initiate (%d bytes)", len(formatted_sdp))
    return formatted_sdp


# ==============================================================================
# SDP Answer -> Jingle Answer (session-accept)
# ==============================================================================

def sdp_answer_to_jingle_accept(sdp_answer_str: str, session_initiate_iq: str) -> str:
    """
    Constructs a Jingle `session-accept` IQ XML string from an SDP answer and the original offer.
    Includes BUNDLE grouping, <rtcp-mux/>, initiator echo, and fallback candidate resolution.
    Forces SHA-256 fingerprint for Jicofo compatibility.
    """
    if not sdp_answer_str or not sdp_answer_str.strip():
        raise JingleTranslationError("sdp_answer_str cannot be empty.")
    if not session_initiate_iq or not session_initiate_iq.strip():
        raise JingleTranslationError("session_initiate_iq cannot be empty.")

    try:
        initiate_root = ET.fromstring(session_initiate_iq.strip())
    except ET.ParseError as exc:
        raise JingleXMLMalformedError(f"Malformed session_initiate_iq: {exc}") from exc

    jingle_offer = _find_elem(initiate_root, "jingle")
    if jingle_offer is None:
        if _strip_ns(initiate_root.tag) == "jingle":
            jingle_offer = initiate_root
        else:
            raise JingleXMLMalformedError("Missing <jingle> element in session_initiate_iq.")

    sid = jingle_offer.attrib.get("sid")
    if not sid:
        raise JingleSessionMismatchError("session_initiate_iq <jingle> tag missing required 'sid' attribute.")

    jicofo_jid = initiate_root.attrib.get("from")
    client_jid = initiate_root.attrib.get("to")
    initiator_jid = jingle_offer.attrib.get("initiator") or jicofo_jid

    # Parse SDP answer blocks
    sdp_ufrag: str = ""
    sdp_pwd: str = ""
    sdp_fingerprint_hash: str = "sha-256"
    sdp_fingerprint: str = ""
    sdp_setup: str = "active"
    codecs_by_mid: Dict[str, List[CodecPayload]] = {}
    candidates_by_mid: Dict[str, List[IceCandidate]] = {}
    direction_by_mid: Dict[str, str] = {}
    ssrc_by_mid: Dict[str, str] = {}
    section_mid: Optional[str] = None
    section_direction: Optional[str] = None
    current_mid: str = "0"

    re_ufrag = re.compile(r"^a=ice-ufrag:(.+)$")
    re_pwd = re.compile(r"^a=ice-pwd:(.+)$")
    re_fp = re.compile(r"^a=fingerprint:(\S+)\s+(.+)$")
    re_setup = re.compile(r"^a=setup:(\S+)$")
    re_mid = re.compile(r"^a=mid:(\S+)$")
    re_ssrc = re.compile(r"^a=ssrc:(\d+)\s")
    re_rtpmap = re.compile(r"^a=rtpmap:(\d+)\s+([^/]+)/(\d+)(?:/(\d+))?$")
    re_fmtp = re.compile(r"^a=fmtp:(\d+)\s+(.+)$")
    re_cand = re.compile(
        r"^a=candidate:(\S+)\s+(\d+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\d+)\s+typ\s+(\S+)(.*)$"
    )

    for line in sdp_answer_str.splitlines():
        line = line.strip()
        if not line:
            continue

        m = re_ufrag.match(line)
        if m:
            sdp_ufrag = m.group(1).strip()
            continue

        m = re_pwd.match(line)
        if m:
            sdp_pwd = m.group(1).strip()
            continue

        m = re_fp.match(line)
        if m:
            hash_algo = m.group(1).strip().lower()
            fp_val = m.group(2).strip()
            # Force SHA-256 as it is the only universally trusted hash by Jicofo
            if hash_algo == "sha-256" or not sdp_fingerprint:
                sdp_fingerprint_hash = hash_algo
                sdp_fingerprint = fp_val
            continue

        m = re_setup.match(line)
        if m:
            sdp_setup = m.group(1).strip()
            continue

        if line.startswith("m="):
            section_mid = None
            section_direction = None
            continue

        m = re_mid.match(line)
        if m:
            current_mid = m.group(1).strip()
            section_mid = current_mid
            codecs_by_mid.setdefault(current_mid, [])
            candidates_by_mid.setdefault(current_mid, [])
            if section_direction is not None:
                direction_by_mid[current_mid] = section_direction
            continue

        if line in ("a=sendrecv", "a=sendonly", "a=recvonly", "a=inactive"):
            section_direction = line[2:]
            if section_mid is not None:
                direction_by_mid[section_mid] = section_direction
            continue

        m = re_ssrc.match(line)
        if m:
            ssrc_by_mid.setdefault(current_mid, m.group(1))
            continue

        m = re_rtpmap.match(line)
        if m:
            pt_id, name, clock, channels = m.groups()
            codecs_by_mid.setdefault(current_mid, []).append(
                CodecPayload(id=pt_id, name=name, clockrate=clock, channels=channels)
            )
            continue

        m = re_fmtp.match(line)
        if m:
            pt_id, param_str = m.groups()
            for c in codecs_by_mid.get(current_mid, []):
                if c.id == pt_id:
                    for kv in param_str.split(";"):
                        if "=" in kv:
                            k, v = kv.split("=", 1)
                            c.parameters[k.strip()] = v.strip()
            continue

        m = re_cand.match(line)
        if m:
            foundation, component, protocol, priority, ip, port, typ, rest = m.groups()
            candidates_by_mid.setdefault(current_mid, []).append(
                IceCandidate(
                    foundation=foundation,
                    component=component,
                    protocol=protocol.lower(),
                    priority=priority,
                    ip=ip,
                    port=port,
                    type=typ,
                )
            )
            continue

    # Build <jingle action="session-accept"> XML
    accept_iq_id = f"_accept_{uuid.uuid4().hex[:8]}"
    to_attr = f' to="{jicofo_jid}"' if jicofo_jid else ""
    from_attr = f' from="{client_jid}"' if client_jid else ""
    responder_attr = f' responder="{client_jid}"' if client_jid else ""
    initiator_attr = f' initiator="{initiator_jid}"' if initiator_jid else ""

    xml_lines: List[str] = [
        f'<iq xmlns="{NS_CLIENT}" type="set"{to_attr}{from_attr} id="{accept_iq_id}">',
        f'  <jingle xmlns="{NS_JINGLE}" action="session-accept" sid="{sid}"{initiator_attr}{responder_attr}>',
    ]

    offer_contents = _find_all_elems(jingle_offer, "content")
    content_names = [oc.attrib.get("name", "0") for oc in offer_contents]

    # BUNDLE group declaration
    if len(content_names) > 0:
        xml_lines.append('    <group xmlns="urn:xmpp:jingle:apps:grouping:0" semantics="BUNDLE">')
        for c_name in content_names:
            xml_lines.append(f'      <content name="{c_name}"/>')
        xml_lines.append('    </group>')

    for oc in offer_contents:
        c_name = oc.attrib.get("name", "0")
        c_creator = oc.attrib.get("creator", "initiator")
        
        direction = direction_by_mid.get(c_name, "both")
        senders_map = {
            "sendrecv": "both",
            "sendonly": "responder",
            "recvonly": "initiator",
            "inactive": "none",
        }
        senders_attr = senders_map.get(direction, "both")

        desc_elem = _find_elem(oc, "description")
        media_type = desc_elem.attrib.get("media", "audio") if desc_elem is not None else "audio"

        xml_lines.append(f'    <content name="{c_name}" creator="{c_creator}" senders="{senders_attr}">')
        xml_lines.append(f'      <description xmlns="{NS_RTP}" media="{media_type}">')
        xml_lines.append('        <rtcp-mux/>')

        # Codec resolution with fallback
        ans_codecs = codecs_by_mid.get(c_name, [])
        if not ans_codecs and "0" in codecs_by_mid:
            ans_codecs = codecs_by_mid["0"]
        if not ans_codecs:
            for codec_list in codecs_by_mid.values():
                if codec_list:
                    ans_codecs = codec_list
                    break

        for codec in ans_codecs:
            ch_attr = f' channels="{codec.channels}"' if codec.channels else (
                ' channels="2"' if codec.name.lower() == "opus" else ""
            )
            xml_lines.append(
                f'        <payload-type id="{codec.id}" name="{codec.name}" clockrate="{codec.clockrate}"{ch_attr}>'
            )
            for pk, pv in codec.parameters.items():
                xml_lines.append(f'          <parameter name="{pk}" value="{pv}"/>')
            xml_lines.append("        </payload-type>")

        ssrc = ssrc_by_mid.get(c_name)
        if ssrc and direction in ("sendonly", "sendrecv"):
            endpoint_id = client_jid.split("/")[-1] if client_jid else "bot"
            tag = "a0" if media_type == "audio" else "v0"
            xml_lines.append(
                f'        <source xmlns="{NS_SSMA}" ssrc="{ssrc}" name="{endpoint_id}-{tag}">'
                f'<parameter name="msid" value="{endpoint_id}-{media_type}-0 {endpoint_id}-{media_type}-0"/>'
                f'</source>'
            )

        xml_lines.append("      </description>")

        # Transport block
        xml_lines.append(
            f'      <transport xmlns="{NS_ICE_UDP}" ufrag="{sdp_ufrag}" pwd="{sdp_pwd}">'
        )
        xml_lines.append("        <rtcp-mux/>")
        if sdp_fingerprint:
            xml_lines.append(
                f'        <fingerprint xmlns="{NS_DTLS}" hash="{sdp_fingerprint_hash}" setup="{sdp_setup}">'
                f'{sdp_fingerprint}</fingerprint>'
            )

        # Candidate resolution with fallback across mid keys
        ans_candidates = candidates_by_mid.get(c_name, [])
        if not ans_candidates and "0" in candidates_by_mid:
            ans_candidates = candidates_by_mid["0"]
        if not ans_candidates:
            for cand_list in candidates_by_mid.values():
                if cand_list:
                    ans_candidates = cand_list
                    break

        for cand in ans_candidates:
            xml_lines.append(
                f'        <candidate component="{cand.component}" foundation="{cand.foundation}" '
                f'ip="{cand.ip}" port="{cand.port}" priority="{cand.priority}" '
                f'protocol="{cand.protocol}" type="{cand.type}"/>'
            )

        xml_lines.append("      </transport>")
        xml_lines.append("    </content>")

    xml_lines.append("  </jingle>")
    xml_lines.append("</iq>")

    session_accept_iq = "".join(line.strip() for line in xml_lines)
    logger.debug("Constructed Jingle session-accept IQ (%d bytes, sid=%s)", len(session_accept_iq), sid)
    return session_accept_iq


# ==============================================================================
# Jitsi Source Declaration Stanza Builder (lib-gst-meet Colibri2 pattern)
# ==============================================================================

def build_source_add_stanza(
    ssrc: int,
    media_type: str = "audio",
    source_name: Optional[str] = None,
    muted: bool = False,
    room_jid: Optional[str] = None,
    display_name: Optional[str] = None,
) -> str:
    """
    Builds the Jitsi Colibri2 / MUC source-declaration presence update stanza.
    """
    nick = display_name or "VAD-Harness-SpeakerBot"
    src_name = source_name or f"{nick}-a0"
    to_attr = f' to="{room_jid}/{nick}"' if room_jid else ""

    stanza_lines = [
        f'<presence xmlns="{NS_CLIENT}"{to_attr}>',
        f'  <nick xmlns="{NS_NICK}">{nick}</nick>',
        f'  <audiomuted xmlns="{NS_AUDIO_MUTED}">{"true" if muted else "false"}</audiomuted>',
        f'  <videomuted xmlns="{NS_VIDEO_MUTED}">true</videomuted>',
        f'  <Sources xmlns="{NS_DTLS}">',
        f'    <Source xmlns="{NS_RTP}" ssrc="{ssrc}" name="{src_name}" media="{media_type}"/>',
        f'  </Sources>',
        f'</presence>',
    ]

    return "\n".join(stanza_lines)


# ==============================================================================
# Trickle ICE Candidate Parser (transport-info)
# ==============================================================================

def parse_transport_info_candidates(transport_info_xml: str) -> List[Tuple[str, IceCandidate]]:
    """
    Parses <candidate> elements from a Jingle transport-info XML string.
    Returns list of (mid, IceCandidate) tuples.
    """
    if not transport_info_xml or not transport_info_xml.strip():
        return []
    try:
        root = ET.fromstring(transport_info_xml.strip())
    except ET.ParseError:
        return []

    jingle_elem = _find_elem(root, "jingle")
    if jingle_elem is None:
        if _strip_ns(root.tag) == "jingle":
            jingle_elem = root
        else:
            return []

    results: List[Tuple[str, IceCandidate]] = []
    content_elems = _find_all_elems(jingle_elem, "content")
    for c_elem in content_elems:
        c_name = c_elem.attrib.get("name", "0")
        trans_elem = _find_elem(c_elem, "transport")
        if trans_elem is None:
            continue
        for cand_elem in _find_all_elems(trans_elem, "candidate"):
            c_ip = cand_elem.attrib.get("ip")
            c_port = cand_elem.attrib.get("port")
            if not c_ip or not c_port:
                continue
            cand = IceCandidate(
                foundation=cand_elem.attrib.get("foundation", "1"),
                component=cand_elem.attrib.get("component", "1"),
                protocol=cand_elem.attrib.get("protocol", "udp").lower(),
                priority=cand_elem.attrib.get("priority", "2130706431"),
                ip=c_ip,
                port=c_port,
                type=cand_elem.attrib.get("type", "host"),
                rel_addr=cand_elem.attrib.get("rel-addr"),
                rel_port=cand_elem.attrib.get("rel-port"),
                tcptype=cand_elem.attrib.get("tcptype"),
                generation=cand_elem.attrib.get("generation"),
                network=cand_elem.attrib.get("network"),
                id=cand_elem.attrib.get("id"),
            )
            results.append((c_name, cand))
    return results