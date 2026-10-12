"""Claude's change for BLK-1.0-14 (FR-1.0-14; WO-1.0-10 B13 amended once the owner approves), written first.

On 2026-10-12, every non-streaming chat request whose reply took more than 30 seconds came back as HTTP 502
`upstream request failed`. The 502 is produced on the session's egress path, not by NVIDIA: it carries no
`Nvcf-Reqid` or `Date`. A streamed request with the same body got its first byte in about 4 seconds and finished with
HTTP 200 after 555 seconds. So the OpenAI-compatible client asks for a stream with usage. It joins only `delta.content`
(reasoning is not output), takes the finish from the last finish_reason and the token counts from the usage chunk, and
never returns a partial stream as a reply. A JSON reply is still parsed as B13 describes.
"""
from __future__ import annotations

import json
import math

import pytest

from tests.aqis_lab.outsourcing.test_acceptance_wo_1_0_10 import (  # noqa: F401  (local_only is an autouse fixture)
    chat_request, local_only, mod, model, setup)

SSE = {"Content-Type": "text/event-stream"}


def chunk(delta: dict | None = None, finish: str | None = None, usage: dict | None = None) -> str:
    body: dict = {"id": "c1", "object": "chat.completion.chunk", "model": "n-a",
                  "choices": [] if delta is None else [{"index": 0, "delta": delta, "finish_reason": finish}]}
    if usage is not None:
        body["usage"] = usage
    return "data: " + json.dumps(body) + "\n\n"


def stream(*events: str, done: bool = True) -> tuple[int, dict, str]:
    return 200, SSE, ": keep-alive\n\n" + "".join(events) + ("data: [DONE]\n\n" if done else "")


GOOD = stream(
    chunk({"role": "assistant", "content": ""}),
    chunk({"reasoning_content": "I should think first. "}),
    chunk({"reasoning_content": "Then answer."}),
    chunk({"content": "Hello"}),
    chunk({"content": ", wörld"}),
    chunk({}, finish="stop"),
    chunk(None, usage={"prompt_tokens": 1234, "completion_tokens": 56, "total_tokens": 1290}),
)


def run(tmp_path, script):
    clock, pool, gov, stand = setup(tmp_path, {"n-a": model("mistral", 1)}, script=script)
    with stand:
        reply = mod("openai_client").OpenAIClient(pool.model("n-a"), gov, 5, base_url=stand.url).generate(chat_request())
    return reply, gov, stand


def test_FR_1_0_14_stream_request_asks_for_a_stream_with_usage(tmp_path):
    _, _, stand = run(tmp_path, [GOOD])
    body = json.loads(stand.generations()[0]["body"])
    assert body["stream"] is True
    assert body["stream_options"] == {"include_usage": True}


def test_FR_1_0_14_stream_reply_joins_content_without_reasoning(tmp_path):
    reply, gov, _ = run(tmp_path, [GOOD])
    assert reply.text == "Hello, wörld"
    assert reply.finish == "STOP"
    assert (reply.prompt_tokens, reply.output_tokens) == (1234, 56)
    assert (reply.prompt_estimated, reply.output_estimated) == (False, False)
    assert reply.model == "n-a"
    assert reply.raw_json == GOOD[2]
    stats = gov.model_stats["n-a"]
    assert (stats.prompt_tokens, stats.output_tokens) == (1234, 56)
    assert stats.starts[-1][1] == 1234


def test_FR_1_0_14_stream_length_finish_maps_to_max_tokens(tmp_path):
    reply, _, _ = run(tmp_path, [stream(chunk({"reasoning_content": "long thought"}), chunk({}, finish="length"),
                                        chunk(None, usage={"prompt_tokens": 10, "completion_tokens": 2048}))])
    assert (reply.text, reply.finish, reply.output_tokens) == ("", "MAX_TOKENS", 2048)


def test_FR_1_0_14_stream_without_usage_is_estimated(tmp_path):
    text = "x" * 71
    reply, _, _ = run(tmp_path, [stream(chunk({"content": text}), chunk({}, finish="stop"))])
    request = chat_request()
    measured = math.ceil((len(request.system) + len(request.turns[0].text)) / 3.5)
    assert (reply.prompt_tokens, reply.output_tokens) == (measured, math.ceil(71 / 3.5))
    assert (reply.prompt_estimated, reply.output_estimated) == (True, True)


def test_FR_1_0_14_stream_error_event_is_never_a_reply(tmp_path):
    bad = stream(chunk({"content": "partial"}), "data: " + json.dumps({"error": {"message": "model crashed"}}) + "\n\n",
                 done=False)
    with pytest.raises(mod("chat").ApiError, match="model crashed"):
        run(tmp_path, [bad])


def test_FR_1_0_14_stream_cut_before_its_finish_is_retried_as_a_transport_failure(tmp_path):
    cut = stream(chunk({"content": "half an ans"}), done=False)
    reply, _, stand = run(tmp_path, [cut, GOOD])
    assert reply.text == "Hello, wörld"
    assert len(stand.generations()) == 2


def test_FR_1_0_14_stream_cut_every_time_raises_transport_error(tmp_path):
    cut = stream(chunk({"content": "half an ans"}), done=False)
    with pytest.raises(mod("chat").TransportError):
        run(tmp_path, [cut] * 4)
