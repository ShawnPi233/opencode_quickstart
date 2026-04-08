"""Deep-merge public + secrets OpenCode JSON and write target opencode.json."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any


def deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    out = deepcopy(base)
    for key, val in overlay.items():
        if key in out and isinstance(out[key], dict) and isinstance(val, dict):
            out[key] = deep_merge(out[key], val)
        else:
            out[key] = deepcopy(val)
    return out


def load_json_file(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    text = path.read_text(encoding="utf-8")
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError(f"{path} root must be a JSON object")
    return data


def save_json_file(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def merged_config(public: dict[str, Any], secrets: dict[str, Any]) -> dict[str, Any]:
    return deep_merge(public, secrets)


def write_merged_to_opencode(
    public_path: Path,
    secrets_path: Path,
    opencode_root: Path,
) -> dict[str, Any]:
    public = load_json_file(public_path)
    secrets = load_json_file(secrets_path)
    merged = merged_config(public, secrets)
    target = opencode_root / "config" / "opencode" / "opencode.json"
    save_json_file(target, merged)
    return merged


def strip_api_keys(obj: Any) -> Any:
    """Recursively set every 'apiKey' value to empty string (for public export)."""
    if isinstance(obj, dict):
        out: dict[str, Any] = {}
        for k, v in obj.items():
            if k == "apiKey":
                out[k] = ""
            else:
                out[k] = strip_api_keys(v)
        return out
    if isinstance(obj, list):
        return [strip_api_keys(x) for x in obj]
    return obj


def extract_api_key_overlay(source: dict[str, Any]) -> dict[str, Any]:
    """
    Build a minimal overlay dict containing only branches that lead to apiKey values,
    so deep_merge(public, overlay) restores keys. Empty strings are skipped.
    """
    def walk(node: Any) -> Any:
        if isinstance(node, dict):
            if "apiKey" in node:
                v = node["apiKey"]
                if isinstance(v, str) and v.strip():
                    return {"apiKey": v}
                return {}
            acc: dict[str, Any] = {}
            for k, v in node.items():
                sub = walk(v)
                if sub == {}:
                    continue
                if isinstance(sub, dict) and len(sub) == 0:
                    continue
                acc[k] = sub
            return acc
        if isinstance(node, list):
            # Preserve list indices for rare list-of-objects with apiKey
            acc_list: list[Any] = []
            for i, item in enumerate(node):
                sub = walk(item)
                if sub != {}:
                    while len(acc_list) <= i:
                        acc_list.append({})
                    acc_list[i] = sub
            return acc_list if any(x != {} for x in acc_list) else {}
        return {}

    overlay = walk(source)
    return overlay if isinstance(overlay, dict) else {}


def split_public_and_secrets(full: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    public = strip_api_keys(deepcopy(full))
    secrets = extract_api_key_overlay(full)
    return public, secrets
