"""Lightweight JSON validation for OpenCode config subsets."""

from __future__ import annotations

import json
from typing import Any


def parse_json_object(text: str) -> dict[str, Any]:
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("根节点必须是 JSON 对象")
    return data


def _ensure_object(data: Any, name: str) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise ValueError(f"{name} 必须是 JSON 对象")
    return data


def _ensure_type(value: Any, expected: type, path: str) -> None:
    if not isinstance(value, expected):
        raise ValueError(f"{path} 必须是 {expected.__name__}")


def validate_public(data: dict[str, Any]) -> None:
    public = _ensure_object(data, "public 配置")
    if "theme" in public:
        _ensure_type(public["theme"], str, "theme")
    if "autoupdate" in public:
        _ensure_type(public["autoupdate"], bool, "autoupdate")
    if "provider" in public:
        _ensure_type(public["provider"], dict, "provider")
    if "models" in public:
        _ensure_type(public["models"], dict, "models")


def validate_secrets(data: dict[str, Any]) -> None:
    _ensure_object(data, "secrets 配置")
