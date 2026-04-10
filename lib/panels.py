"""Single-page dashboard sections (deploy / config / git+import)."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import streamlit as st

from lib.env_init import opencode_subprocess_env, write_env_init
from lib.git_ops import (
    gh_add_ssh_key,
    gh_auth_status,
    gh_cli_version,
    install_gh_cli,
    git_add_all,
    git_commit,
    git_current_branch,
    git_diff_stat,
    git_get_config,
    git_get_remote_url,
    git_is_repository,
    git_pull,
    git_push,
    git_push_set_upstream_origin,
    git_remote_verbose,
    git_set_remote_url,
    git_set_config,
    git_status,
    git_sync_public_json_to_remote,
    ssh_accept_github_hostkey,
    ssh_default_key_exists,
    ssh_default_pubkey_path,
    ssh_generate_default_key,
    ssh_test_github_connection,
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
from lib.skills import (
    SkillContent,
    available_skill_scopes,
    delete_skill,
    list_skills,
    load_skill,
    parse_skill_markdown,
    render_skill_markdown,
    save_skill,
    validate_skill_name,
)


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
    force_npm = st.checkbox(
        "强制重新 npm 安装（已有 opencode 时勾选）", value=False, key="quick_force_npm"
    )

    if st.button("一键安装并应用配置", type="primary", key="one_click_btn"):
        with st.spinner("正在执行（npm 可能较慢）…"):
            ok, lines = run_one_click_setup(
                root, api_key=api_key or "", force_npm=force_npm
            )
        st.text_area(
            "执行记录",
            value="\n\n".join(lines),
            height=min(400, 120 + 20 * len(lines)),
            disabled=True,
        )
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
            st.error(
                "未完成，请根据上方日志排查（常见：未装 Node/npm、网络、缺少 public.json）。"
            )

    st.divider()
    st.markdown("#### 结束：在终端执行（每开一个终端做一次）")
    st.code(f'source "{root_res / "env_init.sh"}"', language="bash")
    st.caption(
        "一键按钮会生成/更新其中的 `env_init.sh`。换机后若挂载路径不变，仍用同一行即可沿用配置与历史。"
    )


def _maybe_auto_sync_public() -> None:
    if not st.session_state.get("git_auto_sync_enabled", False):
        return
    ok, msg = git_sync_public_json_to_remote()
    if ok:
        st.success(f"自动同步：{msg}")
    else:
        st.warning(f"自动同步失败：{msg}")


def _ssh_auth_ok(output: str) -> bool:
    return "successfully authenticated" in output.lower()


def _run_github_ssh_quick_setup(
    key_comment: str, key_title: str
) -> tuple[bool, str, str | None]:
    logs: list[str] = []

    gh_code, gh_out, gh_err = gh_cli_version()
    logs.append("$ gh --version\n" + (gh_out + gh_err).strip())
    if gh_code != 0:
        i_code, i_out, i_err = install_gh_cli()
        logs.append("$ install gh\n" + (i_out + i_err).strip())
        if i_code != 0:
            return (
                False,
                "\n\n".join(part for part in logs if part.strip()),
                "自动安装 gh 失败，请手动安装后重试。",
            )

    auth_code, auth_out, auth_err = gh_auth_status()
    logs.append("$ gh auth status\n" + (auth_out + auth_err).strip())
    if auth_code != 0:
        return (
            False,
            "\n\n".join(part for part in logs if part.strip()),
            "需要先在终端执行 `gh auth login -w` 完成 GitHub 登录，然后回来再点一次。",
        )

    if not ssh_default_key_exists():
        g_code, g_out, g_err = ssh_generate_default_key(key_comment)
        logs.append("$ ssh-keygen -t ed25519 ...\n" + (g_out + g_err).strip())
        if g_code != 0 and not ssh_default_key_exists():
            return (
                False,
                "\n\n".join(part for part in logs if part.strip()),
                "默认 SSH 密钥生成失败，请检查上方日志。",
            )

    h_code, h_out, h_err = ssh_accept_github_hostkey()
    logs.append("$ ssh-keyscan github.com\n" + (h_out + h_err).strip())

    a_code, a_out, a_err = gh_add_ssh_key(str(ssh_default_pubkey_path()), key_title)
    logs.append("$ gh ssh-key add ...\n" + (a_out + a_err).strip())

    t_code, t_out, t_err = ssh_test_github_connection()
    test_output = (t_out + t_err).strip()
    logs.append("$ ssh -T git@github.com\n" + test_output)
    if _ssh_auth_ok(test_output):
        return True, "\n\n".join(part for part in logs if part.strip()), None

    if a_code != 0:
        return (
            False,
            "\n\n".join(part for part in logs if part.strip()),
            "公钥上传未成功，请检查 gh 权限或网络；若你确认 key 已上传，可直接在终端执行 `ssh -T git@github.com` 自检。",
        )

    if h_code != 0 and t_code != 0:
        return (
            False,
            "\n\n".join(part for part in logs if part.strip()),
            "主机指纹或 SSH 认证未完成，请在终端执行 `ssh -T git@github.com` 查看详细原因。",
        )

    return (
        False,
        "\n\n".join(part for part in logs if part.strip()),
        "SSH 连通性还未确认通过，请在终端执行 `ssh -T git@github.com` 查看详细原因。",
    )


def _ensure_opencode_dirs(root: Path) -> None:
    for sub in ("bin", "lib", "config", "data", "state", "config/opencode"):
        (root / sub).mkdir(parents=True, exist_ok=True)


def _install_opencode_cli(root: Path) -> tuple[int, str, str]:
    root.mkdir(parents=True, exist_ok=True)
    _ensure_opencode_dirs(root)
    return run_cmd(
        ["npm", "install", "-g", "opencode-ai", "--prefix", str(root)],
        cwd=str(root),
        timeout=1200,
    )


def _apply_runtime_config(root: Path) -> tuple[bool, str]:
    pub = public_config_path()
    sec = secrets_config_path()
    if not pub.is_file():
        return False, f"缺少 `{pub}`"
    try:
        write_env_init(root)
        write_merged_to_opencode(pub, sec, root)
        return True, "已更新 env_init.sh 和 config/opencode/opencode.json"
    except Exception as e:
        return False, str(e)


def _save_git_identity(
    name: str, email: str, *, write_global: bool
) -> tuple[bool, str]:
    outputs: list[str] = []
    success = True
    for global_scope in [False, True] if write_global else [False]:
        n_code, n_out, n_err = git_set_config(
            "user.name", name, global_scope=global_scope
        )
        e_code, e_out, e_err = git_set_config(
            "user.email", email, global_scope=global_scope
        )
        outputs.append(n_out + n_err + e_out + e_err)
        success = success and n_code == 0 and e_code == 0
    return success, "".join(outputs)


def _load_import_candidate(
    root: Path, src: str, upload, paste: str
) -> tuple[str | None, str | None]:
    if upload is not None:
        return upload.getvalue().decode("utf-8", errors="replace"), None
    if src.strip():
        p = Path(src.strip()).expanduser()
        if not p.is_absolute():
            p = (root / p).resolve()
        else:
            p = p.resolve()
        if not p.is_file():
            return None, f"文件不存在：{p}"
        return p.read_text(encoding="utf-8"), None
    if paste.strip():
        return paste, None
    return None, "请填路径、上传文件或粘贴 JSON"


def _import_into_tracked_config(
    root: Path,
    *,
    src: str,
    upload,
    paste: str,
    overwrite: bool,
) -> tuple[bool, str, tuple[dict, dict] | None]:
    text, err = _load_import_candidate(root, src, upload, paste)
    if err:
        return False, err, None

    try:
        full = parse_json_object(text or "")
        pub_d, sec_d = split_public_and_secrets(full)
        validate_public(pub_d)
        validate_secrets(sec_d)
    except Exception as e:
        return False, str(e), None

    pp = public_config_path()
    sp = secrets_config_path()
    if pp.is_file() and not overwrite:
        return False, "public 已存在，勾选覆盖后再试", (pub_d, sec_d)
    if sp.is_file() and not overwrite:
        return False, "secrets 已存在，勾选覆盖后再试", (pub_d, sec_d)

    try:
        save_json_file(pp, pub_d)
        save_json_file(sp, sec_d)
    except Exception as e:
        return False, str(e), (pub_d, sec_d)

    return True, "已写入 tracked_config", (pub_d, sec_d)


def render_deploy(root: Path) -> None:
    st.subheader("分步部署（进阶）")
    root_res = root.resolve()
    st.caption(f"OpenCode 根：`{root_res}`")
    st.markdown("**终端里加载环境（与快速开始顶部相同）：**")
    st.code(f'source "{root_res / "env_init.sh"}"', language="bash")

    st.caption("常用只需要下面两个主按钮：先补齐本机环境，再写入运行配置。")

    if st.button("一键补齐本机 OpenCode 环境", type="primary", key="deploy_setup_all"):
        with st.spinner("正在安装/更新 OpenCode CLI..."):
            code, out, err = _install_opencode_cli(root)
        st.code(out + err, language="text")
        if code != 0:
            st.error(f"npm 退出码 {code}")
        elif not (root / "bin" / "opencode").is_file():
            st.error("未找到 bin/opencode")
        else:
            try:
                path = write_env_init(root)
                st.success(f"已补齐 CLI 与环境文件：`{path}`")
            except OSError as e:
                st.error(str(e))

    st.caption("配置改完后，点一次把 public + secrets 合并写入运行目录。")
    if st.button("一键写入运行配置", type="primary", key="deploy_apply_runtime"):
        ok, msg = _apply_runtime_config(root)
        if ok:
            st.success(msg)
            st.caption(
                f"若终端里已在跑 OpenCode，可能需要重启；新开终端先执行 `source {root}/env_init.sh`。"
            )
        else:
            st.error(msg)

    with st.expander("手动步骤与自检", expanded=False):
        bin_oc = root / "bin" / "opencode"
        extra = st.text_input(
            "子进程参数（留空则用 --version）",
            value="",
            key="opencode_cli_args",
            help="例如 --help；多个参数用空格分隔（简单拆分，不含引号转义）",
        )
        if st.button("在界面内运行 opencode", key="opencode_in_app"):
            if not bin_oc.is_file():
                st.error(f"未找到 `{bin_oc}`，请先安装 CLI。")
            else:
                argv = [str(bin_oc)]
                raw = (extra or "").strip()
                if raw:
                    argv.extend(raw.split())
                else:
                    argv.append("--version")
                with st.spinner("运行中…"):
                    code, out, err = run_cmd(
                        argv,
                        cwd=str(root),
                        timeout=120,
                        env=opencode_subprocess_env(root),
                    )
                st.code(out + err, language="text")
                if code != 0:
                    st.error(f"退出码 {code}")
                else:
                    st.success("子进程执行完成")
        if st.button("仅生成/更新 env_init.sh", key="env_init"):
            try:
                path = write_env_init(root)
                st.success(f"已写入 `{path}`")
                st.code(f"source {path}", language="bash")
            except OSError as e:
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
                base = st.text_input(
                    "baseURL", value=base_default, key=f"d_base_{name}"
                )
                api_key = st.text_input(
                    "apiKey（secrets）",
                    value=key_default,
                    type="password",
                    key=f"d_key_{name}",
                )
                if "provider" not in edited_public:
                    edited_public["provider"] = {}
                if name not in edited_public["provider"] or not isinstance(
                    edited_public["provider"][name], dict
                ):
                    pub_spec = (
                        public.get("provider", {}).get(name)
                        if isinstance(public.get("provider"), dict)
                        else None
                    )
                    edited_public["provider"][name] = (
                        deepcopy(pub_spec)
                        if isinstance(pub_spec, dict)
                        else strip_api_keys(deepcopy(spec))
                    )
                po = edited_public["provider"][name]
                if "options" not in po or not isinstance(po["options"], dict):
                    po["options"] = {}
                po["options"]["baseURL"] = base
                po["options"]["apiKey"] = ""

                if "provider" not in edited_secrets:
                    edited_secrets["provider"] = {}
                if name not in edited_secrets["provider"] or not isinstance(
                    edited_secrets["provider"][name], dict
                ):
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


def _skill_scope_options() -> tuple[dict[str, object], list[str]]:
    scopes = available_skill_scopes()
    mapping = {scope.label: scope for scope in scopes}
    return mapping, [scope.label for scope in scopes]


def _load_skill_form(scope_key: str, *, record=None) -> None:
    prefix = f"skill_form_{scope_key}_"
    st.session_state[f"{prefix}raw_markdown"] = ""
    if record is None or record.content is None:
        st.session_state[f"{prefix}original_name"] = ""
        st.session_state[f"{prefix}name"] = ""
        st.session_state[f"{prefix}description"] = ""
        st.session_state[f"{prefix}license"] = ""
        st.session_state[f"{prefix}compatibility"] = "opencode"
        st.session_state[f"{prefix}metadata"] = "{}"
        st.session_state[f"{prefix}body"] = (
            "## What I do\n- \n\n## When to use me\n- \n"
        )
        return

    content = record.content
    st.session_state[f"{prefix}original_name"] = record.folder_name
    st.session_state[f"{prefix}name"] = content.name
    st.session_state[f"{prefix}description"] = content.description
    st.session_state[f"{prefix}license"] = content.license
    st.session_state[f"{prefix}compatibility"] = content.compatibility or "opencode"
    st.session_state[f"{prefix}metadata"] = json.dumps(
        content.metadata or {}, indent=2, ensure_ascii=False
    )
    st.session_state[f"{prefix}body"] = content.body


def _apply_skill_content_to_form(
    scope_key: str, content: SkillContent, *, original_name: str = ""
) -> None:
    prefix = f"skill_form_{scope_key}_"
    st.session_state[f"{prefix}original_name"] = original_name
    st.session_state[f"{prefix}name"] = content.name
    st.session_state[f"{prefix}description"] = content.description
    st.session_state[f"{prefix}license"] = content.license
    st.session_state[f"{prefix}compatibility"] = content.compatibility or "opencode"
    st.session_state[f"{prefix}metadata"] = json.dumps(
        content.metadata or {}, indent=2, ensure_ascii=False
    )
    st.session_state[f"{prefix}body"] = content.body


def render_skills() -> None:
    st.subheader("Skill 管理")
    st.caption(
        "按 OpenCode 官方约定管理 `SKILL.md`。支持项目级与全局目录，变更后无需写入 opencode.json。"
    )

    scope_map, scope_labels = _skill_scope_options()
    if "skills_scope_select" not in st.session_state and scope_labels:
        st.session_state["skills_scope_select"] = scope_labels[0]
    selected_label = st.selectbox(
        "Skill 目录",
        options=scope_labels,
        key="skills_scope_select",
        help="支持 .opencode / .claude / .agents 的项目级和全局级 skills 目录。",
    )
    scope = scope_map[selected_label]
    scope_key = scope.key
    scope_dir = scope.directory

    records = list_skills(scope_dir)
    record_map = {record.folder_name: record for record in records}

    st.caption(f"当前目录：`{scope_dir}`")
    st.caption(f"当前共发现 `{len(records)}` 个 skill。")

    options = ["__new__"] + [record.folder_name for record in records]
    selected_key = f"skills_selected_{scope_key}"
    pending_selected_key = f"skills_selected_pending_{scope_key}"
    pending_selected = st.session_state.pop(pending_selected_key, None)
    if pending_selected in options:
        st.session_state[selected_key] = pending_selected
    elif st.session_state.get(selected_key) not in options:
        st.session_state[selected_key] = "__new__"

    selected_folder = st.selectbox(
        "选择 skill",
        options=options,
        key=selected_key,
        format_func=lambda value: "新建 skill" if value == "__new__" else value,
    )

    loaded_key = f"skills_loaded_{scope_key}"
    if st.session_state.get(loaded_key) != selected_folder:
        if selected_folder == "__new__":
            _load_skill_form(scope_key)
        else:
            _load_skill_form(scope_key, record=record_map[selected_folder])
        st.session_state[loaded_key] = selected_folder
        st.session_state.pop(f"skills_preview_content_{scope_key}", None)

    prefix = f"skill_form_{scope_key}_"
    st.markdown("#### 已有 skills")
    if not records:
        st.info("当前目录还没有 skill。")
    else:
        rows = []
        for record in records:
            rows.append(
                {
                    "name": record.folder_name,
                    "description": record.content.description
                    if record.content
                    else "解析失败",
                    "status": "正常" if record.content else f"错误: {record.error}",
                }
            )
        st.dataframe(rows, use_container_width=True, hide_index=True)

    if selected_folder != "__new__":
        current_record = record_map[selected_folder]
        st.caption(f"当前文件：`{current_record.file_path}`")
        if current_record.error:
            st.warning(current_record.error)

    st.markdown("#### 编辑")
    st.text_area(
        "完整 SKILL.md（可直接粘贴）",
        key=f"{prefix}raw_markdown",
        height=180,
        help="支持直接粘贴整份 `SKILL.md`，自动解析 frontmatter 和正文到下方表单。",
    )
    import_col, clear_col = st.columns(2)
    with import_col:
        if st.button("从完整 SKILL.md 解析", key=f"skills_import_markdown_{scope_key}"):
            try:
                raw = st.session_state[f"{prefix}raw_markdown"].strip()
                if not raw:
                    raise ValueError("请先粘贴完整的 SKILL.md 内容")
                content = parse_skill_markdown(raw)
                original_name = st.session_state.get(f"{prefix}original_name", "")
                _apply_skill_content_to_form(
                    scope_key,
                    content,
                    original_name=original_name
                    if original_name == content.name
                    else "",
                )
                st.session_state[f"skills_preview_content_{scope_key}"] = (
                    render_skill_markdown(content)
                )
                st.success("已从完整 SKILL.md 解析到表单")
                st.rerun()
            except Exception as exc:
                st.error(str(exc))
    with clear_col:
        if st.button("清空粘贴区", key=f"skills_clear_markdown_{scope_key}"):
            st.session_state[f"{prefix}raw_markdown"] = ""
            st.rerun()

    meta_col1, meta_col2 = st.columns(2)
    with meta_col1:
        st.text_input(
            "name",
            key=f"{prefix}name",
            help="目录名和 frontmatter 中的 name 必须一致，只能用小写字母、数字和连字符。",
        )
        st.text_input("description", key=f"{prefix}description")
        st.text_input("license", key=f"{prefix}license")
    with meta_col2:
        st.text_input(
            "compatibility",
            key=f"{prefix}compatibility",
            help="可留空，常见值是 `opencode`。",
        )
        st.text_area(
            "metadata(JSON object)",
            key=f"{prefix}metadata",
            height=128,
            help='例如 {"audience": "team", "workflow": "review"}',
        )
    st.text_area("正文", key=f"{prefix}body", height=280)

    def _build_skill_content() -> SkillContent:
        metadata_raw = st.session_state[f"{prefix}metadata"].strip() or "{}"
        metadata = parse_json_object(metadata_raw)
        normalized_metadata = {
            str(k).strip(): str(v).strip()
            for k, v in metadata.items()
            if str(k).strip() and str(v).strip()
        }
        content = SkillContent(
            name=validate_skill_name(st.session_state[f"{prefix}name"]),
            description=st.session_state[f"{prefix}description"].strip(),
            license=st.session_state[f"{prefix}license"].strip(),
            compatibility=st.session_state[f"{prefix}compatibility"].strip(),
            metadata=normalized_metadata,
            body=st.session_state[f"{prefix}body"].rstrip() + "\n",
        )
        if not content.description:
            raise ValueError("description 不能为空")
        return content

    st.info(
        "保存或删除 skill 后，需重启当前 `opencode` 会话，新的 skill 列表才会生效。"
    )

    save_col, preview_col, delete_col = st.columns(3)
    with save_col:
        if st.button("保存 skill", type="primary", key=f"skills_save_{scope_key}"):
            try:
                content = _build_skill_content()
                original_name = st.session_state.get(f"{prefix}original_name") or None
                save_skill(scope_dir, content, original_name=original_name)
                st.session_state[pending_selected_key] = content.name
                st.session_state[loaded_key] = None
                st.session_state[f"skills_preview_content_{scope_key}"] = (
                    render_skill_markdown(content)
                )
                st.success(
                    f"已保存 `{content.name}`，重启 `opencode` 后可加载新 skill。"
                )
                st.rerun()
            except Exception as exc:
                st.error(str(exc))
    with preview_col:
        if st.button("预览 SKILL.md", key=f"skills_preview_{scope_key}"):
            try:
                content = _build_skill_content()
                st.session_state[f"skills_preview_content_{scope_key}"] = (
                    render_skill_markdown(content)
                )
            except Exception as exc:
                st.error(str(exc))
    with delete_col:
        confirm_key = f"skills_delete_confirm_{scope_key}"
        if selected_folder != "__new__":
            st.checkbox("确认删除目录", value=False, key=confirm_key)
            if st.button("删除 skill", key=f"skills_delete_{scope_key}"):
                if not st.session_state.get(confirm_key, False):
                    st.warning("请先勾选“确认删除目录”")
                else:
                    try:
                        delete_skill(scope_dir, selected_folder)
                        st.session_state[pending_selected_key] = "__new__"
                        st.session_state[loaded_key] = None
                        st.session_state.pop(
                            f"skills_preview_content_{scope_key}", None
                        )
                        st.success(
                            f"已删除 `{selected_folder}`，重启 `opencode` 后当前会话才会更新 skill 列表。"
                        )
                        st.rerun()
                    except Exception as exc:
                        st.error(str(exc))

    preview_text = st.session_state.get(f"skills_preview_content_{scope_key}")
    if preview_text:
        with st.expander("预览 SKILL.md", expanded=True):
            st.code(preview_text, language="markdown")


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

        origin_code, origin_out, origin_err = git_get_remote_url("origin")
        current_origin = (origin_out or "").strip() if origin_code == 0 else ""
        st.markdown("#### Git 远程（origin）")
        st.caption(
            "建议改成你自己的 fork 或私有仓库；后续看板内 push 默认都会用这个 origin。"
        )
        remote_url = st.text_input(
            "origin 地址",
            value=current_origin,
            key="dash_git_origin_url",
            placeholder="git@github.com:<user>/<repo>.git",
        )
        if origin_code != 0 and (origin_err or "").strip():
            st.caption(
                "当前还没有配置 origin，保存时会自动执行 `git remote add origin ...`。"
            )
        if st.button("保存 origin 远程", key="git_set_origin"):
            if not remote_url.strip():
                st.warning("请填写 origin 地址")
            else:
                r_code, r_out, r_err = git_set_remote_url("origin", remote_url.strip())
                st.code(r_out + r_err, language="text")
                if r_code == 0:
                    st.success("origin 已更新")
                    st.rerun()
                else:
                    st.error("origin 设置失败，请检查上方日志")

        st.markdown("#### Git 身份（user.name / user.email）")
        c_name_local, o_name_local, _ = git_get_config("user.name", global_scope=False)
        c_mail_local, o_mail_local, _ = git_get_config("user.email", global_scope=False)
        c_name_global, o_name_global, _ = git_get_config("user.name", global_scope=True)
        c_mail_global, o_mail_global, _ = git_get_config(
            "user.email", global_scope=True
        )

        local_name = (o_name_local or "").strip() if c_name_local == 0 else ""
        local_email = (o_mail_local or "").strip() if c_mail_local == 0 else ""
        global_name = (o_name_global or "").strip() if c_name_global == 0 else ""
        global_email = (o_mail_global or "").strip() if c_mail_global == 0 else ""

        effective_name = local_name or global_name
        effective_email = local_email or global_email
        if effective_name and effective_email:
            st.caption(f"当前生效身份：{effective_name} <{effective_email}>")
        else:
            st.warning(
                "当前未检测到完整 Git 身份，提交会失败。请先设置 user.name 和 user.email。"
            )

        st.caption(
            f"仓库级：name={local_name or '(未设置)'} / email={local_email or '(未设置)'}；"
            f"全局：name={global_name or '(未设置)'} / email={global_email or '(未设置)'}"
        )

        id_name = st.text_input(
            "Git 用户名（user.name）",
            value=effective_name,
            key="dash_git_user_name",
            placeholder="Your Name",
        )
        id_email = st.text_input(
            "Git 邮箱（user.email）",
            value=effective_email,
            key="dash_git_user_email",
            placeholder="you@example.com",
        )
        save_global_identity = st.checkbox(
            "同时写入全局 Git 身份（--global）",
            value=False,
            key="git_set_identity_global_toggle",
        )
        if st.button("保存 Git 身份", type="primary", key="git_set_identity_main"):
            if not id_name.strip() or not id_email.strip():
                st.warning("请同时填写 user.name 和 user.email")
            else:
                ok, output = _save_git_identity(
                    id_name.strip(), id_email.strip(), write_global=save_global_identity
                )
                st.code(output, language="text")
                if ok:
                    scope = "全局" if save_global_identity else "当前仓库"
                    st.success(f"已写入{scope} Git 身份")
                    st.rerun()
                else:
                    st.error("设置失败，请检查上方日志")

        code, out, err = git_status()
        if code != 0:
            st.error("git status 失败")
        st.code(out + err, language="text")
        c2, o2, e2 = git_diff_stat()
        if c2 == 0 and (o2 or e2).strip():
            st.caption("diff --stat")
            st.code(o2 + e2, language="text")

        st.divider()
        st.markdown("#### GitHub SSH 一键配置（gh）")
        st.caption(
            "默认点一次就行：自动安装 `gh`、生成默认 SSH 密钥、上传公钥并测试连通性。"
        )

        default_pub = ssh_default_pubkey_path()
        st.caption(f"默认公钥路径：`{default_pub}`")

        with st.expander("高级选项", expanded=False):
            key_comment = st.text_input(
                "SSH key 注释（comment）",
                value="opencode_quickstart@github",
                key="dash_ssh_comment",
            )
            key_title = st.text_input(
                "GitHub 上显示的 key 标题",
                value="opencode-quickstart-key",
                key="dash_ssh_title",
            )

        key_comment = st.session_state.get(
            "dash_ssh_comment", "opencode_quickstart@github"
        )
        key_title = st.session_state.get("dash_ssh_title", "opencode-quickstart-key")

        gh_code, gh_out, gh_err = gh_cli_version()
        auth_code, auth_out, auth_err = (
            gh_auth_status() if gh_code == 0 else (1, "", "")
        )

        if gh_code == 0 and auth_code != 0:
            st.warning("当前还没有登录 GitHub。这个步骤请直接在命令行完成。")
            st.markdown("**请在终端执行**")
            st.code(
                "/root/.local/bin/gh auth login --hostname github.com --git-protocol ssh --web",
                language="bash",
            )
            st.caption(
                "终端里会显示验证码；在 GitHub 页面完成授权后，回来点“检查 GitHub 登录状态”。"
            )
            if st.button("检查 GitHub 登录状态", key="gh_auth_refresh"):
                st.rerun()

        if gh_code == 0 and auth_code == 0:
            st.caption("当前 `gh` 已登录 GitHub。")

        if st.button("一键准备 GitHub SSH", type="primary", key="gh_setup_all"):
            with st.spinner("正在准备 GitHub SSH..."):
                ok, logs, hint = _run_github_ssh_quick_setup(
                    (key_comment or "").strip() or "opencode_quickstart@github",
                    (key_title or "").strip() or "opencode-quickstart-key",
                )
            if logs.strip():
                st.code(logs, language="text")
            if ok:
                st.success("GitHub SSH 已就绪，可以直接 push。")
            elif hint:
                st.warning(hint)

        with st.expander("手动排查", expanded=False):
            if gh_code == 0 and auth_code == 0:
                st.caption("当前 `gh` 已安装且已登录。")
            else:
                st.code(
                    (gh_out + gh_err + auth_out + auth_err).strip(), language="text"
                )
            if st.button("仅测试 GitHub SSH 连通性", key="gh_test_ssh"):
                t_code, t_out, t_err = ssh_test_github_connection()
                st.code(t_out + t_err, language="text")
                if _ssh_auth_ok(t_out + t_err):
                    st.success("SSH 认证通过，可以 push。")
                else:
                    st.warning("未检测到认证成功信息，请根据日志排查。")

        st.divider()
        st.caption(
            "仅提交并 push `tracked_config/opencode.public.json`（与侧栏「自动同步」相同逻辑）"
        )
        if st.button("一键同步 public 到远程", type="primary", key="git_sync_now"):
            ok, log = git_sync_public_json_to_remote()
            if ok:
                st.success(log)
            else:
                st.error(log)

        with st.expander("手动 Git 操作", expanded=False):
            msg = st.text_input(
                "提交说明", value="chore: update tracked_config", key="dash_git_msg"
            )
            if st.button("刷新状态", key="git_refresh"):
                st.rerun()
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
            if st.button("pull --ff-only", key="git_pl"):
                with st.spinner("pull…"):
                    p_code, p_out, p_err = git_pull()
                st.code(p_out + p_err, language="text")
                if p_code != 0:
                    st.error("pull 失败")
            if st.button("push", key="git_ps"):
                with st.spinner("push…"):
                    s_code, s_out, s_err = git_push()
                st.code(s_out + s_err, language="text")
                if s_code != 0:
                    st.error("push 失败")
            if st.button("首次推送：设置 upstream 并 push", key="git_ps_upstream"):
                b_code, b_out, b_err = git_current_branch()
                branch = (b_out or "").strip()
                if b_code != 0 or not branch:
                    st.error("无法识别当前分支")
                    st.code(b_out + b_err, language="text")
                else:
                    with st.spinner(f"push --set-upstream origin {branch} …"):
                        u_code, u_out, u_err = git_push_set_upstream_origin(branch)
                    st.code(u_out + u_err, language="text")
                    if u_code == 0:
                        st.success(f"已设置 upstream：origin/{branch}")
                    else:
                        st.error("设置 upstream 失败")

    st.divider()
    st.markdown("**从现有 opencode.json 导入**（拆成 public + secrets）")
    src = st.text_input("文件路径（可相对 OpenCode 根）", key="dash_import_path")
    up = st.file_uploader("或上传 JSON", type=["json"], key="dash_import_up")
    paste = st.text_area("或粘贴完整 JSON", height=160, key="dash_paste")
    ow = st.checkbox("覆盖已有 public/secrets", value=False, key="dash_import_ow")
    if st.button("一键导入到 tracked_config", type="primary", key="dash_import_main"):
        ok, msg, preview = _import_into_tracked_config(
            root,
            src=src,
            upload=up,
            paste=paste,
            overwrite=ow,
        )
        if preview is not None:
            st.session_state["_import_preview_dash"] = preview
        if ok:
            st.success(msg)
            _maybe_auto_sync_public()
            st.rerun()
        else:
            st.error(msg)

    with st.expander("预览拆分结果", expanded=False):
        if st.button("仅生成预览", key="dash_import_prev"):
            text, err = _load_import_candidate(root, src, up, paste)
            if err:
                st.warning(err)
            else:
                try:
                    full = parse_json_object(text or "")
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
