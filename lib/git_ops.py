"""Git commands scoped to repository root."""

from __future__ import annotations

from pathlib import Path

from lib.paths import repo_root
from lib.run_cmd import run_cmd

# 仅同步可进 Git 的公开配置；密钥文件在 .gitignore 中，不会被 add
PUBLIC_JSON_REL = "tracked_config/opencode.public.json"


def git_argv(*args: str) -> list[str]:
    return ["git", "-C", str(repo_root()), *args]


def _git_remote_env() -> dict[str, str]:
    # Avoid interactive host-key prompt and auto-trust first-seen host key.
    # BatchMode avoids hanging on password/passphrase prompts in dashboard subprocesses.
    return {"GIT_SSH_COMMAND": "ssh -o StrictHostKeyChecking=accept-new -o BatchMode=yes"}


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
    return run_cmd(git_argv("pull", "--ff-only"), cwd=None, timeout=300, env=_git_remote_env())


def git_push() -> tuple[int, str, str]:
    return run_cmd(git_argv("push"), cwd=None, timeout=300, env=_git_remote_env())


def git_current_branch() -> tuple[int, str, str]:
    return run_cmd(git_argv("branch", "--show-current"), cwd=None, timeout=30)


def git_push_set_upstream_origin(branch: str) -> tuple[int, str, str]:
    return run_cmd(
        git_argv("push", "--set-upstream", "origin", branch),
        cwd=None,
        timeout=300,
        env=_git_remote_env(),
    )


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


def install_gh_cli() -> tuple[int, str, str]:
    cmd = """set -e
if command -v gh >/dev/null 2>&1; then
  echo 'gh already installed'
  exit 0
fi

pm_ok=0
if command -v apt-get >/dev/null 2>&1; then
  if apt-get update && apt-get install -y gh; then pm_ok=1; fi
elif command -v dnf >/dev/null 2>&1; then
  if dnf install -y gh; then pm_ok=1; fi
elif command -v yum >/dev/null 2>&1; then
  if yum install -y gh; then pm_ok=1; fi
elif command -v pacman >/dev/null 2>&1; then
  if pacman -Sy --noconfirm github-cli; then pm_ok=1; fi
elif command -v zypper >/dev/null 2>&1; then
  if zypper --non-interactive install gh; then pm_ok=1; fi
elif command -v apk >/dev/null 2>&1; then
  if apk add --no-cache github-cli; then pm_ok=1; fi
fi

if [ "$pm_ok" -eq 1 ] && command -v gh >/dev/null 2>&1; then
  gh --version
  exit 0
fi

echo 'Package manager install failed, fallback to GitHub release tarball...'
if ! command -v curl >/dev/null 2>&1; then
  echo 'curl is required for fallback install' >&2
  exit 1
fi
if ! command -v tar >/dev/null 2>&1; then
  echo 'tar is required for fallback install' >&2
  exit 1
fi
if ! command -v python3 >/dev/null 2>&1; then
  echo 'python3 is required for fallback install' >&2
  exit 1
fi

arch="$(uname -m)"
case "$arch" in
  x86_64|amd64) gh_arch="amd64" ;;
  aarch64|arm64) gh_arch="arm64" ;;
  *)
    echo "unsupported architecture: $arch" >&2
    exit 1
    ;;
esac

tag="$(curl -fsSL https://api.github.com/repos/cli/cli/releases/latest | python3 -c 'import sys, json; print(json.load(sys.stdin)["tag_name"])')"
ver="${tag#v}"
tmp_dir="$(mktemp -d)"
trap 'rm -rf "$tmp_dir"' EXIT
url="https://github.com/cli/cli/releases/download/${tag}/gh_${ver}_linux_${gh_arch}.tar.gz"
curl -fL "$url" -o "$tmp_dir/gh.tgz"
tar -xzf "$tmp_dir/gh.tgz" -C "$tmp_dir"
bin_path="$tmp_dir/gh_${ver}_linux_${gh_arch}/bin/gh"
if [ ! -f "$bin_path" ]; then
  echo "cannot find gh binary at $bin_path" >&2
  exit 1
fi

if [ -w /usr/local/bin ]; then
  install -m 0755 "$bin_path" /usr/local/bin/gh
  echo 'Installed gh to /usr/local/bin/gh'
else
  mkdir -p "$HOME/.local/bin"
  install -m 0755 "$bin_path" "$HOME/.local/bin/gh"
  echo "Installed gh to $HOME/.local/bin/gh"
fi

gh --version
"""
    return run_cmd(["bash", "-lc", cmd], cwd=None, timeout=1800)


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


def ssh_accept_github_hostkey() -> tuple[int, str, str]:
    # This will add github.com host key to known_hosts on first use without interactive prompt.
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

    c4, o4, e4 = run_cmd(git_argv("push"), cwd=None, timeout=300, env=_git_remote_env())
    log = (o3 + e3 + o4 + e4).strip()
    if c4 != 0:
        return False, log or "git push 失败（检查 origin 与凭据）"
    return True, log or "已提交并 push（仅 opencode.public.json）"
