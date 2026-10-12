"""Server-sent event streams of OpenAI-compatible chat completions.

CAPABILITIES:
  CAP-OUTSOURCING-SSE: assemble a streamed chat completion into its content, finish reason, usage and model [tests: test_FR_1_0_14_stream_reply_joins_content_without_reasoning, test_FR_1_0_14_stream_length_finish_maps_to_max_tokens, test_FR_1_0_14_stream_without_usage_is_estimated, test_FR_1_0_14_stream_error_event_is_never_a_reply, test_FR_1_0_14_stream_cut_before_its_finish_is_retried_as_a_transport_failure]
INPUTS AND OUTPUTS:
  Accepts response headers and the response text; returns a Completion; raises ApiError or StreamCut.
CONTRACTS: none.
INVARIANTS:
  - Only `delta.content` of choice 0 is output; reasoning chunks are never part of the text.
  - A stream with neither a finish_reason nor `[DONE]` is never a completion.
NOT IN SCOPE:
  - Sending requests, retries and token accounting (openai_client and governor).
CHANGE LOG:
  2026-10-12 WP-1.0 FR-1.0-14 (Claude, BLK-1.0-14): created.
"""
from __future__ import annotations

import json
from dataclasses import dataclass

from tools.outsourcing.chat import ApiError


class StreamCut(Exception):
    """The stream ended before its finish_reason or `[DONE]`."""


@dataclass(frozen=True)
class Completion:
    text: str
    finish_reason: str | None
    usage: dict | None
    model: str


def is_event_stream(headers: dict[str, str]) -> bool:
    for key, value in headers.items():
        if key.lower() == "content-type":
            return value.split(";")[0].strip().lower() == "text/event-stream"
    return False


def events(body_text: str) -> list[str]:
    """Return the data of each event in order; comments and other fields are dropped."""
    found: list[str] = []
    data: list[str] = []
    for line in body_text.splitlines():
        if not line:
            if data:
                found.append("\n".join(data))
                data = []
        elif line.startswith("data:"):
            data.append(line[6:] if line.startswith("data: ") else line[5:])
    if data:
        found.append("\n".join(data))
    return found


def _event(payload: str, provider: str) -> dict:
    try:
        event = json.loads(payload)
    except (json.JSONDecodeError, ValueError) as e:
        raise ApiError(f"unexpected stream event: {e}") from None
    if not isinstance(event, dict):
        raise ApiError("unexpected stream event: event must be object")
    if "error" in event:
        err = event["error"]
        raise ApiError(f"stream error from {provider}: {err.get('message', err) if isinstance(err, dict) else err}")
    return event


def assemble(body_text: str, provider: str) -> Completion:
    parts: list[str] = []
    finish: str | None = None
    usage: dict | None = None
    model = ""
    done = False
    for payload in events(body_text):
        if payload.strip() == "[DONE]":
            done = True
            break
        event = _event(payload, provider)
        model = str(event.get("model") or model)
        usage = event["usage"] if isinstance(event.get("usage"), dict) else usage
        for choice in event.get("choices") or []:
            if not isinstance(choice, dict) or choice.get("index", 0) != 0:
                continue
            delta = choice.get("delta")
            if isinstance(delta, dict) and isinstance(delta.get("content"), str):
                parts.append(delta["content"])
            finish = str(choice["finish_reason"]) if choice.get("finish_reason") else finish
    if not done and finish is None:
        raise StreamCut(f"stream from {provider} ended before its finish")
    return Completion(text="".join(parts), finish_reason=finish, usage=usage, model=model)
