"""OpenCode quickstart — single-page Streamlit dashboard."""

from __future__ import annotations

import streamlit as st

from lib.panels import (
    render_config,
    render_deploy,
    render_git_and_import,
    render_quickstart,
    render_skills,
)
from lib.ui_sidebar import render_opencode_root_sidebar

st.set_page_config(page_title="OpenCode Quickstart", layout="wide")

root = render_opencode_root_sidebar()

st.title("OpenCode Quickstart")
st.caption("先完成下方「快速开始」；进阶功能在底部折叠区。")

render_quickstart(root)

with st.expander("进阶：分步部署、完整配置编辑、Git / 导入", expanded=False):
    t1, t2, t3, t4 = st.tabs(["分步部署", "配置与密钥", "Git / 导入", "Skills"])
    with t1:
        render_deploy(root)
    with t2:
        render_config(root)
    with t3:
        render_git_and_import(root)
    with t4:
        render_skills()
