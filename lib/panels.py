"""Single-page dashboard sections (deploy / config / git+import)."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import streamlit as st

from lib.env_init import opencode_subprocess_env, write_env_init
from lib.git_ops import (
    git_add_all,
    git_commit,
    git_diff_stat,
    git_is_repository,
    git_pull,
    git_push,
    git_remote_verbose,
    git_status,
    git_sync_public_json_to_remote,
)
from lib.json_validate import parse_json_object, validate_public, validate_secrets
from lib.merge_config import (
    deep_merge,
    load_json_file,
    save_json_file,
    split_public_and_secrets,
    strip_api_keys,
    write_merged_to_opencode,
)
from lib.one_click import run_one_click_setup
from lib.paths import public_config_path, repo_root, secrets_config_path
from lib.run_cmd import run_cmd


def render_quickstart(root: Path) -> None:
    """Primary flow: numbered steps + one button."""
    root_res = root.resolve()
    st.markdown("### 快速开始（从这里进，到这里结束）")
    st.markdown(
        """
**开始** — 侧栏默认 **`/user/<登录名>/opencode`**。请放在**会跟你走的那块盘**上；若以 root 进容器，请改 `OPENCODE_ROOT` 指向你的真实家目录盘。  
换服务器但**硬盘或挂载不变**时，`config`、`data`、`state` 里的 **配置与历史** 会一起沿用。

**1** — （可选）填 **API Key**，只写入本机 `opencode.secrets.json`（**不进 Git**）。

**2** — 点 **一键安装并应用**：创建目录 →（按需）`npm` 安装 CLI → 写 `env_init.sh` → 合并出 `opencode.json`。

**结束** — 把页面最下方的 **`source "…/env_init.sh"`** 复制到**终端**执行，再运行 `opencode`。网页**不能**替你 `source` 终端。
"""
    )

    api_key = st.text_input(
        "API Key（CodexZH / OpenAI 兼容，对应 `provider.openai`）",
        type="password",
        placeholder="sk-…（可不填则保留已有 secrets）",
        key="quick_api_key",
        help="写入 tracked_config/opencode.secrets.json，已 .gitignore",
    )
    force_npm = st.checkbox("强制重新 npm 安装（已有 opencode 时勾选）", value=False, key="quick_force_npm")

    if st.button("一键安装并应用配置", type="primary", key="one_click_btn"):
        with st.spinner("正在执行（npm 可能较慢）…"):
            ok, lines = run_one_click_setup(root, api_key=api_key or "", force_npm=force_npm)
        st.text_area("执行记录", value="\n\n".join(lines), height=min(400, 120 + 20 * len(lines)), disabled=True)
        if ok:
            st.success("一键步骤已完成。")
            _maybe_auto_sync_public()
            bin_oc = root / "bin" / "opencode"
            if bin_oc.is_file():
                c, o, e = run_cmd(
                    [str(bin_oc), "--version"],
                    cwd=str(root),
                    timeout=60,
                    env=opencode_subprocess_env(root),
                )
                if c == 0 and (o or e).strip():
                    st.caption("界面内自检 `opencode --version`：")
                    st.code((o + e).strip(), language="text")
        else:
            st.error("未完成，请根据上方日志排查（常见：未装 Node/npm、网络、缺少 public.json）。")

    st.divider()
    st.markdown("#### 结束：在终端执行（每开一个终端做一次）")
    st.code(f'source "{root_res / "env_init.sh"}"', language="bash")
    st.caption("一键按钮会生成/更新其中的 `env_init.sh`。换机后若挂载路径不变，仍用同一行即可沿用配置与历史。")


def _maybe_auto_sync_public() -> None:
    if not st.session_state.get("git_auto_sync_enabled", False):
        return
    ok, msg = git_sync_public_json_to_remote()
    if ok:
        st.success(f"自动同步：{msg}")
    else:
        st.warning(f"自动同步失败：{msg}")


def render_deploy(root: Path) -> None:
    st.subheader("分步部署（进阶）")
    root_res = root.resolve()
    st.caption(f"OpenCode 根：`{root_res}`")
    st.markdown("**终端里加载环境（与快速开始顶部相同）：**")
    st.code(f'source "{root_res / "env_init.sh"}"', language="bash")

    bin_oc = root / "bin" / "opencode"
    extra = st.text_input(
        "子进程参数（留空则用 --version）",
        value="",
        key="opencode_cli_args",
        help="例如 --help；多个参数用空格分隔（简单拆分，不含引号转义）",
    )
    if st.button("在界面内运行 opencode（便携环境）", type="primary", key="opencode_in_app"):
        if not bin_oc.is_file():
            st.error(f"未找到 `{bin_oc}`，请先执行 npm 安装。")
        else:
            argv = [str(bin_oc)]
            raw = (extra or "").strip()
            if raw:
                argv.extend(raw.split())
            else:
                argv.append("--version")
            with st.spinner("运行中…"):
                code, out, err = run_cmd(argv, cwd=str(root), timeout=120, env=opencode_subprocess_env(root))
            st.code(out + err, language="text")
            if code != 0:
                st.error(f"退出码 {code}")
            else:
                st.success("子进程执行完成（环境已与 env_init.sh 对齐）")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("创建目录结构", type="secondary", key="mk_dirs"):
            for sub in ("bin", "lib", "config", "data", "state", "config/opencode"):
                (root / sub).mkdir(parents=True, exist_ok=True)
            st.success("已创建 bin / lib / config / data / state / config/opencode")
    with c2:
        st.caption("需本机 **Node.js** 与 **npm**。")

    if st.button("npm install -g opencode-ai（--prefix）", type="primary", key="npm_inst"):
        root.mkdir(parents=True, exist_ok=True)
        log_box = st.empty()
        with st.spinner("npm install…"):
            code, out, err = run_cmd(
                ["npm", "install", "-g", "opencode-ai", "--prefix", str(root)],
                cwd=str(root),
                timeout=1200,
            )
        log_box.code(out + err, language="text")
        bin_oc = root / "bin" / "opencode"
        if code != 0:
            st.error(f"npm 退出码 {code}")
        elif not bin_oc.is_file():
            st.error("未找到 bin/opencode")
        else:
            st.success(str(bin_oc))
            st.caption("可用上方「在界面内运行 opencode」自检；终端里日常用仍需 `source …/env_init.sh`。")

    if st.button("生成/更新 env_init.sh", key="env_init"):
        try:
            path = write_env_init(root)
            st.success(f"已写入 `{path}`")
            st.markdown("在要用 OpenCode 的**终端**里执行：")
            st.code(f"source {path}", language="bash")
            st.code(path.read_text(encoding="utf-8"), language="bash")
        except OSError as e:
            st.error(str(e))

    st.divider()
    st.caption("将 `tracked_config` 中 public + secrets **合并**写入本机 OpenCode")
    if st.button("合并写入 opencode.json", type="primary", key="merge_cfg"):
        pub = public_config_path()
        sec = secrets_config_path()
        if not pub.is_file():
            st.error(f"缺少 `{pub}`")
        else:
            try:
                write_merged_to_opencode(pub, sec, root)
                st.success("已写入 config/opencode/opencode.json")
                st.caption(
                    "若终端里已在跑 OpenCode，可能需要**重启 OpenCode**；新开终端请先 "
                    f"`source {root}/env_init.sh` 再运行 `opencode`。"
                )
            except Exception as e:
                st.error(str(e))


def render_config(root: Path) -> None:
    st.subheader("配置与密钥")
    pub_path = public_config_path()
    sec_path = secrets_config_path()
    if not pub_path.is_file():
        st.error(f"缺少 `{pub_path}`，请先用「Git / 导入」从现有 JSON 导入或手动创建。")
        return

    public = load_json_file(pub_path)
    secrets = load_json_file(sec_path) if sec_path.is_file() else {}
    merged = deep_merge(public, secrets)

    theme = str(public.get("theme", "") or "")
    theme = st.text_input("主题 theme", value=theme, key="dash_theme")
    auto = public.get("autoupdate", True)
    if not isinstance(auto, bool):
        auto = bool(auto)
    autoup = st.checkbox("autoupdate", value=auto, key="dash_autoup")

    providers = merged.get("provider")
    if not isinstance(providers, dict) or not providers:
        st.warning("`provider` 为空。可在下方「高级 JSON」中编辑 public。")
        edited_public = deepcopy(public)
        edited_public["theme"] = theme
        edited_public["autoupdate"] = autoup
        edited_secrets = deepcopy(secrets)
    else:
        edited_public = deepcopy(public)
        edited_secrets = deepcopy(secrets)
        edited_public["theme"] = theme
        edited_public["autoupdate"] = autoup

        st.caption("`apiKey` 只写入本机 secrets（不进入 Git）。")
        for name, spec in providers.items():
            if not isinstance(spec, dict):
                continue
            opts = spec.get("options")
            if not isinstance(opts, dict):
                opts = {}
            with st.expander(f"Provider **{name}**", expanded=False):
                base_default = str(opts.get("baseURL", "") or "")
                key_default = str(opts.get("apiKey", "") or "")
                base = st.text_input("baseURL", value=base_default, key=f"d_base_{name}")
                api_key = st.text_input("apiKey（secrets）", value=key_default, type="password", key=f"d_key_{name}")
                if "provider" not in edited_public:
                    edited_public["provider"] = {}
                if name not in edited_public["provider"] or not isinstance(edited_public["provider"][name], dict):
                    pub_spec = public.get("provider", {}).get(name) if isinstance(public.get("provider"), dict) else None
                    edited_public["provider"][name] = (
                        deepcopy(pub_spec) if isinstance(pub_spec, dict) else strip_api_keys(deepcopy(spec))
                    )
                po = edited_public["provider"][name]
                if "options" not in po or not isinstance(po["options"], dict):
                    po["options"] = {}
                po["options"]["baseURL"] = base
                po["options"]["apiKey"] = ""

                if "provider" not in edited_secrets:
                    edited_secrets["provider"] = {}
                if name not in edited_secrets["provider"] or not isinstance(edited_secrets["provider"][name], dict):
                    edited_secrets["provider"][name] = {"options": {}}
                if "options" not in edited_secrets["provider"][name]:
                    edited_secrets["provider"][name]["options"] = {}
                edited_secrets["provider"][name]["options"]["apiKey"] = api_key

    if st.button("保存配置", type="primary", key="save_cfg_main"):
        try:
            validate_public(edited_public)
            validate_secrets(edited_secrets)
            save_json_file(pub_path, edited_public)
            pub_path.parent.mkdir(parents=True, exist_ok=True)
            save_json_file(sec_path, edited_secrets)
            st.success("已保存 public + secrets")
            _maybe_auto_sync_public()
        except Exception as e:
            st.error(str(e))

    with st.expander("高级：编辑 JSON", expanded=False):
        t1, t2 = st.tabs(["public", "secrets"])
        with t1:
            ta = st.text_area(
                "opencode.public.json",
                value=json.dumps(edited_public, indent=2, ensure_ascii=False),
                height=260,
                key="dash_raw_pub",
            )
            if st.button("校验并保存 public", key="save_raw_pub"):
                try:
                    data = parse_json_object(ta)
                    validate_public(data)
                    save_json_file(pub_path, data)
                    st.success("已保存 public")
                    _maybe_auto_sync_public()
                    st.rerun()
                except Exception as e:
                    st.error(str(e))
        with t2:
            tb = st.text_area(
                "opencode.secrets.json",
                value=json.dumps(edited_secrets, indent=2, ensure_ascii=False),
                height=260,
                key="dash_raw_sec",
            )
            if st.button("校验并保存 secrets", key="save_raw_sec"):
                try:
                    data = parse_json_object(tb)
                    validate_secrets(data)
                    save_json_file(sec_path, data)
                    st.success("已保存 secrets（不会触发 Git 自动同步）")
                    st.rerun()
                except Exception as e:
                    st.error(str(e))


def render_git_and_import(root: Path) -> None:
    st.subheader("Git / 导入")
    _r = repo_root()
    st.caption(f"本工具仓库根：`{_r}`")

    if not git_is_repository():
        st.error("不是 Git 仓库")
        st.markdown(
            f"在 `{_r}` 执行 `git init`，或使用 `git clone` 你的**私有**仓库后再运行本应用。"
        )
    else:
        rc, rv_out, rv_err = git_remote_verbose()
        if rc == 0 and (rv_out or rv_err).strip():
            st.caption("当前 remote（请确认指向你的私有库）")
            st.code((rv_out + rv_err).strip(), language="text")

        if st.button("刷新状态", key="git_refresh"):
            st.rerun()
        code, out, err = git_status()
        if code != 0:
            st.error("git status 失败")
        st.code(out + err, language="text")
        c2, o2, e2 = git_diff_stat()
        if c2 == 0 and (o2 or e2).strip():
            st.caption("diff --stat")
            st.code(o2 + e2, language="text")

        msg = st.text_input("提交说明", value="chore: update tracked_config", key="dash_git_msg")
        g1, g2, g3 = st.columns(3)
        with g1:
            if st.button("add + commit（全部）", key="git_ac"):
                if not msg.strip():
                    st.warning("请填写提交说明")
                else:
                    a_code, a_out, a_err = git_add_all()
                    if a_code != 0:
                        st.error("git add 失败")
                        st.code(a_out + a_err)
                    else:
                        c_code, c_out, c_err = git_commit(msg.strip())
                        st.code(c_out + c_err, language="text")
                        if c_code == 0:
                            st.success("已提交")
        with g2:
            if st.button("pull --ff-only", key="git_pl"):
                with st.spinner("pull…"):
                    p_code, p_out, p_err = git_pull()
                st.code(p_out + p_err, language="text")
                if p_code != 0:
                    st.error("pull 失败")
        with g3:
            if st.button("push", key="git_ps"):
                with st.spinner("push…"):
                    s_code, s_out, s_err = git_push()
                st.code(s_out + s_err, language="text")
                if s_code != 0:
                    st.error("push 失败")

        st.divider()
        st.caption("仅提交并 push `tracked_config/opencode.public.json`（与侧栏「自动同步」相同逻辑）")
        if st.button("立即同步 public 到远程", key="git_sync_now"):
            ok, log = git_sync_public_json_to_remote()
            if ok:
                st.success(log)
            else:
                st.error(log)

    st.divider()
    st.markdown("**从现有 opencode.json 导入**（拆成 public + secrets）")
    src = st.text_input("文件路径（可相对 OpenCode 根）", key="dash_import_path")
    up = st.file_uploader("或上传 JSON", type=["json"], key="dash_import_up")
    if st.button("预览拆分", key="dash_import_prev"):
        text: str | None = None
        if up is not None:
            text = up.getvalue().decode("utf-8", errors="replace")
        elif src.strip():
            p = Path(src.strip()).expanduser()
            if not p.is_absolute():
                p = (root / p).resolve()
            else:
                p = p.resolve()
            if not p.is_file():
                st.error(f"文件不存在：{p}")
            else:
                text = p.read_text(encoding="utf-8")
        else:
            st.warning("请填路径或上传文件")
        if text is not None:
            try:
                full = parse_json_object(text)
                pub_d, sec_d = split_public_and_secrets(full)
                validate_public(pub_d)
                validate_secrets(sec_d)
                st.session_state["_import_preview_dash"] = (pub_d, sec_d)
                st.success("已生成预览")
            except Exception as e:
                st.error(str(e))

    prev = st.session_state.get("_import_preview_dash")
    if prev:
        pub_d, sec_d = prev
        with st.expander("预览 public", expanded=True):
            st.code(json.dumps(pub_d, indent=2, ensure_ascii=False), language="json")
        with st.expander("预览 secrets"):
            st.code(json.dumps(sec_d, indent=2, ensure_ascii=False), language="json")
        ow = st.checkbox("覆盖已有 public/secrets", value=False, key="dash_import_ow")
        if st.button("写入 tracked_config", type="primary", key="dash_import_write"):
            pp = public_config_path()
            sp = secrets_config_path()
            if pp.is_file() and not ow:
                st.error("public 已存在，勾选覆盖")
            elif sp.is_file() and not ow:
                st.error("secrets 已存在，勾选覆盖")
            else:
                try:
                    save_json_file(pp, pub_d)
                    save_json_file(sp, sec_d)
                    st.success("已写入")
                    st.session_state.pop("_import_preview_dash", None)
                    _maybe_auto_sync_public()
                    st.rerun()
                except Exception as e:
                    st.error(str(e))

    paste = st.text_area("或粘贴完整 JSON", height=160, key="dash_paste")
    if st.button("从粘贴预览", key="dash_paste_go"):
        if not paste.strip():
            st.warning("请粘贴 JSON")
        else:
            try:
                full = parse_json_object(paste)
                pub_d, sec_d = split_public_and_secrets(full)
                validate_public(pub_d)
                validate_secrets(sec_d)
                st.session_state["_import_preview_dash"] = (pub_d, sec_d)
                st.rerun()
            except Exception as e:
                st.error(str(e))
