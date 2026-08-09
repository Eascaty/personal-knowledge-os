"""Strict stepwise taxonomy classification."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from ..ai import KnowledgeExtraction

@dataclass(frozen=True)
class Classification:
    node_id: str
    path_ids: List[str]
    path_names: List[str]
    confidence: float
    method: str

def _node_maps(
    root: Mapping[str, Any],
) -> Tuple[Dict[str, Mapping[str, Any]], Dict[str, Optional[str]]]:
    nodes: Dict[str, Mapping[str, Any]] = {}
    parents: Dict[str, Optional[str]] = {}

    def visit(node: Mapping[str, Any], parent: Optional[str]) -> None:
        node_id = str(node["id"])
        nodes[node_id] = node
        parents[node_id] = parent
        for child in node.get("children", []):
            visit(child, node_id)

    visit(root, None)
    return nodes, parents


def _valid_suggested_path(
    path_ids: Sequence[str], taxonomy: Mapping[str, Any]
) -> Optional[List[str]]:
    if not path_ids:
        return None
    nodes, parents = _node_maps(taxonomy["root"])
    candidate = list(path_ids)
    root_id = str(taxonomy["root"]["id"])
    if candidate[0] != root_id:
        candidate.insert(0, root_id)
    if any(node_id not in nodes for node_id in candidate):
        return None
    for parent, child in zip(candidate, candidate[1:]):
        if parents[child] != parent:
            return None
    return candidate


def _branch_terms(node: Mapping[str, Any]) -> List[Tuple[str, float]]:
    result: List[Tuple[str, float]] = []

    def visit(value: Mapping[str, Any], depth: int) -> None:
        weight = 1.0 / (1 + depth * 0.25)
        result.append((str(value.get("name", "")), 3.0 * weight))
        for keyword in value.get("keywords", []):
            result.append((str(keyword), 1.0 * weight))
        for child in value.get("children", []):
            visit(child, depth + 1)

    visit(node, 0)
    return result


def _term_score(haystack: str, term: str, weight: float) -> float:
    cleaned = term.strip().casefold()
    if len(cleaned) < 2:
        return 0.0
    if re.fullmatch(r"[a-z0-9+.#_-]+(?: [a-z0-9+.#_-]+)*", cleaned):
        # Avoid treating the short token "AI" inside "email" as an AI signal.
        pattern = (
            r"(?<![a-z0-9])"
            + re.escape(cleaned)
            + r"(?![a-z0-9])"
        )
        count = len(re.findall(pattern, haystack))
    else:
        count = haystack.count(cleaned)
    if not count:
        return 0.0
    return weight * min(count, 5)


def classify_document(
    *,
    title: str,
    body: str,
    extraction: KnowledgeExtraction,
    taxonomy: Mapping[str, Any],
) -> Classification:
    root = taxonomy["root"]
    nodes, _parents = _node_maps(root)
    suggested = _valid_suggested_path(
        extraction.suggested_path_ids, taxonomy
    )
    uncertain_id = str(taxonomy["rules"]["uncertain_destination"])
    if suggested and suggested[-1] != str(root["id"]):
        names = [str(nodes[node_id]["name"]) for node_id in suggested]
        return Classification(
            node_id=suggested[-1],
            path_ids=suggested,
            path_names=names,
            confidence=0.9,
            method="adapter-strict-path",
        )

    haystack = "\n".join(
        [title, body[:100000], " ".join(extraction.tags)]
    ).casefold()
    current = root
    path_ids = [str(root["id"])]
    path_names = [str(root["name"])]
    confidences: List[float] = []
    while current.get("children"):
        children = [
            child
            for child in current.get("children", [])
            if str(child["id"]) != uncertain_id
        ]
        scored: List[Tuple[float, int, Mapping[str, Any]]] = []
        for order, child in enumerate(children):
            score = sum(
                _term_score(haystack, term, weight)
                for term, weight in _branch_terms(child)
            )
            scored.append((score, -order, child))
        scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
        if not scored or scored[0][0] <= 0:
            break
        best_score, _order, best = scored[0]
        second_score = scored[1][0] if len(scored) > 1 else 0.0
        confidence = best_score / (best_score + second_score + 1.0)
        confidences.append(confidence)
        current = best
        path_ids.append(str(current["id"]))
        path_names.append(str(current["name"]))
    if len(path_ids) == 1:
        uncertain = nodes[uncertain_id]
        return Classification(
            node_id=uncertain_id,
            path_ids=[str(root["id"]), uncertain_id],
            path_names=[str(root["name"]), str(uncertain["name"])],
            confidence=0.0,
            method="rules-uncertain",
        )
    return Classification(
        node_id=path_ids[-1],
        path_ids=path_ids,
        path_names=path_names,
        confidence=min(confidences) if confidences else 0.0,
        method="rules-stepwise",
    )


