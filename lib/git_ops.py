"""Git/GitHub helpers used by the Streamlit dashboard."""

from __future__ import annotations

import os
from pathlib import Path

from lib.paths import public_config_path, repo_root
from lib.run_cmd import run_cmd


def _repo() -> Path:
    return repo_root()


def _gh_bin() -> str:
    preferred = Path.home() / ".local" / "bin" / "gh"
    return str(preferred) if preferred.is_file() else "gh"


def _gh_env() -> dict[str, str]:
    env = dict(os.environ)
    env.setdefault("GH_CONFIG_DIR", str(Path.home() / ".config" / "gh"))
    return env


def git_is_repository() -> bool:
    code, _, _ = run_cmd(
        ["git", "rev-parse", "--is-inside-work-tree"], cwd=_repo(), timeout=30
    )
    return code == 0


def git_status() -> tuple[int, str, str]:
    return run_cmd(["git", "status", "--short", "--branch"], cwd=_repo(), timeout=60)


def git_diff_stat() -> tuple[int, str, str]:
    return run_cmd(["git", "diff", "--stat"], cwd=_repo(), timeout=60)


def git_add_all() -> tuple[int, str, str]:
    return run_cmd(["git", "add", "-A"], cwd=_repo(), timeout=60)


def git_commit(message: str) -> tuple[int, str, str]:
    return run_cmd(["git", "commit", "-m", message], cwd=_repo(), timeout=120)


def git_pull() -> tuple[int, str, str]:
    return run_cmd(["git", "pull", "--ff-only"], cwd=_repo(), timeout=300)


def git_push() -> tuple[int, str, str]:
    return run_cmd(["git", "push"], cwd=_repo(), timeout=300)


def git_push_set_upstream_origin(branch: str) -> tuple[int, str, str]:
    return run_cmd(
        ["git", "push", "--set-upstream", "origin", branch], cwd=_repo(), timeout=300
    )


def git_current_branch() -> tuple[int, str, str]:
    return run_cmd(["git", "branch", "--show-current"], cwd=_repo(), timeout=30)


def git_remote_verbose() -> tuple[int, str, str]:
    return run_cmd(["git", "remote", "-v"], cwd=_repo(), timeout=30)


def git_get_config(key: str, *, global_scope: bool) -> tuple[int, str, str]:
    argv = ["git", "config"]
    if global_scope:
        argv.append("--global")
    argv.append(key)
    return run_cmd(argv, cwd=_repo(), timeout=30)


def git_set_config(key: str, value: str, *, global_scope: bool) -> tuple[int, str, str]:
    argv = ["git", "config"]
    if global_scope:
        argv.append("--global")
    argv.extend([key, value])
    return run_cmd(argv, cwd=_repo(), timeout=30)


def _git_has_changes_for(pathspec: str) -> bool:
    code, out, _ = run_cmd(
        ["git", "status", "--short", "--", pathspec], cwd=_repo(), timeout=30
    )
    return code == 0 and bool(out.strip())


def git_sync_public_json_to_remote() -> tuple[bool, str]:
    if not git_is_repository():
        return False, "当前目录不是 Git 仓库"

    public_path = public_config_path()
    if not public_path.is_file():
        return False, f"缺少 {public_path}"

    rel_path = os.path.relpath(public_path, _repo())
    add_code, add_out, add_err = run_cmd(
        ["git", "add", "--", rel_path], cwd=_repo(), timeout=60
    )
    if add_code != 0:
        return False, (add_out + add_err).strip() or "git add 失败"

    if not _git_has_changes_for(rel_path):
        push_code, push_out, push_err = git_push()
        if push_code == 0:
            return True, "public 配置无本地变更，已检查并同步远程"
        text = (push_out + push_err).strip()
        if text:
            return False, text
        return True, "public 配置无本地变更"

    commit_code, commit_out, commit_err = git_commit(
        "chore: update opencode public config"
    )
    if commit_code != 0:
        return False, (commit_out + commit_err).strip() or "git commit 失败"

    push_code, push_out, push_err = git_push()
    if push_code != 0:
        return False, (
            commit_out + commit_err + push_out + push_err
        ).strip() or "git push 失败"

    return True, "已提交并推送 tracked_config/opencode.public.json"


def gh_cli_version() -> tuple[int, str, str]:
    return run_cmd([_gh_bin(), "--version"], cwd=_repo(), timeout=30, env=_gh_env())


def gh_auth_status() -> tuple[int, str, str]:
    return run_cmd(
        [_gh_bin(), "auth", "status"], cwd=_repo(), timeout=30, env=_gh_env()
    )


def gh_auth_login_web() -> tuple[int, str, str]:
    return run_cmd(
        [
            _gh_bin(),
            "auth",
            "login",
            "--hostname",
            "github.com",
            "--git-protocol",
            "ssh",
            "--web",
        ],
        cwd=_repo(),
        timeout=15,
        env=_gh_env(),
    )


def install_gh_cli() -> tuple[int, str, str]:
    script = _repo() / "install_gh_cli.sh"
    return run_cmd(
        ["bash", str(script), "--force"], cwd=_repo(), timeout=1200, env=_gh_env()
    )


def ssh_default_pubkey_path() -> Path:
    return Path.home() / ".ssh" / "id_ed25519.pub"


def ssh_default_key_exists() -> bool:
    pub = ssh_default_pubkey_path()
    key = pub.with_suffix("")
    return pub.is_file() and key.is_file()


def ssh_generate_default_key(comment: str) -> tuple[int, str, str]:
    key_path = ssh_default_pubkey_path().with_suffix("")
    key_path.parent.mkdir(parents=True, exist_ok=True)
    if key_path.exists() or ssh_default_pubkey_path().exists():
        return 1, "", f"Key already exists: {key_path}\n"
    return run_cmd(
        ["ssh-keygen", "-t", "ed25519", "-C", comment, "-f", str(key_path), "-N", ""],
        cwd=_repo(),
        timeout=120,
    )


def gh_add_ssh_key(pubkey_path: str, title: str) -> tuple[int, str, str]:
    return run_cmd(
        [_gh_bin(), "ssh-key", "add", pubkey_path, "--title", title],
        cwd=_repo(),
        timeout=120,
        env=_gh_env(),
    )


def ssh_test_github_connection() -> tuple[int, str, str]:
    return run_cmd(["ssh", "-T", "git@github.com"], cwd=_repo(), timeout=60)


def ssh_accept_github_hostkey() -> tuple[int, str, str]:
    known_hosts = Path.home() / ".ssh" / "known_hosts"
    known_hosts.parent.mkdir(parents=True, exist_ok=True)
    shell = (
        f"touch {known_hosts!s} && "
        f"ssh-keygen -F github.com -f {known_hosts!s} >/dev/null || "
        f"ssh-keyscan github.com >> {known_hosts!s}"
    )
    return run_cmd(["bash", "-lc", shell], cwd=_repo(), timeout=60)
