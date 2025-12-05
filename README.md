# MLO: Getting Started with the EPFL RCP Cluster

This repository contains the basic steps to start running scripts and notebooks on the EPFL RCP cluster. We provide scripts that make your life easier by automating most of the boilerplate. The setup is loosely based on infrastructure from TML/CLAIRE and earlier scripts by Atli.

## Overview

The RCP cluster provides:
- **GPUs**: A100 (40GB/80GB), H100 (80GB), H200 (140GB), V100
- **Stack**: [Docker](https://www.docker.com) (containers), [Kubernetes](https://kubernetes.io) (orchestration), [run:ai](https://run.ai) (scheduler)

## Getting Help

- **FAQ**: Check the [frequently asked questions page](docs/faq.md)
- **Slack**: Reach out on `#-cluster` or `#-it` channels
- **Resources**: See [quick links](#quick-links) below

> [!TIP]
> If you have little prior experience with ML workflows, the setup below may seem daunting at first. You can copy‑paste the commands in order; the scripts are designed to hide most of the complexity. The only requirement is that you have a basic understanding of how to use a terminal and git.

> [!CAUTION]
> Using the cluster creates costs. Please be mindful of the resources you use. **Do not forget to stop your jobs when not used!**

Content overview:
- [Getting Help](#getting-help)
- [Quick Start](#quick-start)
- [Setup Guide](#setup-guide)
  - [1. Pre-setup (Access \& Repository)](#1-pre-setup-access--repository)
  - [2. Setup Tools on Your Machine](#2-setup-tools-on-your-machine)
  - [3. Login to the Cluster](#3-login-to-the-cluster)
  - [4. Configure Your `.env` File](#4-configure-your-env-file)
  - [5. Start Your First Job](#5-start-your-first-job)
- [Using VS Code](#using-vs-code)
- [Recommended Workflow](#recommended-workflow)
- [`csub.py` Usage and Arguments](#csubpy-usage-and-arguments)
- [Advanced Topics](#advanced-topics)
- [Reference](#reference)


---

## Quick Start

> [!TIP] 
> **TL;DR** – After completing the setup, interaction with the cluster looks like this:
>
> ```bash
> # Start an interactive job with 1 GPU
> python csub.py -n sandbox
> 
> # Connect to your job
> runai exec sandbox -it -- zsh
> 
> # Run your code
> cd /mloscratch/homes/<your_username>
> python main.py
> 
> # Or start a training job in one command
> python csub.py -n experiment --train --command "cd /mloscratch/homes/<your_username>/<your_code>; python main.py"
> ```

---

## Setup Guide

> [!IMPORTANT]
> **Network requirement**: You must be on the EPFL WiFi or connected to the VPN. The cluster is not accessible otherwise.

### 1. Pre-setup (Access & Repository)

**1. Request cluster access**

Ask Jennifer or Martin to add you to the `runai-mlo` group: https://groups.epfl.ch/

**2. Prepare your code repository**

While waiting for access, create a GitHub repository for your code. This is best practice regardless of our cluster setup.

**3. Set up experiment tracking (optional)**

- **Weights & Biases**: Create an account at [wandb.ai](https://wandb.ai/) and get your API key
- **Hugging Face**: Create an account at [huggingface.co](https://huggingface.co/) and get your token (if using their models)

### 2. Setup Tools on Your Machine

> [!IMPORTANT]
> **Platform note**: The setup below was tested on macOS with Apple Silicon. For other systems, adapt the commands accordingly.
> - **Linux**: Replace `darwin/arm64` with `linux/amd64` in URLs
> - **Windows**: Use WSL (Windows Subsystem for Linux)

#### Install kubectl

Download and install kubectl v1.29.6 (matching the cluster version):

```bash
# macOS with Apple Silicon
curl -LO "https://dl.k8s.io/release/v1.29.6/bin/darwin/arm64/kubectl"

# Linux (AMD64)
# curl -LO "https://dl.k8s.io/release/v1.29.6/bin/linux/amd64/kubectl"

# Install
chmod +x ./kubectl
sudo mv ./kubectl /usr/local/bin/kubectl
sudo chown root: /usr/local/bin/kubectl
``` 

See https://kubernetes.io/docs/tasks/tools/install-kubectl/ for other platforms.

#### Setup kubeconfig

Download the kube config file to `~/.kube/config`:

```bash
curl -o ~/.kube/config https://raw.githubusercontent.com/epfml/getting-started/main/kubeconfig.yaml
```

#### Install run:ai CLI

Download and install the run:ai CLI:

```bash
# macOS with Apple Silicon
wget --content-disposition https://rcp-caas-prod.rcp.epfl.ch/cli/darwin

# Linux (replace 'darwin' with 'linux')
# wget --content-disposition https://rcp-caas-prod.rcp.epfl.ch/cli/linux

# Install
chmod +x ./runai
sudo mv ./runai /usr/local/bin/runai
sudo chown root: /usr/local/bin/runai
```

### 3. Login to the Cluster

#### Login to run:ai

```bash
runai login
```

#### Verify access

```bash
# List available projects
runai list projects

# Set your default project
runai config project mlo-$GASPAR_USERNAME
```

#### Verify Kubernetes connection

```bash
kubectl get nodes
```

You should see the RCP cluster nodes listed.

### 4. Configure Your `.env` File

This setup keeps **all personal configuration and secrets** in a local `.env` file (never committed to git).

#### Clone and create `.env`

```bash
git clone https://github.com/epfml/getting-started.git
cd getting-started
cp user.env.example .env
```

#### Fill in required fields

Open `.env` in an editor and configure:

| Variable | Description | Example |
|----------|-------------|---------|
| `LDAP_USERNAME` | Your EPFL/Gaspar username | `jdoe` |
| `LDAP_UID` | Your numeric LDAP user ID | `177449` |
| `LDAP_GROUPNAME` | For MLO | `MLO-unit` |
| `LDAP_GID` | For MLO | `83070` |
| `RUNAI_PROJECT` | Your project | `mlo-<username>` |
| `K8S_NAMESPACE` | Your namespace | `runai-mlo-<username>` |
| `RUNAI_IMAGE` | Docker image | `ic-registry.epfl.ch/mlo/mlo-base:uv1` |
| `RUNAI_SECRET_NAME` | Secret name | `runai-mlo-<username>-env` |
| `WORKING_DIR` | Working directory | `/mloscratch/homes/<username>` |

#### Find your LDAP UID

To ensure correct file permissions:

```bash
# SSH into HaaS machine (use your Gaspar password)
ssh <your_gaspar_username>@haas001.rcp.epfl.ch

# Get your UID
id
```

Copy the number after `uid=` (e.g., `uid=177449`) into `LDAP_UID` in your `.env` file.

#### Optional: Add secrets and tokens

Optionally configure in `.env`:

- `WANDB_API_KEY` – Weights & Biases API key
- `HF_TOKEN` – Hugging Face token
- `GIT_USER_NAME` / `GIT_USER_EMAIL` – Git identity for commits
- GitHub SSH keys (auto-loaded from `~/.ssh/github` if empty):
  - `GITHUB_SSH_KEY_PATH` / `GITHUB_SSH_PUBLIC_KEY_PATH` (to override default paths)

#### Sync your secret

The secret is automatically synced when starting a job. To manually sync:

```bash
python csub.py --sync-secret-only
```

### 5. Start Your First Job

#### Start an interactive pod

```bash
python csub.py -n sandbox
```

#### Wait for the pod to start

This can take a few minutes. Monitor the status:

```bash
# List all jobs
runai list

# Check specific job status
runai describe job sandbox
```

#### Connect to your pod

Once the status shows `Running`:

```bash
runai exec sandbox -it -- zsh
```

You should now be inside a terminal on the cluster! 🎉

### 6. Clone and Run Your Code

#### Clone your repository

Inside the pod, clone your code into your scratch home folder:

```bash
cd /mloscratch/homes/<your_username>
git clone https://github.com/<your_username>/<your_repo>.git
cd <your_repo>
```

#### Set up your Python environment

The default image includes [uv](https://github.com/astral-sh/uv) as the recommended package manager (pip also works):

```bash
# Create and activate virtual environment
uv venv .venv
source .venv/bin/activate

# Install dependencies
uv pip install -r requirements.txt
```

#### Run your code

```bash
python main.py
```

If you configured `WANDB_API_KEY` or `HF_TOKEN` in `.env`, authentication should work automatically.

---

## Using VS Code

For remote development on the cluster:

1. **Install extensions**
   - [Kubernetes](https://marketplace.visualstudio.com/items?itemName=ms-kubernetes-tools.vscode-kubernetes-tools)
   - [Dev Containers](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers)

2. **Attach to your pod**
   - Navigate to: **Kubernetes** → **rcp-cluster** → **Workloads** → **Pods**
   - Right-click your pod → **Attach Visual Studio Code**
   - Open `/mloscratch/homes/<your_username>` in the remote session

For detailed instructions, see the [Managing Workflows guide](docs/managing_workflows.md#using-vs-code).

---

## Recommended Workflow

> [!TIP]
> **Development cycle**:
> 1. Develop code locally or on the cluster (using VS Code)
> 2. Push changes to GitHub
> 3. Run experiments on the cluster via `runai exec sandbox -it -- zsh`
> 4. Keep code and experiments organized and reproducible

> [!IMPORTANT]
> **Critical reminders**:
> - **Pods can be killed anytime** – Implement checkpointing and recovery
> - **Store files on scratch** – Everything in `~/` is lost when pods restart
> - **Use `/mloscratch/homes/<username>`** – Shell config and VS Code settings persist here
> - **Delete failed jobs** – Run `runai delete job <name>` before restarting
> - **Background jobs** – Use training mode: `python csub.py -n exp --train --command "..."`

> [!CAUTION]
> **Using the cluster creates costs.** Always stop your jobs when not in use!

For detailed workflow guidance, see the [Managing Workflows guide](docs/managing_workflows.md).

---


## `csub.py` Usage and Arguments

The `csub.py` script is a thin wrapper around the run:ai CLI that simplifies job submission by:
- Reading configuration and secrets from `.env`
- Syncing Kubernetes secrets automatically
- Constructing and executing `runai submit` commands

### Basic Usage

```bash
python csub.py -n <job_name> -g <num_gpus> -t <time> --command "<cmd>" [--train]
```

### Common Examples

```bash
# CPU-only pod for development
python csub.py -n dev-cpu

# Interactive development pod with 1 GPU
python csub.py -n dev-gpu -g 1

# Training job with 4 A100 GPUs
python csub.py -n experiment --train -g 4 --command "cd /mloscratch/homes/user/code; python train.py"

# Use specific GPU type
python csub.py -n my-job -g 2 --node-type h100 --train --command "..."

# Dry run (see command without executing)
python csub.py -n test --dry --command "..."
```

### Available Arguments

| Argument | Description | Default |
|----------|-------------|---------|
| `-n`, `--name` | Job name | Auto-generated (username + timestamp) |
| `-g`, `--gpus` | Number of GPUs | `0` (CPU-only) |
| `-t`, `--time` | Maximum runtime (e.g., `12h`, `2d6h30m`) | `12h` |
| `-c`, `--command` | Command to run | `sleep <duration>` |
| `--train` | Submit as training workload (non-interactive) | Interactive mode |
| `-i`, `--image` | Docker image | From `RUNAI_IMAGE` in `.env` |
| `--node-type` | GPU type: `v100`, `h100`, `h200`, `default`, `a100-40g` | `default` (A100) |
| `--cpus` | Number of CPUs | Platform default |
| `--memory` | CPU memory request | Platform default |
| `-p`, `--port` | Expose container port (for Jupyter, etc.) | None |
| `--large-shm` | Request larger `/dev/shm` | False |
| `--host-ipc` | Share host IPC namespace | False |
| `--backofflimit` | Retries before marking training job failed | `0` |

### Secret Management

| Argument | Description |
|----------|-------------|
| `--sync-secret-only` | Only sync `.env` to Kubernetes secret, don't submit job |
| `--skip-secret-sync` | Don't sync secret before submission |
| `--secret-name` | Override `RUNAI_SECRET_NAME` from `.env` |
| `--env-file` | Path to `.env` file | `.env` |

### Advanced Options

| Argument | Description |
|----------|-------------|
| `--uid` | Override `LDAP_UID` from `.env` |
| `--gid` | Override `LDAP_GID` from `.env` |
| `--pvc` | Override `SCRATCH_PVC` from `.env` |
| `--dry` | Print command without executing |

### After Submission

After submitting, `csub.py` prints useful follow-up commands:

```bash
runai describe job <name>  # Check job status
runai logs <name>          # View logs
runai exec <name> -it -- zsh  # Connect to pod
runai delete job <name>    # Delete job
```

Run `python csub.py -h` for the complete help text.

---

## Advanced Topics

### Managing Workflows

For detailed guides on day-to-day operations, see the [Managing Workflows guide](docs/managing_workflows.md):

- [Pod management](docs/managing_workflows.md#managing-pods) – Commands to list, describe, delete jobs
- [Important workflow notes](docs/managing_workflows.md#important-notes-and-workflow) – Job types, GPU selection, best practices
- [HaaS machine](docs/managing_workflows.md#the-haas-machine) – File transfer between storage systems
- [File management](docs/managing_workflows.md#file-management) – Understanding storage (mloscratch, mlodata1, mloraw1)

### Alternative Workflows

- **Run:ai CLI directly**: See [`docs/runai_cli.md`](docs/runai_cli.md) for using run:ai without `csub.py`
- **Custom Docker images**: See [Creating Custom Images](#creating-custom-docker-images)
- **Distributed training**: See [`docs/multinode.md`](docs/multinode.md) for multi-node jobs

### Creating Custom Docker Images

If you need custom dependencies:

1. **Get registry access**
   - Login at https://ic-registry.epfl.ch/ and verify you see the MLO project
   - The `runai-mlo` group should already have access

2. **Install Docker**
   ```bash
   brew install --cask docker  # macOS
   ```
   If you get "Cannot connect to the Docker daemon", run Docker Desktop GUI first.

3. **Login to registry**
   ```bash
   docker login ic-registry.epfl.ch  # Use GASPAR credentials
   ```

4. **Modify and publish**
   - Edit `docker/Dockerfile` as needed
   - Use `docker/publish.sh` to build and push
   - **Important**: Rename your image (e.g., `mlo/<your-username>:tag`) to avoid overwriting the default

**Example workflow:**
```bash
docker build . -t <your-tag>
docker tag <your-tag> ic-registry.epfl.ch/mlo/<your-tag>
docker push ic-registry.epfl.ch/mlo/<your-tag>
```

See also [Matteo's custom Docker example](https://gist.github.com/mpagli/6d0667654bf8342eb4923fedf731660e).

### Port Forwarding

To access services running in your pod (e.g., Jupyter):

```bash
kubectl get pods
kubectl port-forward <pod_name> 8888:8888
```

Then access at `http://localhost:8888`

### Distributed Training

For multi-node training across several compute nodes, see the detailed guide:

- **Documentation**: [`docs/multinode.md`](docs/multinode.md)
- **Official docs**: https://docs.run.ai/v2.13/Researcher/cli-reference/runai-submit-dist-pytorch/

---

## Reference

### File Overview

```
├── csub.py                # Job submission wrapper (wraps runai submit)
├── utils.py               # Python helpers for csub.py
├── user.env.example       # Template for .env (copy and configure)
├── docker/
│   ├── Dockerfile         # uv-enabled base image (RCP template)
│   ├── entrypoint.sh      # Runtime bootstrap script
│   └── publish.sh         # Build and push Docker images
├── kubeconfig.yaml        # Kubeconfig template for ~/.kube/config
└── docs/
    ├── faq.md             # Frequently asked questions
    ├── managing_workflows.md  # Day-to-day operations guide
    ├── README.md          # Architecture deep dive
    ├── runai_cli.md       # Alternative run:ai CLI workflows
    ├── multinode.md       # Multi-node/distributed training
    └── how_to_use_k8s_secret.md  # Kubernetes secrets reference
```

### Deep Dive: How This Setup Works

For technical details about the Docker image, entrypoint script, environment variables, and secret management:

**Read the architecture explainer**: [`docs/README.md`](docs/README.md)

Topics covered:
- Runtime environment and entrypoint
- Permissions model and shared caches
- uv-based Python workflow
- Images and publishing
- Secrets, SSH, and Kubernetes integration

### Quick Links

**RCP Resources**
- [RCP Main Page](https://www.epfl.ch/research/facilities/rcp/)
- [Documentation](https://wiki.rcp.epfl.ch)
- [Dashboard](https://portal.rcp.epfl.ch/)
- [Docker Registry](https://ic-registry.epfl.ch/)
- [Quick Start Guide](https://wiki.rcp.epfl.ch/en/home/CaaS/Quick_Start)

**run:ai Documentation**
- [Official run:ai docs](https://docs.run.ai)

**Related Resources**
- [Compute and Storage @ CLAIRE](https://prickly-lip-484.notion.site/Compute-and-Storage-CLAIRE-91b4eddcc16c4a95a5ab32a83f3a8294) – Similar setup by colleagues

**MLO Cluster Repositories (OUTDATED)**

These repositories contain shared tooling and infrastructure (by previous PhD students). Contact Martin for editor access. **They are outdated and not maintained anymore.**

- [epfml/epfml-utils](https://github.com/epfml/epfml-utils) – Python package for shared tooling (`pip install epfml-utils`)
- [epfml/mlocluster-setup](https://github.com/epfml/mlocluster-setup) – Base images and setup for semi-permanent machines
