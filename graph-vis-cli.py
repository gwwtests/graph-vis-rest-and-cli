#!/usr/bin/env python3
"""graph-vis-cli — CLI for the graph visualization server.

Connects to a graph-vis server via REST API. Non-interactive by default
(reads from stdin for easy piping). Use --repl for interactive mode.

Usage
-----
    echo "Alice knows Bob" | ./graph-vis-cli.py       # pipe commands (default)
    ./graph-vis-cli.py "Alice knows Bob" "g"          # positional commands
    ./graph-vis-cli.py -i commands.txt                # read from file
    ./graph-vis-cli.py -l data.csv "g"                # load file, then command
    ./graph-vis-cli.py -l data.csv -s out.jsonl       # load file, store result
    ./graph-vis-cli.py -l data.csv --repl             # load file, then REPL
    ./graph-vis-cli.py --repl                         # interactive REPL
    ./graph-vis-cli.py help                           # show help

Environment
-----------
    GRAPH_VIS_HOST      Server IP (default: 127.0.0.1)
    GRAPH_VIS_PORT      Server port (default: 7849)
    GRAPH_VIS_TIMEOUT   Per-request timeout in seconds (default: 10)

Exit codes
----------
    0   All requested work succeeded.
    1   At least one command / load / store failed (e.g. HTTP error,
        converter error, missing file).
    2   Every request was refused — the server is unreachable.

Commands
--------
    add / a / +      <from> <to>           Add labelless edge (2 bare words)
    add / a / +      <subj> <pred> <obj>   Add triplet (3 bare words)
    add-node / an    <id>                  Add single node
    add-edge / ae    <from> <pred> <to>    Add edge
    del / d / rm     <id>                  Delete node (cascade edges)
    del-edge / de    <edge-id>             Delete edge
    list / ls / l    [nodes|edges]         List graph contents
    graph / g                              Full graph summary
    clear                                  Clear graph to empty state
    Load / L         <filepath>            Load graph from file (.csv .jsonl etc.)
    store / Store / S <filepath>           Save graph to file (.jsonl .csv .dot .ttl .mermaid)
    +++[format]      ...  +++              Multiline block (plain/csv/jsonl/ttl/dot/mermaid)
    help / ? / h                           Show command reference
    quit / exit / q                        Exit REPL
"""

import argparse
import cmd
import errno
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request


class GraphClient:
    """HTTP client for the graph-vis REST API using only stdlib."""

    def __init__(self, host, port, verbosity=0, timeout=10.0):
        self.base_url = f"http://{host}:{port}"
        self.verbosity = verbosity
        self.timeout = timeout
        # Failure accounting for process exit codes.
        self.requests = 0            # total requests attempted
        self.failures = 0            # requests that did not return 2xx JSON
        self.connection_refused = 0  # subset of failures: server unreachable

    def _request(self, method, path, data=None):
        url = f"{self.base_url}{path}"
        body = json.dumps(data).encode() if data else None
        req = urllib.request.Request(url, data=body, method=method)
        if body:
            req.add_header("Content-Type", "application/json")

        t0 = time.time()
        self.requests += 1
        if self.verbosity >= 1:
            print(f"  -> {method} {url}", file=sys.stderr)
        if self.verbosity >= 3 and body:
            print(f"  -> body: {body.decode()}", file=sys.stderr)

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                elapsed = time.time() - t0
                resp_body = resp.read().decode()
                if self.verbosity >= 1:
                    print(f"  <- {resp.status} ({elapsed:.3f}s)", file=sys.stderr)
                if self.verbosity >= 2:
                    print(f"  <- headers: {dict(resp.headers)}", file=sys.stderr)
                if self.verbosity >= 3:
                    print(f"  <- body: {resp_body}", file=sys.stderr)
                return json.loads(resp_body)
        except urllib.error.HTTPError as e:
            # Server responded, but with a non-2xx status (e.g. 403 read-only).
            self.failures += 1
            detail = ""
            try:
                detail = e.read().decode().strip()
            except Exception:
                pass
            print(f"HTTP {e.code} {e.reason}: {method} {path}", file=sys.stderr)
            if detail:
                print(f"  {detail}", file=sys.stderr)
            return None
        except urllib.error.URLError as e:
            # Could not complete the request (connection refused, timeout, DNS).
            self.failures += 1
            reason = getattr(e, "reason", None)
            if isinstance(reason, ConnectionRefusedError) or (
                isinstance(reason, OSError) and reason.errno == errno.ECONNREFUSED
            ):
                self.connection_refused += 1
            print(f"Error: {e.reason if reason is not None else e} "
                  f"({method} {path})", file=sys.stderr)
            return None

    def get_graph(self):
        return self._request("GET", "/api/graph")

    def add_node(self, node_id, label=None, **extras):
        data = {"id": node_id, "label": label or node_id, **extras}
        return self._request("POST", "/api/add-node", data)

    def remove_node(self, node_id):
        return self._request("POST", "/api/remove-node", {"id": node_id})

    def add_edge(self, frm, to, label, **extras):
        data = {"from": frm, "to": to, "label": label, **extras}
        return self._request("POST", "/api/add-edge", data)

    def remove_edge(self, edge_id):
        return self._request("POST", "/api/remove-edge", {"id": edge_id})

    def add_triplet(self, subject, predicate, obj):
        return self._request("POST", "/api/add-triplet",
                             {"subject": subject, "predicate": predicate,
                              "object": obj})

    def clear_graph(self):
        return self._request("POST", "/api/clear")

    def screenshot(self, filename=None, **params):
        """Download screenshot from browser. Returns raw image bytes or None."""
        query = '&'.join(f'{k}={v}' for k, v in params.items()
                         if v is not None)
        url = f"{self.base_url}/api/screenshot"
        if query:
            url += '?' + urllib.parse.quote(query, safe='=&')
        req = urllib.request.Request(url)
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                data = resp.read()
                if filename:
                    with open(filename, 'wb') as f:
                        f.write(data)
                return data
        except urllib.error.HTTPError as e:
            if e.code == 503:
                return None
            raise

    def get_dom(self):
        """Get graph layout introspection data."""
        return self._request("GET", "/api/dom")

    def set_ui(self, input_visible):
        """Toggle browser UI visibility."""
        return self._request("POST", "/api/ui", {"input_visible": input_visible})


def run_converter(script_path, argv, input_text=None, timeout=60):
    """Run a format converter script, preferring its own shebang.

    Converter scripts carry PEP-723 ``uv run`` shebangs so that dependencies
    (e.g. rdflib for .ttl/.n3) resolve automatically. When the script is
    executable we invoke it directly so the shebang runs; otherwise we fall
    back to the current interpreter (which only works for stdlib converters).

    Returns a ``subprocess.CompletedProcess``. The timeout defaults to 60s
    because first-run ``uv`` dependency resolution can be slow.
    """
    if os.access(script_path, os.X_OK):
        cmd = [script_path, *argv]
    else:
        cmd = [sys.executable, script_path, *argv]
    return subprocess.run(
        cmd, input=input_text, capture_output=True, text=True, timeout=timeout,
    )


# Converter extension mapping (ingest: format → graph)
CONVERTER_MAP = {
    ".csv": "csv2graph",
    ".ttl": "ttl2graph",
    ".n3": "ttl2graph",
    ".dot": "dot2graph",
    ".gv": "dot2graph",
    ".mermaid": "mermaid2graph",
    ".mmd": "mermaid2graph",
    ".jsonl": "jsonl2graph",
}

# Export converter mapping (graph → format)
EXPORT_MAP = {
    ".csv": "graph2csv",
    ".ttl": "graph2ttl",
    ".n3": "graph2ttl",
    ".dot": "graph2dot",
    ".gv": "graph2dot",
    ".mermaid": "graph2mermaid",
    ".mmd": "graph2mermaid",
    ".jsonl": "graph2jsonl",
}


class GraphREPL(cmd.Cmd):
    """Interactive REPL for graph-vis server."""

    def __init__(self, client):
        super().__init__()
        self.client = client
        self.prompt = f"graph@{client.base_url.split('//')[1]}> "
        self._multiline = MultilineProcessor(self)
        self.json_output = False  # when True, graph/list emit raw JSON/JSONL

    def onecmd(self, line):
        if self._multiline.feed(line):
            return False
        return super().onecmd(line)

    def postcmd(self, stop, line):
        if self._multiline.in_block:
            self.prompt = f"  {self._multiline.block_format or 'block'}> "
        else:
            self.prompt = f"graph@{self.client.base_url.split('//')[1]}> "
        return stop

    def preloop(self):
        graph = self.client.get_graph()
        if graph:
            nn, ne = len(graph["nodes"]), len(graph["edges"])
            print(f"Connected to {self.client.base_url} ({nn} nodes, {ne} edges)")
        else:
            print(f"Warning: Could not connect to {self.client.base_url}")
        print("Type 'help' or '?' for commands.")

    # -- Commands ----------------------------------------------------------

    def do_add(self, arg):
        """add <from> <to> — Add labelless edge; add <subj> <pred> <obj> — Add triplet (shortcut: a)"""
        parts = arg.split()
        if len(parts) == 2:
            r = self.client.add_edge(parts[0], parts[1], "")
            if r and r.get("ok"):
                print(f"Added edge: {parts[0]} → {parts[1]}")
        elif len(parts) == 3:
            r = self.client.add_triplet(*parts)
            if r and r.get("ok"):
                print(f"Added: {parts[0]} —{parts[1]}→ {parts[2]}")
        else:
            print("Usage: add <from> <to>  OR  add <subject> <predicate> <object>")

    do_a = do_add

    def do_add_node(self, arg):
        """add-node <id> — Add a single node (shortcut: an)"""
        node_id = arg.strip()
        if not node_id:
            print("Usage: add-node <id>")
            return
        r = self.client.add_node(node_id)
        if r and r.get("ok"):
            print(f"Added node: {node_id}")

    do_an = do_add_node

    def do_add_edge(self, arg):
        """add-edge <from> <predicate> <to> — Add an edge (shortcut: ae)"""
        parts = arg.split()
        if len(parts) != 3:
            print("Usage: add-edge <from> <predicate> <to>")
            return
        r = self.client.add_edge(parts[0], parts[2], parts[1])
        if r and r.get("ok"):
            print(f"Added edge: {parts[0]} —{parts[1]}→ {parts[2]}")

    do_ae = do_add_edge

    def do_del(self, arg):
        """del <id> — Delete a node and its edges (shortcuts: d, rm, delete)"""
        node_id = arg.strip()
        if not node_id:
            print("Usage: del <id>")
            return
        r = self.client.remove_node(node_id)
        if r and r.get("ok"):
            removed = r.get("removed_edges", [])
            print(f"Deleted node: {node_id} (removed {len(removed)} edge(s))")

    do_d = do_del
    do_rm = do_del
    do_delete = do_del

    def do_del_edge(self, arg):
        """del-edge <edge-id> — Delete an edge (shortcut: de)"""
        edge_id = arg.strip()
        if not edge_id:
            print("Usage: del-edge <edge-id>")
            return
        r = self.client.remove_edge(edge_id)
        if r and r.get("ok"):
            removed = "removed" if r.get("removed") else "not found"
            print(f"Edge {edge_id}: {removed}")

    do_de = do_del_edge

    def do_list(self, arg):
        """list [nodes|edges] — List graph contents (shortcuts: ls, l)"""
        graph = self.client.get_graph()
        if not graph:
            return
        what = arg.strip().lower()
        if self.json_output:
            if what in ("", "all", "nodes", "n"):
                for n in graph["nodes"]:
                    print(json.dumps({"type": "node", **n}))
            if what in ("", "all", "edges", "e"):
                for e in graph["edges"]:
                    print(json.dumps({"type": "edge", **e}))
            return
        if what in ("", "all"):
            self._print_nodes(graph["nodes"])
            self._print_edges(graph["edges"])
        elif what in ("nodes", "n"):
            self._print_nodes(graph["nodes"])
        elif what in ("edges", "e"):
            self._print_edges(graph["edges"])
        else:
            print("Usage: list [nodes|edges]")

    do_ls = do_list
    do_l = do_list

    def _print_nodes(self, nodes):
        print(f"Nodes ({len(nodes)}):")
        for n in nodes:
            print(f"  {n['id']}")

    def _print_edges(self, edges):
        print(f"Edges ({len(edges)}):")
        for e in edges:
            print(f"  {e['id']}: {e['from']} —{e['label']}→ {e['to']}")

    def do_graph(self, arg):
        """graph — Show full graph summary (shortcut: g)"""
        graph = self.client.get_graph()
        if not graph:
            return
        if self.json_output:
            print(json.dumps(graph))
            return
        nn, ne = len(graph["nodes"]), len(graph["edges"])
        print(f"Graph: {nn} nodes, {ne} edges")
        if nn > 0:
            self._print_nodes(graph["nodes"])
        if ne > 0:
            self._print_edges(graph["edges"])

    do_g = do_graph

    def do_clear(self, arg):
        """clear — Clear graph to empty state"""
        r = self.client.clear_graph()
        if r and r.get("ok"):
            print("Graph cleared.")

    def do_screenshot(self, arg):
        """screenshot [filename] — Save graph screenshot (shortcut: ss)"""
        filename = arg.strip() or "graph.png"
        # Parse optional params from filename like: graph.png padding=0.2 format=jpeg
        parts = filename.split()
        actual_file = parts[0]
        params = {}
        for p in parts[1:]:
            if '=' in p:
                k, v = p.split('=', 1)
                params[k] = v
        data = self.client.screenshot(filename=actual_file, **params)
        if data is None:
            print("Error: No browser connected (503)")
            return
        print(f"Saved: {actual_file} ({len(data)} bytes)")

    do_ss = do_screenshot

    def do_dom(self, arg):
        """dom — Show graph DOM/layout info"""
        result = self.client.get_dom()
        if result is None:
            print("Error: No browser connected (503)")
            return
        print(json.dumps(result, indent=2))

    def do_ui(self, arg):
        """ui hide|show — Toggle input controls (shortcuts: ui off/on)"""
        arg = arg.strip().lower()
        if arg in ('hide', 'off'):
            self.client.set_ui(False)
            print("UI hidden.")
        elif arg in ('show', 'on'):
            self.client.set_ui(True)
            print("UI shown.")
        else:
            print("Usage: ui hide|show  (aliases: off/on)")

    def do_Load(self, arg):
        """Load <filepath> — Load graph from file (shortcut: L)"""
        filepath = arg.strip()
        if not filepath:
            print("Usage: Load <filepath>")
            return
        if not os.path.isfile(filepath):
            print(f"File not found: {filepath}")
            self.client.failures += 1
            return
        _, ext = os.path.splitext(filepath)
        ext = ext.lower()
        # JSONL: load directly to preserve styling extras
        if ext == ".jsonl":
            self._load_jsonl(filepath)
            return
        converter_name = CONVERTER_MAP.get(ext)
        if not converter_name:
            print(f"Unsupported format: {ext}")
            print(f"Supported: {', '.join(sorted(set(CONVERTER_MAP.values())))}")
            self.client.failures += 1
            return
        # Find converter script
        script_dir = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "scripts", "converters", converter_name,
            f"{converter_name}.py",
        )
        if not os.path.isfile(script_dir):
            print(f"Converter not found: {script_dir}")
            self.client.failures += 1
            return
        try:
            result = run_converter(script_dir, [filepath])
            if result.returncode != 0:
                print(f"Converter error: {result.stderr}")
                self.client.failures += 1
                return
            self._load_intermediate(result.stdout, filepath, ext)
        except subprocess.TimeoutExpired:
            print("Converter timed out (60s)")
            self.client.failures += 1

    do_L = do_Load

    def do_store(self, arg):
        """store <filepath> — Save graph to file (shortcuts: Store, S)"""
        filepath = arg.strip()
        if not filepath:
            print("Usage: store <filepath>")
            return
        graph = self.client.get_graph()
        if graph is None:
            return
        _, ext = os.path.splitext(filepath)
        ext = ext.lower()
        # Default to JSONL if no extension
        if not ext:
            filepath += ".jsonl"
            ext = ".jsonl"
        converter_name = EXPORT_MAP.get(ext)
        if not converter_name:
            print(f"Unsupported export format: {ext}")
            print(f"Supported: {', '.join(sorted(set(EXPORT_MAP.values())))}")
            self.client.failures += 1
            return
        # Find converter script
        script_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "scripts", "converters", converter_name,
            f"{converter_name}.py",
        )
        if not os.path.isfile(script_path):
            print(f"Converter not found: {script_path}")
            self.client.failures += 1
            return
        graph_json = json.dumps(graph)
        try:
            result = run_converter(script_path, [], input_text=graph_json)
            if result.returncode != 0:
                print(f"Converter error: {result.stderr}")
                self.client.failures += 1
                return
            with open(filepath, "w") as f:
                f.write(result.stdout)
            nn, ne = len(graph["nodes"]), len(graph["edges"])
            fmt_name = ext.lstrip(".")
            print(f"Stored {ne} edges, {nn} nodes to {filepath} ({fmt_name})")
        except subprocess.TimeoutExpired:
            print("Converter timed out (60s)")
            self.client.failures += 1

    do_Store = do_store
    do_S = do_store

    def _load_intermediate(self, text, filepath, ext):
        """Parse intermediate format and send triplets to server."""
        lines = text.strip().split("\n")
        if len(lines) < 1:
            print("Empty converter output")
            return
        header = lines[0].split()
        if len(header) != 2:
            print(f"Invalid header: {lines[0]}")
            return
        vn, en = int(header[0]), int(header[1])
        loaded_edges = 0
        loaded_nodes = set()
        for line in lines[1:]:
            parts = line.split(None, 2)
            if len(parts) == 3:
                frm, to, label = parts
                self.client.add_triplet(frm, label, to)
                loaded_nodes.update([frm, to])
                loaded_edges += 1
        fmt_name = ext.lstrip(".")
        print(f"Loaded {loaded_edges} edges, {len(loaded_nodes)} nodes "
              f"from {filepath} ({fmt_name})")

    def _process_jsonl_lines(self, lines):
        """Shared JSONL processing: parse lines and send to server."""
        loaded_nodes = 0
        loaded_edges = 0
        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            obj = json.loads(line)
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
                self.client.add_triplet(obj["subject"], obj["predicate"], obj["object"])
                loaded_edges += 1
        return loaded_nodes, loaded_edges

    def _load_jsonl(self, filepath):
        """Load JSONL file directly, preserving styling extras."""
        with open(filepath) as fh:
            loaded_nodes, loaded_edges = self._process_jsonl_lines(fh)
        print(f"Loaded {loaded_edges} edges, {loaded_nodes} nodes from {filepath} (jsonl)")

    def _load_jsonl_text(self, text):
        """Load JSONL from a text string (for multiline blocks)."""
        loaded_nodes, loaded_edges = self._process_jsonl_lines(text.split("\n"))
        if loaded_nodes or loaded_edges:
            print(f"Loaded {loaded_edges} edges from multiline jsonl block")

    def do_quit(self, arg):
        """quit — Exit the REPL (shortcuts: exit, q)"""
        print("Bye.")
        return True

    do_exit = do_quit
    do_q = do_quit
    do_EOF = do_quit  # Ctrl+D

    def do_help(self, arg):
        """help — Show command reference (shortcuts: ?, h)"""
        if arg:
            super().do_help(arg)
            return
        print("""Commands:
  add / a / +      <from> <to>            Add labelless edge
                   <subj> <pred> <obj>   Add triplet
  add-node / an    <id>                  Add single node
  add-edge / ae    <from> <pred> <to>    Add edge
  del / d / rm / - <id>                  Delete node (cascade)
  del-edge / de    <edge-id>             Delete edge
  list / ls / l    [nodes|edges]         List graph contents
  graph / g                              Full graph summary
  clear                                  Clear graph to empty state
  screenshot / ss  [filename] [k=v ...]  Save graph screenshot
  dom                                    Show graph layout info
  ui               hide|show             Toggle input controls
  Load / L         <filepath>            Load from file
  store / Store / S <filepath>           Save to file
  help / ? / h                           Show this help
  quit / exit / q                        Exit

Shorthand: 2 bare words = add labelless edge (e.g. "Alice Bob")
           3 bare words = add triplet (e.g. "Alice knows Bob")
Formats for Load:  .csv .ttl .n3 .dot .gv .mermaid .mmd .jsonl
Formats for store: .jsonl .csv .dot .gv .ttl .n3 .mermaid .mmd

Multiline blocks:
  +++              Start plain block (each line is a command)
  +++csv           Start CSV block
  +++jsonl         Start JSONL block (with styling support)
  +++ttl|dot|mermaid   Start format block
  +++              End block""")

    do_h = do_help

    def default(self, line):
        """Handle unrecognized commands — 2 bare words add labelless edge, 3 bare words add triplet."""
        parts = line.split()
        if parts and parts[0] == '+':
            self.do_add(' '.join(parts[1:]))
        elif parts and parts[0] == '-':
            self.do_del(' '.join(parts[1:]))
        elif len(parts) in (2, 3):
            self.do_add(line)
        else:
            print(f"Unknown command: {line.split()[0] if parts else ''}")
            print("Type 'help' for commands.")

    def emptyline(self):
        pass  # Don't repeat last command


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
        self.block_format = None  # None = plain (execute each line as command)
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
                self.block_format = MULTILINE_FORMAT_MAP.get(fmt_suffix)  # None for plain
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
            result = run_converter(script_dir, [], input_text=text)
            if result.returncode != 0:
                print(f"Converter error: {result.stderr}")
                return
            ext = {"csv": ".csv", "ttl": ".ttl", "dot": ".dot",
                   "mermaid": ".mermaid"}[fmt]
            self.repl._load_intermediate(result.stdout, f"<block:{fmt}>", ext)
        except subprocess.TimeoutExpired:
            print("Converter timed out (60s)")


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="CLI for the graph visualization server. "
                    "Non-interactive by default (reads stdin). Use --repl for interactive mode.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  echo "Alice knows Bob" | %(prog)s            Pipe commands (default)
  %(prog)s "Alice knows Bob" "g"               Positional commands
  %(prog)s -l data.csv "g"                     Load file, run command
  %(prog)s -l data.csv -s out.jsonl            Load file, store result
  %(prog)s -l data.csv --repl                  Load file, enter REPL
  %(prog)s --repl                              Interactive REPL
  %(prog)s help                                Show help

Environment variables:
  GRAPH_VIS_HOST    Server IP (default: 127.0.0.1)
  GRAPH_VIS_PORT    Server port (default: 7849)""",
    )
    # Connection
    parser.add_argument("--host",
                        default=os.environ.get("GRAPH_VIS_HOST", "127.0.0.1"),
                        help="Server IP (env: GRAPH_VIS_HOST, default: 127.0.0.1)")
    parser.add_argument("--port", type=int,
                        default=int(os.environ.get("GRAPH_VIS_PORT", "7849")),
                        help="Server port (env: GRAPH_VIS_PORT, default: 7849)")
    parser.add_argument("--timeout", type=float,
                        default=float(os.environ.get("GRAPH_VIS_TIMEOUT", "10")),
                        help="Per-request timeout in seconds "
                             "(env: GRAPH_VIS_TIMEOUT, default: 10)")
    parser.add_argument("-v", "--verbose", action="count", default=0,
                        help="Increase verbosity (-v, -vv, -vvv)")
    parser.add_argument("--json", action="store_true",
                        help="Emit raw JSON/JSONL for graph/list (machine-readable)")

    # Input modes
    parser.add_argument("--stdin", action="store_true",
                        help="Read commands from stdin (default when no args)")
    parser.add_argument("-i", "--input", type=str, metavar="FILE",
                        help="Read commands from file")
    parser.add_argument("--repl", action="store_true",
                        help="Enter interactive REPL mode")

    # Pre-loading
    parser.add_argument("-l", "--load", action="append", default=[],
                        metavar="FILE",
                        help="Load graph file before commands (repeatable)")

    # Post-execution store
    parser.add_argument("-s", "--store", type=str, metavar="FILE",
                        help="Save graph to file after commands (.jsonl .csv .dot .ttl .mermaid)")

    # Positional commands
    parser.add_argument("commands", nargs="*",
                        help="Commands to execute (each arg is one command)")

    return parser.parse_args(argv)


def execute_command(repl, line):
    """Execute a single command line through the REPL command processor."""
    line = line.strip()
    if not line or line.startswith("#"):
        return
    repl.onecmd(line)


def execute_commands(repl, lines):
    """Execute a sequence of command lines, handling multiline blocks."""
    proc = MultilineProcessor(repl)
    for line in lines:
        if not proc.feed(line.rstrip("\n") if isinstance(line, str) else line):
            execute_command(repl, line)
    if proc.in_block:
        print("Warning: unterminated +++ block")


def load_files(repl, files):
    """Load graph files via the Load command."""
    for filepath in files:
        repl.do_Load(filepath)


def main():
    args = parse_args()

    # Handle "help" as positional command
    if args.commands == ["help"]:
        parse_args(["--help"])
        return

    client = GraphClient(args.host, args.port, args.verbose, args.timeout)
    repl = GraphREPL(client)
    repl.json_output = args.json

    # Step 1: Load files
    if args.load:
        load_files(repl, args.load)

    # Step 2: Execute commands from chosen input mode
    if args.commands:
        execute_commands(repl, args.commands)
    elif args.input:
        with open(args.input) as f:
            execute_commands(repl, f)
    elif args.stdin:
        execute_commands(repl, sys.stdin)
    elif not args.repl:
        # No explicit commands and no --repl. Choose based on context:
        #   * piped stdin (not a TTY)      -> consume it as commands
        #   * bare TTY with no other work  -> drop into the REPL
        #   * TTY with -l/-s work queued    -> run steps and exit (no REPL)
        if not sys.stdin.isatty():
            execute_commands(repl, sys.stdin)
        elif not args.load and not args.store:
            args.repl = True

    # Step 3: Store graph if requested
    if args.store:
        repl.do_store(args.store)

    # Step 4: Enter REPL if requested
    if args.repl:
        try:
            repl.cmdloop()
        except KeyboardInterrupt:
            print("\nBye.")
        return  # interactive session: no non-zero exit for command errors

    # Step 5: Non-interactive exit codes.
    #   2 = every request was refused (server unreachable)
    #   1 = at least one command / load / store failed
    #   0 = success
    if client.requests and client.connection_refused == client.requests:
        sys.exit(2)
    if client.failures:
        sys.exit(1)


if __name__ == "__main__":
    main()
