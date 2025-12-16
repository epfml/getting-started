#!/usr/bin/python3

"""
Submission helper for the EPFL RCP cluster.

This version drops the intermediate Kubernetes YAML and instead shells out to
the run:ai CLI directly. User and secret specific configuration is stored in a
local .env file (see templates/user.env.example) that is mirrored into a
Kubernetes secret before each submission.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from datetime import datetime
from typing import Dict, List, Tuple

from utils import (
    DEFAULT_ENV_FILE,
    ensure_secret,
    maybe_populate_github_ssh,
    parse_env_file,
    rendered_env_file,
    shlex_join,
    parse_duration,
    add_env_flags,
    add_secret_env_flags,
)

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Wrapper around runai submit that keeps configuration in a .env file."
    )
    parser.add_argument("-n", "--name", type=str, help="Job name (auto generated if omitted)")
    parser.add_argument("--uid", type=int, help="Run the container as this UID instead of LDAP_UID from the env file")
    parser.add_argument("--gid", type=int, help="Run the container as this GID instead of LDAP_GID from the env file")
    parser.add_argument("-c", "--command", type=str, help="Command to run inside the container (default: sleep for the requested duration)")
    parser.add_argument("-t", "--time", type=str, help="Maximum runtime formatted as 12h, 2d6h30m, ... (default 12h for the keep-alive sleep)")
    parser.add_argument("-g", "--gpus", type=int, default=0, help="Number of GPUs")
    parser.add_argument("--cpus", type=int, help="Number of CPUs (omit to use platform default)")
    parser.add_argument("--memory", type=str, help="Requested CPU memory (omit to use platform default)")
    parser.add_argument("-i", "--image", type=str, help="Override RUNAI_IMAGE from the env file")
    parser.add_argument("-p", "--port", type=int, help="Expose a container port")
    parser.add_argument("--train", action="store_true", help="Submit as a training workload")
    parser.add_argument("--distributed", action="store_true", help="Submit a distributed workload")
    parser.add_argument("--workers", default=0, type=int, help="Only read for distributed workloads. Number of nodes IN ADDITION to the master node. I.e., the total number of nodes is the number of workers + 1 (the master node)")
    parser.add_argument("--dry", action="store_true", help="Print the generated runai command")
    parser.add_argument("--env-file", type=str, default=DEFAULT_ENV_FILE, help="Path to the .env file (default: .env in the repo root)")
    parser.add_argument("--sync-secret-only", action="store_true", help="Create/refresh the Kubernetes secret and exit without submitting a job")
    parser.add_argument("--skip-secret-sync", action="store_true", help="Do not (re)create the Kubernetes secret before submission")
    parser.add_argument("--secret-name", type=str, help="Override RUNAI_SECRET_NAME from the env file")
    parser.add_argument("--pvc", type=str, help="Override SCRATCH_PVC from the env file")
    parser.add_argument("--backofflimit", type=int, default=0, help="Retries before marking a training job as failed")
    parser.add_argument("--node-type", type=str, choices=["", "v100", "h100", "h200", "default", "a100-40g"], default="", help="GPU node pool to target")
    parser.add_argument("--host-ipc", action="store_true", help="Share the host IPC namespace")
    parser.add_argument("--large-shm", action="store_true", help="Request a larger /dev/shm")
    return parser


def build_runai_command(
    args: argparse.Namespace, env: Dict[str, str]
) -> Tuple[List[str], str]:
    assert args.train + args.distributed <= 1, "Choose --train or --distributed but not both"

    job_name = (
        args.name
        or f"{env['LDAP_USERNAME']}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    )
    image = args.image or env.get("RUNAI_IMAGE")
    if not image:
        sys.exit("RUNAI_IMAGE must be defined either in the env file or via --image.")

    secret_name = args.secret_name or env.get("RUNAI_SECRET_NAME")
    if not secret_name:
        sys.exit(
            "RUNAI_SECRET_NAME must be defined in the env file or via --secret-name."
        )

    namespace = env.get("K8S_NAMESPACE") or env.get("RUNAI_PROJECT")
    if not namespace:
        sys.exit("Define K8S_NAMESPACE or RUNAI_PROJECT in the env file.")

    pvc = args.pvc or env.get("SCRATCH_PVC")
    if not pvc:
        sys.exit("Define SCRATCH_PVC in the env file or pass --pvc.")

    scratch_mount_path = env.get("SCRATCH_MOUNT_PATH", "/mloscratch")
    scratch_root = env.get("SCRATCH_HOME_ROOT") or f"{scratch_mount_path}/homes"
    working_dir = env.get("WORKING_DIR") or f"{scratch_root}/{env['LDAP_USERNAME']}"
    hf_home = env.get("HF_HOME") or f"{scratch_mount_path}/hf_cache"
    run_uid = str(args.uid) if args.uid is not None else env["LDAP_UID"]
    run_gid = str(args.gid) if args.gid is not None else env["LDAP_GID"]

    scratch_home = working_dir

    literal_env = {
        "HOME": f"/home/{env['LDAP_USERNAME']}",
        "NB_USER": env["LDAP_USERNAME"],
        "NB_UID": run_uid,
        "NB_GROUP": env["LDAP_GROUPNAME"],
        "NB_GID": run_gid,
        "WORKING_DIR": working_dir,
        "SCRATCH_HOME": scratch_home,
        "SCRATCH_HOME_ROOT": scratch_root,
        "EPFML_LDAP": env["LDAP_USERNAME"],
        "HF_HOME": hf_home,
        "UV_PYTHON_VERSION": env.get("UV_PYTHON_VERSION", "3.11"),
        "TZ": env.get("TZ", "Europe/Zurich"),
        # Keep runtime shell and tool caches available when using `runai exec`
        "GIT_CONFIG_GLOBAL": f"{scratch_home}/.gitconfig",
        "UV_CACHE_DIR": f"{scratch_home}/.cache/uv",
        "UV_PYTHON_INSTALL_DIR": f"{scratch_home}/.uv",
    }

    duration = parse_duration(args.time)
    user_command = args.command or f"sleep {duration}"
    shell_command = f"source ~/.zshrc && {user_command}"

    cmd: List[str] = ["runai"]
    cmd.extend(["submit-dist", "pytorch"] if args.distributed else ["submit"])
    cmd.extend([
        "--name",
        job_name,
        "--project",
        env.get("RUNAI_PROJECT", namespace),
        "--image",
        image,
        "--gpu",
        str(args.gpus),
        "--run-as-uid",
        run_uid,
        "--run-as-gid",
        run_gid,
        "--pvc",
        f"{pvc}:{scratch_mount_path}",
        "--image-pull-policy",
        "Always",
        "--allow-privilege-escalation",
        "true",
    ])

    if args.cpus is not None:
        cmd.extend(["--cpu", str(args.cpus)])

    if args.memory:
        cmd.extend(["--memory", args.memory])

    if not args.train and not args.distributed:
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
        if args.node_type in {"h200", "h100"} and not args.train and not args.distributed:
            cmd.append("--preemptible")
            
    if args.distributed:
        cmd.extend([
            "--workers", str(args.workers),
            "--annotation", "k8s.v1.cni.cncf.io/networks=kube-system/roce", 
            "--extended-resource", "rdma/rdma=1"
        ])

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


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    env_path = Path(args.env_file).expanduser()
    env = parse_env_file(env_path)
    maybe_populate_github_ssh(env)
    secret_name = args.secret_name or env.get("RUNAI_SECRET_NAME")
    namespace = env.get("K8S_NAMESPACE") or env.get("RUNAI_PROJECT")

    if not secret_name:
        sys.exit("RUNAI_SECRET_NAME (or --secret-name) is required.")
    if not namespace:
        sys.exit("K8S_NAMESPACE or RUNAI_PROJECT must be defined in the env file.")

    if args.sync_secret_only or not args.skip_secret_sync:
        with rendered_env_file(env) as rendered_path:
            ensure_secret(rendered_path, namespace, secret_name)
        if args.sync_secret_only:
            print(f"Secret {secret_name} was updated in namespace {namespace}.")
            return

    cmd, job_name = build_runai_command(args, env)

    if args.dry:
        print(shlex_join(cmd))
        return

    print(f"→ {shlex_join(cmd)}")
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as exc:
        sys.exit(exc.returncode)

    print("\nJob submitted. Handy commands:")
    print(f"runai describe job {job_name}")
    print(f"runai logs {job_name}")
    print(f"runai exec {job_name} -it -- zsh")
    print(f"runai delete job {job_name}")

if __name__ == "__main__":
    main()
