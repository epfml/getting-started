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
        comment_out_priority = "#"  # comment
    else:
        comment_out_priority = ""

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
# Source: runaijob/templates/runai-job.yaml
apiVersion: run.ai/v1
kind: RunaiJob
metadata:
  name: {args.name}
  labels:
    {comment_out_priority}priorityClassName: "build" # Interactive Job if present, for Train Job REMOVE this line
    user: {user_cfg['user']}
spec:
  template:
    metadata:
      labels:
        user: {user_cfg['user']}
    spec:
      hostIPC: true
      schedulerName: runai-scheduler
      restartPolicy: Never
      securityContext:
        runAsUser: {user_cfg['uid']}
        runAsGroup: {user_cfg['gid']}
      containers:
        - name: {args.name}
          image: {args.image}
          imagePullPolicy: Always
          workingDir: "/home/{user_cfg['user']}"
          securityContext:
            allowPrivilegeEscalation: true
          stdin:
          tty:
          args: [
              "/bin/bash",
              "-c",
              "{args.command}",
          ]
          env:
            - name: HOME
              value: "/home/{user_cfg['user']}"
            - name: NB_USER
              value: {user_cfg['user']}
            - name: NB_UID
              value: "{user_cfg['uid']}"
            - name: NB_GROUP
              value: {user_cfg['group']}
            - name: NB_GID
              value: "{user_cfg['gid']}"
            - name: WORKING_DIR
              value: "{working_dir}"
            - name: SYMLINK_TARGETS
              value: "{symlink_targets}"
            - name: SYMLINK_PATHS
              value: "{symlink_paths}"
            - name: SYMLINK_TYPES
              value: "{symlink_types}"
            - name: WANDB_API_KEY
              value: {user_cfg['wandb_api_key']}
            - name: EPFML_LDAP
              value: {user_cfg['user']}
          resources:
            limits:
              nvidia.com/gpu: {args.gpus}
            requests: 
              cpu: {args.cpus}
          volumeMounts:
            - mountPath: /mloscratch
              name: mloscratch
            - mountPath: /dev/shm  # Increase shared memory size
              name: dshm
          ports:
            - protocol: 'TCP'
              containerPort: 22
      volumes:
        - name: mloscratch
          persistentVolumeClaim:
            claimName: runai-mlo-{user_cfg['user']}-scratch
        - name: dshm  # Increase the shared memory size
          emptyDir:
            medium: Memory
      # nodeSelector:
      #   run.ai/type: G10
"""

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml") as f:
        f.write(cfg)
        f.flush()
        if args.dry:
            print(cfg)
        else:
            result = subprocess.run(
                ["kubectl", "create", "-f", f.name],
                # check=True,
                capture_output=True,
                # text=True,
            )
            print(result.stdout)
            print(result.stderr)

    print("\nThe following commands may come in handy:")
    print(f"runai bash {args.name} - opens an interactive shell on the pod")
    print(
        f"runai delete job {args.name} - kills the job and removes it from the list of jobs"
    )
    print(
        f"runai describe job {args.name} - shows information on the status/execution of the job"
    )
    print("runai list jobs - list all jobs and their status")
    print(f"runai logs {args.name} - shows the output/logs for the job")
