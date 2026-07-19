"""Server-Sent-Events (/api/events) streaming tests.

Proves that with an SSE subscriber connected, a mutation produces the
corresponding event on the stream — the CLI --subscribe foundation.

Note on approach: neither the sync `TestClient` (deadlocks holding a stream
open during a concurrent request) nor `httpx.ASGITransport` (buffers the whole
response body, which never ends for an infinite SSE stream) can drive an
open-ended event stream in-process. So these tests exercise the endpoint's
`StreamingResponse.body_iterator` directly on one event loop: register a
subscriber via the real `/api/events` handler, fire a mutation through the real
REST endpoint (store update + `manager.broadcast`), and assert the next chunk
pulled from the stream is the corresponding SSE `data:` frame. A live
end-to-end smoke test over real HTTP lives in `test_sse_live` (skipped unless
GRAPH_VIS_LIVE=1).
"""

import asyncio
import json

import pytest

from graph_vis_server import (
    AddEdgeRequest,
    AddNodeRequest,
    AddTripletRequest,
    RemoveEdgeRequest,
    add_edge,
    add_node,
    add_triplet,
    clear_graph,
    manager,
    remove_edge,
    sse_events,
)

TIMEOUT = 5.0


def _parse_data_frame(chunk: str):
    """Parse an SSE `data: {...}\\n\\n` frame into its event dict, or None."""
    line = chunk.strip()
    if not line.startswith("data:"):
        return None
    return json.loads(line[len("data:"):].strip())


async def _next_data_frame(agen, limit=10):
    """Pull chunks until a `data:` frame appears (skips comments/heartbeats)."""
    for _ in range(limit):
        chunk = await agen.__anext__()
        evt = _parse_data_frame(chunk)
        if evt is not None:
            return evt
    return None


async def _subscribe():
    """Open the SSE stream; return (StreamingResponse, body_iterator).

    The subscriber queue is registered synchronously inside `sse_events()`, and
    the first pulled chunk is the ``: connected`` comment.
    """
    resp = await sse_events()
    assert resp.media_type == "text/event-stream"
    agen = resp.body_iterator
    first = await agen.__anext__()
    assert first.startswith(":")  # ": connected"
    assert len(manager.sse_queues) == 1
    return resp, agen


def _run(coro):
    return asyncio.run(asyncio.wait_for(coro, TIMEOUT))


def test_events_media_type_and_registration():
    async def scenario():
        resp, agen = await _subscribe()
        await agen.aclose()
        assert len(manager.sse_queues) == 0
    _run(scenario())


def test_events_receives_add_node():
    async def scenario():
        _, agen = await _subscribe()
        await add_node(AddNodeRequest(id="A", label="A"))
        evt = await _next_data_frame(agen)
        await agen.aclose()
        return evt
    evt = _run(scenario())
    assert evt is not None
    assert evt["event"] == "add-node"
    assert evt["data"]["id"] == "A"


def test_events_receives_add_triplet():
    async def scenario():
        _, agen = await _subscribe()
        await add_triplet(AddTripletRequest(subject="X", predicate="knows", object="Y"))
        evt = await _next_data_frame(agen)
        await agen.aclose()
        return evt
    evt = _run(scenario())
    assert evt is not None
    assert evt["event"] == "add-triplet"
    assert evt["data"]["subject"] == "X"
    assert evt["data"]["object"] == "Y"


def test_events_receives_add_edge():
    async def scenario():
        _, agen = await _subscribe()
        await add_edge(AddEdgeRequest.model_validate(
            {"from": "A", "to": "B", "label": "links"}))
        evt = await _next_data_frame(agen)
        await agen.aclose()
        return evt
    evt = _run(scenario())
    assert evt is not None
    assert evt["event"] == "add-edge"
    assert evt["data"]["id"] == "A-links-B"


def test_events_receives_remove_edge():
    async def scenario():
        await add_triplet(AddTripletRequest(subject="A", predicate="r", object="B"))
        _, agen = await _subscribe()
        await remove_edge(RemoveEdgeRequest(id="A-r-B"))
        evt = await _next_data_frame(agen)
        await agen.aclose()
        return evt
    evt = _run(scenario())
    assert evt is not None
    assert evt["event"] == "remove-edge"
    assert evt["data"]["id"] == "A-r-B"


def test_events_receives_clear():
    async def scenario():
        _, agen = await _subscribe()
        await clear_graph()
        evt = await _next_data_frame(agen)
        await agen.aclose()
        return evt
    evt = _run(scenario())
    assert evt is not None
    assert evt["event"] == "clear"


def test_events_forwards_rev_when_present():
    """SSE payload is tolerant of an extra `rev` field (collab-resync overlap)."""
    async def scenario():
        _, agen = await _subscribe()
        # Inject through the same fan-out path a broadcast uses.
        manager.sse_fan_out({"event": "add-node", "data": {"id": "Z"}, "rev": 7})
        evt = await _next_data_frame(agen)
        await agen.aclose()
        return evt
    evt = _run(scenario())
    assert evt is not None
    assert evt["event"] == "add-node"
    assert evt["rev"] == 7


def test_events_two_subscribers_both_receive():
    async def scenario():
        _, agen1 = await _subscribe()
        resp2 = await sse_events()
        agen2 = resp2.body_iterator
        assert (await agen2.__anext__()).startswith(":")
        assert len(manager.sse_queues) == 2
        await add_node(AddNodeRequest(id="Fan", label="Fan"))
        e1 = await _next_data_frame(agen1)
        e2 = await _next_data_frame(agen2)
        await agen1.aclose()
        await agen2.aclose()
        return e1, e2
    e1, e2 = _run(scenario())
    assert e1["data"]["id"] == "Fan"
    assert e2["data"]["id"] == "Fan"


def test_events_slow_consumer_dropped_no_leak():
    """A subscriber whose bounded queue fills is dropped (no unbounded growth)."""
    async def scenario():
        resp, agen = await _subscribe()
        # Never pull from the generator; flood past SSE_QUEUE_MAXSIZE.
        maxsize = manager.SSE_QUEUE_MAXSIZE
        for i in range(maxsize + 10):
            manager.sse_fan_out({"event": "add-node", "data": {"id": str(i)}})
        # The stuck subscriber must have been dropped, not left to grow.
        assert len(manager.sse_queues) == 0
        await agen.aclose()
    _run(scenario())
