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
    ./graph-vis-cli.py -l data.csv --repl             # load file, then REPL
    ./graph-vis-cli.py --repl                         # interactive REPL
    ./graph-vis-cli.py help                           # show help

Environment
-----------
    GRAPH_VIS_HOST   Server IP (default: 127.0.0.1)
    GRAPH_VIS_PORT   Server port (default: 7849)

Commands
--------
    add / a          <subj> <pred> <obj>   Add triplet (default for 3 bare words)
    add-node / an    <id>                  Add single node
    add-edge / ae    <from> <pred> <to>    Add edge
    del / d / rm     <id>                  Delete node (cascade edges)
    del-edge / de    <edge-id>             Delete edge
    list / ls / l    [nodes|edges]         List graph contents
    graph / g                              Full graph summary
    Load / L         <filepath>            Load graph from file
    help / ? / h                           Show command reference
    quit / exit / q                        Exit REPL
"""

import argparse
import cmd
import json
import os
import subprocess
import sys
import time
import urllib.request
import urllib.error


class GraphClient:
    """HTTP client for the graph-vis REST API using only stdlib."""

    def __init__(self, host, port, verbosity=0):
        self.base_url = f"http://{host}:{port}"
        self.verbosity = verbosity

    def _request(self, method, path, data=None):
        url = f"{self.base_url}{path}"
        body = json.dumps(data).encode() if data else None
        req = urllib.request.Request(url, data=body, method=method)
        if body:
            req.add_header("Content-Type", "application/json")

        t0 = time.time()
        if self.verbosity >= 1:
            print(f"  -> {method} {url}", file=sys.stderr)
        if self.verbosity >= 3 and body:
            print(f"  -> body: {body.decode()}", file=sys.stderr)

        try:
            with urllib.request.urlopen(req) as resp:
                elapsed = time.time() - t0
                resp_body = resp.read().decode()
                if self.verbosity >= 1:
                    print(f"  <- {resp.status} ({elapsed:.3f}s)", file=sys.stderr)
                if self.verbosity >= 2:
                    print(f"  <- headers: {dict(resp.headers)}", file=sys.stderr)
                if self.verbosity >= 3:
                    print(f"  <- body: {resp_body}", file=sys.stderr)
                return json.loads(resp_body)
        except urllib.error.URLError as e:
            print(f"Error: {e}", file=sys.stderr)
            return None

    def get_graph(self):
        return self._request("GET", "/api/graph")

    def add_node(self, node_id, label=None):
        return self._request("POST", "/api/add-node",
                             {"id": node_id, "label": label or node_id})

    def remove_node(self, node_id):
        return self._request("POST", "/api/remove-node", {"id": node_id})

    def add_edge(self, frm, to, label):
        return self._request("POST", "/api/add-edge",
                             {"from": frm, "to": to, "label": label})

    def remove_edge(self, edge_id):
        return self._request("POST", "/api/remove-edge", {"id": edge_id})

    def add_triplet(self, subject, predicate, obj):
        return self._request("POST", "/api/add-triplet",
                             {"subject": subject, "predicate": predicate,
                              "object": obj})


# Converter extension mapping
CONVERTER_MAP = {
    ".csv": "csv2graph",
    ".ttl": "ttl2graph",
    ".n3": "ttl2graph",
    ".dot": "dot2graph",
    ".gv": "dot2graph",
    ".mermaid": "mermaid2graph",
    ".mmd": "mermaid2graph",
}


class GraphREPL(cmd.Cmd):
    """Interactive REPL for graph-vis server."""

    def __init__(self, client):
        super().__init__()
        self.client = client
        self.prompt = f"graph@{client.base_url.split('//')[1]}> "

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
        """add <subject> <predicate> <object> — Add a triplet (shortcut: a)"""
        parts = arg.split()
        if len(parts) != 3:
            print("Usage: add <subject> <predicate> <object>")
            return
        r = self.client.add_triplet(*parts)
        if r and r.get("ok"):
            print(f"Added: {parts[0]} —{parts[1]}→ {parts[2]}")

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
        nn, ne = len(graph["nodes"]), len(graph["edges"])
        print(f"Graph: {nn} nodes, {ne} edges")
        if nn > 0:
            self._print_nodes(graph["nodes"])
        if ne > 0:
            self._print_edges(graph["edges"])

    do_g = do_graph

    def do_Load(self, arg):
        """Load <filepath> — Load graph from file (shortcut: L)"""
        filepath = arg.strip()
        if not filepath:
            print("Usage: Load <filepath>")
            return
        if not os.path.isfile(filepath):
            print(f"File not found: {filepath}")
            return
        _, ext = os.path.splitext(filepath)
        ext = ext.lower()
        converter_name = CONVERTER_MAP.get(ext)
        if not converter_name:
            print(f"Unsupported format: {ext}")
            print(f"Supported: {', '.join(sorted(set(CONVERTER_MAP.values())))}")
            return
        # Find converter script
        script_dir = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "scripts", "converters", converter_name,
            f"{converter_name}.py",
        )
        if not os.path.isfile(script_dir):
            print(f"Converter not found: {script_dir}")
            return
        try:
            result = subprocess.run(
                [sys.executable, script_dir, filepath],
                capture_output=True, text=True, timeout=30,
            )
            if result.returncode != 0:
                print(f"Converter error: {result.stderr}")
                return
            self._load_intermediate(result.stdout, filepath, ext)
        except subprocess.TimeoutExpired:
            print("Converter timed out (30s)")

    do_L = do_Load

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
  add / a / +      <subj> <pred> <obj>   Add triplet
  add-node / an    <id>                  Add single node
  add-edge / ae    <from> <pred> <to>    Add edge
  del / d / rm / - <id>                  Delete node (cascade)
  del-edge / de    <edge-id>             Delete edge
  list / ls / l    [nodes|edges]         List graph contents
  graph / g                              Full graph summary
  Load / L         <filepath>            Load from file
  help / ? / h                           Show this help
  quit / exit / q                        Exit

Shorthand: 3 bare words = add triplet (e.g. "Alice knows Bob")
Formats for Load: .csv .ttl .n3 .dot .gv .mermaid .mmd""")

    do_h = do_help

    def default(self, line):
        """Handle unrecognized commands — 3 bare words become add triplet."""
        parts = line.split()
        if parts and parts[0] == '+':
            self.do_add(' '.join(parts[1:]))
        elif parts and parts[0] == '-':
            self.do_del(' '.join(parts[1:]))
        elif len(parts) == 3:
            self.do_add(line)
        else:
            print(f"Unknown command: {line.split()[0] if parts else ''}")
            print("Type 'help' for commands.")

    def emptyline(self):
        pass  # Don't repeat last command


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="CLI for the graph visualization server. "
                    "Non-interactive by default (reads stdin). Use --repl for interactive mode.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  echo "Alice knows Bob" | %(prog)s            Pipe commands (default)
  %(prog)s "Alice knows Bob" "g"               Positional commands
  %(prog)s -l data.csv "g"                     Load file, run command
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
    parser.add_argument("-v", "--verbose", action="count", default=0,
                        help="Increase verbosity (-v, -vv, -vvv)")

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

    client = GraphClient(args.host, args.port, args.verbose)
    repl = GraphREPL(client)

    # Step 1: Load files
    if args.load:
        load_files(repl, args.load)

    # Step 2: Execute commands from chosen input mode
    if args.commands:
        # Positional command args
        for cmd_line in args.commands:
            execute_command(repl, cmd_line)
    elif args.input:
        # Read from file
        with open(args.input) as f:
            for line in f:
                execute_command(repl, line)
    elif args.stdin or (not args.commands and not args.repl):
        # Read from stdin (explicit --stdin or default when no args)
        if not sys.stdin.isatty() or args.stdin:
            for line in sys.stdin:
                execute_command(repl, line)
        elif not args.repl:
            # TTY with no args and no --repl — show help hint and enter REPL
            args.repl = True

    # Step 3: Enter REPL if requested
    if args.repl:
        try:
            repl.cmdloop()
        except KeyboardInterrupt:
            print("\nBye.")


if __name__ == "__main__":
    main()
