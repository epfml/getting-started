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

from utils import (
    DEFAULT_ENV_FILE,
    build_runai_command,
    ensure_secret,
    maybe_populate_github_ssh,
    parse_env_file,
    rendered_env_file,
    shlex_join,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Wrapper around runai submit that keeps configuration in a .env file."
    )
    parser.add_argument("-n", "--name", type=str, help="Job name (auto generated if omitted)")
    parser.add_argument("-c", "--command", type=str, help="Command to run inside the container (default: sleep for the requested duration)")
    parser.add_argument("-t", "--time", type=str, help="Maximum runtime formatted as 12h, 2d6h30m, ... (default 12h for the keep-alive sleep)")
    parser.add_argument("-g", "--gpus", type=int, default=0, help="Number of GPUs")
    parser.add_argument("--cpus", type=int, default=8, help="Number of CPUs")
    parser.add_argument("--memory", type=str, default="32G", help="Requested CPU memory")
    parser.add_argument("-i", "--image", type=str, help="Override RUNAI_IMAGE from the env file")
    parser.add_argument("-p", "--port", type=int, help="Expose a container port")
    parser.add_argument("--train", action="store_true", help="Submit as a training workload")
    parser.add_argument("--dry", action="store_true", help="Print the generated runai command")
    parser.add_argument("--env-file", type=str, default=DEFAULT_ENV_FILE, help="Path to the .env file (default: .env in the repo root)")
    parser.add_argument("--sync-secret-only", action="store_true", help="Create/refresh the Kubernetes secret and exit without submitting a job")
    parser.add_argument("--skip-secret-sync", action="store_true", help="Do not (re)create the Kubernetes secret before submission")
    parser.add_argument("--secret-name", type=str, help="Override RUNAI_SECRET_NAME from the env file")
    parser.add_argument("--pvc", type=str, help="Override SCRATCH_PVC from the env file (default: mlo-scratch)")
    parser.add_argument("--backofflimit", type=int, default=0, help="Retries before marking a training job as failed")
    parser.add_argument("--node-type", type=str, choices=["", "v100", "h100", "h200", "default", "a100-40g"], default="", help="GPU node pool to target")
    parser.add_argument("--host-ipc", action="store_true", help="Share the host IPC namespace")
    parser.add_argument("--large-shm", action="store_true", help="Request a larger /dev/shm")
    return parser


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
