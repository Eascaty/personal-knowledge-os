"""Build a secure static knowledge website from one canonical JSON document.

The public API is :func:`build_site`.  It accepts either a mapping or a path to
JSON, validates the strict parent/child taxonomy, applies the requested
visibility policy, and atomically publishes a dependency-free static bundle.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import shutil
import struct
import tempfile
import uuid
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence, Union
from urllib.parse import urlsplit, urlunsplit


SCHEMA_VERSION = 1
VALID_VISIBILITIES = {"private", "public"}
ASSET_DIR = Path(__file__).with_name("assets")
REQUIRED_ASSETS = ("index.html", "app.js", "styles.css")


class SiteDataError(ValueError):
    """Raised when canonical site data violates the integration contract."""


@dataclass(frozen=True)
class BuildResult:
    """A compact description of a successful site build."""

    output_dir: Path
    visibility: str
    allow_indexing: bool
    node_count: int
    document_count: int
    relation_count: int
    content_digest: str


def _as_text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(value).strip()


def _as_text_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    if not isinstance(value, Sequence) or isinstance(value, (bytes, bytearray)):
        return []
    return [text for item in value if (text := _as_text(item))]


DataInput = Union[Mapping[str, Any], str, os.PathLike]


def _load_data(data_or_path: DataInput) -> dict[str, Any]:
    if isinstance(data_or_path, Mapping):
        return copy.deepcopy(dict(data_or_path))
    path = Path(data_or_path)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SiteDataError(f"{path} 不是有效 JSON：{exc}") from exc
    if not isinstance(payload, dict):
        raise SiteDataError("canonical JSON 顶层必须是对象")
    return payload


def _require_identifier(value: Any, field: str) -> str:
    identifier = _as_text(value)
    if not identifier:
        raise SiteDataError(f"{field} 不能为空")
    if len(identifier) > 200:
        raise SiteDataError(f"{field} 过长")
    return identifier


def _safe_public_url(value: Any) -> str:
    """Return a publishable HTTP(S) URL without query credentials or fragments."""

    raw = _as_text(value)
    if not raw:
        return ""
    try:
        split = urlsplit(raw)
    except ValueError:
        return ""
    if split.scheme not in {"http", "https"} or not split.hostname:
        return ""
    if split.username or split.password:
        return ""
    hostname = split.hostname
    if ":" in hostname and not hostname.startswith("["):
        hostname = f"[{hostname}]"
    netloc = hostname
    if split.port:
        netloc = f"{netloc}:{split.port}"
    # Public knowledge pages do not need tracking or signed query parameters.
    # Dropping the whole query is safer than trying to enumerate secret names.
    return urlunsplit((split.scheme, netloc, split.path, "", ""))


def _normalize_source(source: Any, visibility: str) -> dict[str, Any]:
    if isinstance(source, str):
        source = {"origin": source, "original_name": Path(source).name}
    if not isinstance(source, Mapping):
        return {}

    original_name = Path(_as_text(source.get("original_name"))).name
    public_url = _safe_public_url(source.get("public_url"))
    origin_url = _safe_public_url(source.get("origin"))
    origin = public_url or origin_url
    normalized: dict[str, Any] = {
        "kind": _as_text(source.get("kind"), "unknown"),
        "original_name": original_name,
        "origin": origin,
        "sha256": _as_text(source.get("sha256")),
    }
    if visibility == "private":
        # Local absolute paths are deliberately not shipped even in an
        # Access-protected site.  The basename above is enough to identify the
        # local source while avoiding a home-directory disclosure.
        normalized["available_locally"] = bool(
            _as_text(source.get("origin")) and not origin_url
        )
    return normalized


def _normalize_evidence(evidence: Any) -> list[dict[str, str]]:
    if not isinstance(evidence, Sequence) or isinstance(
        evidence, (str, bytes, bytearray)
    ):
        return []
    result: list[dict[str, str]] = []
    for index, item in enumerate(evidence):
        if isinstance(item, str):
            excerpt = item.strip()
            if excerpt:
                result.append(
                    {
                        "id": f"evidence-{index + 1}",
                        "excerpt": excerpt,
                        "locator": "",
                        "source_label": "",
                    }
                )
            continue
        if not isinstance(item, Mapping):
            continue
        excerpt = _as_text(item.get("excerpt") or item.get("quote"))
        if not excerpt:
            continue
        result.append(
            {
                "id": _as_text(item.get("id"), f"evidence-{index + 1}"),
                "excerpt": excerpt,
                "locator": _as_text(
                    item.get("locator")
                    or item.get("page")
                    or item.get("timestamp")
                ),
                "source_label": _as_text(
                    item.get("source_label") or item.get("source")
                ),
            }
        )
    return result


def _stable_id(prefix: str, *parts: str) -> str:
    digest = hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()[:12]
    return f"{prefix}-{digest}"


def _flatten_taxonomy(taxonomy: Mapping[str, Any]) -> tuple[str, list[dict[str, Any]]]:
    """Flatten the nested taxonomy format used by project configuration."""

    root_value = taxonomy.get("root")
    root = root_value if isinstance(root_value, Mapping) else taxonomy
    nodes: list[dict[str, Any]] = []
    used_ids: set[str] = set()

    def visit(
        raw_node: Mapping[str, Any], parent_id: Optional[str], names: list[str]
    ) -> None:
        name = _as_text(raw_node.get("name"), "未命名分类")
        raw_id = _as_text(raw_node.get("id"))
        node_id = raw_id or _stable_id("node", *names, name)
        if node_id in used_ids:
            raise SiteDataError(f"嵌套 taxonomy 中存在重复节点 ID：{node_id}")
        used_ids.add(node_id)
        nodes.append(
            {
                "id": node_id,
                "parent_id": parent_id,
                "name": name,
                "locked": bool(raw_node.get("locked", False)),
                "summary": _as_text(raw_node.get("summary")),
                "visibility": _as_text(
                    raw_node.get("visibility"), "private"
                ),
            }
        )
        child_values = raw_node.get("children", [])
        if child_values is None:
            child_values = []
        if not isinstance(child_values, list):
            raise SiteDataError(f"taxonomy 节点 {node_id} 的 children 必须是数组")
        for child in child_values:
            if not isinstance(child, Mapping):
                raise SiteDataError(f"taxonomy 节点 {node_id} 包含无效子节点")
            visit(child, node_id, [*names, name])

    visit(root, None, [])
    return nodes[0]["id"], nodes


def _path_parts(value: Any) -> list[str]:
    if isinstance(value, str):
        return [
            part.strip()
            for part in re.split(r"\s*(?:/|>|→)\s*", value)
            if part.strip()
        ]
    return _as_text_list(value)


def _resolve_node_id(
    raw_document: Mapping[str, Any],
    node_map: Mapping[str, Mapping[str, Any]],
    root_id: str,
) -> str:
    explicit = _as_text(raw_document.get("node_id"))
    if explicit:
        return explicit
    requested_path = _path_parts(raw_document.get("path"))
    if not requested_path:
        return root_id
    matches = []
    for node_id, node in node_map.items():
        path = list(node["path"])
        if path == requested_path or path[1:] == requested_path:
            matches.append(node_id)
    if len(matches) == 1:
        return matches[0]
    if not matches:
        raise SiteDataError(
            f"文档路径不存在于 taxonomy：{' / '.join(requested_path)}"
        )
    raise SiteDataError(f"文档路径不唯一：{' / '.join(requested_path)}")


def _derive_tree(
    nodes: list[dict[str, Any]], root_id: str
) -> tuple[dict[str, dict[str, Any]], dict[str, list[str]]]:
    node_map: dict[str, dict[str, Any]] = {}
    children: dict[str, list[str]] = {}
    for index, raw in enumerate(nodes):
        if not isinstance(raw, Mapping):
            raise SiteDataError(f"nodes[{index}] 必须是对象")
        node_id = _require_identifier(raw.get("id"), f"nodes[{index}].id")
        if node_id in node_map:
            raise SiteDataError(f"重复的节点 ID：{node_id}")
        parent_value = raw.get("parent_id")
        parent_id = None if parent_value in (None, "") else _as_text(parent_value)
        node_map[node_id] = {
            "id": node_id,
            "parent_id": parent_id,
            "name": _as_text(raw.get("name"), node_id),
            "locked": bool(raw.get("locked", False)),
            "summary": _as_text(raw.get("summary")),
            "visibility": (
                _as_text(raw.get("visibility"), "private")
                if _as_text(raw.get("visibility"), "private")
                in VALID_VISIBILITIES
                else "private"
            ),
        }
        if parent_id is not None:
            children.setdefault(parent_id, []).append(node_id)

    if root_id not in node_map:
        raise SiteDataError(f"根节点不存在：{root_id}")
    roots = [item["id"] for item in node_map.values() if item["parent_id"] is None]
    if roots != [root_id]:
        raise SiteDataError(
            f"专业目录必须且只能有一个根节点 {root_id}，当前根节点：{roots}"
        )
    for item in node_map.values():
        parent_id = item["parent_id"]
        if parent_id is not None and parent_id not in node_map:
            raise SiteDataError(
                f"节点 {item['id']} 引用了不存在的父节点 {parent_id}"
            )

    visited: set[str] = set()
    visiting: set[str] = set()

    def walk(node_id: str, path: list[str]) -> None:
        if node_id in visiting:
            raise SiteDataError(f"专业目录存在循环：{' / '.join(path)}")
        if node_id in visited:
            return
        visiting.add(node_id)
        item = node_map[node_id]
        item["level"] = len(path)
        item["path"] = path + [item["name"]]
        for child_id in children.get(node_id, []):
            walk(child_id, item["path"])
        visiting.remove(node_id)
        visited.add(node_id)

    walk(root_id, [])
    if len(visited) != len(node_map):
        unreachable = sorted(set(node_map) - visited)
        raise SiteDataError(f"存在未连接到根节点的分类：{', '.join(unreachable)}")
    return node_map, children


def normalize_site_data(
    data_or_path: DataInput,
    *,
    visibility: str = "private",
) -> dict[str, Any]:
    """Validate, normalize and visibility-filter canonical site data.

    Canonical input contract (schema version 1):

    - ``root``: root taxonomy node ID.
    - ``nodes``: strict tree nodes with ``id``, ``parent_id`` and ``name``.
    - ``documents``: knowledge documents with exactly one ``node_id``.
    - ``relations``: optional auxiliary node-to-node relationships.

    Extra fields are tolerated.  This lets the core evolve without coupling the
    static site to database internals.
    """

    if visibility not in VALID_VISIBILITIES:
        raise ValueError("visibility 必须是 private 或 public")
    raw = _load_data(data_or_path)
    if raw.get("schema_version") != SCHEMA_VERSION:
        raise SiteDataError(
            f"不支持的 schema_version：{raw.get('schema_version')!r}，"
            f"当前只支持 {SCHEMA_VERSION}"
        )

    raw_nodes = raw.get("nodes")
    if raw_nodes is None and isinstance(raw.get("taxonomy"), Mapping):
        inferred_root, raw_nodes = _flatten_taxonomy(raw["taxonomy"])
    else:
        inferred_root = ""
    if not isinstance(raw_nodes, list) or not raw_nodes:
        raise SiteDataError("必须提供非空 nodes 数组或嵌套 taxonomy")
    root_id = _require_identifier(
        raw.get("root") or raw.get("root_id") or inferred_root, "root"
    )
    node_map, children = _derive_tree(raw_nodes, root_id)

    raw_documents = raw.get("documents", [])
    if not isinstance(raw_documents, list):
        raise SiteDataError("documents 必须是数组")
    documents: list[dict[str, Any]] = []
    document_ids: set[str] = set()
    embedded_relations: list[dict[str, Any]] = []
    for index, raw_document in enumerate(raw_documents):
        if not isinstance(raw_document, Mapping):
            raise SiteDataError(f"documents[{index}] 必须是对象")
        node_id = _resolve_node_id(raw_document, node_map, root_id)
        doc_id = _as_text(raw_document.get("id")) or _stable_id(
            "document",
            node_id,
            _as_text(raw_document.get("title"), "未命名知识"),
            _as_text(raw_document.get("source_id")),
        )
        if doc_id in document_ids:
            raise SiteDataError(f"重复的文档 ID：{doc_id}")
        document_ids.add(doc_id)
        if node_id not in node_map:
            raise SiteDataError(f"文档 {doc_id} 引用了不存在的节点 {node_id}")
        doc_visibility = _as_text(
            raw_document.get("visibility"), "private"
        ).casefold()
        if doc_visibility not in VALID_VISIBILITIES:
            raise SiteDataError(
                f"文档 {doc_id} 的 visibility 必须是 private 或 public"
            )
        if visibility == "public" and doc_visibility != "public":
            continue

        content = _as_text(
            raw_document.get("content")
            or raw_document.get("body")
            or raw_document.get("body_markdown")
        )
        if content and not bool(raw_document.get("publish_content", True)):
            content = ""
        document = {
            "id": doc_id,
            "source_id": _as_text(raw_document.get("source_id")),
            "title": _as_text(raw_document.get("title"), "未命名知识"),
            "summary": _as_text(raw_document.get("summary")),
            "content": content,
            "key_points": _as_text_list(raw_document.get("key_points")),
            "tags": _as_text_list(raw_document.get("tags")),
            "node_id": node_id,
            "path": list(node_map[node_id]["path"]),
            "visibility": doc_visibility,
            "status": _as_text(raw_document.get("status"), "unverified"),
            "source": _normalize_source(raw_document.get("source"), visibility),
            "evidence": _normalize_evidence(raw_document.get("evidence")),
            "updated_at": _as_text(raw_document.get("updated_at")),
        }
        documents.append(document)
        document_relations = raw_document.get("relations", [])
        if isinstance(document_relations, list):
            for relation_index, relation in enumerate(document_relations):
                if not isinstance(relation, Mapping):
                    continue
                embedded = dict(relation)
                embedded.setdefault("from_node_id", node_id)
                embedded.setdefault("document_id", doc_id)
                embedded.setdefault("visibility", doc_visibility)
                embedded.setdefault(
                    "id", f"{doc_id}-relation-{relation_index + 1}"
                )
                embedded_relations.append(embedded)

    raw_relations = raw.get("relations", [])
    if not isinstance(raw_relations, list):
        raise SiteDataError("relations 必须是数组")
    raw_relations = [*raw_relations, *embedded_relations]
    allowed_document_ids = {item["id"] for item in documents}
    relations: list[dict[str, Any]] = []
    relation_ids: set[str] = set()
    for index, raw_relation in enumerate(raw_relations):
        if not isinstance(raw_relation, Mapping):
            raise SiteDataError(f"relations[{index}] 必须是对象")
        from_node_id = _require_identifier(
            raw_relation.get("from_node_id") or raw_relation.get("from_id"),
            f"relations[{index}].from_node_id",
        )
        to_node_id = _require_identifier(
            raw_relation.get("to_node_id") or raw_relation.get("to_id"),
            f"relations[{index}].to_node_id",
        )
        if from_node_id not in node_map or to_node_id not in node_map:
            raise SiteDataError(
                f"关系引用了不存在的节点：{from_node_id} → {to_node_id}"
            )
        relation_id = _as_text(
            raw_relation.get("id"), f"relation-{index + 1}"
        )
        if relation_id in relation_ids:
            raise SiteDataError(f"重复的关系 ID：{relation_id}")
        relation_ids.add(relation_id)
        document_id = _as_text(raw_relation.get("document_id"))
        relation_visibility = _as_text(
            raw_relation.get("visibility"), "private"
        ).casefold()
        if relation_visibility not in VALID_VISIBILITIES:
            relation_visibility = "private"
        if visibility == "public":
            # A public document is sufficient provenance for a derived
            # relation.  A document-less relation must itself be explicitly
            # public.
            if document_id:
                if document_id not in allowed_document_ids:
                    continue
            elif relation_visibility != "public":
                continue
        elif document_id and document_id not in document_ids:
            raise SiteDataError(
                f"关系 {relation_id} 引用了不存在的文档 {document_id}"
            )
        try:
            confidence = float(raw_relation.get("confidence", 0.0))
        except (TypeError, ValueError):
            confidence = 0.0
        relations.append(
            {
                "id": relation_id,
                "from_node_id": from_node_id,
                "to_node_id": to_node_id,
                "type": _as_text(raw_relation.get("type"), "related_to"),
                "label": _as_text(raw_relation.get("label"), "相关"),
                "document_id": document_id,
                "confidence": max(0.0, min(1.0, confidence)),
                "visibility": relation_visibility,
                "evidence_ids": _as_text_list(raw_relation.get("evidence_ids")),
            }
        )

    if visibility == "public":
        required_nodes = {root_id}
        for document in documents:
            current_id: Optional[str] = document["node_id"]
            while current_id is not None and current_id not in required_nodes:
                required_nodes.add(current_id)
                current_id = node_map[current_id]["parent_id"]
        # Only relations whose complete path already belongs to public content
        # are retained.  They must never reveal an otherwise private category.
        relations = [
            relation
            for relation in relations
            if relation["from_node_id"] in required_nodes
            and relation["to_node_id"] in required_nodes
        ]
        node_map = {
            node_id: item
            for node_id, item in node_map.items()
            if node_id in required_nodes
        }
        children = {
            parent_id: [child for child in child_ids if child in required_nodes]
            for parent_id, child_ids in children.items()
            if parent_id in required_nodes
        }

    direct_counts = {node_id: 0 for node_id in node_map}
    for document in documents:
        direct_counts[document["node_id"]] += 1

    def descendant_count(node_id: str) -> int:
        return direct_counts[node_id] + sum(
            descendant_count(child_id) for child_id in children.get(node_id, [])
        )

    nodes: list[dict[str, Any]] = []
    for node_id, item in node_map.items():
        normalized_node = dict(item)
        normalized_node["children"] = list(children.get(node_id, []))
        normalized_node["direct_document_count"] = direct_counts[node_id]
        normalized_node["document_count"] = descendant_count(node_id)
        nodes.append(normalized_node)

    site = raw.get("site") if isinstance(raw.get("site"), Mapping) else {}
    declared_visibility = _as_text(raw.get("visibility"))
    result = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": _as_text(raw.get("generated_at")),
        "site": {
            "title": _as_text(site.get("title"), "我的知识体系"),
            "description": _as_text(
                site.get("description"), "按专业母子链路组织的个人知识网络"
            ),
            "language": _as_text(site.get("language"), "zh-CN"),
            "visibility": visibility or declared_visibility,
        },
        "root": root_id,
        "nodes": nodes,
        "documents": documents,
        "relations": relations,
        "stats": {
            "node_count": len(nodes),
            "document_count": len(documents),
            "relation_count": len(relations),
            **(
                dict(raw.get("stats", {}))
                if isinstance(raw.get("stats"), Mapping)
                else {}
            ),
        },
    }
    # These are authoritative after filtering, so overwrite any supplied stats.
    result["stats"].update(
        {
            "node_count": len(nodes),
            "document_count": len(documents),
            "relation_count": len(relations),
        }
    )
    return result


def _taxonomy_payload(data: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": data["schema_version"],
        "generated_at": data["generated_at"],
        "root": data["root"],
        "nodes": [
            {
                key: node[key]
                for key in (
                    "id",
                    "parent_id",
                    "name",
                    "level",
                    "path",
                    "locked",
                    "summary",
                    "children",
                    "direct_document_count",
                    "document_count",
                )
            }
            for node in data["nodes"]
        ],
    }


def _search_payload(data: Mapping[str, Any]) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    for node in data["nodes"]:
        items.append(
            {
                "id": node["id"],
                "type": "node",
                "node_id": node["id"],
                "title": node["name"],
                "path": node["path"],
                "summary": node["summary"],
                "tags": [],
                "updated_at": "",
                "search_text": " ".join(
                    [*node["path"], node["summary"]]
                ).casefold(),
            }
        )
    for document in data["documents"]:
        searchable = [
            document["title"],
            document["summary"],
            document["content"],
            *document["key_points"],
            *document["tags"],
            *document["path"],
            *[evidence["excerpt"] for evidence in document["evidence"]],
        ]
        items.append(
            {
                "id": document["id"],
                "type": "document",
                "node_id": document["node_id"],
                "title": document["title"],
                "path": document["path"],
                "summary": document["summary"],
                "tags": document["tags"],
                "updated_at": document["updated_at"],
                "search_text": " ".join(searchable).casefold(),
            }
        )
    return {
        "schema_version": data["schema_version"],
        "generated_at": data["generated_at"],
        "items": items,
    }


def _graph_payload(data: Mapping[str, Any]) -> dict[str, Any]:
    nodes = [
        {
            "id": node["id"],
            "name": node["name"],
            "path": node["path"],
            "level": node["level"],
            "document_count": node["document_count"],
        }
        for node in data["nodes"]
    ]
    tree_edges = [
        {
            "id": f"tree:{node['parent_id']}:{node['id']}",
            "from": node["parent_id"],
            "to": node["id"],
            "type": "parent_of",
        }
        for node in data["nodes"]
        if node["parent_id"] is not None
    ]
    relation_edges = [
        {
            "id": relation["id"],
            "from": relation["from_node_id"],
            "to": relation["to_node_id"],
            "type": relation["type"],
            "label": relation["label"],
            "document_id": relation["document_id"],
            "confidence": relation["confidence"],
            "evidence_ids": relation["evidence_ids"],
        }
        for relation in data["relations"]
    ]
    return {
        "schema_version": data["schema_version"],
        "generated_at": data["generated_at"],
        "nodes": nodes,
        "tree_edges": tree_edges,
        "relation_edges": relation_edges,
    }


def _json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    ).encode("utf-8")


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_json_bytes(value))


def _png_chunk(kind: bytes, payload: bytes) -> bytes:
    return (
        struct.pack(">I", len(payload))
        + kind
        + payload
        + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)
    )


def _make_icon(size: int) -> bytes:
    """Generate a small geometric RGBA PNG without an image dependency."""

    rows = []
    for y in range(size):
        row = bytearray([0])
        for x in range(size):
            nx = x / max(1, size - 1)
            ny = y / max(1, size - 1)
            red = int(20 + 24 * nx)
            green = int(31 + 31 * ny)
            blue = int(49 + 25 * (1 - nx))
            # Three warm parent/child nodes joined by a subtle diagonal.
            radius = size * 0.105
            centers = (
                (size * 0.31, size * 0.29),
                (size * 0.52, size * 0.51),
                (size * 0.72, size * 0.72),
            )
            on_node = any(
                (x - cx) ** 2 + (y - cy) ** 2 <= radius**2
                for cx, cy in centers
            )
            on_link = abs((y - x) - size * 0.01) < size * 0.027
            if on_node:
                red, green, blue = 240, 180, 93
            elif on_link and size * 0.25 < x < size * 0.78:
                red, green, blue = 92, 161, 154
            row.extend((red, green, blue, 255))
        rows.append(bytes(row))
    raw = b"".join(rows)
    signature = b"\x89PNG\r\n\x1a\n"
    header = struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0)
    return (
        signature
        + _png_chunk(b"IHDR", header)
        + _png_chunk(b"IDAT", zlib.compress(raw, level=9))
        + _png_chunk(b"IEND", b"")
    )


def _render_index(template: str, data: Mapping[str, Any], noindex: bool) -> str:
    site = data["site"]
    replacements = {
        "{{SITE_TITLE}}": _html_escape(site["title"]),
        "{{SITE_DESCRIPTION}}": _html_escape(site["description"]),
        "{{LANGUAGE}}": _html_escape(site["language"]),
        "{{ROBOTS_META}}": (
            "noindex, nofollow, noarchive, nosnippet"
            if noindex
            else "index, follow"
        ),
    }
    for marker, replacement in replacements.items():
        template = template.replace(marker, replacement)
    return template


def _html_escape(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#x27;")
    )


def _headers(private: bool, noindex: bool) -> str:
    robot_header = (
        "\n  X-Robots-Tag: noindex, nofollow, noarchive, nosnippet"
        if noindex
        else ""
    )
    data_cache = (
        "private, no-store, max-age=0"
        if private
        else "public, max-age=300, must-revalidate"
    )
    return f"""/*
  Content-Security-Policy: default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; font-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'none'; worker-src 'self'; manifest-src 'self'; upgrade-insecure-requests
  Referrer-Policy: no-referrer
  X-Content-Type-Options: nosniff
  X-Frame-Options: DENY
  Permissions-Policy: camera=(), microphone=(), geolocation=(), payment=(), usb=(), interest-cohort=()
  Cross-Origin-Opener-Policy: same-origin
  Cross-Origin-Resource-Policy: same-origin
  Cache-Control: public, max-age=0, must-revalidate{robot_header}

/data/*
  Cache-Control: {data_cache}

/assets/*
  Cache-Control: public, max-age=300, must-revalidate

/icons/*
  Cache-Control: public, max-age=31536000, immutable
"""


def _service_worker(cache_version: str, private: bool) -> str:
    shell_files = [
        "./",
        "./index.html",
        "./assets/styles.css",
        "./assets/app.js",
        "./manifest.webmanifest",
        "./offline.html",
        "./icons/icon-192.png",
        "./icons/icon-512.png",
    ]
    public_data = [
        "./data/site-data.json",
        "./data/taxonomy.json",
        "./data/search-index.json",
        "./data/graph.json",
    ]
    cache_files = shell_files if private else shell_files + public_data
    cache_literal = json.dumps(cache_files, ensure_ascii=False)
    data_policy = """
  if (url.pathname.includes("/data/")) {
    event.respondWith(fetch(event.request, { cache: "no-store" }));
    return;
  }
""" if private else ""
    return f"""const CACHE_NAME = "knowledge-os-{cache_version}";
const CACHE_FILES = {cache_literal};

self.addEventListener("install", (event) => {{
  event.waitUntil(caches.open(CACHE_NAME).then((cache) => cache.addAll(CACHE_FILES)));
  self.skipWaiting();
}});

self.addEventListener("activate", (event) => {{
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key))))
      .then(() => self.clients.claim())
  );
}});

self.addEventListener("fetch", (event) => {{
  if (event.request.method !== "GET") return;
  const url = new URL(event.request.url);
  if (url.origin !== self.location.origin) return;
{data_policy}
  event.respondWith(
    fetch(event.request)
      .then((response) => {{
        if (response.ok) {{
          const clone = response.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(event.request, clone));
        }}
        return response;
      }})
      .catch(() => caches.match(event.request).then((cached) => cached || caches.match("./offline.html")))
  );
}});
"""


def _manifest(data: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "name": data["site"]["title"],
        "short_name": "知识体系",
        "description": data["site"]["description"],
        "lang": data["site"]["language"],
        "start_url": "./",
        "scope": "./",
        "display": "standalone",
        "background_color": "#f4f2eb",
        "theme_color": "#141f31",
        "icons": [
            {
                "src": "./icons/icon-192.png",
                "sizes": "192x192",
                "type": "image/png",
                "purpose": "any maskable",
            },
            {
                "src": "./icons/icon-512.png",
                "sizes": "512x512",
                "type": "image/png",
                "purpose": "any maskable",
            },
        ],
    }


def _validate_build(directory: Path) -> None:
    required = [
        "index.html",
        "offline.html",
        "assets/app.js",
        "assets/styles.css",
        "manifest.webmanifest",
        "service-worker.js",
        "robots.txt",
        "_headers",
        "data/site-data.json",
        "data/taxonomy.json",
        "data/search-index.json",
        "data/graph.json",
        "icons/icon-192.png",
        "icons/icon-512.png",
    ]
    missing = [name for name in required if not (directory / name).is_file()]
    if missing:
        raise SiteDataError(f"网站构建缺少文件：{', '.join(missing)}")
    index = (directory / "index.html").read_text(encoding="utf-8")
    if re.search(r"\{\{[A-Z_]+\}\}", index):
        raise SiteDataError("index.html 中仍有未替换的模板变量")
    for relative in (
        "data/site-data.json",
        "data/taxonomy.json",
        "data/search-index.json",
        "data/graph.json",
        "manifest.webmanifest",
    ):
        json.loads((directory / relative).read_text(encoding="utf-8"))
    for size in (192, 512):
        signature = (directory / f"icons/icon-{size}.png").read_bytes()[:8]
        if signature != b"\x89PNG\r\n\x1a\n":
            raise SiteDataError(f"icon-{size}.png 不是有效 PNG")


def _safe_output_directory(output_dir: Union[str, os.PathLike]) -> Path:
    requested = Path(output_dir).expanduser()
    if requested.is_symlink():
        raise ValueError("网站输出目录不能是符号链接")
    # Resolve existing parent aliases (macOS /var -> /private/var included)
    # before any replace/delete operation, so the real target is unambiguous.
    output = requested.resolve(strict=False)
    if output in {Path("/"), Path.home(), Path(Path.cwd().anchor)}:
        raise ValueError("拒绝把宽泛目录作为网站输出目录")
    return output


def build_site(
    data_or_path: DataInput,
    output_dir: Union[str, os.PathLike] = "site/dist",
    *,
    visibility: str = "private",
    allow_indexing: bool = False,
) -> BuildResult:
    """Build and atomically replace a complete static site.

    ``allow_indexing`` is deliberately opt-in and is rejected for private
    builds.  Private PWA builds cache only the application shell, never
    knowledge JSON.
    """

    if visibility == "private" and allow_indexing:
        raise ValueError("private 构建不能允许搜索引擎索引")
    data = normalize_site_data(data_or_path, visibility=visibility)
    output = _safe_output_directory(output_dir)
    output.parent.mkdir(parents=True, exist_ok=True)

    for asset in REQUIRED_ASSETS:
        if not (ASSET_DIR / asset).is_file():
            raise SiteDataError(f"缺少网站源资源：{ASSET_DIR / asset}")

    canonical_bytes = _json_bytes(data)
    content_digest = hashlib.sha256(canonical_bytes).hexdigest()
    temp = Path(
        tempfile.mkdtemp(prefix=f".{output.name}-build-", dir=output.parent)
    )
    backup = output.with_name(
        f".{output.name}-previous-{uuid.uuid4().hex}"
    )
    try:
        (temp / "assets").mkdir(parents=True)
        (temp / "icons").mkdir(parents=True)
        (temp / "data").mkdir(parents=True)
        template = (ASSET_DIR / "index.html").read_text(encoding="utf-8")
        noindex = visibility == "private" or not allow_indexing
        (temp / "index.html").write_text(
            _render_index(template, data, noindex), encoding="utf-8"
        )
        shutil.copyfile(ASSET_DIR / "app.js", temp / "assets" / "app.js")
        shutil.copyfile(ASSET_DIR / "styles.css", temp / "assets" / "styles.css")
        (temp / "offline.html").write_text(
            _render_index(
                (ASSET_DIR / "offline.html").read_text(encoding="utf-8"),
                data,
                noindex,
            ),
            encoding="utf-8",
        )
        (temp / "service-worker.js").write_text(
            _service_worker(content_digest[:16], visibility == "private"),
            encoding="utf-8",
        )
        _write_json(temp / "manifest.webmanifest", _manifest(data))
        _write_json(temp / "data" / "site-data.json", data)
        _write_json(temp / "data" / "taxonomy.json", _taxonomy_payload(data))
        _write_json(temp / "data" / "search-index.json", _search_payload(data))
        _write_json(temp / "data" / "graph.json", _graph_payload(data))
        (temp / "icons" / "icon-192.png").write_bytes(_make_icon(192))
        (temp / "icons" / "icon-512.png").write_bytes(_make_icon(512))
        (temp / "_headers").write_text(
            _headers(visibility == "private", noindex), encoding="utf-8"
        )
        (temp / "robots.txt").write_text(
            (
                "User-agent: *\nDisallow: /\n"
                if noindex
                else "User-agent: *\nAllow: /\n"
            ),
            encoding="utf-8",
        )
        _write_json(
            temp / "build-meta.json",
            {
                "schema_version": SCHEMA_VERSION,
                "content_digest": content_digest,
                "generated_at": data["generated_at"],
                "visibility": visibility,
                "allow_indexing": allow_indexing,
                "node_count": len(data["nodes"]),
                "document_count": len(data["documents"]),
                "relation_count": len(data["relations"]),
                "private_data_cached_by_service_worker": False
                if visibility == "private"
                else None,
            },
        )
        _validate_build(temp)

        if backup.exists():
            raise ValueError(f"随机备份路径意外存在：{backup}")
        if output.exists():
            if not output.is_dir():
                raise ValueError(f"输出路径已存在且不是目录：{output}")
            os.replace(output, backup)
        try:
            os.replace(temp, output)
        except BaseException:
            if backup.exists() and not output.exists():
                os.replace(backup, output)
            raise
        if backup.exists():
            shutil.rmtree(backup)
    finally:
        if temp.exists():
            shutil.rmtree(temp)

    return BuildResult(
        output_dir=output,
        visibility=visibility,
        allow_indexing=allow_indexing,
        node_count=len(data["nodes"]),
        document_count=len(data["documents"]),
        relation_count=len(data["relations"]),
        content_digest=content_digest,
    )
