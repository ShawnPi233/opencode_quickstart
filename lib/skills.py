"""Helpers for managing OpenCode skills from the dashboard."""

from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass
from pathlib import Path

from lib.paths import repo_root

SKILL_NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


@dataclass(frozen=True)
class SkillScope:
    key: str
    label: str
    directory: Path


@dataclass(frozen=True)
class SkillContent:
    name: str
    description: str
    body: str
    license: str = ""
    compatibility: str = ""
    metadata: dict[str, str] | None = None


@dataclass(frozen=True)
class SkillRecord:
    folder_name: str
    file_path: Path
    content: SkillContent | None
    error: str = ""


def available_skill_scopes() -> list[SkillScope]:
    root = repo_root()
    home = Path.home()
    return [
        SkillScope("project-opencode", "项目 .opencode", root / ".opencode" / "skills"),
        SkillScope("project-claude", "项目 .claude", root / ".claude" / "skills"),
        SkillScope("project-agents", "项目 .agents", root / ".agents" / "skills"),
        SkillScope(
            "global-opencode",
            "全局 ~/.config/opencode",
            home / ".config" / "opencode" / "skills",
        ),
        SkillScope("global-claude", "全局 ~/.claude", home / ".claude" / "skills"),
        SkillScope("global-agents", "全局 ~/.agents", home / ".agents" / "skills"),
    ]


def validate_skill_name(name: str) -> str:
    value = name.strip()
    if not value:
        raise ValueError("skill 名称不能为空")
    if len(value) > 64:
        raise ValueError("skill 名称长度不能超过 64")
    if not SKILL_NAME_RE.fullmatch(value):
        raise ValueError(
            "skill 名称只能包含小写字母、数字和单个连字符，且不能以连字符开头或结尾"
        )
    return value


def _strip_quotes(value: str) -> str:
    text = value.strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in {'"', "'"}:
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return text[1:-1]
    return text


def parse_skill_markdown(
    text: str, *, expected_folder: str | None = None
) -> SkillContent:
    if not text.startswith("---\n") and text != "---":
        raise ValueError("SKILL.md 必须以 YAML frontmatter 开头")

    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise ValueError("SKILL.md 必须以 `---` 开头")

    end_index = None
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            end_index = index
            break
    if end_index is None:
        raise ValueError("SKILL.md 缺少 frontmatter 结束标记 `---`")

    frontmatter_lines = lines[1:end_index]
    body = "\n".join(lines[end_index + 1 :]).lstrip("\n")

    data: dict[str, object] = {"metadata": {}}
    current_map: str | None = None
    for raw in frontmatter_lines:
        if not raw.strip():
            continue
        if raw.startswith("  "):
            if current_map != "metadata":
                continue
            entry = raw.strip()
            if ":" not in entry:
                continue
            key, value = entry.split(":", 1)
            metadata = data.setdefault("metadata", {})
            if isinstance(metadata, dict):
                metadata[key.strip()] = _strip_quotes(value)
            continue

        current_map = None
        if ":" not in raw:
            continue
        key, value = raw.split(":", 1)
        key = key.strip()
        value = value.strip()
        if key == "metadata":
            current_map = "metadata"
            data["metadata"] = {}
            continue
        if key in {"name", "description", "license", "compatibility"}:
            data[key] = _strip_quotes(value)

    name = validate_skill_name(str(data.get("name", "")))
    description = str(data.get("description", "")).strip()
    if not description:
        raise ValueError("frontmatter 缺少 description")
    if len(description) > 1024:
        raise ValueError("description 长度不能超过 1024")
    if expected_folder and expected_folder != name:
        raise ValueError("frontmatter 中的 name 必须与目录名一致")

    metadata = data.get("metadata")
    metadata_dict = metadata if isinstance(metadata, dict) else {}
    normalized_metadata = {
        str(k).strip(): str(v).strip()
        for k, v in metadata_dict.items()
        if str(k).strip() and str(v).strip()
    }
    return SkillContent(
        name=name,
        description=description,
        body=body,
        license=str(data.get("license", "")).strip(),
        compatibility=str(data.get("compatibility", "")).strip(),
        metadata=normalized_metadata,
    )


def _yaml_scalar(value: str) -> str:
    text = value.strip()
    if not text:
        return '""'
    if any(ch in text for ch in [":", "#", "[", "]", "{", "}", "\n"]) or text != value:
        return json.dumps(text, ensure_ascii=False)
    return text


def render_skill_markdown(content: SkillContent) -> str:
    lines = [
        "---",
        f"name: {_yaml_scalar(content.name)}",
        f"description: {_yaml_scalar(content.description)}",
    ]
    if content.license.strip():
        lines.append(f"license: {_yaml_scalar(content.license)}")
    if content.compatibility.strip():
        lines.append(f"compatibility: {_yaml_scalar(content.compatibility)}")
    metadata = content.metadata or {}
    if metadata:
        lines.append("metadata:")
        for key in sorted(metadata):
            value = metadata[key]
            if key.strip() and value.strip():
                lines.append(f"  {key.strip()}: {_yaml_scalar(value)}")
    lines.append("---")
    lines.append("")
    body = content.body.rstrip()
    if body:
        lines.append(body)
    return "\n".join(lines).rstrip() + "\n"


def list_skills(scope_dir: Path) -> list[SkillRecord]:
    if not scope_dir.is_dir():
        return []
    records: list[SkillRecord] = []
    for child in sorted(scope_dir.iterdir(), key=lambda item: item.name):
        if not child.is_dir():
            continue
        skill_file = child / "SKILL.md"
        if not skill_file.is_file():
            continue
        try:
            content = parse_skill_markdown(
                skill_file.read_text(encoding="utf-8"), expected_folder=child.name
            )
            records.append(SkillRecord(child.name, skill_file, content))
        except Exception as exc:
            records.append(SkillRecord(child.name, skill_file, None, str(exc)))
    return records


def load_skill(scope_dir: Path, folder_name: str) -> SkillRecord:
    skill_file = scope_dir / folder_name / "SKILL.md"
    if not skill_file.is_file():
        raise FileNotFoundError(f"未找到 {skill_file}")
    try:
        content = parse_skill_markdown(
            skill_file.read_text(encoding="utf-8"), expected_folder=folder_name
        )
        return SkillRecord(folder_name, skill_file, content)
    except Exception as exc:
        return SkillRecord(folder_name, skill_file, None, str(exc))


def save_skill(
    scope_dir: Path,
    content: SkillContent,
    *,
    original_name: str | None = None,
) -> Path:
    name = validate_skill_name(content.name)
    scope_dir.mkdir(parents=True, exist_ok=True)

    target_dir = scope_dir / name
    if original_name:
        original = validate_skill_name(original_name)
        original_dir = scope_dir / original
        if original != name:
            if target_dir.exists():
                raise FileExistsError(f"目标 skill 已存在：{name}")
            if original_dir.exists():
                original_dir.rename(target_dir)
        else:
            target_dir.mkdir(parents=True, exist_ok=True)
    elif target_dir.exists() and not (target_dir / "SKILL.md").is_file():
        raise FileExistsError(f"目录已存在但不是有效 skill：{target_dir}")
    else:
        target_dir.mkdir(parents=True, exist_ok=True)

    skill_file = target_dir / "SKILL.md"
    skill_file.write_text(render_skill_markdown(content), encoding="utf-8")
    return skill_file


def delete_skill(scope_dir: Path, folder_name: str) -> None:
    target = scope_dir / validate_skill_name(folder_name)
    if not target.exists():
        raise FileNotFoundError(f"未找到 skill 目录：{target}")
    shutil.rmtree(target)
