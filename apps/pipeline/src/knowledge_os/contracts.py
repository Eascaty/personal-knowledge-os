"""Shared, dependency-free contract validation for cross-application payloads."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Mapping, Optional


CONTRACT_DIR = Path(__file__).resolve().parents[4] / "packages" / "contracts"
CANONICAL_SCHEMA = CONTRACT_DIR / "canonical.schema.json"


class ContractError(ValueError):
    """Raised when a payload does not satisfy a shared project contract."""


def load_canonical_schema() -> dict[str, Any]:
    """Load the repository-owned canonical JSON Schema."""

    payload = json.loads(CANONICAL_SCHEMA.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ContractError("canonical schema 顶层必须是对象")
    return payload


def _resolve_reference(root: Mapping[str, Any], reference: str) -> Mapping[str, Any]:
    if not reference.startswith("#/"):
        raise ContractError(f"不支持外部 JSON Schema 引用：{reference}")
    current: Any = root
    for part in reference[2:].split("/"):
        key = part.replace("~1", "/").replace("~0", "~")
        if not isinstance(current, Mapping) or key not in current:
            raise ContractError(f"JSON Schema 引用不存在：{reference}")
        current = current[key]
    if not isinstance(current, Mapping):
        raise ContractError(f"JSON Schema 引用不是对象：{reference}")
    return current


def _matches_type(value: Any, expected: str) -> bool:
    return {
        "object": isinstance(value, Mapping),
        "array": isinstance(value, list),
        "string": isinstance(value, str),
        "integer": isinstance(value, int) and not isinstance(value, bool),
        "number": isinstance(value, (int, float)) and not isinstance(value, bool),
        "boolean": isinstance(value, bool),
        "null": value is None,
    }.get(expected, False)


def _validate(
    value: Any,
    rule: Mapping[str, Any],
    root: Mapping[str, Any],
    path: str,
) -> None:
    reference = rule.get("$ref")
    if isinstance(reference, str):
        _validate(value, _resolve_reference(root, reference), root, path)
        return

    expected = rule.get("type")
    expected_types = [expected] if isinstance(expected, str) else expected
    if isinstance(expected_types, list) and not any(
        isinstance(item, str) and _matches_type(value, item)
        for item in expected_types
    ):
        raise ContractError(f"{path} 类型不符合契约，期望 {expected_types}")

    if "const" in rule and value != rule["const"]:
        raise ContractError(f"{path} 必须等于 {rule['const']!r}")
    if isinstance(rule.get("enum"), list) and value not in rule["enum"]:
        raise ContractError(f"{path} 不在允许值 {rule['enum']} 中")

    if isinstance(value, Mapping):
        required = rule.get("required", [])
        if isinstance(required, list):
            missing = [key for key in required if key not in value]
            if missing:
                raise ContractError(f"{path} 缺少必填字段：{', '.join(missing)}")
        properties = rule.get("properties", {})
        if isinstance(properties, Mapping):
            for key, child_rule in properties.items():
                if key in value and isinstance(child_rule, Mapping):
                    _validate(value[key], child_rule, root, f"{path}.{key}")
            if rule.get("additionalProperties") is False:
                extra = sorted(set(value) - set(properties))
                if extra:
                    raise ContractError(f"{path} 包含未声明字段：{', '.join(extra)}")

    if isinstance(value, list):
        minimum = rule.get("minItems")
        if isinstance(minimum, int) and len(value) < minimum:
            raise ContractError(f"{path} 至少需要 {minimum} 项")
        item_rule = rule.get("items")
        if isinstance(item_rule, Mapping):
            for index, item in enumerate(value):
                _validate(item, item_rule, root, f"{path}[{index}]")

    if isinstance(value, str):
        minimum = rule.get("minLength")
        if isinstance(minimum, int) and len(value) < minimum:
            raise ContractError(f"{path} 长度不能小于 {minimum}")
        pattern = rule.get("pattern")
        if isinstance(pattern, str) and re.search(pattern, value) is None:
            raise ContractError(f"{path} 不匹配格式 {pattern}")

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        minimum = rule.get("minimum")
        maximum = rule.get("maximum")
        if isinstance(minimum, (int, float)) and value < minimum:
            raise ContractError(f"{path} 不能小于 {minimum}")
        if isinstance(maximum, (int, float)) and value > maximum:
            raise ContractError(f"{path} 不能大于 {maximum}")


def validate_canonical_contract(
    payload: Mapping[str, Any],
    schema: Optional[Mapping[str, Any]] = None,
) -> None:
    """Validate normalized canonical data against the supported schema subset."""

    contract = dict(schema) if schema is not None else load_canonical_schema()
    _validate(payload, contract, contract, "$")
