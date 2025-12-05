#!/usr/bin/python3

"""Utility helpers shared by the csub CLI entrypoint."""

from __future__ import annotations

import argparse
import base64
import re
import shlex
import subprocess
import sys
import tempfile
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Tuple

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
    pub_path = _expand_path(env.get("GITHUB_SSH_PUBLIC_KEY_PATH"), Path(f"{key_path}.pub"))
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


def build_runai_command(args: argparse.Namespace, env: Dict[str, str]) -> Tuple[List[str], str]:
    job_name = args.name or f"{env['LDAP_USERNAME']}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    image = args.image or env.get("RUNAI_IMAGE")
    if not image:
        sys.exit("RUNAI_IMAGE must be defined either in the env file or via --image.")

    secret_name = args.secret_name or env.get("RUNAI_SECRET_NAME")
    if not secret_name:
        sys.exit("RUNAI_SECRET_NAME must be defined in the env file or via --secret-name.")

    namespace = env.get("K8S_NAMESPACE") or env.get("RUNAI_PROJECT")
    if not namespace:
        sys.exit("Define K8S_NAMESPACE or RUNAI_PROJECT in the env file.")

    pvc = args.pvc or env.get("SCRATCH_PVC", "mlo-scratch")
    working_dir = env.get("WORKING_DIR") or f"/mloscratch/homes/{env['LDAP_USERNAME']}"
    scratch_root = env.get("SCRATCH_HOME_ROOT", "/mloscratch/homes")
    literal_env = {
        "HOME": f"/home/{env['LDAP_USERNAME']}",
        "NB_USER": env["LDAP_USERNAME"],
        "NB_UID": env["LDAP_UID"],
        "NB_GROUP": env["LDAP_GROUPNAME"],
        "NB_GID": env["LDAP_GID"],
        "WORKING_DIR": working_dir,
        "SCRATCH_HOME": working_dir,
        "SCRATCH_HOME_ROOT": scratch_root,
        "EPFML_LDAP": env["LDAP_USERNAME"],
        "HF_HOME": "/mloscratch/hf_cache",
        "UV_PYTHON_VERSION": env.get("UV_PYTHON_VERSION", "3.11"),
        "TZ": env.get("TZ", "Europe/Zurich"),
    }

    duration = parse_duration(args.time)
    user_command = args.command or f"sleep {duration}"
    shell_command = f"source ~/.zshrc && {user_command}"

    cmd: List[str] = [
        "runai",
        "submit",
        "--name",
        job_name,
        "--project",
        env.get("RUNAI_PROJECT", namespace),
        "--image",
        image,
        "--gpu",
        str(args.gpus),
        "--cpu",
        str(args.cpus),
        "--memory",
        args.memory,
        "--run-as-uid",
        env["LDAP_UID"],
        "--run-as-gid",
        env["LDAP_GID"],
        "--pvc",
        f"{pvc}:/mloscratch",
        "--image-pull-policy",
        "Always",
        "--allow-privilege-escalation",
        "true",
    ]

    if not args.train:
        cmd.append("--interactive")
    else:
        cmd.extend(["--backoff-limit", str(args.backofflimit)])

    if args.port:
        cmd.extend(["--port", str(args.port)])

    if args.host_ipc:
        cmd.append("--host-ipc")
    if args.large_shm:
        cmd.append("--large-shm")

    if args.node_type:
        cmd.extend(["--node-pools", args.node_type])
        if args.node_type in {"h100", "default", "a100-40g"} and not args.train:
            cmd.append("--preemptible")

    add_env_flags(cmd, literal_env)
    add_secret_env_flags(
        cmd,
        env,
        secret_name,
        env.get("EXTRA_SECRET_KEYS", "").split(","),
    )

    cmd.extend(
        [
            "--",
            "/bin/zsh",
            "-c",
            shell_command,
        ]
    )
    return cmd, job_name


__all__ = [
    "DEFAULT_ENV_FILE",
    "build_runai_command",
    "ensure_secret",
    "maybe_populate_github_ssh",
    "parse_env_file",
    "rendered_env_file",
    "shlex_join",
]

