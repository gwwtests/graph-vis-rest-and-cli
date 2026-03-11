# Multiline Mode, JSONL Format & Styling Pass-Through

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add multiline block syntax (`+++`/`+++format`) to the CLI, a JSONL format for loading styled graphs, labelless edges, and vis-network styling pass-through from API to frontend.

**Architecture:** The server API models get optional `extras` dict fields that pass through to vis-network. A new `jsonl2graph` converter handles JSONL input with styling. The CLI gets a `MultilineProcessor` that intercepts `+++` markers and accumulates/dispatches blocks. Label becomes optional for edges (defaults to `""`).

**Tech Stack:** Python 3.11+, FastAPI/Pydantic, vis-network (frontend unchanged — already does pass-through), pytest

---

### Task 1: Server — Make edge label optional + extras pass-through on add-node

**Files:**

* Modify: `graph-vis-server.py` (Pydantic models + GraphStore + endpoints)
* Test: `tests/test_api.py`

**Step 1: Write failing tests**

Add to `tests/test_api.py`:

```python
def test_add_node_with_extras(client):
    r = client.post("/api/add-node", json={
        "id": "Styled", "label": "Styled",
        "color": "#ff0000", "shape": "diamond",
    })
    assert r.status_code == 200
    node = r.json()["node"]
    assert node["color"] == "#ff0000"
    assert node["shape"] == "diamond"

    graph = client.get("/api/graph").json()
    assert graph["nodes"][0]["color"] == "#ff0000"


def test_add_node_with_font(client):
    r = client.post("/api/add-node", json={
        "id": "F", "label": "F",
        "font": {"color": "white", "size": 18},
    })
    node = r.json()["node"]
    assert node["font"] == {"color": "white", "size": 18}


def test_add_edge_optional_label(client):
    client.post("/api/add-node", json={"id": "A", "label": "A"})
    client.post("/api/add-node", json={"id": "B", "label": "B"})
    r = client.post("/api/add-edge", json={"from": "A", "to": "B"})
    assert r.status_code == 200
    edge = r.json()["edge"]
    assert edge["label"] == ""
    assert edge["id"] == "A--B"


def test_add_edge_with_extras(client):
    client.post("/api/add-node", json={"id": "A", "label": "A"})
    client.post("/api/add-node", json={"id": "B", "label": "B"})
    r = client.post("/api/add-edge", json={
        "from": "A", "to": "B", "label": "likes",
        "color": "#00ff00", "width": 3,
    })
    edge = r.json()["edge"]
    assert edge["color"] == "#00ff00"
    assert edge["width"] == 3

    graph = client.get("/api/graph").json()
    assert graph["edges"][0]["color"] == "#00ff00"
```

**Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=. pytest tests/test_api.py::test_add_node_with_extras tests/test_api.py::test_add_edge_optional_label tests/test_api.py::test_add_edge_with_extras tests/test_api.py::test_add_node_with_font -v -p no:playwright`
Expected: FAIL (422 validation errors for extra fields, required label)

**Step 3: Implement server changes**

In `graph-vis-server.py`:

1. Change Pydantic models to accept extras:

```python
class AddNodeRequest(BaseModel):
    id: str
    label: str
    extras: dict = {}

    model_config = {"extra": "allow"}

    def node_dict(self) -> dict:
        """Build node dict with id, label, and any extra vis-network properties."""
        d = {"id": self.id, "label": self.label}
        # Merge any extra fields (color, shape, font, etc.)
        for k, v in self.model_extra.items():
            d[k] = v
        return d
```

Wait — simpler approach. Use `model_config = {"extra": "allow"}` and merge `model_extra` into stored dicts:

For `AddNodeRequest`: add `model_config = {"extra": "allow"}`. In `add_node` endpoint, build node dict from base fields + extras.

For `AddEdgeRequest`: make `label` optional (default `""`), add `model_config = {"extra": "allow"}`.

For `GraphStore.add_node`: accept `**extras` and merge into stored dict.
For `GraphStore.add_edge`: accept `**extras`, handle empty label in edge ID.

```python
class AddNodeRequest(BaseModel):
    id: str
    label: str
    model_config = {"extra": "allow"}


class AddEdgeRequest(BaseModel):
    edge_from: str = Field(alias="from")
    edge_to: str = Field(alias="to")
    label: str = ""
    id: Optional[str] = None
    model_config = {"populate_by_name": True, "extra": "allow"}
```

GraphStore changes:

```python
def add_node(self, node_id: str, label: str, **extras) -> dict:
    node = {"id": node_id, "label": label, **extras}
    self.nodes[node_id] = node
    return node

def add_edge(self, edge_from: str, edge_to: str, label: str = "",
             edge_id: Optional[str] = None, **extras) -> dict:
    if edge_id is None:
        edge_id = f"{edge_from}-{label}-{edge_to}" if label else f"{edge_from}--{edge_to}"
    edge = {"id": edge_id, "from": edge_from, "to": edge_to, "label": label, **extras}
    self.edges[edge_id] = edge
    return edge
```

Endpoint changes:

```python
@app.post("/api/add-node")
async def add_node(req: AddNodeRequest):
    extras = req.model_extra or {}
    node = store.add_node(req.id, req.label, **extras)
    await manager.broadcast({"event": "add-node", "data": node})
    return {"ok": True, "node": node}

@app.post("/api/add-edge")
async def add_edge(req: AddEdgeRequest):
    extras = req.model_extra or {}
    edge = store.add_edge(req.edge_from, req.edge_to, req.label, req.id, **extras)
    await manager.broadcast({"event": "add-edge", "data": edge})
    return {"ok": True, "edge": edge}
```

**Step 4: Run tests to verify they pass**

Run: `PYTHONPATH=. pytest tests/test_api.py -v -p no:playwright`
Expected: ALL PASS (including all existing tests)

**Step 5: Commit**

```bash
git add graph-vis-server.py tests/test_api.py
git commit -m "feat: add styling extras pass-through and optional edge labels

* AddNodeRequest/AddEdgeRequest accept extra vis-network properties
* GraphStore stores and returns extras (color, shape, font, etc.)
* Edge label now optional (defaults to empty string)
* Edge ID uses -- separator for labelless edges"
```

---

### Task 2: CLI — Labelless edges (2 bare words = add edge without label)

**Files:**

* Modify: `graph-vis-cli.py` (GraphClient, GraphREPL.default, do_add)
* Test: `tests/test_cli.py`

**Step 1: Write failing tests**

Add to `tests/test_cli.py`:

```python
def test_repl_default_two_words(capsys):
    """2 bare words should add edge without label."""
    c = GraphClient("127.0.0.1", 7849)
    repl = GraphREPL(c)
    with patch.object(c, "add_edge", return_value={"ok": True}):
        repl.default("Alice Bob")
        c.add_edge.assert_called_once_with("Alice", "Bob", "")


def test_repl_plus_two_words(capsys):
    """+ with 2 words should add edge without label."""
    c = GraphClient("127.0.0.1", 7849)
    repl = GraphREPL(c)
    with patch.object(c, "add_edge", return_value={"ok": True}):
        repl.default("+ Alice Bob")
        c.add_edge.assert_called_once_with("Alice", "Bob", "")
```

**Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=. pytest tests/test_cli.py::test_repl_default_two_words tests/test_cli.py::test_repl_plus_two_words -v -p no:playwright --noconftest`
Expected: FAIL

**Step 3: Implement**

In `graph-vis-cli.py`, update `do_add` to accept 2 or 3 args:

```python
def do_add(self, arg):
    """add <subj> <pred> <obj> | add <from> <to> — Add triplet or edge"""
    parts = arg.split()
    if len(parts) == 3:
        r = self.client.add_triplet(*parts)
        if r and r.get("ok"):
            print(f"Added: {parts[0]} —{parts[1]}→ {parts[2]}")
    elif len(parts) == 2:
        r = self.client.add_edge(parts[0], parts[1], "")
        if r and r.get("ok"):
            print(f"Added: {parts[0]} → {parts[1]}")
    else:
        print("Usage: add <subject> <predicate> <object>")
        print("       add <from> <to>")
```

Update `default`:

```python
def default(self, line):
    parts = line.split()
    if parts and parts[0] == '+':
        self.do_add(' '.join(parts[1:]))
    elif parts and parts[0] == '-':
        self.do_del(' '.join(parts[1:]))
    elif len(parts) == 3:
        self.do_add(line)
    elif len(parts) == 2:
        self.do_add(line)
    else:
        print(f"Unknown command: {line.split()[0] if parts else ''}")
        print("Type 'help' for commands.")
```

**Step 4: Run tests to verify they pass**

Run: `PYTHONPATH=. pytest tests/test_cli.py -v -p no:playwright --noconftest`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add graph-vis-cli.py tests/test_cli.py
git commit -m "feat: support labelless edges (2 bare words = connect without label)

* do_add accepts 2 args (from, to) for labelless edge
* default() treats 2 bare words as add edge
* + shortcut works with 2 words too"
```

---

### Task 3: JSONL converter — `scripts/converters/jsonl2graph/`

**Files:**

* Create: `scripts/converters/jsonl2graph/jsonl2graph.py`
* Test: `tests/test_jsonl2graph.py`

**Step 1: Write failing tests**

Create `tests/test_jsonl2graph.py`:

```python
"""Tests for jsonl2graph converter."""

import io
import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__),
                                "..", "scripts", "converters", "jsonl2graph"))

from jsonl2graph import convert, format_output


def test_convert_triplets():
    data = '\n'.join([
        json.dumps({"type": "triplet", "subject": "A", "predicate": "knows", "object": "B"}),
        json.dumps({"type": "triplet", "subject": "B", "predicate": "likes", "object": "C"}),
    ])
    result = convert(io.StringIO(data))
    assert len(result["nodes"]) == 3
    assert len(result["edges"]) == 2
    assert result["edges"][0]["from"] == "A"
    assert result["edges"][0]["label"] == "knows"


def test_convert_nodes_with_extras():
    data = json.dumps({
        "type": "node", "id": "X", "label": "X-Label",
        "color": "#ff0000", "shape": "diamond",
    })
    result = convert(io.StringIO(data))
    assert len(result["nodes"]) == 1
    assert result["nodes"][0]["color"] == "#ff0000"
    assert result["nodes"][0]["shape"] == "diamond"


def test_convert_edges_with_extras():
    data = '\n'.join([
        json.dumps({"type": "node", "id": "A", "label": "A"}),
        json.dumps({"type": "node", "id": "B", "label": "B"}),
        json.dumps({
            "type": "edge", "from": "A", "to": "B", "label": "connects",
            "color": "#00ff00", "width": 3,
        }),
    ])
    result = convert(io.StringIO(data))
    assert result["edges"][0]["color"] == "#00ff00"
    assert result["edges"][0]["width"] == 3


def test_convert_edge_optional_label():
    data = '\n'.join([
        json.dumps({"type": "node", "id": "A", "label": "A"}),
        json.dumps({"type": "node", "id": "B", "label": "B"}),
        json.dumps({"type": "edge", "from": "A", "to": "B"}),
    ])
    result = convert(io.StringIO(data))
    assert result["edges"][0]["label"] == ""


def test_convert_mixed():
    """Nodes, edges, and triplets together."""
    data = '\n'.join([
        json.dumps({"type": "node", "id": "A", "label": "Alpha", "color": "red"}),
        json.dumps({"type": "triplet", "subject": "A", "predicate": "knows", "object": "B"}),
        json.dumps({"type": "edge", "from": "B", "to": "A", "label": "trusts", "width": 2}),
    ])
    result = convert(io.StringIO(data))
    # A defined explicitly + B from triplet
    assert len(result["nodes"]) == 2
    assert len(result["edges"]) == 2
    # A keeps explicit styling
    a_node = [n for n in result["nodes"] if n["id"] == "A"][0]
    assert a_node["color"] == "red"
    assert a_node["label"] == "Alpha"


def test_convert_skips_comments_and_blanks():
    data = '\n'.join([
        "# this is a comment",
        "",
        json.dumps({"type": "node", "id": "A", "label": "A"}),
        "   ",
    ])
    result = convert(io.StringIO(data))
    assert len(result["nodes"]) == 1


def test_format_output_plain():
    result = {
        "nodes": [{"id": "A", "label": "A"}, {"id": "B", "label": "B"}],
        "edges": [{"id": "A-knows-B", "from": "A", "to": "B", "label": "knows"}],
    }
    out = format_output(result, fmt="plain")
    lines = out.strip().split("\n")
    assert lines[0] == "2 1"
    assert "A B knows" in lines[1]


def test_format_output_jsonl():
    result = {
        "nodes": [{"id": "A", "label": "A", "color": "red"}],
        "edges": [],
    }
    out = format_output(result, fmt="jsonl")
    obj = json.loads(out.strip())
    assert obj["type"] == "node"
    assert obj["color"] == "red"


def test_convert_from_file(tmp_path):
    f = tmp_path / "test.jsonl"
    f.write_text('\n'.join([
        json.dumps({"type": "triplet", "subject": "X", "predicate": "y", "object": "Z"}),
    ]))
    result = convert(str(f))
    assert len(result["edges"]) == 1
```

**Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=. pytest tests/test_jsonl2graph.py -v`
Expected: FAIL (import error — module doesn't exist)

**Step 3: Implement jsonl2graph.py**

Create `scripts/converters/jsonl2graph/jsonl2graph.py`:

```python
#!/usr/bin/env python3
"""jsonl2graph -- Convert JSONL graph descriptions to graph intermediate format.

Each line is a JSON object with a required "type" field:

    {"type": "node", "id": "A", "label": "A", "color": "#ff0000", "shape": "diamond"}
    {"type": "edge", "from": "A", "to": "B", "label": "knows", "color": "#00ff00"}
    {"type": "triplet", "subject": "A", "predicate": "knows", "object": "B"}

Node type
---------
Required: id, label.  All other fields are vis-network styling pass-through
(color, shape, size, font, borderWidth, etc.).

Edge type
---------
Required: from, to.  Optional: label (default ""), id (auto-generated).
All other fields are vis-network styling pass-through (color, width, dashes, etc.).

Triplet type
------------
Required: subject, predicate, object.  Creates nodes (id=label=subject/object)
and an edge (from=subject, to=object, label=predicate).  No styling support —
use explicit node/edge entries for that.

Output Formats
--------------
* **plain** (default) -- ``Vn En`` header + ``from to label`` lines.
* **csv** -- ``from,to,label`` header + CSV data rows.
* **jsonl** -- Re-serialized with type field, preserving all extras.

Usage
-----
    ./jsonl2graph.py input.jsonl              # plain text to stdout
    ./jsonl2graph.py input.jsonl --jsonl      # round-trip JSONL
    cat input.jsonl | ./jsonl2graph.py        # read from stdin

Library usage::

    from jsonl2graph import convert, format_output

    result = convert("data.jsonl")
    # result = {"nodes": [...], "edges": [...]}
    print(format_output(result, fmt="plain"))
"""

import argparse
import csv
import io
import json
import sys


def convert(source):
    """Parse JSONL and return structured graph with styling.

    Parameters
    ----------
    source : str or file-like
        Filesystem path or open file/StringIO.

    Returns
    -------
    dict
        {"nodes": [node_dicts...], "edges": [edge_dicts...]}
        Each dict contains at minimum id/label (nodes) or id/from/to/label (edges),
        plus any extra vis-network styling properties.
    """
    if isinstance(source, str):
        with open(source) as fh:
            return _parse(fh)
    return _parse(source)


def _parse(fh):
    nodes = {}   # id -> full dict
    edges = []   # list of full dicts

    for line in fh:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        obj = json.loads(line)
        typ = obj.get("type")

        if typ == "node":
            node_id = obj["id"]
            node = dict(obj)
            del node["type"]
            if "label" not in node:
                node["label"] = node_id
            if node_id in nodes:
                nodes[node_id].update(node)
            else:
                nodes[node_id] = node

        elif typ == "edge":
            frm = obj["from"]
            to = obj["to"]
            label = obj.get("label", "")
            edge = dict(obj)
            del edge["type"]
            edge["label"] = label
            if "id" not in edge:
                edge["id"] = f"{frm}-{label}-{to}" if label else f"{frm}--{to}"
            # Auto-create nodes
            if frm not in nodes:
                nodes[frm] = {"id": frm, "label": frm}
            if to not in nodes:
                nodes[to] = {"id": to, "label": to}
            edges.append(edge)

        elif typ == "triplet":
            subj = obj["subject"]
            pred = obj["predicate"]
            obj_node = obj["object"]
            if subj not in nodes:
                nodes[subj] = {"id": subj, "label": subj}
            if obj_node not in nodes:
                nodes[obj_node] = {"id": obj_node, "label": obj_node}
            edge_id = f"{subj}-{pred}-{obj_node}"
            edges.append({
                "id": edge_id, "from": subj, "to": obj_node, "label": pred,
            })

    return {"nodes": list(nodes.values()), "edges": edges}


def format_output(result, fmt="plain"):
    """Serialize graph result to requested format.

    Parameters
    ----------
    result : dict
        {"nodes": [...], "edges": [...]}.
    fmt : str
        "plain", "csv", or "jsonl".
    """
    nodes = result["nodes"]
    edges = result["edges"]

    if fmt == "plain":
        lines = [f"{len(nodes)} {len(edges)}"]
        for e in edges:
            lines.append(f"{e['from']} {e['to']} {e['label']}")
        return "\n".join(lines)

    if fmt == "csv":
        buf = io.StringIO()
        writer = csv.writer(buf, lineterminator="\n")
        writer.writerow(["from", "to", "label"])
        for e in edges:
            writer.writerow([e["from"], e["to"], e["label"]])
        return buf.getvalue().rstrip("\n")

    if fmt == "jsonl":
        lines = []
        for n in nodes:
            lines.append(json.dumps({"type": "node", **n}))
        for e in edges:
            lines.append(json.dumps({"type": "edge", **e}))
        return "\n".join(lines)

    raise ValueError(f"Unknown format: {fmt!r}")


def main():
    parser = argparse.ArgumentParser(
        description="Convert JSONL graph descriptions to graph intermediate format.",
    )
    parser.add_argument("file", nargs="?", default=None,
                        help="JSONL input file (default: stdin)")
    parser.add_argument("--csv", action="store_true",
                        help="Output in CSV format")
    parser.add_argument("--jsonl", action="store_true",
                        help="Output in JSONL format")
    if len(sys.argv) > 1 and sys.argv[1] == "help":
        parser.parse_args(["--help"])
    args = parser.parse_args()

    fmt = "plain"
    if args.csv:
        fmt = "csv"
    elif args.jsonl:
        fmt = "jsonl"

    if args.file:
        result = convert(args.file)
    else:
        result = convert(sys.stdin)

    print(format_output(result, fmt))


if __name__ == "__main__":
    main()
```

**Step 4: Run tests to verify they pass**

Run: `PYTHONPATH=. pytest tests/test_jsonl2graph.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add scripts/converters/jsonl2graph/jsonl2graph.py tests/test_jsonl2graph.py
git commit -m "feat: add jsonl2graph converter with styling support

* Handles node/edge/triplet types in JSONL format
* Passes through all vis-network styling properties (color, shape, font, etc.)
* Edge label optional (defaults to empty string)
* Supports plain/csv/jsonl output formats
* Works as CLI tool and importable library"
```

---

### Task 4: CLI — Register JSONL in converter map + JSONL-aware loading

**Files:**

* Modify: `graph-vis-cli.py` (CONVERTER_MAP, _load_intermediate, new _load_jsonl)
* Test: `tests/test_cli.py`

**Step 1: Write failing tests**

Add to `tests/test_cli.py`:

```python
def test_converter_map_jsonl():
    """JSONL extension is in CONVERTER_MAP."""
    from graph_vis_cli import CONVERTER_MAP
    assert ".jsonl" in CONVERTER_MAP
    assert CONVERTER_MAP[".jsonl"] == "jsonl2graph"


def test_load_jsonl_with_extras(tmp_path, capsys):
    """Loading JSONL passes styling extras to server."""
    f = tmp_path / "test.jsonl"
    f.write_text('\n'.join([
        json.dumps({"type": "node", "id": "A", "label": "A", "color": "red"}),
        json.dumps({"type": "edge", "from": "A", "to": "B", "label": "x", "width": 3}),
    ]))
    c = GraphClient("127.0.0.1", 7849)
    repl = GraphREPL(c)
    add_node_calls = []
    add_edge_calls = []
    with patch.object(c, "add_node", side_effect=lambda *a, **kw: (add_node_calls.append((a, kw)), {"ok": True})[1]):
        with patch.object(c, "add_edge", side_effect=lambda *a, **kw: (add_edge_calls.append((a, kw)), {"ok": True})[1]):
            repl.do_Load(str(f))
    # Verify extras passed through
    assert any(kw.get("color") == "red" for _, kw in add_node_calls)
    assert any(kw.get("width") == 3 for _, kw in add_edge_calls)
```

**Step 2: Run to verify fail**

Run: `PYTHONPATH=. pytest tests/test_cli.py::test_converter_map_jsonl tests/test_cli.py::test_load_jsonl_with_extras -v -p no:playwright --noconftest`
Expected: FAIL

**Step 3: Implement**

In `graph-vis-cli.py`:

1. Add to CONVERTER_MAP: `".jsonl": "jsonl2graph"`
2. Add `add_node` and `add_edge` with extras to `GraphClient`:

```python
def add_node(self, node_id, label=None, **extras):
    data = {"id": node_id, "label": label or node_id, **extras}
    return self._request("POST", "/api/add-node", data)

def add_edge(self, frm, to, label, **extras):
    data = {"from": frm, "to": to, "label": label, **extras}
    return self._request("POST", "/api/add-edge", data)
```

3. For JSONL files, use a different loading path that preserves extras. Modify `do_Load` to detect JSONL and call `_load_jsonl` instead of running the converter as subprocess:

```python
def do_Load(self, arg):
    filepath = arg.strip()
    if not filepath:
        print("Usage: Load <filepath>")
        return
    if not os.path.isfile(filepath):
        print(f"File not found: {filepath}")
        return
    _, ext = os.path.splitext(filepath)
    ext = ext.lower()
    if ext == ".jsonl":
        self._load_jsonl(filepath)
        return
    # ... existing converter logic ...
```

```python
def _load_jsonl(self, filepath):
    """Load JSONL file directly, preserving styling extras."""
    import json as _json
    loaded_nodes = 0
    loaded_edges = 0
    with open(filepath) as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            obj = _json.loads(line)
            typ = obj.get("type")
            if typ == "node":
                node_id = obj["id"]
                label = obj.get("label", node_id)
                extras = {k: v for k, v in obj.items()
                          if k not in ("type", "id", "label")}
                self.client.add_node(node_id, label, **extras)
                loaded_nodes += 1
            elif typ == "edge":
                frm, to = obj["from"], obj["to"]
                label = obj.get("label", "")
                extras = {k: v for k, v in obj.items()
                          if k not in ("type", "from", "to", "label", "id")}
                if "id" in obj:
                    extras["id"] = obj["id"]
                self.client.add_edge(frm, to, label, **extras)
                loaded_edges += 1
            elif typ == "triplet":
                self.client.add_triplet(
                    obj["subject"], obj["predicate"], obj["object"])
                loaded_edges += 1
                loaded_nodes += 2  # approximate
    print(f"Loaded {loaded_edges} edges, {loaded_nodes} nodes "
          f"from {filepath} (jsonl)")
```

**Step 4: Run tests**

Run: `PYTHONPATH=. pytest tests/test_cli.py -v -p no:playwright --noconftest`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add graph-vis-cli.py tests/test_cli.py
git commit -m "feat: register JSONL format for file loading with styling extras

* Add .jsonl to CONVERTER_MAP
* Direct JSONL loading preserves all vis-network styling properties
* GraphClient.add_node/add_edge accept **extras for pass-through"
```

---

### Task 5: CLI — Multiline processor (`+++`/`+++format` blocks)

**Files:**

* Modify: `graph-vis-cli.py` (new MultilineProcessor class, wrap execute_command)
* Test: `tests/test_cli.py`

**Step 1: Write failing tests**

Add to `tests/test_cli.py`:

```python
from graph_vis_cli import MultilineProcessor


def test_multiline_plain_block():
    """Plain +++ block executes each line as a command."""
    c = GraphClient("127.0.0.1", 7849)
    repl = GraphREPL(c)
    commands_executed = []
    proc = MultilineProcessor(repl)

    with patch.object(c, "add_triplet", return_value={"ok": True}):
        assert proc.feed("+++") is True  # entered block
        assert proc.feed("Alice knows Bob") is True  # buffered
        assert proc.feed("Bob likes Charlie") is True  # buffered
        assert proc.feed("+++") is True  # closed + executed


def test_multiline_csv_block():
    """+++csv block feeds content through csv converter."""
    c = GraphClient("127.0.0.1", 7849)
    repl = GraphREPL(c)
    proc = MultilineProcessor(repl)

    with patch.object(c, "add_triplet", return_value={"ok": True}):
        proc.feed("+++csv")
        proc.feed("source,target,relationship")
        proc.feed("Alice,Bob,knows")
        proc.feed("+++")

    c.add_triplet.assert_called_once_with("Alice", "knows", "Bob")


def test_multiline_jsonl_block():
    """+++jsonl block feeds content through JSONL processor."""
    c = GraphClient("127.0.0.1", 7849)
    repl = GraphREPL(c)
    proc = MultilineProcessor(repl)

    with patch.object(c, "add_node", return_value={"ok": True}):
        proc.feed("+++jsonl")
        proc.feed('{"type":"node","id":"X","label":"X","color":"red"}')
        proc.feed("+++")

    c.add_node.assert_called_once_with("X", "X", color="red")


def test_multiline_not_in_block():
    """Lines outside block return False (not consumed)."""
    c = GraphClient("127.0.0.1", 7849)
    repl = GraphREPL(c)
    proc = MultilineProcessor(repl)
    assert proc.feed("Alice knows Bob") is False
    assert proc.feed("g") is False


def test_multiline_nested_not_allowed():
    """Starting +++ inside a block is treated as content."""
    c = GraphClient("127.0.0.1", 7849)
    repl = GraphREPL(c)
    proc = MultilineProcessor(repl)

    with patch.object(c, "add_triplet", return_value={"ok": True}):
        proc.feed("+++")
        # This +++ inside is just a line that will fail as a command
        proc.feed("+++")
        # Block was closed by second +++
    assert not proc.in_block
```

**Step 2: Run to verify fail**

Run: `PYTHONPATH=. pytest tests/test_cli.py::test_multiline_plain_block -v -p no:playwright --noconftest`
Expected: FAIL (ImportError — MultilineProcessor doesn't exist)

**Step 3: Implement MultilineProcessor**

Add to `graph-vis-cli.py` before `parse_args`:

```python
# Format aliases for multiline blocks
MULTILINE_FORMAT_MAP = {
    "csv": "csv",
    "ttl": "ttl", "n3": "ttl",
    "dot": "dot", "gv": "dot",
    "mermaid": "mermaid", "mmd": "mermaid",
    "jsonl": "jsonl",
}


class MultilineProcessor:
    """Accumulates lines between +++ markers and dispatches as a block."""

    def __init__(self, repl):
        self.repl = repl
        self.in_block = False
        self.block_format = None  # None = plain (execute each line)
        self.buffer = []

    def feed(self, line):
        """Process a line. Returns True if consumed (in block or block marker)."""
        stripped = line.strip()

        # Check for +++ open/close marker
        if stripped == "+++" or (stripped.startswith("+++") and not self.in_block):
            if self.in_block:
                # Closing marker
                self._flush()
                self.in_block = False
                self.block_format = None
                self.buffer = []
                return True
            else:
                # Opening marker — check for format suffix
                fmt_suffix = stripped[3:].strip().lower()
                if fmt_suffix and fmt_suffix not in MULTILINE_FORMAT_MAP:
                    return False  # Not a valid block opener
                self.in_block = True
                self.block_format = MULTILINE_FORMAT_MAP.get(fmt_suffix)
                self.buffer = []
                return True

        if self.in_block:
            self.buffer.append(line)
            return True

        return False  # Not in block, not consumed

    def _flush(self):
        """Process accumulated block content."""
        if not self.buffer:
            return

        if self.block_format is None:
            # Plain mode: execute each line as a command
            for line in self.buffer:
                execute_command(self.repl, line)
        elif self.block_format == "jsonl":
            self._flush_jsonl()
        else:
            self._flush_converter()

    def _flush_jsonl(self):
        """Process JSONL block content directly."""
        text = "\n".join(self.buffer)
        self.repl._load_jsonl_text(text)

    def _flush_converter(self):
        """Run block content through a converter subprocess."""
        fmt = self.block_format
        # Map format name to converter + appropriate input handling
        converter_name = {
            "csv": "csv2graph", "ttl": "ttl2graph",
            "dot": "dot2graph", "mermaid": "mermaid2graph",
        }[fmt]
        script_dir = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "scripts", "converters", converter_name,
            f"{converter_name}.py",
        )
        if not os.path.isfile(script_dir):
            print(f"Converter not found: {script_dir}")
            return
        text = "\n".join(self.buffer) + "\n"
        try:
            result = subprocess.run(
                [sys.executable, script_dir],
                input=text, capture_output=True, text=True, timeout=30,
            )
            if result.returncode != 0:
                print(f"Converter error: {result.stderr}")
                return
            ext = {"csv": ".csv", "ttl": ".ttl", "dot": ".dot",
                   "mermaid": ".mermaid"}[fmt]
            self.repl._load_intermediate(result.stdout, f"<block:{fmt}>", ext)
        except subprocess.TimeoutExpired:
            print("Converter timed out (30s)")
```

Also add `_load_jsonl_text` helper to `GraphREPL`:

```python
def _load_jsonl_text(self, text):
    """Load JSONL from a text string (for multiline blocks)."""
    import json as _json
    loaded_nodes = 0
    loaded_edges = 0
    for line in text.split("\n"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        obj = _json.loads(line)
        typ = obj.get("type")
        if typ == "node":
            node_id = obj["id"]
            label = obj.get("label", node_id)
            extras = {k: v for k, v in obj.items()
                      if k not in ("type", "id", "label")}
            self.client.add_node(node_id, label, **extras)
            loaded_nodes += 1
        elif typ == "edge":
            frm, to = obj["from"], obj["to"]
            label = obj.get("label", "")
            extras = {k: v for k, v in obj.items()
                      if k not in ("type", "from", "to", "label", "id")}
            if "id" in obj:
                extras["id"] = obj["id"]
            self.client.add_edge(frm, to, label, **extras)
            loaded_edges += 1
        elif typ == "triplet":
            self.client.add_triplet(
                obj["subject"], obj["predicate"], obj["object"])
            loaded_edges += 1
    if loaded_nodes or loaded_edges:
        print(f"Loaded {loaded_edges} edges from multiline jsonl block")
```

Update `execute_command` to use MultilineProcessor (via a wrapper):

```python
def execute_commands(repl, lines):
    """Execute a sequence of command lines, handling multiline blocks."""
    proc = MultilineProcessor(repl)
    for line in lines:
        if not proc.feed(line.rstrip("\n") if isinstance(line, str) else line):
            execute_command(repl, line)
    if proc.in_block:
        print("Warning: unterminated +++ block")
```

Update `main()` to use `execute_commands` instead of looping `execute_command`:

```python
if args.commands:
    execute_commands(repl, args.commands)
elif args.input:
    with open(args.input) as f:
        execute_commands(repl, f)
elif args.stdin or (not args.commands and not args.repl):
    if not sys.stdin.isatty() or args.stdin:
        execute_commands(repl, sys.stdin)
    elif not args.repl:
        args.repl = True
```

For REPL mode, integrate MultilineProcessor into the REPL loop. Add to `GraphREPL.__init__`:

```python
self._multiline = MultilineProcessor(self)
```

Override `onecmd` in `GraphREPL`:

```python
def onecmd(self, line):
    if self._multiline.feed(line):
        return False
    return super().onecmd(line)
```

And update the prompt dynamically:

```python
def precmd(self, line):
    if self._multiline.in_block:
        return line  # Will be handled by onecmd's multiline check
    return line
```

Update prompt in `postcmd`:

```python
def postcmd(self, stop, line):
    if self._multiline.in_block:
        self.prompt = f"  {self._multiline.block_format or 'block'}> "
    else:
        self.prompt = f"graph@{self.client.base_url.split('//')[1]}> "
    return stop
```

**Step 4: Run tests**

Run: `PYTHONPATH=. pytest tests/test_cli.py -v -p no:playwright --noconftest`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add graph-vis-cli.py tests/test_cli.py
git commit -m "feat: add multiline block mode (+++/+++format)

* MultilineProcessor handles +++ open/close markers
* Plain blocks execute each line as a command
* Format blocks (+++csv, +++jsonl, etc.) feed through converters
* Works in REPL, stdin, file input, and positional args
* REPL prompt changes to indicate block mode"
```

---

### Task 6: Example files

**Files:**

* Create: `examples/styled-graph.jsonl`
* Create: `examples/multiline-demo.txt` (command file showing +++ blocks)

**Step 1: Create styled-graph.jsonl**

```jsonl
{"type":"node","id":"Server","label":"API Server","color":{"background":"#4CAF50","border":"#388E3C"},"shape":"box","font":{"color":"white","size":16}}
{"type":"node","id":"DB","label":"Database","color":{"background":"#2196F3","border":"#1565C0"},"shape":"database","font":{"color":"white","size":16}}
{"type":"node","id":"Cache","label":"Redis Cache","color":{"background":"#FF9800","border":"#E65100"},"shape":"diamond","font":{"size":14}}
{"type":"node","id":"Client","label":"Web Client","color":{"background":"#9C27B0","border":"#6A1B9A"},"shape":"circle","font":{"color":"white","size":14}}
{"type":"node","id":"Worker","label":"Background Worker","color":{"background":"#607D8B","border":"#37474F"},"shape":"box","font":{"color":"white","size":14}}
{"type":"edge","from":"Client","to":"Server","label":"HTTP/REST","color":{"color":"#4CAF50"},"width":3}
{"type":"edge","from":"Server","to":"DB","label":"queries","color":{"color":"#2196F3"},"width":2}
{"type":"edge","from":"Server","to":"Cache","label":"reads/writes","color":{"color":"#FF9800"},"width":2,"dashes":true}
{"type":"edge","from":"Server","to":"Worker","label":"enqueues","color":{"color":"#607D8B"},"width":1,"dashes":[5,5]}
{"type":"edge","from":"Worker","to":"DB","label":"writes","color":{"color":"#795548"},"width":1}
```

**Step 2: Create multiline-demo.txt**

```text
# Multiline block demo — use with: ./graph-vis-cli.py -i examples/multiline-demo.txt

# Plain block: each line is a command
+++
Alice knows Bob
Bob knows Charlie
Charlie knows Alice
+++

# CSV block
+++csv
source,target,relationship
Server,Database,queries
Server,Cache,reads
Cache,Database,syncs
+++

# JSONL block with styling
+++jsonl
{"type":"node","id":"HQ","label":"Headquarters","color":"#ff0000","shape":"star"}
{"type":"edge","from":"HQ","to":"Server","label":"manages","width":3}
+++

# Show the result
g
```

**Step 3: Commit**

```bash
git add examples/styled-graph.jsonl examples/multiline-demo.txt
git commit -m "docs: add JSONL and multiline block example files

* styled-graph.jsonl: server architecture with vis-network styling
* multiline-demo.txt: demonstrates +++/+++csv/+++jsonl blocks"
```

---

### Task 7: Update README and help text

**Files:**

* Modify: `graph-vis-cli.README.md`
* Modify: `graph-vis-cli.py` (help text in do_help and module docstring)
* Modify: `AGENTS.md`

**Step 1: Update graph-vis-cli.README.md**

Add after the "Commands" table section:

```markdown
## Multiline Blocks

Use `+++` markers to input multiple lines as a block:

### Plain block (each line is a command)

```
+++
Alice knows Bob
Bob likes Charlie
Charlie trusts Alice
+++
```

### Format blocks (content parsed as that format)

```
+++csv
source,target,relationship
Alice,Bob,knows
Bob,Charlie,likes
+++

+++jsonl
{"type":"node","id":"HQ","label":"HQ","color":"red","shape":"star"}
{"type":"edge","from":"HQ","to":"Server","label":"manages","width":3}
+++

+++ttl
@prefix : <http://example.org/> .
:Alice :knows :Bob .
+++
```

Supported formats: `csv`, `ttl`/`n3`, `dot`/`gv`, `mermaid`/`mmd`, `jsonl`

In REPL mode, the prompt changes to show you're inside a block.
```

Add JSONL to the Load Format Support table.

Add to the examples section:

```markdown
./graph-vis-cli.py -l examples/styled-graph.jsonl "g"
./graph-vis-cli.py -i examples/multiline-demo.txt
```

Update `do_help` in CLI to mention multiline blocks and 2-word edges.

Update AGENTS.md CLI section to mention JSONL and multiline.

**Step 2: Commit**

```bash
git add graph-vis-cli.README.md graph-vis-cli.py AGENTS.md
git commit -m "docs: document multiline blocks, JSONL format, and labelless edges"
```

---

### Task 8: Final integration test

**Step 1: Run all tests**

```bash
PYTHONPATH=. pytest tests/test_api.py tests/test_ws.py -v -p no:playwright
PYTHONPATH=. pytest tests/test_cli.py -v -p no:playwright --noconftest
PYTHONPATH=. pytest tests/test_jsonl2graph.py -v
```

Expected: ALL PASS

**Step 2: Manual smoke test**

```bash
# Load JSONL example
./graph-vis-cli.py -l examples/styled-graph.jsonl "g"

# Multiline demo
./graph-vis-cli.py -i examples/multiline-demo.txt

# Labelless edge
echo "Alice Bob" | ./graph-vis-cli.py
```
