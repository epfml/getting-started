#!/usr/bin/python3

"""Utility helpers shared by the csub CLI entrypoint."""

from __future__ import annotations

import base64
import re
import shlex
import subprocess
import sys
import tempfile
from contextlib import contextmanager
from datetime import timedelta
from pathlib import Path
from typing import Dict, Iterable, Iterator, List

DEFAULT_ENV_FILE = ".env"
DEFAULT_GITHUB_KEY_PATH = Path("~/.ssh/github").expanduser()
DEFAULT_TIME_SECONDS = 12 * 60 * 60
SECRET_KEYS = {
    "WANDB_API_KEY",
    "HF_TOKEN",
    "SSH_PRIVATE_KEY_B64",
    "SSH_PUBLIC_KEY",
    "SSH_KNOWN_HOSTS",
    "GIT_USER_NAME",
    "GIT_USER_EMAIL",
    "GITHUB_TOKEN",
}


def parse_env_file(path: Path) -> Dict[str, str]:
    env: Dict[str, str] = {}
    if not path.exists():
        sys.exit(
            f"Environment file {path} does not exist. Copy templates/user.env.example first."
        )

    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        if "=" not in line:
            sys.exit(f"Invalid line in {path}: {raw_line}")
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if value and value[0] == value[-1] and value.startswith(("'", '"')):
            value = value[1:-1]
        env[key] = value
    return env


def _expand_path(raw: str | None, fallback: Path) -> Path:
    return Path(raw).expanduser() if raw else fallback


def maybe_populate_github_ssh(env: Dict[str, str]) -> None:
    """Populate SSH_* secrets from a local GitHub key if they are empty."""
    key_path = _expand_path(env.get("GITHUB_SSH_KEY_PATH"), DEFAULT_GITHUB_KEY_PATH)
    pub_path = _expand_path(
        env.get("GITHUB_SSH_PUBLIC_KEY_PATH"), Path(f"{key_path}.pub")
    )
    print(f"[csub] key_path: {key_path}")

    if not env.get("SSH_PRIVATE_KEY_B64") and key_path.exists():
        print(f"[csub] Loading SSH_PRIVATE_KEY_B64 from {key_path}", file=sys.stderr)
        encoded = base64.b64encode(key_path.read_bytes()).decode("ascii")
        env["SSH_PRIVATE_KEY_B64"] = encoded
        print(f"[csub] Loaded SSH_PRIVATE_KEY_B64 from {key_path}", file=sys.stderr)

    if not env.get("SSH_PUBLIC_KEY") and pub_path.exists():
        env["SSH_PUBLIC_KEY"] = pub_path.read_text().strip()
        print(f"[csub] Loaded SSH_PUBLIC_KEY from {pub_path}", file=sys.stderr)


@contextmanager
def rendered_env_file(env: Dict[str, str]) -> Iterator[Path]:
    """Serialize the in-memory env dict to a temporary file for kubectl."""
    tmp = tempfile.NamedTemporaryFile("w", delete=False)
    tmp_path = Path(tmp.name)
    try:
        with tmp:
            for key, value in env.items():
                tmp.write(f"{key}={value}\n")
        yield tmp_path
    finally:
        tmp_path.unlink(missing_ok=True)


def parse_duration(spec: str | None) -> int:
    if not spec:
        return DEFAULT_TIME_SECONDS
    pattern = r"^((?P<days>\d+)d)?((?P<hours>\d+)h)?((?P<minutes>\d+)m)?((?P<seconds>\d+)s?)?$"
    match = re.match(pattern, spec)
    if not match:
        sys.exit(f"Invalid duration '{spec}'. Use formats like 12h, 45m, 2d6h30m.")
    parts = {k: int(v) for k, v in match.groupdict().items() if v}
    return int(timedelta(**parts).total_seconds())


def shlex_join(cmd: Iterable[str]) -> str:
    return " ".join(shlex.quote(str(token)) for token in cmd)


def ensure_secret(env_path: Path, namespace: str, secret_name: str) -> None:
    create_cmd = [
        "kubectl",
        "-n",
        namespace,
        "create",
        "secret",
        "generic",
        secret_name,
        f"--from-env-file={env_path}",
        "--dry-run=client",
        "-o",
        "yaml",
    ]
    try:
        rendered = subprocess.run(
            create_cmd,
            check=True,
            capture_output=True,
            text=True,
        ).stdout
    except subprocess.CalledProcessError as exc:
        sys.exit(f"kubectl failed to render the secret:\n{exc.stderr}")

    try:
        subprocess.run(
            ["kubectl", "-n", namespace, "apply", "-f", "-"],
            input=rendered,
            check=True,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        sys.exit(f"kubectl failed to apply the secret:\n{exc.stderr}")


def add_env_flags(cmd: List[str], values: Dict[str, str]) -> None:
    for key, value in values.items():
        if value == "":
            continue
        cmd.extend(["--environment", f"{key}={value}"])


def add_secret_env_flags(
    cmd: List[str],
    env: Dict[str, str],
    secret_name: str,
    extra_secret_keys: Iterable[str],
) -> None:
    keys = set(SECRET_KEYS).union(k.strip() for k in extra_secret_keys if k.strip())
    for key in sorted(keys):
        if key not in env or env[key] == "":
            continue
        cmd.extend(["--environment", f"{key}=SECRET:{secret_name},{key}"])


__all__ = [
    "DEFAULT_ENV_FILE",
    "build_runai_command",
    "ensure_secret",
    "maybe_populate_github_ssh",
    "parse_env_file",
    "rendered_env_file",
    "shlex_join",
]
