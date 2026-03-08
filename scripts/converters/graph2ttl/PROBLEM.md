# graph2ttl

## Problem Statement

Given a graph in JSON format (as returned by the `/api/graph` endpoint), convert
it to an RDF Turtle (.ttl) document. Each edge in the graph becomes an RDF
triple, where the source node is the subject, the edge label is the predicate,
and the target node is the object.

Turtle is a triple-centric format: only edges are represented. Nodes without
edges, visual styling properties, and other extras are silently dropped. This
is a lossy export by design.

## Input Format

A JSON object with `nodes` and `edges` arrays:

```json
{
  "nodes": [
    {"id": "Alice", "label": "Alice"},
    {"id": "Bob", "label": "Bob"}
  ],
  "edges": [
    {"id": "e1", "from": "Alice", "to": "Bob", "label": "knows"}
  ]
}
```

## Output Format

An RDF Turtle document using `ex:` as the namespace prefix:

```turtle
@prefix ex: <http://example.org/> .

ex:Alice ex:knows ex:Bob .
```

## Rules

* Each edge `(from, to, label)` becomes a triple `ex:<from> ex:<label> ex:<to> .`
* Node IDs and edge labels are sanitized: spaces become underscores, special
  characters are percent-encoded
* Edges without a label use `ex:relatedTo` as the default predicate
* Triples are sorted lexicographically for deterministic output
* Nodes that have no edges are **not** included (TTL is triple-centric)
* An empty graph (no edges) produces only the prefix declaration
* Styling extras (color, width, shape, etc.) are silently dropped

## Examples

### Simple Graph

**Input** (`simple.json`):

```json
{"nodes": [{"id": "Alice"}, {"id": "Bob"}, {"id": "Charlie"}],
 "edges": [{"from": "Alice", "to": "Bob", "label": "knows"},
           {"from": "Bob", "to": "Charlie", "label": "likes"}]}
```

**Output:**

```turtle
@prefix ex: <http://example.org/> .

ex:Alice ex:knows ex:Bob .
ex:Bob ex:likes ex:Charlie .
```

### Empty Graph

**Input** (`empty.json`):

```json
{"nodes": [], "edges": []}
```

**Output:**

```turtle
@prefix ex: <http://example.org/> .

```
