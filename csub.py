#!/usr/bin/python3

import argparse
from datetime import datetime, timedelta
import re
import subprocess
import tempfile
import yaml
import os

parser = argparse.ArgumentParser(description="Cluster Submit Utility")
parser.add_argument(
    "-n",
    "--name",
    type=str,
    required=False,
    help="Job name (has to be unique in the namespace)",
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
    default=4,
    required=False,
    help="The number of CPUs requested (default 4)",
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

if __name__ == "__main__":
    args = parser.parse_args()

    if not os.path.exists(args.user):
        print(
            f"User file {args.user} does not exist, use the template in `template/user.yaml` to create your user file."
        )
        exit(1)

    with open(args.user, "r") as file:
        user_cfg = yaml.safe_load(file)

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
        backofflimit = f"""
  backoffLimit: 
    value: {args.backofflimit}
"""
    else:
        workload_kind = "InteractiveWorkload"
        backofflimit = ""

    working_dir = user_cfg["working_dir"]
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
    cfg = f"""
apiVersion: run.ai/v2alpha1
kind: {workload_kind}
metadata:
  annotations:
    runai-cli-version: 2.9.18
  labels:
    PreviousJob: "true"
  name: {args.name}
  namespace: runai-mlo-{user_cfg['user']}
spec:
  name:
    value: {args.name}
  arguments: 
      value: "/bin/zsh -c 'source ~/.zshrc && {args.command}'" # zshrc is just loaded to have some env variables ready
  environment:
    items:
      HOME:
        value: "/home/{user_cfg['user']}"
      NB_USER:
        value: {user_cfg['user']}
      NB_UID:
        value: "{user_cfg['uid']}"
      NB_GROUP:
        value: {user_cfg['group']}
      NB_GID:
        value: "{user_cfg['gid']}"
      WORKING_DIR:
        value: "{working_dir}"
      SYMLINK_TARGETS:
        value: "{symlink_targets}"
      SYMLINK_PATHS:
        value: "{symlink_paths}"
      SYMLINK_TYPES:
        value: "{symlink_types}"
      WANDB_API_KEY:
        value: {user_cfg['wandb_api_key']}
      EPFML_LDAP:
        value: {user_cfg['user']}
  gpu:
    value: "{args.gpus}"
  cpu:
    value: "{args.cpus}"
  memory:
    value: "{args.memory}"
  image:
    value: {args.image}
  imagePullPolicy:
    value: Always
  {backofflimit}
  pvcs:
    items:
      pvc--0:
        value:
          claimName: runai-mlo-{user_cfg['user']}-scratch
          existingPvc: true
          path: /mloscratch
          readOnly: false
  runAsGid:
    value: {user_cfg['gid']}
  runAsUid:
    value: {user_cfg['uid']}
  runAsUser: 
    value: true    
  serviceType:
    value: ClusterIP
  username:
    value: {user_cfg['user']}
"""

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml") as f:
        f.write(cfg)
        f.flush()
        if args.dry:
            print(cfg)
        else:
            result = subprocess.run(
                ["kubectl", "apply", "-f", f.name],
                # check=True,
                capture_output=True,
                # text=True,
            )
            print(result.stdout)
            print(result.stderr)

    print("\nThe following commands may come in handy:")
    print(f"runai exec {args.name} -it zsh # opens an interactive shell on the pod")
    print(
        f"runai delete job {args.name} # kills the job and removes it from the list of jobs"
    )
    print(
        f"runai describe job {args.name} # shows information on the status/execution of the job"
    )
    print("runai list jobs # list all jobs and their status")
    print(f"runai logs {args.name} # shows the output/logs for the job")
