"""Extraction, strict hierarchical classification, indexing, and export."""

from __future__ import annotations

import hashlib
import html
import json
import re
import shutil
import subprocess
import zipfile
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple
from xml.etree import ElementTree

from . import db
from .ai import Adapter, KnowledgeExtraction, RelationSuggestion
from .config import ProjectPaths, atomic_write_json, atomic_write_text


class ExtractionError(RuntimeError):
    pass


class NeedsExternalTool(ExtractionError):
    pass


@dataclass(frozen=True)
class Classification:
    node_id: str
    path_ids: List[str]
    path_names: List[str]
    confidence: float
    method: str


@dataclass(frozen=True)
class RunSummary:
    claimed: int
    completed: int
    retried: int
    failed: int


class _ReadableHTMLParser(HTMLParser):
    BLOCKS = {
        "article",
        "aside",
        "blockquote",
        "br",
        "div",
        "footer",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "header",
        "li",
        "main",
        "p",
        "section",
        "tr",
    }
    SKIP = {"script", "style", "noscript", "svg"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: List[str] = []
        self.skip_depth = 0
        self.title = ""
        self._in_title = False

    def handle_starttag(
        self, tag: str, attrs: List[Tuple[str, Optional[str]]]
    ) -> None:
        lowered = tag.casefold()
        if lowered in self.SKIP:
            self.skip_depth += 1
        if lowered == "title":
            self._in_title = True
        if lowered in self.BLOCKS and not self.skip_depth:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        lowered = tag.casefold()
        if lowered == "title":
            self._in_title = False
        if lowered in self.SKIP and self.skip_depth:
            self.skip_depth -= 1
        if lowered in self.BLOCKS and not self.skip_depth:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self.skip_depth:
            return
        value = data.strip()
        if not value:
            return
        if self._in_title:
            self.title = (self.title + " " + value).strip()
        self.parts.append(value)
        self.parts.append(" ")

    def text(self) -> str:
        value = "".join(self.parts)
        value = re.sub(r"[ \t]+\n", "\n", value)
        value = re.sub(r"\n[ \t]+", "\n", value)
        value = re.sub(r"[ \t]{2,}", " ", value)
        value = re.sub(r"\n{3,}", "\n\n", value)
        return value.strip()


TEXT_EXTENSIONS = {
    ".c",
    ".cc",
    ".conf",
    ".cpp",
    ".css",
    ".csv",
    ".go",
    ".h",
    ".html",
    ".htm",
    ".ini",
    ".java",
    ".js",
    ".json",
    ".log",
    ".md",
    ".properties",
    ".py",
    ".rb",
    ".rst",
    ".sh",
    ".sql",
    ".toml",
    ".ts",
    ".tsx",
    ".txt",
    ".xml",
    ".yaml",
    ".yml",
}


def _decode_text(data: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-16", "gb18030"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    decoded = data.decode("utf-8", errors="replace")
    replacement_ratio = decoded.count("\ufffd") / max(1, len(decoded))
    if replacement_ratio > 0.02:
        raise ExtractionError("file does not look like supported text")
    return decoded


def _title_from_text(text: str, fallback: str) -> str:
    for line in text.splitlines():
        candidate = re.sub(r"^#{1,6}\s*", "", line).strip()
        if candidate:
            return candidate[:200]
    return Path(fallback).stem[:200] or "未命名资料"


def _extract_docx(path: Path) -> str:
    try:
        with zipfile.ZipFile(str(path)) as archive:
            xml_data = archive.read("word/document.xml")
    except (zipfile.BadZipFile, KeyError) as exc:
        raise ExtractionError(f"invalid DOCX: {exc}") from exc
    root = ElementTree.fromstring(xml_data)
    namespace = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    paragraphs: List[str] = []
    for paragraph in root.iter(namespace + "p"):
        pieces = [
            element.text or ""
            for element in paragraph.iter(namespace + "t")
            if element.text
        ]
        if pieces:
            paragraphs.append("".join(pieces))
    return "\n\n".join(paragraphs).strip()


def _extract_pdf(path: Path) -> str:
    executable = shutil.which("pdftotext")
    if not executable:
        raise NeedsExternalTool(
            "PDF extraction requires the free local 'pdftotext' command"
        )
    try:
        result = subprocess.run(
            [executable, "-layout", str(path), "-"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=120,
        )
    except (subprocess.SubprocessError, OSError) as exc:
        raise ExtractionError(f"pdftotext failed: {exc}") from exc
    text = result.stdout.decode("utf-8", errors="replace").strip()
    if not text:
        raise NeedsExternalTool(
            "PDF contains no text; OCRmyPDF/Tesseract preprocessing is required"
        )
    return text


def extract_source(path: Path, original_name: str) -> Tuple[str, str]:
    suffix = Path(original_name).suffix.casefold()
    if suffix == ".docx":
        body = _extract_docx(path)
        return _title_from_text(body, original_name), body
    if suffix == ".pdf":
        body = _extract_pdf(path)
        return _title_from_text(body, original_name), body
    data = path.read_bytes()
    if suffix in {".html", ".htm"}:
        parser = _ReadableHTMLParser()
        parser.feed(_decode_text(data))
        body = parser.text()
        return parser.title[:200] or _title_from_text(body, original_name), body
    if suffix in TEXT_EXTENSIONS or not suffix:
        body = _decode_text(data).replace("\x00", "").strip()
        return _title_from_text(body, original_name), body

    # Accept an unknown extension only when it is convincingly plain text.
    sample = data[:8192]
    if sample and sum(byte == 0 for byte in sample) == 0:
        body = _decode_text(data).replace("\x00", "").strip()
        return _title_from_text(body, original_name), body
    raise ExtractionError(f"unsupported local format: {suffix or '(none)'}")


def _normalized_markdown(
    *,
    source_id: str,
    sha256: str,
    title: str,
    original_name: str,
    imported_at: str,
    body: str,
) -> str:
    frontmatter = {
        "id": source_id,
        "source_sha256": sha256,
        "title": title,
        "original_name": original_name,
        "imported_at": imported_at,
        "visibility": "private",
        "generated_by": "knowledge-os/extract-v1",
    }
    lines = ["---"]
    for key, value in frontmatter.items():
        lines.append(
            f"{key}: {json.dumps(value, ensure_ascii=False, separators=(',', ':'))}"
        )
    lines.extend(["---", "", f"# {title}", "", body.strip(), ""])
    return "\n".join(lines)


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


def _safe_component(name: str) -> str:
    value = re.sub(r"[\x00-\x1f/\\:]+", "-", name).strip(" .")
    return (value or "未命名")[:100]


def _write_knowledge_note(
    paths: ProjectPaths,
    *,
    source: Mapping[str, Any],
    document: Mapping[str, Any],
    extraction: KnowledgeExtraction,
    classification: Classification,
) -> str:
    display_path = classification.path_names[1:]
    directory = paths.vault_dir.joinpath(
        *[_safe_component(name) for name in display_path]
    )
    filename = f"{_safe_component(str(document['title']))}-{str(document['id'])[-12:]}.md"
    output = directory / "资料" / filename
    metadata = {
        "id": document["id"],
        "source_id": source["id"],
        "source_sha256": source["sha256"],
        "taxonomy_node_id": classification.node_id,
        "taxonomy_path": display_path,
        "classification_method": classification.method,
        "classification_confidence": round(classification.confidence, 4),
        "visibility": document.get("visibility", "private"),
        "model": extraction.model_name,
        "prompt_version": extraction.prompt_version,
        "updated_at": db.utc_now(),
    }
    lines = ["---"]
    for key, value in metadata.items():
        lines.append(f"{key}: {json.dumps(value, ensure_ascii=False)}")
    lines.extend(
        [
            "---",
            "",
            f"# {document['title']}",
            "",
            "## 摘要",
            "",
            extraction.summary or "尚无摘要。",
            "",
            "## 关键知识",
            "",
        ]
    )
    if extraction.key_points:
        lines.extend(f"- {point}" for point in extraction.key_points)
    else:
        lines.append("- 尚未提取关键知识。")
    lines.extend(
        [
            "",
            "## 标签",
            "",
            "、".join(extraction.tags) if extraction.tags else "无",
            "",
            "## 来源证据",
            "",
            f"- 原始文件：`{source['raw_path']}`",
            f"- SHA-256：`{source['sha256']}`",
            f"- 原始名称：{source['original_name']}",
            "",
            "## 标准化正文",
            "",
            str(document["body"]).strip(),
            "",
        ]
    )
    atomic_write_text(output, "\n".join(lines))
    try:
        return output.relative_to(paths.root).as_posix()
    except ValueError:
        return str(output)


def _upsert_relations(
    connection: Any,
    document_id: str,
    relations: Sequence[RelationSuggestion],
) -> None:
    valid_ids = {
        str(row[0]) for row in connection.execute("SELECT id FROM nodes WHERE active=1")
    }
    connection.execute("DELETE FROM relations WHERE document_id=?", (document_id,))
    for relation in relations:
        if (
            relation.from_node_id not in valid_ids
            or relation.to_node_id not in valid_ids
            or relation.from_node_id == relation.to_node_id
        ):
            continue
        identity = "|".join(
            [
                document_id,
                relation.from_node_id,
                relation.to_node_id,
                relation.relation_type,
            ]
        )
        relation_id = "rel-" + hashlib.sha256(identity.encode("utf-8")).hexdigest()[:24]
        connection.execute(
            """
            INSERT OR REPLACE INTO relations(
                id, from_node_id, to_node_id, relation_type, label,
                document_id, confidence
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                relation_id,
                relation.from_node_id,
                relation.to_node_id,
                relation.relation_type[:80],
                relation.label[:200],
                document_id,
                max(0.0, min(float(relation.confidence), 1.0)),
            ),
        )
    connection.commit()


def _quarantine(
    paths: ProjectPaths,
    source: Mapping[str, Any],
    *,
    stage: str,
    error: str,
) -> None:
    record = {
        "source_id": source["id"],
        "stage": stage,
        "error": error,
        "raw_path": source["raw_path"],
        "recorded_at": db.utc_now(),
        "note": "原始资料仍保留在 raw；修复解析器后可重试。",
    }
    atomic_write_json(paths.quarantine_dir / f"{source['id']}.json", record)


def _process_extract(
    connection: Any,
    paths: ProjectPaths,
    source: Mapping[str, Any],
    runtime: Mapping[str, Any],
) -> None:
    raw_path = (paths.root / str(source["raw_path"])).resolve()
    raw_root = paths.raw_dir.resolve()
    try:
        raw_path.relative_to(raw_root)
    except ValueError as exc:
        raise ExtractionError(
            f"raw source escapes the project raw directory: {raw_path}"
        ) from exc
    if not raw_path.is_file():
        raise ExtractionError(f"raw source is missing: {raw_path}")
    title, body = extract_source(raw_path, str(source["original_name"]))
    if not body.strip():
        raise ExtractionError("source yielded an empty document")
    normalized_path = (
        paths.normalized_dir
        / str(source["sha256"])[:2]
        / f"{source['sha256']}.md"
    )
    markdown = _normalized_markdown(
        source_id=str(source["id"]),
        sha256=str(source["sha256"]),
        title=title,
        original_name=str(source["original_name"]),
        imported_at=str(source["imported_at"]),
        body=body,
    )
    atomic_write_text(normalized_path, markdown)
    relative_normalized = normalized_path.relative_to(paths.root).as_posix()
    db.upsert_document(
        connection,
        {
            "id": source["id"],
            "source_id": source["id"],
            "title": title,
            "normalized_path": relative_normalized,
            "body": body,
            "visibility": "private",
            "model_name": "pending",
            "prompt_version": "pending",
        },
    )
    db.enqueue_job(
        connection,
        str(source["id"]),
        "enrich",
        max_attempts=int(runtime.get("pipeline", {}).get("max_attempts", 3)),
    )


def _process_enrich(
    connection: Any,
    paths: ProjectPaths,
    source: Mapping[str, Any],
    runtime: Mapping[str, Any],
    taxonomy: Mapping[str, Any],
    adapter: Adapter,
) -> None:
    document = connection.execute(
        "SELECT * FROM documents WHERE id=?", (source["id"],)
    ).fetchone()
    if document is None:
        raise ExtractionError("document was not extracted before enrichment")
    extraction = adapter.extract(
        title=str(document["title"]),
        body=str(document["body"]),
        taxonomy=taxonomy,
    )
    classification = classify_document(
        title=str(document["title"]),
        body=str(document["body"]),
        extraction=extraction,
        taxonomy=taxonomy,
    )
    db.update_document_enrichment(
        connection,
        str(document["id"]),
        summary=extraction.summary,
        key_points=extraction.key_points,
        tags=extraction.tags,
        model_name=extraction.model_name,
        prompt_version=extraction.prompt_version,
    )
    db.place_document(
        connection,
        str(document["id"]),
        classification.node_id,
        classification.confidence,
        classification.method,
    )
    _upsert_relations(connection, str(document["id"]), extraction.relations)
    enriched_document = dict(document)
    enriched_document.update(
        {
            "summary": extraction.summary,
            "key_points": extraction.key_points,
            "tags": extraction.tags,
        }
    )
    vault_path = _write_knowledge_note(
        paths,
        source=source,
        document=enriched_document,
        extraction=extraction,
        classification=classification,
    )
    db.add_event(
        connection,
        "knowledge_note_written",
        source_id=str(source["id"]),
        details={"path": vault_path, "node_id": classification.node_id},
    )
    connection.commit()
    db.enqueue_job(
        connection,
        str(source["id"]),
        "index",
        max_attempts=int(runtime.get("pipeline", {}).get("max_attempts", 3)),
    )


def process_jobs(
    connection: Any,
    paths: ProjectPaths,
    runtime: Mapping[str, Any],
    taxonomy: Mapping[str, Any],
    adapter: Adapter,
    *,
    max_jobs: int = 100,
) -> RunSummary:
    pipeline = runtime.get("pipeline", {})
    db.recover_stale_jobs(
        connection, int(pipeline.get("stale_job_minutes", 30))
    )
    claimed = completed = retried = failed = 0
    for _ in range(max(0, int(max_jobs))):
        job = db.claim_next_job(connection)
        if job is None:
            break
        claimed += 1
        source = db.source_by_id(connection, str(job["source_id"]))
        if source is None:
            outcome = db.fail_job(
                connection,
                int(job["id"]),
                "source record is missing",
                retry_base_seconds=0,
            )
            failed += 1 if outcome == "failed" else 0
            retried += 1 if outcome == "retry" else 0
            continue
        try:
            stage = str(job["stage"])
            if stage == "extract":
                _process_extract(connection, paths, source, runtime)
            elif stage == "enrich":
                _process_enrich(
                    connection, paths, source, runtime, taxonomy, adapter
                )
            elif stage == "index":
                db.index_document(connection, str(source["id"]))
            else:
                raise ExtractionError(f"unknown pipeline stage: {stage}")
            db.finish_job(connection, int(job["id"]))
            completed += 1
        except Exception as exc:
            outcome = db.fail_job(
                connection,
                int(job["id"]),
                f"{type(exc).__name__}: {exc}",
                retry_base_seconds=int(pipeline.get("retry_base_seconds", 30)),
            )
            if outcome == "failed":
                failed += 1
                _quarantine(
                    paths,
                    source,
                    stage=str(job["stage"]),
                    error=f"{type(exc).__name__}: {exc}",
                )
            else:
                retried += 1
    return RunSummary(
        claimed=claimed, completed=completed, retried=retried, failed=failed
    )


def rebuild_vault_indexes(
    connection: Any, paths: ProjectPaths
) -> int:
    nodes = connection.execute(
        "SELECT * FROM nodes WHERE active=1 ORDER BY level, sort_order, name"
    ).fetchall()
    written = 0
    for node in nodes:
        names = json.loads(node["path_json"])
        if int(node["level"]) == 0:
            directory = paths.vault_dir
        else:
            directory = paths.vault_dir.joinpath(
                *[_safe_component(name) for name in names[1:]]
            )
        children = connection.execute(
            """
            SELECT name FROM nodes
            WHERE parent_id=? AND active=1
            ORDER BY sort_order, name
            """,
            (node["id"],),
        ).fetchall()
        documents = connection.execute(
            """
            SELECT d.title, d.id, d.summary
            FROM documents d
            JOIN placements p ON p.document_id=d.id
            WHERE p.node_id=?
            ORDER BY d.updated_at DESC
            """,
            (node["id"],),
        ).fetchall()
        lines = [
            "---",
            f"id: {json.dumps(node['id'], ensure_ascii=False)}",
            f"taxonomy_path: {json.dumps(names[1:], ensure_ascii=False)}",
            'generated_by: "knowledge-os/index-v1"',
            "---",
            "",
            f"# {node['name']}",
            "",
        ]
        if children:
            lines.extend(["## 子级", ""])
            lines.extend(f"- [{child['name']}](./{_safe_component(child['name'])}/)" for child in children)
            lines.append("")
        lines.extend(["## 本节点资料", ""])
        if documents:
            for document in documents:
                lines.append(f"- **{document['title']}** — {document['summary'][:180]}")
        else:
            lines.append("- 暂无资料。")
        lines.append("")
        atomic_write_text(directory / "_index.md", "\n".join(lines))
        written += 1
    return written


def _document_rows(connection: Any, visibility: str) -> List[Any]:
    condition = "" if visibility == "private" else "WHERE d.visibility='public'"
    return connection.execute(
        f"""
        SELECT d.*, s.kind, s.origin, s.original_name, s.raw_path, s.sha256,
               p.node_id, p.confidence, p.method, n.path_json
        FROM documents d
        JOIN sources s ON s.id=d.source_id
        JOIN placements p ON p.document_id=d.id
        JOIN nodes n ON n.id=p.node_id
        {condition}
        ORDER BY d.updated_at DESC, d.id
        """
    ).fetchall()


def build_site_data(
    connection: Any,
    paths: ProjectPaths,
    taxonomy: Mapping[str, Any],
    runtime: Mapping[str, Any],
    *,
    visibility: str = "private",
    output: Optional[Path] = None,
) -> Dict[str, Any]:
    if visibility not in {"private", "public"}:
        raise ValueError("visibility must be private or public")
    rebuild_vault_indexes(connection, paths)
    document_rows = _document_rows(connection, visibility)
    active_node_ids = {
        str(row[0])
        for row in connection.execute(
            "SELECT id FROM nodes WHERE active=1"
        ).fetchall()
    }
    orphaned_documents = [
        str(row["id"])
        for row in document_rows
        if str(row["node_id"]) not in active_node_ids
    ]
    if orphaned_documents:
        raise ExtractionError(
            "documents reference inactive taxonomy nodes: {}".format(
                ", ".join(orphaned_documents[:10])
            )
        )
    relation_rows = connection.execute(
        """
        SELECT r.* FROM relations r
        LEFT JOIN documents d ON d.id=r.document_id
        WHERE ?='private' OR d.visibility='public'
        ORDER BY r.id
        """,
        (visibility,),
    ).fetchall()
    relations = [
        {
            "id": row["id"],
            "from_node_id": row["from_node_id"],
            "to_node_id": row["to_node_id"],
            "type": row["relation_type"],
            "label": row["label"],
            "document_id": row["document_id"],
            "confidence": row["confidence"],
        }
        for row in relation_rows
    ]
    relations_by_document: Dict[str, List[str]] = {}
    for relation in relations:
        document_id = relation.get("document_id")
        if document_id:
            relations_by_document.setdefault(str(document_id), []).append(
                str(relation["id"])
            )

    documents: List[Dict[str, Any]] = []
    for row in document_rows:
        path = json.loads(row["path_json"])[1:]
        raw_origin = str(row["origin"])
        # Absolute local paths reveal usernames and folder names without
        # helping a remotely viewed static site. Only durable web citations
        # survive an export; local provenance remains in private SQLite.
        source_origin = (
            raw_origin
            if raw_origin.startswith(("https://", "http://"))
            else ("manual" if raw_origin == "manual" else "local-file")
        )
        documents.append(
            {
                "id": row["id"],
                "source_id": row["source_id"],
                "title": row["title"],
                "summary": row["summary"],
                "content": row["body"],
                "key_points": json.loads(row["key_points_json"]),
                "path": path,
                "node_id": row["node_id"],
                "source": {
                    "kind": row["kind"],
                    "original_name": row["original_name"],
                    "origin": source_origin,
                    "sha256": row["sha256"],
                },
                "evidence": [
                    {
                        "id": f"{row['id']}-source",
                        "excerpt": re.sub(r"\s+", " ", str(row["body"])).strip()[:500],
                        "locator": row["original_name"],
                        "source_label": row["original_name"],
                    }
                ],
                "tags": json.loads(row["tags_json"]),
                "visibility": row["visibility"],
                "relations": relations_by_document.get(str(row["id"]), []),
                "classification": {
                    "confidence": row["confidence"],
                    "method": row["method"],
                },
                "model": {
                    "name": row["model_name"],
                    "prompt_version": row["prompt_version"],
                },
                "updated_at": row["updated_at"],
            }
        )
    counts_by_node = {
        str(row["node_id"]): int(row["count"])
        for row in connection.execute(
            """
            SELECT p.node_id, COUNT(*) AS count
            FROM placements p JOIN documents d ON d.id=p.document_id
            WHERE ?='private' OR d.visibility='public'
            GROUP BY p.node_id
            """,
            (visibility,),
        )
    }
    taxonomy_tree = deepcopy(taxonomy["root"])

    def attach_counts(node: Dict[str, Any]) -> int:
        direct = counts_by_node.get(str(node["id"]), 0)
        total = direct
        for child in node.get("children", []):
            total += attach_counts(child)
        node["direct_document_count"] = direct
        node["document_count"] = total
        return total

    attach_counts(taxonomy_tree)
    node_rows = connection.execute(
        "SELECT * FROM nodes WHERE active=1 ORDER BY level, sort_order, name"
    ).fetchall()
    nodes = [
        {
            "id": row["id"],
            "parent_id": row["parent_id"],
            "name": row["name"],
            "level": row["level"],
            "path": json.loads(row["path_json"])[1:],
            "locked": bool(row["locked"]),
            "document_count": counts_by_node.get(str(row["id"]), 0),
        }
        for row in node_rows
    ]
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    status = db.status_summary(connection)
    canonical: Dict[str, Any] = {
        "schema_version": 1,
        "generated_at": generated_at,
        "visibility": visibility,
        "site": {
            "title": runtime.get("site", {}).get("title", "我的知识体系"),
            "visibility": visibility,
        },
        "root": str(taxonomy["root"]["id"]),
        "taxonomy": taxonomy_tree,
        "nodes": nodes,
        "documents": documents,
        "relations": relations,
        "stats": status["counts"],
    }
    output_path = output or (paths.site_data_dir / "site-data.json")
    atomic_write_json(output_path, canonical)
    # Compatibility alias for simple consumers; content is intentionally
    # identical and remains a disposable build artifact.
    if output is None:
        atomic_write_json(paths.site_data_dir / "knowledge.json", canonical)
        atomic_write_json(
            paths.site_data_dir / "taxonomy.json",
            {
                "schema_version": 1,
                "generated_at": generated_at,
                "root": taxonomy_tree,
                "nodes": nodes,
            },
        )
        atomic_write_json(
            paths.site_data_dir / "search-index.json",
            {
                "schema_version": 1,
                "generated_at": generated_at,
                "documents": [
                    {
                        "id": item["id"],
                        "title": item["title"],
                        "summary": item["summary"],
                        "content": item["content"],
                        "path": item["path"],
                        "tags": item["tags"],
                    }
                    for item in documents
                ],
            },
        )
        atomic_write_json(
            paths.site_data_dir / "graph.json",
            {
                "schema_version": 1,
                "generated_at": generated_at,
                "nodes": nodes,
                "relations": relations,
                "document_placements": [
                    {"document_id": item["id"], "node_id": item["node_id"]}
                    for item in documents
                ],
            },
        )
    return canonical
