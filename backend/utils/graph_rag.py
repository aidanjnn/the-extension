import os
import re
from pathlib import Path
from dataclasses import dataclass, field

import networkx as nx
import numpy as np


@dataclass
class SearchResult:
    file: str
    snippet: str
    score: float
    node_type: str


@dataclass
class GraphMetrics:
    nodes_traversed: int = 0
    embeddings_computed: int = 0
    query_tokens: int = 0


class CodeGraph:
    def __init__(self):
        self.graph = nx.DiGraph()
        self.embeddings: dict[str, list[float]] = {}
        self.node_content: dict[str, str] = {}
        self.metrics = GraphMetrics()

    def build_graph(self, directory: str):
        self.graph.clear()
        self.embeddings.clear()
        self.node_content.clear()

        root = Path(directory)
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            if path.suffix not in {".py", ".ts", ".tsx", ".js", ".json", ".css"}:
                continue
            if any(p in str(path) for p in ["node_modules", "__pycache__", ".git", "dist"]):
                continue

            rel = str(path.relative_to(root))
            content = path.read_text(errors="ignore")
            self.graph.add_node(rel, type="file")
            self.node_content[rel] = content

            # Extract entities and add as child nodes
            for entity_name, entity_type, snippet in self._extract_entities(content, rel):
                node_id = f"{rel}::{entity_name}"
                self.graph.add_node(node_id, type=entity_type)
                self.graph.add_edge(rel, node_id)
                self.node_content[node_id] = snippet

    def _extract_entities(self, content: str, filename: str) -> list[tuple]:
        entities = []
        if filename.endswith(".py"):
            for m in re.finditer(r"^(?:async\s+)?def\s+(\w+)\s*\(", content, re.MULTILINE):
                start = m.start()
                snippet = content[start:start+300]
                entities.append((m.group(1), "function", snippet))
            for m in re.finditer(r"^class\s+(\w+)", content, re.MULTILINE):
                start = m.start()
                snippet = content[start:start+300]
                entities.append((m.group(1), "class", snippet))
        elif filename.endswith((".ts", ".tsx", ".js")):
            for m in re.finditer(r"(?:function|const|class)\s+(\w+)", content):
                start = m.start()
                snippet = content[start:start+300]
                entities.append((m.group(1), "function", snippet))
        return entities

    def index_embeddings(self, entities: list[str] | None = None):
        from utils.config import get_embeddings
        embed_fn = get_embeddings()
        nodes = entities or list(self.node_content.keys())
        texts = [self.node_content[n] for n in nodes if n in self.node_content]
        if not texts:
            return
        vectors = embed_fn.embed_documents(texts)
        for node, vector in zip(nodes, vectors):
            self.embeddings[node] = vector
        self.metrics.embeddings_computed += len(texts)

    def search(self, query: str, top_k: int = 5) -> list[SearchResult]:
        from utils.config import get_embeddings
        if not self.embeddings:
            return self._fallback_grep(query, top_k)

        embed_fn = get_embeddings()
        query_vec = np.array(embed_fn.embed_query(query))
        self.metrics.query_tokens += len(query.split())

        scores: list[tuple[float, str]] = []
        for node, vec in self.embeddings.items():
            similarity = float(np.dot(query_vec, np.array(vec)) /
                               (np.linalg.norm(query_vec) * np.linalg.norm(vec) + 1e-9))
            scores.append((similarity, node))

        scores.sort(reverse=True)
        top_nodes = [n for _, n in scores[:top_k]]

        # BFS expansion to include related nodes
        expanded = set(top_nodes)
        for node in top_nodes:
            if node in self.graph:
                for neighbor in nx.bfs_tree(self.graph, node, depth_limit=1).nodes():
                    expanded.add(neighbor)
                    self.metrics.nodes_traversed += 1

        results = []
        for node in list(expanded)[:top_k]:
            score = next((s for s, n in scores if n == node), 0.0)
            node_type = self.graph.nodes[node].get("type", "file") if node in self.graph else "file"
            results.append(SearchResult(
                file=node,
                snippet=self.node_content.get(node, "")[:500],
                score=score,
                node_type=node_type,
            ))

        return sorted(results, key=lambda r: r.score, reverse=True)

    def _fallback_grep(self, query: str, top_k: int) -> list[SearchResult]:
        results = []
        terms = query.lower().split()
        for node, content in self.node_content.items():
            lower = content.lower()
            score = sum(1 for t in terms if t in lower) / len(terms)
            if score > 0:
                results.append(SearchResult(
                    file=node,
                    snippet=content[:500],
                    score=score,
                    node_type="file",
                ))
        return sorted(results, key=lambda r: r.score, reverse=True)[:top_k]

    def get_metrics(self) -> dict:
        return {
            "nodes_total": self.graph.number_of_nodes(),
            "edges_total": self.graph.number_of_edges(),
            "nodes_traversed": self.metrics.nodes_traversed,
            "embeddings_computed": self.metrics.embeddings_computed,
        }
