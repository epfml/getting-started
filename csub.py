#!/usr/bin/python3

import argparse
from datetime import datetime, timedelta
from pprint import pprint
import re
import subprocess
import tempfile
import yaml
import json
import os
import time
import sys


parser = argparse.ArgumentParser(description="Cluster Submit Utility")
parser.add_argument(
    "-n",
    "--name",
    type=str,
    required=False,
    help="Job name (has to be unique in the namespace)",
)
parser.add_argument(
    "-cl",
    "--cluster",
    type=str,
    default="rcp-caas",
    choices=["ic-caas", "rcp-caas"],
)
parser.add_argument(
    "-c",
    "--command",
    type=str,
    required=False,
    help="Command to run on the instance (default sleep for duration)",
)
parser.add_argument(
    "-t",
    "--time",
    type=str,
    required=False,
    help="The maximum duration allowed for this job (default 24h)",
)
parser.add_argument(
    "-g",
    "--gpus",
    type=int,
    default=1,
    required=False,
    help="The number of GPUs requested (default 1)",
)
parser.add_argument(
    "--cpus",
    type=int,
    default=1,
    required=False,
    help="The number of CPUs requested (default 1)",
)
parser.add_argument(
    "--memory",
    type=str,
    default="4G",
    required=False,
    help="The minimum amount of CPU memory (default 4G). must match regular expression '^([+-]?[0-9.]+)([eEinumkKMGTP]*[-+]?[0-9]*)$'",
)
# TODO: add gpu memory or GPU selection argument
parser.add_argument(
    "-i",
    "--image",
    type=str,
    required=False,
    default="ic-registry.epfl.ch/mlo/mlo:v1",
    help="The URL of the docker image that will be used for the job",
)
parser.add_argument(
    "-p",
    "--port",
    type=int,
    required=False,
    help="A cluster port for connect to this node",
)
parser.add_argument(
    "-u",
    "--user",
    type=str,
    default="user.yaml",
    help="Path to a yaml file that defines the user",
)
parser.add_argument(
    "--train",
    action="store_true",
    help="train job (default is interactive, which has higher priority)",
)
parser.add_argument(
    "-d",
    "--dry",
    action="store_true",
    help="Print the generated yaml file instead of submitting it",
)
parser.add_argument(
    "--backofflimit",
    default=0,
    type=int,
    help="specifies the number of retries before marking a workload as failed (default 0). only exists for train jobs",
)
parser.add_argument(
    "--node_type",
    type=str,
    default="",
    choices=["", "g9", "g10", "h100", "v100", "default"],
    help="node type to run on (default is empty, which means any node). \
          IC cluster: g9 for V100, g10 for A100. \
          RCP-Prod cluster: h100 for H100, use 'default' to get A100 on interactive jobs",
)
parser.add_argument(
    "--host_ipc",
    action="store_true",
    help="created workload will use the host's ipc namespace",
)
parser.add_argument(
    "--no_symlinks",
    action="store_true",
    help="do not create symlinks to the user's home directory",
)
parser.add_argument(
    "--large_shm",
    action="store_true",
    help="use large shared memory /dev/shm for the job",
)
parser.add_argument(
    "--follow",
    action="store_true",
    help="follow logs of the launched job",
)
parser.add_argument(
    "--github-secret-file",
    default="~/.ssh/github",
    help="private ssh key for github to be set as env",
)


def to_string_values(d):
    if not isinstance(d, dict):
        return str(d)
    return {k: to_string_values(v) for k, v in d.items()}


if __name__ == "__main__":
    args = parser.parse_args()

    args.user = os.path.expanduser(args.user)

    if not os.path.exists(args.user):
        print(
            f"User file {args.user} does not exist, use the template in `template/user.yaml` to create your user file."
        )
        exit(1)

    with open(args.user, "r") as file:
        user_cfg = yaml.safe_load(file)

    scratch_name = f"runai-mlo-{user_cfg['user']}-scratch"

    # get current cluster and make sure argument matches
    current_cluster = subprocess.run(
        ["kubectl", "config", "current-context"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    ).stdout.strip()

    if current_cluster == "rcp-caas":
        # the latest version can be found on https://wiki.rcp.epfl.ch/home/CaaS/FAQ/how-to-prepare-environment
        runai_cli_version = "2.18.94"
        scratch_name = "mlo-scratch"
    elif current_cluster == "ic-caas":
        runai_cli_version = "2.16.52"
    assert (
        current_cluster == args.cluster
    ), f"Current cluster is {current_cluster}, but you specified {args.cluster}. Use --cluster {current_cluster}"

    if args.name is None:
        args.name = f"{user_cfg['user']}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

    if args.time is None:
        args.time = 7 * 24 * 60 * 60
    else:
        pattern = r"((?P<days>\d+)d)?((?P<hours>\d+)h)?((?P<minutes>\d+)m)?((?P<seconds>\d+)s?)?"
        match = re.match(pattern, args.time)
        parts = {k: int(v) for k, v in match.groupdict().items() if v}
        args.time = int(timedelta(**parts).total_seconds())

    if args.command is None:
        args.command = f"sleep {args.time}"

    if args.train:
        workload_kind = "TrainingWorkload"
    else:
        workload_kind = "InteractiveWorkload"

    working_dir = user_cfg["working_dir"]
    if not args.no_symlinks:
        symlink_targets, symlink_destinations = zip(*user_cfg["symlinks"].items())
        symlink_targets = ":".join(
            [os.path.join(working_dir, target) for target in symlink_targets]
        )
        symlink_paths = ":".join(
            [
                os.path.join(f"/home/{user_cfg['user']}", dest[1])
                for dest in symlink_destinations
            ]
        )
        symlink_types = ":".join([dest[0] for dest in symlink_destinations])
    else:
        symlink_targets = ""
        symlink_paths = ""
        symlink_types = ""

    # this is the yaml file that will be submitted to the cluster
    cfg: dict = dict(
        apiVersion="run.ai/v2alpha1",
        kind=workload_kind,
        metadata=dict(
            annotations={"runai-cli-version": runai_cli_version},
            labels={"PreviousJob": "true"},
            name=args.name,
            namespace=f"runai-mlo-{user_cfg['user']}",
        ),
        spec=dict(
            name={"value": args.name},
            arguments={"value": f"/bin/zsh -c 'source ~/.zshrc && {args.command}'"},
            environment=dict(
                items=to_string_values(
                    {
                        "HOME": {"value": f"/home/{user_cfg['user']}"},
                        "NB_USER": {"value": user_cfg["user"]},
                        "NB_UID": {"value": user_cfg["uid"]},
                        "NB_GROUP": {"value": user_cfg["group"]},
                        "NB_GID": {"value": user_cfg["gid"]},
                        "WORKING_DIR": {"value": working_dir},
                        "SYMLINK_TARGETS": {"value": symlink_targets},
                        "SYMLINK_PATHS": {"value": symlink_paths},
                        "SYMLINK_TYPES": {"value": symlink_types},
                        "WANDB_API_KEY": {"value": user_cfg["wandb_api_key"]},
                        "HF_HOME": {"value": "/mloscratch/hf_cache"},
                        "HF_TOKEN": {"value": user_cfg["hf_token"]},
                        "EPFML_LDAP": {"value": user_cfg["user"]},
                    }
                )
            ),
            gpu={"value": str(args.gpus)},
            cpu={"value": str(args.cpus)},
            memory={"value": str(args.memory)},
            image={"value": args.image},
            imagePullPolicy={"value": "Always"},
            pvcs={
                "items": {
                    "pvc--0": {
                        "value": {
                            "claimName": scratch_name,
                            "existingPvc": True,
                            "path": "/mloscratch",
                            "readOnly": False,
                        }
                    }
                }
            },
            runAsGid={"value": user_cfg["gid"]},
            runAsUid={"value": user_cfg["uid"]},
            runAsUser={"value": True},
            serviceType={"value": "ClusterIP"},
            username={"value": user_cfg["user"]},
            allowPrivilegeEscalation={"value": True},
        ),
    )

    #### some additional flags that can be added at the end of the config
    if args.node_type:
        cfg["spec"]["nodePools"] = {"value": args.node_type}
        if args.node_type in ["g10", "h100", "default"] and not args.train:
            cfg["spec"]["preemptible"] = {"value": True}
    cfg["spec"]["hostIpc"] = {"value": args.host_ipc}
    if args.train:
        cfg["spec"]["backoffLimit"] = {"value": args.backofflimit}

    if args.large_shm:
        cfg["spec"]["largeShm"] = {"value": True}

    github_key = os.path.expanduser(args.github_secret_file)
    if os.path.exists(github_key):
        with open(github_key) as f:
            cfg["spec"]["environment"]["items"]["GITHUB_KEY"] = {"value": f.read()}

    with tempfile.NamedTemporaryFile(mode="w+", suffix=".yaml") as f:
        yaml.dump(cfg, f)
        f.flush()
        if args.dry:
            f.seek(0)
            print(f.read())
            exit()
        # Run the subprocess and capture stdout and stderr
        result = subprocess.run(
            ["kubectl", "apply", "-f", f.name],
            # check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

    # Check if there was an error
    if result.returncode != 0:
        print("Error encountered:")
        # Prettify and print the stderr
        pprint(result.stderr)
        exit(1)

    print("Output:")
    # Prettify and print the stdout
    print(result.stdout)

    print("If the above says 'created', the job has been submitted.")

    print(
        f"If the above says 'job unchanged', the job with name {args.name} "
        f"already exists (and you might need to delete it)."
    )

    print("\nThe following commands may come in handy:")
    print(
        f"runai exec {args.name} -it zsh # opens an interactive shell on the pod"
    )
    print(
        f"runai delete job {args.name} # kills the job and removes it from the list of jobs"
    )
    print(
        f"runai describe job {args.name} # shows information on the status/execution of the job"
    )
    print("runai list jobs # list all jobs and their status")
    print(f"runai logs {args.name} # shows the output/logs for the job")

    if args.follow:
        print("Waiting for start...", end="", flush=True)
        started = False
        while not started:
            time.sleep(1)
            result = subprocess.run(
                ["runai", "describe", "job", args.name, "--output", "json"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            latest_status = json.loads(result.stdout)["status"]
            started = json.loads(result.stdout)["status"] not in {"Pending", "ContainerCreating"}
            print(".", end="", flush=True)

        print(latest_status, "\n=================================\n", flush=True)
        following = subprocess.run(
            ["runai", "logs", args.name, "--follow"],
            stdout=sys.stdout,
            stderr=sys.stderr,
            text=True,
        )
        exit(following.returncode)
