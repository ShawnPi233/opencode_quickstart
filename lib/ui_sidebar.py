"""Shared Streamlit sidebar for OPENCODE_ROOT (env > input > default) and Git 自动同步开关."""

from __future__ import annotations

import os
from pathlib import Path

import streamlit as st

from lib.paths import default_opencode_root, load_ui_settings, resolve_opencode_root, save_ui_settings


def render_opencode_root_sidebar() -> Path:
    st.sidebar.markdown("### OpenCode 根目录")
    env = os.environ.get("OPENCODE_ROOT", "").strip()
    if env:
        st.sidebar.caption("已设置环境变量 `OPENCODE_ROOT`（优先生效）")
        root = resolve_opencode_root()
        st.sidebar.code(str(root), language="text")
        _render_git_auto_sync_toggle()
        return root

    saved = load_ui_settings().get("opencode_root", "") or ""
    if "oc_root_sidebar" not in st.session_state:
        st.session_state.oc_root_sidebar = saved or str(default_opencode_root())

    def _on_root_change() -> None:
        save_ui_settings({"opencode_root": st.session_state.oc_root_sidebar})

    _hint = (
        "默认 **`/user/<登录名>/opencode`**（与 `USER` 一致）。若以 **root** 进容器且无法写 `/user/root`，"
        "请在本机 **`export OPENCODE_ROOT=/user/<你的账号>/opencode`** 或 **`$HOME/opencode`**。"
    )
    st.sidebar.caption(_hint)
    st.sidebar.text_input(
        "路径（可相对本仓库）",
        key="oc_root_sidebar",
        help=_hint,
        on_change=_on_root_change,
    )
    _render_git_auto_sync_toggle()
    raw = st.session_state.oc_root_sidebar
    if not str(raw).strip():
        return default_opencode_root()
    return resolve_opencode_root(sidebar_input=str(raw))


def _render_git_auto_sync_toggle() -> None:
    st.sidebar.divider()
    st.sidebar.markdown("### Git 自动同步")
    settings = load_ui_settings()
    if "git_auto_sync_enabled" not in st.session_state:
        st.session_state.git_auto_sync_enabled = bool(settings.get("git_auto_sync_enabled", False))

    def _on_sync_change() -> None:
        save_ui_settings({"git_auto_sync_enabled": bool(st.session_state.git_auto_sync_enabled)})

    st.sidebar.checkbox(
        "保存公开配置后自动 push",
        key="git_auto_sync_enabled",
        on_change=_on_sync_change,
        help=(
            "开启后，每次成功写入 `tracked_config/opencode.public.json`（含提供商表单、主题、导入 public）时，"
            "会自动 `git add` 该文件、`commit`（有变更时）并 `git push`。"
            "不会提交 `opencode.secrets.json`。请自行使用**私有**远程仓库并配置好 origin 与凭据。"
        ),
    )
