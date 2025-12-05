# Architecture Deep Dive

This document provides a technical explanation of how the MLO cluster setup works. It's **not required** for following the [getting started guide](../README.md), but useful for understanding the system in depth.

## Overview

The revamped setup features:

**Modern workflow**
- `csub.py` wraps the run:ai CLI directly (no generated YAML files)
- Simple CLI commands that you could type by hand

**Security-first approach**
- All personal data (UID/GID, tokens, SSH keys, W&B, HF, git identity) lives in a local `.env` file
- `.env` is **never committed to git**
- Every submission syncs `.env` into a Kubernetes secret
- Pods only read secrets at runtime

**Clean runtime environment**
- Based on the new RCP template
- Uses [uv](https://github.com/astral-sh/uv) for Python package management
- Clean zsh setup
- Minimal symlink tree (only essential VS Code state)

**Ephemeral secrets**
- SSH keys are created on-the-fly for every pod from the secret payload
- Nothing sensitive is stored permanently on scratch

---

## Runtime Environment, Entrypoint, and Permissions

### Docker Image

The Docker image (`docker/Dockerfile`) follows the RCP template:

| Component | Details |
|-----------|---------|
| **Base image** | `nvcr.io/nvidia/pytorch:24.02-py3` (CUDA 12, PyTorch pre-installed) |
| **System packages** | Build tools, git, zsh, ssh client, tmux, etc. |
| **Python manager** | [uv](https://github.com/astral-sh/uv) installed system-wide at `/usr/local/bin/uv` |
| **Entrypoint** | Custom bootstrap script at `docker/entrypoint.sh` |

### Entrypoint Script: High-Level Flow

On every pod start, `entrypoint.sh` performs these steps:

#### 1. Bootstrap Detection

**Action**: Checks for required environment variables

- If missing (`NB_USER`, `NB_UID`, `NB_GROUP`, `NB_GID`, `SCRATCH_HOME_ROOT`, `WORKING_DIR`): Logs warning and executes command as root
- If present (always when using `csub.py`): Proceeds with full bootstrap

#### 2. LDAP User/Group Mirroring

**Action**: Creates your EPFL identity inside the container

- Ensures group with GID `NB_GID` and name `NB_GROUP` exists
- Ensures user with UID `NB_UID` and name `NB_USER` exists
- Configures:
  - Shell: `/bin/zsh`
  - Home: `/home/${NB_USER}`
  - Groups: `sudo`, `adm`
  - Sudo: Passwordless

**Result**: Files created on `/mloscratch` show up with your real EPFL UID/GID

#### 3. Scratch-Backed Storage Configuration

**Action**: Sets up persistent storage with correct permissions

- Computes: `SCRATCH_HOME="${SCRATCH_HOME_ROOT}/${NB_USER}"`
- Sets umask: `umask 007` (group-writable, no world access)
- Creates and configures:
  - `SCRATCH_HOME`: Your persistent home (`/mloscratch/homes/<username>`)
  - `WORKING_DIR`: Where commands execute
  - `HF_HOME`: Shared Hugging Face cache (`/mloscratch/hf_cache`)

**NFS workaround**: Because NFS is root-squashed, the script impersonates a "scratch seed" user (`mljaggi-admin`) to create directories with `chmod 770`. This ensures:
- Directories are writable by the `MLO-unit` group (GID 83070)
- No world-readable access

#### 4. Shell State and Dotfiles

**Action**: Configures persistent shell environment

- Creates: `${SCRATCH_HOME}/.shell/`
- Copies (first run only): oh-my-zsh and `.zshrc` from `/docker`
- Configures environment:
  - `ZDOTDIR`: `${SCRATCH_HOME}/.shell`
  - `ZSH`: oh-my-zsh folder path
  - History: `${SCRATCH_HOME}/.zsh_history`
  - Git config: `${SCRATCH_HOME}/.gitconfig`
- Symlinks to `/home/${NB_USER}` for compatibility

#### 5. Persistent Symlinks (Minimal)

**Action**: Links only essential state from scratch to home

Symlinks from `SCRATCH_HOME` to `/home/${NB_USER}`:
- `.zsh_history` (file)
- `.vscode` (directory)
- `.vscode-server` (directory)

**Everything else** in `/home/${NB_USER}` is ephemeral.

#### 6. SSH Configuration (Ephemeral)

**Action**: Re-creates SSH keys from secrets on every pod start

- Removes and recreates `/home/${NB_USER}/.ssh` (mode `0700`)
- Decodes `SSH_PRIVATE_KEY_B64` → `id_rsa` (mode `0600`)
- Writes `SSH_PUBLIC_KEY` → `id_rsa.pub` (mode `0644`)
- Writes `SSH_KNOWN_HOSTS` → `known_hosts` (mode `0644`)
- Unsets `SSH_PRIVATE_KEY_B64` variable

**Security**: No sensitive SSH material is ever stored on scratch.

#### 7. uv Cache Configuration

**Action**: Configures persistent Python package caches

- Sets `UV_CACHE_DIR="${SCRATCH_HOME}/.cache/uv"`
- Sets `UV_PYTHON_INSTALL_DIR="${SCRATCH_HOME}/.uv"`
- Creates directories as LDAP user

**Result**: uv-managed Python toolchains survive across pods.

#### 8. Git Identity (Optional)

**Action**: Configures global git identity if provided

If `GIT_USER_NAME` / `GIT_USER_EMAIL` are set in `.env`:
```bash
git config --global user.name "..."
git config --global user.email "..."
```

Writes to persistent `GIT_CONFIG_GLOBAL` on scratch.

#### 9. Command Execution

**Action**: Hands off to your actual command

Executes:
```bash
sudo -n -H --preserve-env="${SUDO_PRESERVE_VARS}" -u "${NB_USER}" -- \
  /bin/bash -c 'cd "$1"; shift; exec "$@"' bash "${WORKING_DIR}" "$@"
```

Your command runs:
- **As**: `NB_USER` (your LDAP identity)
- **From**: `WORKING_DIR` (persistent)
- **With**: Environment variables preserved

---

> [!IMPORTANT]
> **Storage persistence model**:
> - **Ephemeral**: Everything under `/home/${NB_USER}` (except symlinked items)
> - **Persistent**: Everything under `SCRATCH_HOME` (`/mloscratch/homes/<user>`)
> - **Permissions**: Group-writable for MLO-unit group (GID 83070)

### Permissions Model and Shared Caches

#### UID/GID Mapping

| Aspect | Details |
|--------|---------|
| **Container UID** | `NB_UID` (from `LDAP_UID` in `.env`) |
| **Container GID** | `NB_GID` (from `LDAP_GID`, typically `83070` for MLO-unit) |
| **Effect** | Files created on `/mloscratch` appear with your real EPFL UID/GID on HaaS and other systems |

#### Group-Based Sharing

**Directory permissions**: `chmod 770` + `umask 007` + GID 83070

This ensures:
- ✅ You and other MLO-unit members can collaborate on shared folders
- ❌ Other Unix users ("world") cannot read or write your data

#### Shared Caches

**Hugging Face cache**: `HF_HOME=/mloscratch/hf_cache`

- Created with group-writable permissions
- Allows multiple users to share cached models/datasets
- Avoids redundant downloads of large artifacts

**Troubleshooting permission errors**:

If you encounter permission errors on `/mloscratch/hf_cache`:

1. Verify `LDAP_UID` and `LDAP_GID` in `.env` are correct
2. Ensure your shells use `umask 007` (entrypoint enforces this automatically)
3. See the [FAQ entry about HF cache permissions](faq.md)

#### Shell Customization

- Default shell: `/bin/zsh`
- `ZDOTDIR`: Points to scratch (`${SCRATCH_HOME}/.shell`)
- Customizations persist across pods

> [!IMPORTANT]
> **Storage rule**: Keep **projects, environments, and data** under `/mloscratch/homes/<user>`, not `/home/<user>`.

---

## uv-Based Python Workflow

We use [uv](https://github.com/astral-sh/uv) instead of conda for faster, more reliable Python package management.

### Basic Workflow

```bash
# Navigate to your project
cd /mloscratch/homes/<username>/project

# Create virtual environment
uv venv .venv

# Activate environment
source .venv/bin/activate

# Install dependencies
uv pip install -r requirements.txt

# Alternative: Using pyproject.toml
uv sync

# Run your code
uv run python train.py
```

### Cache Persistence

- **uv cache**: `${SCRATCH_HOME}/.cache/uv`
- **Python installations**: `${SCRATCH_HOME}/.uv`

Both are on scratch, so environments **survive across pods** while keeping the pod filesystem clean.

### Why uv?

- **Fast**: 10-100x faster than pip
- **Reliable**: Deterministic dependency resolution
- **Modern**: Compatible with pyproject.toml and modern Python standards

---

## Images and Publishing

### Default Image

The provided image should work for most workflows:

```
ic-registry.epfl.ch/mlo/mlo-base:uv1
```

### Building Custom Images

If you need custom dependencies:

```bash
# Customize docker/Dockerfile as needed

# Set build variables
export IMAGE_PATH=mlo/<your-tag>
export TAG=uv-v2
export LDAP_USERNAME=<gaspar>
export LDAP_UID=<uid>
export LDAP_GROUPNAME=MLO-unit
export LDAP_GID=83070

# Build and push
cd docker
./publish.sh
```

**What `publish.sh` does**:
- Passes LDAP build args to Docker
- Builds the image with proper tags
- Pushes to EPFL registry

**Using your custom image**:

Update `.env`:
```bash
RUNAI_IMAGE=ic-registry.epfl.ch/${IMAGE_PATH}:${TAG}
```

---

## Secrets, SSH, and Kubernetes Integration

### Kubernetes Secrets Overview

Basic Kubernetes secret usage:

```bash
# Create secret
kubectl create secret generic my-secret --from-literal=key=value

# Use in run:ai job
runai submit --environment WANDB_API_KEY=SECRET:my-secret,key
```

See the [Kubernetes secret reminder](how_to_use_k8s_secret.md) for more examples.

### How csub.py Handles Secrets

`csub.py` automates secret management:

1. Reads all variables from `.env`
2. Creates/updates Kubernetes secret in your namespace
3. Maps environment variables to the secret via `--environment KEY=SECRET:<secretName>,KEY`

**Default secret-backed variables**:
- `WANDB_API_KEY`
- `HF_TOKEN`
- `SSH_PRIVATE_KEY_B64`
- `SSH_PUBLIC_KEY`
- `SSH_KNOWN_HOSTS`
- `GIT_USER_NAME`
- `GIT_USER_EMAIL`

**Adding more secrets**: Append to `EXTRA_SECRET_KEYS` in `.env` (comma-separated).

### SSH Configuration

#### `.env` Configuration

```bash
# Auto-filled from ~/.ssh/github if empty
SSH_PRIVATE_KEY_B64=....                    # base64 encoded private key
SSH_PUBLIC_KEY=ssh-ed25519 AAAA...          # public key

# Known hosts (typically GitHub)
SSH_KNOWN_HOSTS=github.com ssh-ed25519 AAAA...

# Optional: override default key paths
GITHUB_SSH_KEY_PATH=/path/to/ssh/private/key
GITHUB_SSH_PUBLIC_KEY_PATH=/path/to/ssh/public/key
```

#### Auto-Population Logic

`csub.py` (via `maybe_populate_github_ssh`):

1. Checks if `SSH_PRIVATE_KEY_B64` and `SSH_PUBLIC_KEY` are empty
2. If empty:
   - Uses `GITHUB_SSH_KEY_PATH` if set, otherwise defaults to `~/.ssh/github`
   - Uses `GITHUB_SSH_PUBLIC_KEY_PATH` if set, otherwise defaults to `~/.ssh/github.pub`
   - Reads and base64-encodes the private key
   - Reads the public key
3. Injects into Kubernetes secret

#### Runtime Behavior

The entrypoint:
1. Decodes `SSH_PRIVATE_KEY_B64` → `/home/<user>/.ssh/id_rsa` (mode `0600`)
2. Writes `SSH_PUBLIC_KEY` → `/home/<user>/.ssh/id_rsa.pub` (mode `0644`)
3. Writes `SSH_KNOWN_HOSTS` → `/home/<user>/.ssh/known_hosts` (mode `0644`)
4. Unsets `SSH_PRIVATE_KEY_B64` variable

**Result**: Git over SSH works immediately in every pod, with no sensitive material stored on scratch.

> [!TIP]
> **Easiest setup for git over SSH**:
> 1. Create a dedicated GitHub SSH key: `ssh-keygen -t ed25519 -f ~/.ssh/github`
> 2. Add `~/.ssh/github.pub` to your GitHub account
> 3. Leave all `SSH_*` fields empty in `.env`
> 4. `csub.py` will auto-sync the key for you

---

## Working Efficiently

### Monitoring Jobs

```bash
# List all jobs
runai list jobs

# Detailed job status
runai describe job <name>

# View logs
runai logs <name>

# Connect to pod
runai exec <name> -it -- zsh
```

### VS Code Remote Development

1. Install Kubernetes and Dev Containers extensions
2. Navigate: **Kubernetes** → **rcp-cluster** → **Workloads** → **Pods**
3. Right-click pod → **Attach Visual Studio Code**
4. Open `/mloscratch/homes/<username>` in the remote session

See [Managing Workflows: VS Code](managing_workflows.md#using-vs-code) for details.

### Data Hygiene

| Location | Persistence | Use For |
|----------|-------------|---------|
| `/home/<user>` | **Ephemeral** | Nothing important (lost when pod dies) |
| `/mloscratch/homes/<user>` | **Persistent** | Projects, checkpoints, caches, code |
| `mlodata1` | **Long-term archive** | Published results, paper artifacts |

**Moving to archive**:
```bash
ssh <gaspar>@haas001.rcp.epfl.ch
rsync -avP /mnt/mlo/scratch/homes/<user>/results /mnt/mlo/mlodata1/<user>/
```

### Port Forwarding

Access services running in pods:

```bash
kubectl port-forward <pod-name> 8888:8888
```

Then visit `http://localhost:8888`

### Cleanup

Remove completed jobs:

```bash
runai list | grep " Succeeded " | awk '{print $1}' | xargs -r runai delete job
```

---

## Additional Documentation

- **[Managing Workflows](managing_workflows.md)**: Day-to-day operations, pod management, file management
- **[Multi-node Training](multinode.md)**: Distributed training across multiple nodes
- **[Run:ai CLI](runai_cli.md)**: Alternative workflows using raw run:ai commands
- **[FAQ](faq.md)**: Frequently asked questions and troubleshooting
- **[Main README](../README.md)**: Getting started guide for new users