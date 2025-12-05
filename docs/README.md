# More detailed explanation of the setup

Some more detailed explanation of the setup. This is a more technical explanation of the setup, and is not necessary to follow the getting started guide.

Highlights of the revamped setup:
- `csub.py` now shells out to the run:ai CLI directly. There is no generated YAML anymore, only the CLI command you would type by hand.
- All personal data (UID/GID, tokens, SSH keys, W&B, HF, git identity, …) lives in a local `.env` file that you keep out of git. Every submission syncs this file into a Kubernetes secret and the pod only reads secrets at runtime.
- The runtime image is based on the new RCP template, uses `uv` for Python package management, provides a clean zsh setup, and avoids the giant symlink tree from the previous iteration.
- SSH keys are created on-the-fly for every pod from the secret payload. Nothing sensitive is stored permanently on scratch.

## Runtime environment, entrypoint and permissions

The Docker image (`docker/Dockerfile`) follows the new RCP template:

- base image: `nvcr.io/nvidia/pytorch:24.02-py3` (CUDA 12, PyTorch pre-installed),
- Debian packages: build tools, git, zsh, ssh client, tmux, etc.,
- [uv](https://github.com/astral-sh/uv) installed system-wide (`/usr/local/bin/uv`),
- a custom entrypoint script at `docker/entrypoint.sh`.

### High-level flow of `entrypoint.sh`

On every pod start, `entrypoint.sh` roughly does the following:

1. **Detects whether it should bootstrap anything at all.**  
   If the key environment variables (`NB_USER`, `NB_UID`, `NB_GROUP`, `NB_GID`, `SCRATCH_HOME_ROOT`, `WORKING_DIR`) are missing, the script logs a warning and simply `exec`s the original command as-is (you get a plain root shell).  
   When the pod is started via `csub.py`, these variables are always set.

2. **Mirrors your LDAP user & group inside the container.**  
   The script:
   - ensures there is a group with GID `NB_GID` and name `NB_GROUP`, creating/renaming as needed;
   - ensures a user with UID `NB_UID` and name `NB_USER` exists (creating or renaming an existing UID if necessary);
   - sets the user’s shell to `/bin/zsh`, home to `/home/${NB_USER}`, puts the user into `sudo`/`adm`, and grants passwordless sudo for convenience.  
   This is what makes files you create on `/mloscratch` show up with your real EPFL UID/GID.

3. **Configures the scratch-backed home and working directory.**  
   - It computes `SCRATCH_HOME="${SCRATCH_HOME:-${SCRATCH_HOME_ROOT}/${NB_USER}}"` and sets a strict umask: `umask 007` (group-writable, no world access).  
   - Using a helper `ensure_dir_with_owner`, it creates and permissions:
     - `SCRATCH_HOME` (your persistent “home” on scratch),
     - `WORKING_DIR` (where the entrypoint finally `cd`s into),
     - `HF_HOME` (defaults to `/mloscratch/hf_cache`, shared HF cache).  
   - Because the underlying NFS export is root-squashed, the script does **not** call `chown` directly. Instead it impersonates a designated “scratch seed” user (by default `mljaggi-admin`) via `sudo -u "${SCRATCH_SEED_USER:-mljaggi-admin}"` to run `mkdir -p` and `chmod 770`. This ensures:
     - directories exist,
     - they are writable by the `MLO-unit` group (GID 83070),
     - they are not readable by unrelated users or the `world`.

4. **Stages shell state and dotfiles on scratch.**  
   The script:
   - creates a per-user shell root `${SCRATCH_HOME}/.shell`,
   - copies the base oh-my-zsh and `.zshrc` from `/docker` into that directory (first run only),
   - sets `ZDOTDIR` to `${SCRATCH_HOME}/.shell`, `ZSH` to the oh-my-zsh folder,
   - stores shell history in `${SCRATCH_HOME}/.zsh_history` and a global git config in `${SCRATCH_HOME}/.gitconfig`.  
   It then symlinks these back into `/home/${NB_USER}` so tools expecting `~/.zshrc` and `~/.oh-my-zsh` still work.

5. **Creates a small set of persistent symlinks.**  
   Via `link_persistent_item`, it only symlinks:
   - `.zsh_history` (file),
   - `.vscode` (dir),
   - `.vscode-server` (dir),  
   from scratch into `/home/${NB_USER}`. Everything else in `/home/${NB_USER}` remains ephemeral inside the pod. This keeps the layout predictable while still persisting the important editor state.

6. **Re-hydrates SSH configuration from secrets.**  
   - Removes and recreates `/home/${NB_USER}/.ssh` with correct `0700` permissions.
   - If `SSH_PRIVATE_KEY_B64` is set, it is base64-decoded into `id_rsa` (mode `0600`).
   - If `SSH_PUBLIC_KEY` is set, it is written to `id_rsa.pub` (mode `0644`).
   - If `SSH_KNOWN_HOSTS` is set, it is written to `known_hosts` (mode `0644`).  
   Afterwards, the base64 variable is unset inside the process. Since the secret is mounted as environment only, no sensitive material is persisted on scratch.

7. **Configures uv caches and Python install location.**  
   - Sets `UV_CACHE_DIR="${SCRATCH_HOME}/.cache/uv"` and `UV_PYTHON_INSTALL_DIR="${SCRATCH_HOME}/.uv"`.
   - Ensures those directories exist as the LDAP user.  
   This is why uv-managed Python toolchains survive across pods.

8. **Applies git identity from env (optional).**  
   If you set `GIT_USER_NAME` / `GIT_USER_EMAIL` in `.env`, the entrypoint runs:
   - `git config --global user.name ...`
   - `git config --global user.email ...`  
   for the LDAP user, writing into the persistent `GIT_CONFIG_GLOBAL` on scratch.

9. **Hands over control to your command as the LDAP user in `WORKING_DIR`.**  
   Finally, the script runs:
   - `sudo -n -H --preserve-env="${SUDO_PRESERVE_VARS}" -u "${NB_USER}" -- /bin/bash -c 'cd "$1"; shift; exec "$@"' bash "${WORKING_DIR}" "$@"`  
   so your actual container command executes:
   - as `NB_USER` (your LDAP identity),
   - from the persistent `WORKING_DIR`,
   - with key environment variables (`SCRATCH_HOME`, `WORKING_DIR`, `HF_HOME`, uv paths, git config, shell settings) preserved.

The important takeaway: **anything under `/home/${NB_USER}` is ephemeral; anything under `SCRATCH_HOME` (usually `/mloscratch/homes/<user>`) persists across pods and is group-writable for the MLO-unit group.**

### Permissions model and shared caches

To summarise the permissions setup:

- **UID/GID mapping**
  - Inside the container, your effective UID is `NB_UID` (from `LDAP_UID` in `.env`), and your primary GID is `NB_GID` (from `LDAP_GID`, typically `83070` for `MLO-unit`).
  - This means files created on `/mloscratch` show up on the HaaS machine and elsewhere with your real EPFL UID/GID.

- **Group-based sharing**
  - Directories created by the entrypoint on scratch are `chmod 770` by the “scratch seed” user. Combined with `umask 007` and GID 83070, this ensures:
    - you and other MLO-unit members can collaborate on shared folders,
    - other Unix users (“world”) cannot read or write your data.

- **HF cache and other shared state**
  - `HF_HOME` defaults to `/mloscratch/hf_cache` and is created with group-writable permissions. This allows multiple users to share the Hugging Face cache and avoid re-downloading large artefacts.
  - If you hit permission errors around `/mloscratch/hf_cache`, first check:
    - that your UID/GID in `.env` are correct,
    - that your shells use `umask 007` (entrypoint enforces it for pods; see also the [FAQ entry about HF cache permissions](faq.md)).

Because the shell defaults to `/bin/zsh` with `ZDOTDIR` on scratch, you can keep your usual zsh customisations; just remember that your **projects, environments, and data should live under `/mloscratch/homes/<user>`**, not in `/home/<user>`.

## uv-based Python workflow

We no longer bootstrap conda environments. Instead each pod comes with uv pre-installed:

```bash
cd /mloscratch/homes/<you>/project
uv venv .venv
source .venv/bin/activate
uv pip install -r requirements.txt
# or, if you manage dependencies via pyproject.toml:
uv sync
uv run python train.py
```

The uv cache and Python installations live on scratch, so environments survive across pods while keeping the pod filesystem clean.

## Images & publishing

The provided image (`ic-registry.epfl.ch/mlo/mlo:uv-base`) should work for most workflows. If you need custom dependencies:

```bash
# customise Dockerfile if needed
export IMAGE_PATH=mlo/<your-tag>
export TAG=uv-v2
export LDAP_USERNAME=<gaspar>
export LDAP_UID=<uid> LDAP_GROUPNAME=MLO-unit LDAP_GID=83070
./publish.sh
```

`publish.sh` passes the LDAP build args expected by the RCP template and pushes to the EPFL registry. Afterwards set `RUNAI_IMAGE=ic-registry.epfl.ch/${IMAGE_PATH}:${TAG}` in `.env`.

## Secrets, SSH, and kube integration

The repo ships with `how_to_use_k8s_secret.txt` as a minimal reminder:

```
kubectl create secret generic my-secret --from-literal=key=value
runai submit --environment WANDB_API_KEY=SECRET:my-secret,key
```

`csub.py` automates this; each environment variable listed under `SECRET_KEYS` in the script is turned into `--environment KEY=SECRET:<secretName>,KEY`. To add additional secret-backed variables simply append them (comma separated) to `EXTRA_SECRET_KEYS` in `.env`.

For SSH we expect the following entries in `.env`:

```
SSH_PRIVATE_KEY_B64=....                  # base64 encoded private key (auto-filled from ~/.ssh/github if empty)
SSH_PUBLIC_KEY=ssh-ed25519 AAAA...        # auto-filled from ~/.ssh/github.pub if empty
SSH_KNOWN_HOSTS=github.com ssh-ed25519 AAAA...

# Optional: override which local key gets auto-synced into SSH_*
GITHUB_SSH_KEY_PATH=/path/to/ssh/private/key
GITHUB_SSH_PUBLIC_KEY_PATH=/path/to/ssh/public/key
```

`csub.py` (via `maybe_populate_github_ssh`) will:
- use `GITHUB_SSH_KEY_PATH` / `GITHUB_SSH_PUBLIC_KEY_PATH` if set,
- otherwise default to `~/.ssh/github` and `~/.ssh/github.pub`,
- and only fill `SSH_PRIVATE_KEY_B64` / `SSH_PUBLIC_KEY` if they are empty.

The entrypoint then decodes the private key, writes the public key + known hosts file and applies correct permissions, so git over SSH works immediately inside every pod without persisting sensitive material anywhere on scratch.

> [!TIP]
> If all you want is “git over SSH from inside pods”, the easiest path is:
> - create a dedicated GitHub SSH key locally under `~/.ssh/github`,
> - leave all `SSH_*` fields empty in `.env`,
> - optionally configure `GITHUB_SSH_KEY_PATH` if you keep the key elsewhere.

For more examples of raw Kubernetes secrets and how they interact with run:ai, see the short [Kubernetes secret reminder](how_to_use_k8s_secret.md).

## Working efficiently

- **Monitoring**: `runai list jobs`, `runai describe job <name>`, `runai logs <name>`.
- **VS Code**: use the Kubernetes extension → rcp-cluster → Workloads → Pods → *Attach Visual Studio Code*. Remember to open `/mloscratch/homes/<user>` inside the remote session.
- **Data hygiene**: everything under `/home/<user>` is ephemeral. Keep projects, checkpoints, and caches under `/mloscratch/homes/<user>` and move long-term artefacts to `mlodata1` via the HaaS machine (`ssh <gaspar>@haas001.rcp.epfl.ch`).
- **Port forwarding**: `kubectl port-forward <pod> 8888:8888` works once the pod is running.
- **Cleanup**: `runai list | grep " Succeeded " | awk '{print $1}' | xargs -r runai delete job`.

For distributed or multi-node jobs see [`multinode.md`](multinode.md).  
For running raw run:ai commands or using ready-made base images, see [`runai_cli.md`](runai_cli.md).  
Frequently asked questions live in [`faq.md`](faq.md).  
The high-level, user-facing getting-started guide is the top-level [`../README.md`](../README.md).