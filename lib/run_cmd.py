"""Subprocess helper with optional live output streaming."""

from __future__ import annotations

import selectors
import subprocess
import time
from collections.abc import Mapping, Sequence
from pathlib import Path


def run_cmd(
    argv: Sequence[str],
    *,
    cwd: Path | str | None = None,
    timeout: float | None = 600,
    env: Mapping[str, str] | None = None,
    live: bool = False,
) -> tuple[int, str, str]:
    """
    Run a command; return (exit_code, stdout, stderr) as strings (utf-8 with replace).
    """
    if live:
        kw: dict = {
            "stdout": subprocess.PIPE,
            "stderr": subprocess.STDOUT,
            "text": True,
            "encoding": "utf-8",
            "errors": "replace",
            "bufsize": 1,
        }
        if cwd is not None:
            kw["cwd"] = str(cwd)
        if env is not None:
            kw["env"] = dict(env)

        start = time.monotonic()
        chunks: list[str] = []
        proc = subprocess.Popen(list(argv), **kw)
        selector = selectors.DefaultSelector()

        try:
            if proc.stdout is not None:
                selector.register(proc.stdout, selectors.EVENT_READ)

            while True:
                if timeout is not None and time.monotonic() - start > timeout:
                    proc.kill()
                    proc.wait()
                    output = "".join(chunks)
                    return 124, output, "\n[timeout]\n"

                if proc.poll() is not None and not selector.get_map():
                    break

                events = selector.select(timeout=0.1)
                if not events:
                    if proc.poll() is not None:
                        break
                    continue

                for key, _ in events:
                    chunk = (
                        key.fileobj.read1(4096)
                        if hasattr(key.fileobj, "read1")
                        else key.fileobj.read()
                    )
                    if not chunk:
                        selector.unregister(key.fileobj)
                        continue
                    chunks.append(chunk)
                    print(chunk, end="", flush=True)

            output = "".join(chunks)
            return proc.returncode or 0, output, ""
        except OSError as e:
            return 1, "", f"{type(e).__name__}: {e}\n"
        finally:
            selector.close()

    kw: dict = {
        "capture_output": True,
        "text": True,
        "encoding": "utf-8",
        "errors": "replace",
    }
    if cwd is not None:
        kw["cwd"] = str(cwd)
    if env is not None:
        kw["env"] = dict(env)
    if timeout is not None:
        kw["timeout"] = timeout
    try:
        proc = subprocess.run(list(argv), **kw)
        out = proc.stdout or ""
        err = proc.stderr or ""
        return proc.returncode, out, err
    except subprocess.TimeoutExpired as e:
        out = (e.stdout or "") if isinstance(e.stdout, str) else ""
        err = (e.stderr or "") if isinstance(e.stderr, str) else ""
        err = err + "\n[timeout]\n"
        return 124, out, err
    except OSError as e:
        return 1, "", f"{type(e).__name__}: {e}\n"
