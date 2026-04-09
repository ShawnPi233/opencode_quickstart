"""Git commands scoped to repository root."""

from __future__ import annotations

from pathlib import Path

from lib.paths import repo_root
from lib.run_cmd import run_cmd

# 仅同步可进 Git 的公开配置；密钥文件在 .gitignore 中，不会被 add
PUBLIC_JSON_REL = "tracked_config/opencode.public.json"


def git_argv(*args: str) -> list[str]:
    return ["git", "-C", str(repo_root()), *args]


def git_is_repository() -> bool:
    """True if repo_root() is a Git work tree (has .git)."""
    code, out, _ = run_cmd(git_argv("rev-parse", "--is-inside-work-tree"), cwd=None, timeout=15)
    return code == 0 and out.strip() == "true"


def git_status() -> tuple[int, str, str]:
    return run_cmd(git_argv("status", "--porcelain", "-b"), cwd=None, timeout=60)


def git_diff_stat() -> tuple[int, str, str]:
    return run_cmd(git_argv("diff", "--stat"), cwd=None, timeout=60)


def git_add_all() -> tuple[int, str, str]:
    return run_cmd(git_argv("add", "-A"), cwd=None, timeout=120)


def git_commit(message: str) -> tuple[int, str, str]:
    return run_cmd(git_argv("commit", "-m", message), cwd=None, timeout=120)


def git_pull() -> tuple[int, str, str]:
    return run_cmd(git_argv("pull", "--ff-only"), cwd=None, timeout=300)


def git_push() -> tuple[int, str, str]:
    return run_cmd(git_argv("push"), cwd=None, timeout=300)


def git_current_branch() -> tuple[int, str, str]:
    return run_cmd(git_argv("branch", "--show-current"), cwd=None, timeout=30)


def git_push_set_upstream_origin(branch: str) -> tuple[int, str, str]:
    return run_cmd(git_argv("push", "--set-upstream", "origin", branch), cwd=None, timeout=300)


def git_remote_verbose() -> tuple[int, str, str]:
    return run_cmd(git_argv("remote", "-v"), cwd=None, timeout=30)


def git_get_config(key: str, *, global_scope: bool = False) -> tuple[int, str, str]:
    argv = ["config"]
    if global_scope:
        argv.append("--global")
    argv.extend(["--get", key])
    return run_cmd(git_argv(*argv), cwd=None, timeout=30)


def git_set_config(key: str, value: str, *, global_scope: bool = False) -> tuple[int, str, str]:
    argv = ["config"]
    if global_scope:
        argv.append("--global")
    argv.extend([key, value])
    return run_cmd(git_argv(*argv), cwd=None, timeout=30)


def gh_cli_version() -> tuple[int, str, str]:
    return run_cmd(["gh", "--version"], cwd=None, timeout=30)


def gh_auth_status() -> tuple[int, str, str]:
    return run_cmd(["gh", "auth", "status"], cwd=None, timeout=30)


def ssh_default_pubkey_path() -> Path:
    return Path.home() / ".ssh" / "id_ed25519.pub"


def ssh_default_key_exists() -> bool:
    pub = ssh_default_pubkey_path()
    pri = pub.with_suffix("")
    return pub.is_file() and pri.is_file()


def ssh_generate_default_key(comment: str) -> tuple[int, str, str]:
    pub = ssh_default_pubkey_path()
    pri = pub.with_suffix("")
    if pub.is_file() or pri.is_file():
        return 1, "", f"默认密钥已存在：{pri} / {pub}\n"
    pri.parent.mkdir(parents=True, exist_ok=True)
    return run_cmd(
        ["ssh-keygen", "-t", "ed25519", "-C", comment, "-f", str(pri), "-N", ""],
        cwd=None,
        timeout=60,
    )


def gh_add_ssh_key(pubkey_path: str, title: str) -> tuple[int, str, str]:
    return run_cmd(["gh", "ssh-key", "add", pubkey_path, "--title", title], cwd=None, timeout=60)


def ssh_test_github_connection() -> tuple[int, str, str]:
    # `accept-new` avoids first-connect interactive prompt and only trusts first seen host key.
    return run_cmd(
        [
            "ssh",
            "-o",
            "BatchMode=yes",
            "-o",
            "StrictHostKeyChecking=accept-new",
            "-T",
            "git@github.com",
        ],
        cwd=None,
        timeout=30,
    )


def git_sync_public_json_to_remote(
    commit_message: str = "chore: sync opencode.public.json",
) -> tuple[bool, str]:
    """
    Stage only tracked_config/opencode.public.json, commit if there is a staged diff, then push.
    Does not add secrets or other files.
    """
    if not git_is_repository():
        return False, "当前项目根不是 Git 仓库"
    root = repo_root()
    pub = root / PUBLIC_JSON_REL
    if not pub.is_file():
        return False, f"缺少 {PUBLIC_JSON_REL}"

    c1, o1, e1 = run_cmd(git_argv("add", PUBLIC_JSON_REL), cwd=None, timeout=60)
    if c1 != 0:
        return False, (o1 + e1).strip() or "git add 失败"

    c2, _, _ = run_cmd(git_argv("diff", "--cached", "--quiet"), cwd=None, timeout=30)
    if c2 == 0:
        return True, "公开配置无变更，已跳过提交与 push"

    c3, o3, e3 = run_cmd(git_argv("commit", "-m", commit_message), cwd=None, timeout=120)
    if c3 != 0:
        return False, (o3 + e3).strip() or "git commit 失败"

    c4, o4, e4 = run_cmd(git_argv("push"), cwd=None, timeout=300)
    log = (o3 + e3 + o4 + e4).strip()
    if c4 != 0:
        return False, log or "git push 失败（检查 origin 与凭据）"
    return True, log or "已提交并 push（仅 opencode.public.json）"
