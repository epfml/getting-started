## MLO: Getting started with the EPFL RCP cluster
This repository contains the basic steps to start running scripts and notebooks on the EPFL RCP cluster so that you do not have to go through all the documentation by yourself. We provide scripts that make your life easier by automating most of the boilerplate. The setup is loosely based on infrastructure from TML/CLAIRE and earlier scripts by Atli :)

The RCP cluster has A100 (40GB/80GB), H100 (80GB), H200 (140GB) and V100 GPUs that you can choose from. The system is built on top of [Docker](https://www.docker.com) (containers), [Kubernetes](https://kubernetes.io) (container orchestration) and [run:ai](https://run.ai) (scheduler on top of Kubernetes).

For starters, we recommend going through the [minimal basic setup](#minimal-basic-setup) first and then reading the [important notes](#important-notes-and-workflow).

If you have questions about the cluster or this setup that are not answered here, check the [frequently asked questions page](docs/faq.md) or reach out to your colleagues (e.g. via the `#cluster` or `#it` channels on Slack). There are more resources under the [quick links](#quick-links) below.

> [!TIP]
> If you have little prior experience with ML workflows, the setup below may seem daunting at first. You can copy‑paste the commands in order; the scripts are designed to hide most of the complexity. The only requirement is that you have a basic understanding of how to use a terminal and git.

> [!CAUTION]
> Using the cluster creates costs. Please be mindful of the resources you use. **Do not forget to stop your jobs when not used!**

Content overview:
- [MLO: Getting started with the EPFL RCP cluster](#mlo-getting-started-with-the-epfl-rcp-cluster)
- [Minimal basic setup](#minimal-basic-setup)
- [1: Pre-setup (access, repository)](#1-pre-setup-access-repository)
- [2: Setup the tools on your own machine](#2-setup-the-tools-on-your-own-machine)
- [3: Login](#3-login)
- [4: Configure your `.env` file](#4-configure-your-env-file)
- [5: Use this repo to start a job](#5-use-this-repo-to-start-a-job)
- [6: Cloning and running your code](#6-cloning-and-running-your-code)
- [Managing workflows and advanced topics](#managing-workflows-and-advanced-topics)
  - [Using VSCODE](#using-vscode)
  - [Managing pods](#managing-pods)
  - [Important notes and workflow](#important-notes-and-workflow)
  - [The HaaS machine](#the-haas-machine)
  - [File management](#file-management)
    - [Moving data onto/between storage](#moving-data-ontobetween-storage)
  - [`csub.py` usage and arguments](#csubpy-usage-and-arguments)
  - [Alternative workflow: using the run:ai CLI and base docker images with pre-installed packages](#alternative-workflow-using-the-runai-cli-and-base-docker-images-with-pre-installed-packages)
  - [Creating a custom docker image](#creating-a-custom-docker-image)
  - [Port forwarding](#port-forwarding)
  - [Distributed training](#distributed-training)
- [File overview of this repository](#file-overview-of-this-repository)
- [Deep dive: how this setup works](#deep-dive-how-this-setup-works)
- [Quick links](#quick-links)
  - [Other cluster-related code repositories](#other-cluster-related-code-repositories)


## Minimal basic setup
The step-by-step instructions for first time users to quickly get a job running. 

> [!TIP] 
> After completing the setup, the **TL;DR** of the interaction with the cluster (using the scripts in this repo) is:
> * Get a running job with one GPU that is reserved for you: `python csub.py -n sandbox`
> 
> * Connect to a terminal inside your job: `runai exec sandbox -it -- zsh`
> 
> * Run your code: `cd /mloscratch/homes/<your username>; python main.py`
>
> * In one go, you can also do: `python csub.py -n experiment --train --command "cd /mloscratch/homes/<your username>/<your code>; python main.py "`

---

> [!IMPORTANT]
> Make sure you are on the EPFL wifi or connected to the VPN. The cluster is otherwise not accessible.

## 1: Pre-setup (access, repository)

**Group access:** You need to have access to the cluster. For that, ask Jennifer or Martin (or someone else) to add you to the group `runai-mlo`: https://groups.epfl.ch/

**Prepare your code:** While you are waiting to get access, create a GitHub repository where you will implement your code. Irrespective of our cluster or this guide, it is best practice to keep track of your code with a GitHub repo.

**Prepare Weights and Biases or HuggingFace:** For logging the results of your experiments, you can use [Weights and Biases](https://wandb.ai/). Create an account if you don't already have one. You will need an API key to later log your experiments. The same goes for the [Huggingface Hub](https://huggingface.co/) if you want to use their hosted models.

The following are just a bunch of commands you need to run to get started. If you do not understand them in detail, you can copy-paste them into your terminal :)

## 2: Setup the tools on your own machine

> [!IMPORTANT]
> The setup below was tested on macOS with Apple Silicon. If you are using a different system, you may need to adapt the commands.
> For Windows, we have no experience with the setup and thereby recommend WSL (Windows Subsystem for Linux) to run the commands.

1. Install kubectl. To make sure the version matches with the clusters (status: 15.12.2023), on macOS with Apple Silicon, run the following commands. For other systems, you will need to change the URL in the command above (check https://kubernetes.io/docs/tasks/tools/install-kubectl/). Make sure that the version matches with the version of the cluster!
```bash
# Sketch for macOS with Apple Silicon.
# Download a specific version (here v1.29.6 for Apple Silicon macOS)
curl -LO "https://dl.k8s.io/release/v1.29.6/bin/darwin/arm64/kubectl"
# Linux: curl -LO "https://dl.k8s.io/release/v1.29.6/bin/linux/amd64/kubectl"
# Give it the right permissions and move it.
chmod +x ./kubectl
sudo mv ./kubectl /usr/local/bin/kubectl
sudo chown root: /usr/local/bin/kubectl
``` 

2. Setup the kube config file: Take our template file [`kubeconfig.yaml`](kubeconfig.yaml) as your config in the home folder `~/.kube/config`. Note that the file on your machine has no suffix.
```bash
curl -o  ~/.kube/config https://raw.githubusercontent.com/epfml/getting-started/main/kubeconfig.yaml
```

3. Install the run:ai CLI for RCP:
```bash
# Sketch for macOS with Apple Silicon
# Download the CLI from the link shown in the help section.
# for Linux: replace `darwin` with `linux`
wget --content-disposition https://rcp-caas-prod.rcp.epfl.ch/cli/darwin
# Give it the right permissions and move it.
chmod +x ./runai
sudo mv ./runai /usr/local/bin/runai
sudo chown root: /usr/local/bin/runai
```

## 3: Login

1. Login to the RCP cluster and check that you can see your projects.
```bash
# Login to the cluster
runai login

# Check that things worked fine
runai list projects

# Put default project
runai config project mlo-$GASPAR_USERNAME
```

2. Verify that Kubernetes is configured correctly.
```bash
kubectl get nodes
```
You should see the RCP cluster nodes listed.


## 4: Configure your `.env` file

Instead of editing Kubernetes YAML files, this setup keeps **all personal configuration and secrets** in a local `.env` file in the repo root. This file is **never committed to git**.

1. Clone this repository (if you have not already) and create your `.env`:
```bash
git clone https://github.com/epfml/getting-started-new.git  # skip if already cloned
cd getting-started-new
cp user.env.example .env
```

2. Fill in your identity and project information.

Open `.env` in an editor and set at least:

- `LDAP_USERNAME` – your EPFL/Gaspar username (e.g. `jdoe`).
- `LDAP_UID` – your numeric LDAP user ID.
- `LDAP_GROUPNAME` – for MLO this should be `MLO-unit`.
- `LDAP_GID` – for MLO this is `83070`.
- `RUNAI_PROJECT` – usually `mlo-<your_username>`.
- `K8S_NAMESPACE` – usually `runai-mlo-<your_username>`.
- `RUNAI_IMAGE` – default is `ic-registry.epfl.ch/mlo/mlo-base:uv1` (works for most cases).
- `RUNAI_SECRET_NAME` – any unique name in your namespace, e.g. `runai-mlo-<you>-env`.
- `WORKING_DIR` – usually `/mloscratch/homes/<your_username>`.

3. Find your numeric UID on the HaaS machine.

To make sure file permissions on scratch work correctly, we want the UID inside the container to match your real EPFL UID.

- SSH into the HaaS machine using your **Gaspar password**:
```bash
ssh <your_gaspar_username>@haas001.rcp.epfl.ch
```
- Once logged in, run:
```bash
id
```
- The number after `uid=` (for example, `uid=177449(...)`) is your **LDAP UID**. Copy that value into `LDAP_UID` in your `.env` file.  
  The group ID for the MLO group is already set to `83070` in `LDAP_GID` and usually does not need to be changed.

4. (Optional) Fill in secrets and tokens.

In `.env`, you can additionally set:

- `WANDB_API_KEY` – your Weights & Biases API key (optional).
- `HF_TOKEN` – your Hugging Face token (optional).
- `GIT_USER_NAME` / `GIT_USER_EMAIL` – used to set global git identity inside pods.
- SSH keys (`SSH_PRIVATE_KEY_B64`, `SSH_PUBLIC_KEY`, `SSH_KNOWN_HOSTS`) if you want to control them manually.
  - By default, if these are empty and you have a key at `~/.ssh/github`, `csub.py` will read that key automatically.
- `GITHUB_SSH_KEY_PATH` / `GITHUB_SSH_PUBLIC_KEY_PATH` – optional paths to override which local SSH key is auto-synced into `SSH_*`. Set these if your GitHub key is not stored at `~/.ssh/github`.

If you leave the SSH fields empty and rely on the defaults, `csub.py` will auto-load the key from `GITHUB_SSH_KEY_PATH` (by default `~/.ssh/github`) and inject it into the secret for you.

5. Create or update the Kubernetes secret from `.env`.

Whenever you change your `.env`, you can run:
```bash
python csub.py --sync-secret-only
```
This command pushes the contents of `.env` into a Kubernetes secret in your namespace. It is idempotent, so it is safe to re‑run whenever you update `.env`.
The env syncing is handled automatically by `csub.py` when you start a job, so you do not need to run this command manually unless you want to sync the secret manually.


## 5: Use this repo to start a job

1. Ensure your `.env` is configured and the secret is synced (see above).

2. Create a pod with 1 GPU (interactive sandbox).
```bash
python csub.py -n sandbox
```

3. Wait until the pod has a `Running` status. This can take a few minutes. Check the status of the job with:
```bash
runai list # shows all jobs
runai describe job sandbox # shows the status of the job sandbox
```

4. When it is running, connect to the pod:
```bash
runai exec sandbox -it -- zsh
```

5. If everything worked correctly, you should be inside a terminal on the cluster!


## 6: Cloning and running your code

1. Clone your fork of your GitHub repository (where you have your experiment code) into the pod **inside your scratch home folder**.
```bash
# Inside the pod
cd /mloscratch/homes/<your_username>
git clone https://github.com/<your_username>/<your_code>.git
cd <your_code>
```

2. Create an environment that contains the packages needed for your experiments.

The default image ships with [uv](https://github.com/astral-sh/uv) as the recommended Python package manager, but `pip` also works. Example using uv:
```bash
# inside the pod, in /mloscratch/homes/<your_username>/<your_code>
uv venv .venv
source .venv/bin/activate
uv pip install -r requirements.txt
```

3. Now you can run the code as you would on your local machine. For example, to run a `main.py` script (assuming you wrote it in your code), you simply do:
```bash
# Inside the pod, inside /mloscratch/homes/<your_username>/<your_code>
python main.py
```

Hopefully, this should work and you're up and running! If you set `WANDB_API_KEY` and/or `HF_TOKEN` in `.env`, your jobs should automatically authenticate with Weights & Biases and/or Hugging Face.

For remote development (changing code, debugging, etc.), we recommend using VS Code. You can find more information on how to set it up in the [VS Code section](#using-vscode).

> [!TIP]
> Generally, the workflow we recommend is simple: develop your code locally or on the cluster (e.g. with VS Code), then push it to your repository. Once you want to try, run it on the cluster with the terminal that is attached via `runai exec sandbox -it -- zsh`. This way, you can keep your code and experiments organized and reproducible.
>
> Note that your pods **can be killed anytime**. This means you might need to restart an experiment (with the `python csub.py` command we give above). You can see the status of your jobs with `runai list`. If a job has status "Failed", you have to delete it via `runai delete job sandbox` before being able to start the same job again.
> 
> **Keep your files inside your home folder**: Importantly, when a job is restarted or killed, everything inside the container folders of `~/` are lost. This is why you need to work inside `/mloscratch/homes/<your username>`. Shell configuration and VS Code settings are set up to persist on scratch.
>
> To have a job that can run in the background, do `python csub.py -n sandbox --train --command "cd /mloscratch/homes/<your username>/<your code>; python main.py "`

You're good to go now! It is up to you to customize your environment and install the packages you need. Read up on the rest of this README to learn more about the cluster and the scripts.

> [!CAUTION]
> Using the cluster creates costs. Please do not forget to stop your jobs when not used!

## Managing workflows and advanced topics

### Using VSCODE
To easily attach a VSCODE window to a pod we recommend the following steps: 
1. Install the [Kubernetes](https://marketplace.visualstudio.com/items?itemName=ms-kubernetes-tools.vscode-kubernetes-tools) and [Dev Containers](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers) extensions.
2. From your VSCODE window, click on Kubernetes -> rcp-cluster -> Workloads -> Pods, and you should be able to see all your running pods.
3. Right-click on the pod you want to access and select `Attach Visual Studio Code`, this will start a vscode session attached to your pod.
4. The symlinks ensure that settings and extensions are stored in `mloscratch/homes/<gaspar username>` and therefore shared across pods.
5. Note that when opening the VS code window, it opens the home folder of the pod (not scratch!). You can navigate to your working directory (code) by navigating to `/mloscratch/homes/<your username>`.

You can also see a pictorial description [here](https://wiki.rcp.epfl.ch/en/home/CaaS/FAQ/how-to-vscode).

### Managing pods
After starting pods with the script, you can manage your pods using run:ai and the following commands: 
``` bash
runai exec pod_name -it -- zsh # - opens an interactive shell on the pod 
runai delete job pod_name # kills the job and removes it from the list of jobs
runai describe job pod_name # shows information on the status/execution of the job
runai list jobs # list all jobs and their status 
runai logs pod_name # shows the output/logs for the job
```
Some commands that might come in handy (credits to Thijs):
```bash
# Clean up succeeded jobs from run:ai.
runai list | grep " Succeeded " | awk '{print $1}' | parallel runai delete job {}
# Overview of active jobs that fits on your screen.
runai list jobs | sed '1d' | awk '{printf "%-42s %-20s\n", $1, $2}'
# Auto-updating listing of jobs and their states.
watch -n 10 "runai list | sed 1d | awk '{printf \"%0-40s %0-20s\n\", \$1, \$2}'"
```

### Important notes and workflow
We provide the script in this repo as a convenient way of creating jobs (see more details in the section below).
* The default job is just an interactive one (with `sleep`) that you can use for development. 
  * 'Interactive' jobs are a concept from run:ai. Every user can have 1 interactive GPU. They have higher priority than other jobs and can live up to 12 hours. You can use them for debugging. If you need more than 1 GPU, you need to submit a training job.
* For a training job, use the flag `--train`, and replace the command with your training command. Using a training job allows you to use more than 1 GPU (up to 8 on one node). Moreover, a training job makes sure that the pod is killed when your code/experiment is finished in order to save money.
* When choosing types of GPUs on the RCP cluster you have handful of options. You should consider both cost and memory and compute requirements of your job while choosing among them. 
  * High-end GPUs like H100 and H200 come with significantly higher costs, so they should be used with care. 
  * A100 GPUs are good enough for most of use cases. If your job does not require large memory, A100 40GB or V100 may be more cost-effective and faster to schedule. If your code is not heavily compute-bound and works well on older hardware, using V100 is preferred. 
  * For memory-intensive workloads, H200 with 140GB RAM is recommended. 
  * Overall, if you plan to run a series of jobs, it's a good idea to inform your supervisor in advance.
* For specifying the type of GPU while submitting with `csub.py`, you should use the flag `--node_type`. If you are submitting directly through CLI, you should use the flag `--node-pools` instead. In both cases, you should choose from `[v100|h100|h200|default|a100-40g]`, where `default` corresponds to A100 GPUs. So if you want to use A100 as an example, you should add `--node-pools default` in CLI submission or `--node_type default` when submitting `csub.py`.

Of course, the script is just one suggested workflow that tries to maximize productivity and minimize costs -- you're free to find your own workflow, of course. For whichever workflow you go for, keep these things in mind:
> [!IMPORTANT]
> * Work within `/mloscratch`. This is the shared storage that is mounted to your pod.
>   * Create a directory with your GASPAR username in `/mloscratch/` folder. This will be your personal folder. Except under special circumstances, all your files should be kept inside your personal folder (e.g. `/mloscratch/nicolas` if your username is nicolas) or in your personal home folder (e.g. `/mloscratch/homes/nicolas`).**  
>   * Should you use the `csub.py` script, the first run will automatically create a working directory with your username inside `/mloscratch/homes`.
>   * Suggestion: use a GitHub repo to store your code and clone it inside your folder.
> * Moving things onto the cluster or between folders can also be done easily via [HaaS machine](#the-haas-machine). For more details on storage, see [file management](#file-management).
> * Remember that your job can get killed ***anytime*** if run:ai needs to make space for other users. Make sure to implement checkpointing and recovery into your scripts. 
> * CPU-only pods are cheap, approx 3 CHF/month, so we recommend creating a CPU-only machine that you can let run and use for code development/debugging through VSCODE.
> * When your code is ready and you want to run some experiments or you need to debug on GPU, you can create one or more new pods with GPU. Simply specify the command in the python launch script.
> * Using a training job makes sure that you kill the pod when your code/experiment is finished in order to save money.

Most importantly:
>[!CAUTION]
> Using the cluster creates costs. Please do not forget to stop your jobs when not used!


### The HaaS machine
The HaaS machine is provided by IT that allows you to move files, create folders, and copy files between `mlodata1`, `mloraw1`, and `mloscratch`, without needing to create a pod. You can access it via:
```bash
  # For basic file movement, folder creation, or
  # copying from/to mlodata1 to/from scratch:
  ssh <gaspar_username>@haas001.rcp.epfl.ch
```
The volumes are mounted inside the folders `/mnt/mlo/mlodata1`, `/mnt/mlo/mloraw1`, `/mnt/mlo/scratch`. See below for what the spaces are used for.

### File management
Reminder: the cluster uses kubernetes pods, which means that in principle, any file created inside a pod will be deleted when the pod is killed. 

To store files permanently, you need to mount network disks to your pod. In our case, this is `mloscratch` -- _all_ code and experimentation should be stored there. Except under special circumstances, all your files should be kept inside your personal folder (e.g. `/mloscratch/nicolas` if your username is nicolas) or in your personal home folder (e.g. `/mloscratch/homes/nicolas`). Scratch is high-performance storage that is meant to be accessed/mounted from pods. Even though it is called "scratch", you do not need to generally worry about losing data (it is just not replicated across multiple hard drives).

For very secure long-term storage, we have:
* `mlodata1`. 
  * This is long term storage, backed up carefully with replication (i.e. stored on multiple hard drives). This is meant to contain artifacts that you want to keep for an undetermined amount of time (e.g. things for a publication). 
* `mloraw1`
   * Not clear right now how this will be used in the future (status: 15.12.2023).
> [!CAUTION]
> You cannot mount mlodata or mloraw on pods. Use the haas machine below to access it.

#### Moving data onto/between storage
Since `mloscratch` is not _replicated_, whenever you need things to become permanent, move them to `mlodata1`. This could be the case for paper artifacts, certain results or checkpoints, and so on. 

Currently, if you need to move things between `mlodata1` and `scratch`, you need to do this manually via a machine provided by IT:
```bash
  # For basic file movement, folder creation, or
  # copying from/to mlodata1 to/from scratch:
  ssh <gaspar_username>@haas001.rcp.epfl.ch
```
The volumes are mounted inside the folders `/mnt/mlo/mlodata1`, `/mnt/mlo/mloraw1`, `/mnt/mlo/scratch`. You can copy files between them using `cp` or `rsync`.

**TODO:** Update with permanent machine for MLO once we have it.

### `csub.py` usage and arguments

The Python script `csub.py` is a thin wrapper around the run:ai CLI that makes it easier to launch jobs by:

- reading configuration and secrets from `.env`,
- (optionally) ensuring the Kubernetes secret is in sync,
- constructing the `runai submit` command and executing it for you.

General usage:

```bash
python csub.py -n <job_name> -g <number of GPUs> -t <time> -i ic-registry.epfl.ch/mlo/mlo-base:uv1 --command "<cmd>" [--train]
```

All available arguments:

- **`-n`, `--name`**: Job name (auto‑generated if omitted; includes your username and a timestamp).
- **`--uid`**: Run the container as this UID instead of `LDAP_UID` from `.env`.
- **`--gid`**: Run the container as this GID instead of `LDAP_GID` from `.env`.
- **`-c`, `--command`**: Command to run inside the container (default: `sleep <duration>` so the pod stays alive).
- **`-t`, `--time`**: Maximum runtime, formatted like `12h`, `45m`, `2d6h30m` (default: 12h for the keep‑alive sleep).
- **`-g`, `--gpus`**: Number of GPUs to request (default: `0`, i.e. CPU‑only pod).
- **`--cpus`**: Number of CPUs to request (omit to use the platform default).
- **`--memory`**: CPU memory request (omit to use the platform default).
- **`-i`, `--image`**: Override `RUNAI_IMAGE` from `.env`.
- **`-p`, `--port`**: Expose a container port (for port‑forwarding / Jupyter etc.).
- **`--train`**: Submit as a **training workload** (non‑interactive, background job; supports retries).
- **`--dry`**: Only print the generated `runai submit ...` command and exit (no submission).
- **`--env-file`**: Path to the `.env` file (default: `.env` in the repo root).
- **`--sync-secret-only`**: Create/refresh the Kubernetes secret from `.env` and exit **without** submitting a job.
- **`--skip-secret-sync`**: Do **not** (re)create the Kubernetes secret before submission (use if you know it is up‑to‑date).
- **`--secret-name`**: Override `RUNAI_SECRET_NAME` from `.env`.
- **`--pvc`**: Override `SCRATCH_PVC` from `.env`.
- **`--backofflimit`**: Number of retries before marking a **training** job as failed (default: `0`).
- **`--node-type`**: GPU node pool to target; one of `{v100, h100, h200, default, a100-40g}`.  
  - For `h100`/`h200` interactive jobs, `csub.py` automatically adds `--preemptible`.
- **`--host-ipc`**: Share the host IPC namespace.
- **`--large-shm`**: Request a larger `/dev/shm` for workloads that need more shared memory.

After submitting a job, `csub.py` prints useful follow‑up commands:

- `runai describe job <name>`
- `runai logs <name>`
- `runai exec <name> -it -- zsh`
- `runai delete job <name>`

You can always run `python csub.py -h` to see the up‑to‑date help text.

### Alternative workflow: using the run:ai CLI and base docker images with pre-installed packages
The setup in this repository is just one way of running and managing the cluster. You can also use the run:ai CLI directly, or use the scripts in this repository as a starting point for your own setup. For more details, see the [the dedicated readme](docs/runai_cli.md).

### Creating a custom docker image
In case you want to customize it and create your own docker image, follow these steps:
- **Request registry access**: This step is needed to push your own docker images in the container. Try login here https://ic-registry.epfl.ch/ and see if you see members inside the MLO project. The groups of runai are already added, it should work already. If not, reach out to Alex or a colleague.
 - **Install Docker:** `brew install --cask docker` (or any other preferred way according to the docker website). When you execute commands via terminal and you see an error '“Cannot connect to the Docker daemon”', try running docker via GUI the first time and then the commands should work.
 - **Login registry:** `docker login ic-registry.epfl.ch` and use your GASPAR credentials. Same for the RCP cluster: `docker login registry.rcp.epfl.ch` (but we're currently not using it).
 
 
 Modify Dockerfile:** 
   - The repo contains a template Dockerfile that you can modify in case you need a custom image 
   - Push the new docker using the script `publish.sh`
   - **Remember to rename the image (`mlo/username:tag`) such that you do not overwrite the default one**

**Additional example:** Alternatively, Matteo also wrote a custom one and summarized the steps here: https://gist.github.com/mpagli/6d0667654bf8342eb4923fedf731660e
* He created an image that runs by default under his Gaspar user ID and group ID. You can find those IDs in e.g. https://people.epfl.ch/matteo.pagliardini under 'donnees administratives'.
* Upload your image to EPFL's registry
```bash
docker build . -t <your-tag>
docker login ic-registry.epfl.ch -u <your-epfl-username> -p <your-epfl-password> # use your epfl credentials
docker tag <your-tag> ic-registry.epfl.ch/mlo/<your-tag>
docker push ic-registry.epfl.ch/mlo/<your-tag>
```

### Port forwarding
If you want to access a port on your pod from your local machine, you can use port forwarding. For example, if you want to access a jupyter notebook running on your pod, you can do the following:
```bash
kubectl get pods
kubectl port-forward <pod_name> 8888:8888
```

### Distributed training
Newer versions of runai support distributed training, meaning the ability to use run accross multiple compute nodes, even beyond the several GPUs available on one node. This is currently set up on the new RCP Prod cluster (rcp-caas).
A nice [documentation to get started with distributed jobs is available here](docs/multinode.md).

## File overview of this repository
```bash
├── csub.py              # Submission helper: wraps `runai submit` and syncs the .env-backed secret
├── utils.py             # Shared Python helpers for csub.py (env parsing, secret creation, etc.)
├── user.env.example     # Template for your local .env (copy to .env and fill in)
├── docker/
│   ├── Dockerfile       # uv-enabled base image (RCP template)
│   ├── entrypoint.sh    # Runtime bootstrap (user creation, scratch dirs, SSH, uv caches, etc.)
│   └── publish.sh       # Helper to build and push the Docker image
├── kubeconfig.yaml      # Kubeconfig that you should store in ~/.kube/config
├── docs/
│   ├── faq.md           # FAQ
│   ├── runai_cli.md     # Run:ai CLI guide and examples
│   ├── multinode.md     # Notes on distributed / multi-node jobs
│   └── how_to_use_k8s_secret.md  # Short reminder on Kubernetes secrets and run:ai
└── README.md            # This file
```


## Deep dive: how this setup works

If you want to understand the setup in more detail (how the Docker image is constructed, how `entrypoint.sh` prepares your scratch folders and shell, how `.env` is converted into a Kubernetes secret, and how `csub.py` maps its arguments to `runai submit`), read the companion explainer:

- **Architecture and setup explainer**: [`docs/README.md`](docs/README.md)


## Quick links

 * RCP main page: https://www.epfl.ch/research/facilities/rcp/
 * Docs: https://wiki.rcp.epfl.ch
 * Dashboard: (https://portal.rcp.epfl.ch/).
 * Docker registry: https://ic-registry.epfl.ch/
 * Getting started guide: https://wiki.rcp.epfl.ch/en/home/CaaS/Quick_Start

run:ai docs: https://docs.run.ai

If you want to read up more on the cluster, you can checkout a great in-depth guide by our colleagues at CLAIRE. They have a similar setup of compute and storage: 
* [Compute and Storage @ CLAIRE](https://prickly-lip-484.notion.site/Compute-and-Storage-CLAIRE-91b4eddcc16c4a95a5ab32a83f3a8294#)


### Other cluster-related code repositories
These repositories are mostly by previous PhDs. They used these repositories to manage shared compute infrastructure. If you want to contribute, please ask Martin to add you as an editor.
* [epfml/epfml-utils](https://github.com/epfml/epfml-utils)
  * Python package (pip install epfml-utils) for shared tooling.
* [epfml/mlocluster-setup](https://github.com/epfml/mlocluster-setup)
  * Base docker images, and setup code for semi-permanent shared machines (less recommended).
