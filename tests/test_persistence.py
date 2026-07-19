"""Persistence tests: boot-time --load + debounced JSONL autosave.

Covers:
* load_jsonl_into_store() replicates the CLI JSONL contract (node/edge/triplet,
  styling extras, auto-created endpoints) — verified through GET /api/graph.
* DebouncedAutosaver writes lossless JSONL atomically, round-trips through the
  loader, coalesces bursts, and persists an empty graph after clear.
* trigger_autosave() is a no-op when autosave is unconfigured.
"""

import asyncio
import json

import pytest

import graph_vis_server
from graph_vis_server import (
    DebouncedAutosaver,
    GraphStore,
    _graph_to_jsonl,
    load_jsonl_into_store,
    store,
)


@pytest.fixture(autouse=True)
def reset_autosaver():
    """The module-level autosaver leaks between tests otherwise: a stale saver
    would fire pending debounce writes after a test ends. Reset it each time."""
    graph_vis_server.autosaver = None
    yield
    saver = graph_vis_server.autosaver
    if saver is not None and saver._task is not None:
        saver._task.cancel()
    graph_vis_server.autosaver = None


# ---------------------------------------------------------------------------
# Boot-time load
# ---------------------------------------------------------------------------

def test_load_jsonl_into_store_nodes_and_edges(tmp_path):
    f = tmp_path / "g.jsonl"
    f.write_text(
        '{"type":"node","id":"A","label":"Alice","color":"red"}\n'
        '{"type":"node","id":"B","label":"Bob"}\n'
        '{"type":"edge","from":"A","to":"B","label":"knows"}\n'
    )
    target = GraphStore()
    nodes, edges = load_jsonl_into_store(target, str(f))
    assert (nodes, edges) == (2, 1)
    assert target.nodes["A"]["label"] == "Alice"
    assert target.nodes["A"]["color"] == "red"  # styling extra preserved
    assert "A-knows-B" in target.edges


def test_load_jsonl_triplet_and_autocreated_nodes(tmp_path):
    f = tmp_path / "g.jsonl"
    f.write_text('{"type":"triplet","subject":"X","predicate":"likes","object":"Y"}\n')
    target = GraphStore()
    nodes, edges = load_jsonl_into_store(target, str(f))
    assert (nodes, edges) == (0, 1)
    # Endpoints auto-created by add_triplet
    assert "X" in target.nodes and "Y" in target.nodes
    assert "X-likes-Y" in target.edges


def test_load_jsonl_skips_comments_and_blanks(tmp_path):
    f = tmp_path / "g.jsonl"
    f.write_text(
        "# a comment\n"
        "\n"
        '{"type":"node","id":"Solo"}\n'
    )
    target = GraphStore()
    nodes, edges = load_jsonl_into_store(target, str(f))
    assert (nodes, edges) == (1, 0)
    assert target.nodes["Solo"]["label"] == "Solo"  # label defaults to id


def test_load_at_boot_visible_via_api(tmp_path, client):
    """Load into the shared module store, then confirm via GET /api/graph —
    the same store the API serves from (proves boot-load reaches clients)."""
    f = tmp_path / "boot.jsonl"
    f.write_text(
        '{"type":"node","id":"Root","label":"Root"}\n'
        '{"type":"edge","from":"Root","to":"Leaf","label":"has"}\n'
    )
    load_jsonl_into_store(store, str(f))
    graph = client.get("/api/graph").json()
    ids = {n["id"] for n in graph["nodes"]}
    # Store.add_edge does NOT auto-create endpoint nodes — same as the CLI
    # loader (_process_jsonl_lines); the frontend/vis-network materializes the
    # implicit "Leaf" endpoint on render.
    assert ids == {"Root"}
    assert graph["edges"][0]["id"] == "Root-has-Leaf"


# ---------------------------------------------------------------------------
# Autosave writer / round-trip
# ---------------------------------------------------------------------------

def test_flush_writes_atomic_lossless_jsonl(tmp_path):
    target = GraphStore()
    target.add_node("A", "Alice", color="red")
    target.add_edge("A", "B", "knows")
    path = tmp_path / "out.jsonl"
    saver = DebouncedAutosaver(str(path), target)
    saver.flush()

    assert path.exists()
    # No leftover temp files
    assert list(tmp_path.glob("*.tmp*")) == []
    # Round-trips back into an identical store
    reloaded = GraphStore()
    load_jsonl_into_store(reloaded, str(path))
    assert reloaded.nodes["A"]["color"] == "red"
    assert "A-knows-B" in reloaded.edges


def test_flush_empty_graph_writes_empty_file(tmp_path):
    """After clear, the autosave file must become empty so a restart yields an
    empty graph, not stale content."""
    path = tmp_path / "empty.jsonl"
    saver = DebouncedAutosaver(str(path), GraphStore())
    saver.flush()
    assert path.exists()
    assert path.read_text() == ""


def test_flush_creates_missing_parent_dir(tmp_path):
    target = GraphStore()
    target.add_node("A", "A")
    path = tmp_path / "nested" / "deep" / "out.jsonl"
    saver = DebouncedAutosaver(str(path), target)
    saver.flush()
    assert path.exists()


def test_graph_to_jsonl_matches_converter():
    data = {
        "nodes": [{"id": "A", "label": "A"}],
        "edges": [{"id": "A--B", "from": "A", "to": "B", "label": ""}],
    }
    lines = _graph_to_jsonl(data).splitlines()
    assert json.loads(lines[0]) == {"type": "node", "id": "A", "label": "A"}
    assert json.loads(lines[1])["type"] == "edge"


# ---------------------------------------------------------------------------
# Debounce behaviour (async, deterministic with a tiny delay)
# ---------------------------------------------------------------------------

def test_debounced_schedule_writes_after_delay(tmp_path):
    async def run():
        target = GraphStore()
        target.add_node("A", "Alice")
        path = tmp_path / "debounce.jsonl"
        saver = DebouncedAutosaver(str(path), target, delay=0.05)
        graph_vis_server.autosaver = saver

        graph_vis_server.trigger_autosave()
        assert not path.exists()  # not written yet — still debouncing
        await asyncio.sleep(0.15)
        assert path.exists()

        reloaded = GraphStore()
        load_jsonl_into_store(reloaded, str(path))
        assert "A" in reloaded.nodes

    asyncio.run(run())


def test_debounce_coalesces_burst(tmp_path):
    async def run():
        target = GraphStore()
        path = tmp_path / "burst.jsonl"
        saver = DebouncedAutosaver(str(path), target, delay=0.05)
        graph_vis_server.autosaver = saver

        # Rapid burst: each schedule cancels the previous pending write
        for i in range(5):
            target.add_node(f"N{i}", f"N{i}")
            graph_vis_server.trigger_autosave()
            await asyncio.sleep(0.01)
        assert not path.exists()  # coalesced — nothing written mid-burst
        await asyncio.sleep(0.12)

        reloaded = GraphStore()
        load_jsonl_into_store(reloaded, str(path))
        assert len(reloaded.nodes) == 5  # single write captured final state

    asyncio.run(run())


def test_trigger_autosave_noop_when_unconfigured():
    graph_vis_server.autosaver = None
    # Must not raise
    graph_vis_server.trigger_autosave()
