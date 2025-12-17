#!/usr/bin/env bash
set -euo pipefail

log() {
  echo "[entrypoint] $*"
}

# NOTE: NB_* vars are injected via csub.py; without them we fall back to plain root shell
need_env() {
  local missing=()
  for var in NB_USER NB_UID NB_GROUP NB_GID SCRATCH_HOME_ROOT WORKING_DIR; do
    if [[ -z "${!var:-}" ]]; then
      missing+=("$var")
    fi
  done
  if ((${#missing[@]})); then
    log "Missing env vars (${missing[*]}), skipping bootstrap."
    exec "$@"
  fi
}

ensure_posix_user() {
  # Mirror the LDAP user inside the container and grant passwordless sudo
  su - root <<EOF >/dev/null
root
set -euo pipefail
if ! getent group ${NB_GROUP} >/dev/null 2>&1; then
  if getent group ${NB_GID} >/dev/null 2>&1; then
    GROUP_NAME=\$(getent group ${NB_GID} | cut -d: -f1)
    if [[ "\$GROUP_NAME" != "${NB_GROUP}" ]]; then
      groupmod -n ${NB_GROUP} "\$GROUP_NAME"
    fi
  else
    groupadd ${NB_GROUP} -g ${NB_GID}
  fi
fi
EXISTING_UID_USER=\$(getent passwd ${NB_UID} | cut -d: -f1 || true)
if [[ -n "\$EXISTING_UID_USER" && "\$EXISTING_UID_USER" != "${NB_USER}" ]]; then
  echo "[entrypoint] Renaming existing UID ${NB_UID} user '\$EXISTING_UID_USER' to ${NB_USER}"
  usermod -l ${NB_USER} "\$EXISTING_UID_USER"
  usermod -d /home/${NB_USER} -m ${NB_USER}
fi
if ! id -u ${NB_USER} >/dev/null 2>&1; then
  echo "[entrypoint] Creating user ${NB_USER}"
  useradd -M -s /bin/zsh -N -u ${NB_UID} -g ${NB_GID} ${NB_USER}
fi
echo "${NB_USER}:${NB_USER}" | chpasswd
usermod -aG sudo,adm ${NB_USER}
mkdir -p /home/${NB_USER}
chown ${NB_USER}:${NB_GROUP} /home/${NB_USER}
chsh -s /bin/zsh ${NB_USER}
if ! grep -q "^${NB_USER} " /etc/sudoers; then
  echo "${NB_USER} ALL=(ALL:ALL) NOPASSWD:ALL" >> /etc/sudoers
fi
EOF
  rm -rf "/home/${NB_USER}/.zshrc"
}

SUDO_PRESERVE_VARS="SCRATCH_HOME,ZDOTDIR,ZSH,HISTFILE,GIT_CONFIG_GLOBAL,UV_CACHE_DIR,UV_PYTHON_INSTALL_DIR,WORKING_DIR,HF_HOME"

run_as_scratch_owner() {
  # Scratch exports are root-squashed, so we impersonate the seed owner for mkdir/chmod
  local owner_user="${SCRATCH_SEED_USER:-mljaggi-admin}"
  sudo -n -u "${owner_user}" -- "$@" || true
}

run_as_nb_user() {
  # Convenience wrapper to execute commands as the LDAP user while keeping env in sync
  sudo -n -H --preserve-env="${SUDO_PRESERVE_VARS}" -u "${NB_USER}" -- "$@"
}

ensure_dir_with_owner() {
  # Make sure the directory exists and has group-write perms; no chown to avoid root-squash
  local target="$1"
  if [[ ! -d "$target" ]]; then
    log "Creating ${target} as scratch owner"
    run_as_scratch_owner mkdir -p "$target" || true
  fi

  if [[ -d "$target" ]]; then
    log "Ensuring permissions on ${target} via scratch owner"
    run_as_scratch_owner chmod 770 "$target" || true
  fi
}

setup_shell_state() {
  # Stage oh-my-zsh and dotfiles on scratch so they persist across pods
  local shell_root="${SCRATCH_HOME}/.shell"
  local home_zshrc="/home/${NB_USER}/.zshrc"
  local home_ohmyzsh="/home/${NB_USER}/.oh-my-zsh"
  run_as_nb_user mkdir -p "${shell_root}"
  if [[ ! -d "${shell_root}/.oh-my-zsh" && -d /docker/.oh-my-zsh ]]; then
    run_as_nb_user cp -r /docker/.oh-my-zsh "${shell_root}/.oh-my-zsh"
  fi
  if [[ ! -f "${shell_root}/.zshrc" && -f /docker/.zshrc ]]; then
    run_as_nb_user cp /docker/.zshrc "${shell_root}/.zshrc"
  fi
  export ZDOTDIR="${shell_root}"
  export ZSH="${shell_root}/.oh-my-zsh"
  export HISTFILE="${SCRATCH_HOME}/.zsh_history"
  run_as_nb_user touch "${HISTFILE}"
  run_as_nb_user chmod 600 "${HISTFILE}"
  export GIT_CONFIG_GLOBAL="${SCRATCH_HOME}/.gitconfig"
  run_as_nb_user touch "${GIT_CONFIG_GLOBAL}"
  run_as_nb_user ln -snf "${shell_root}/.zshrc" "${home_zshrc}"
  run_as_nb_user ln -snf "${shell_root}/.oh-my-zsh" "${home_ohmyzsh}"
}

link_persistent_item() {
  # symlink selected dot-directories back into /home for better tooling defaults
  local name="$1"
  local kind="$2"
  local persistent="${SCRATCH_HOME}/${name}"
  local dest="/home/${NB_USER}/${name}"
  if [[ "$kind" == "dir" ]]; then
    run_as_nb_user mkdir -p "$persistent"
  else
    run_as_nb_user touch "$persistent"
  fi
  run_as_nb_user ln -snf "$persistent" "$dest"
}

setup_git_identity() {
  # Optional global git identity pulled from env
  local existing_name existing_email
  existing_name="$(run_as_nb_user git config --global --get user.name || true)"
  existing_email="$(run_as_nb_user git config --global --get user.email || true)"

  if [[ -n "${GIT_USER_NAME:-}" && -z "${existing_name}" ]]; then
    run_as_nb_user git config --global user.name "${GIT_USER_NAME}"
  fi
  if [[ -n "${GIT_USER_EMAIL:-}" && -z "${existing_email}" ]]; then
    run_as_nb_user git config --global user.email "${GIT_USER_EMAIL}"
  fi
}

setup_ssh() {
  # Re-hydrate SSH material from env vars; everything lives inside /home/${NB_USER}
  local ssh_dir="/home/${NB_USER}/.ssh"
  run_as_nb_user rm -rf "${ssh_dir}"
  run_as_nb_user mkdir -p "${ssh_dir}"
  run_as_nb_user chmod 700 "${ssh_dir}"
  if [[ -n "${SSH_PRIVATE_KEY_B64:-}" ]]; then
    echo "${SSH_PRIVATE_KEY_B64}" | base64 --decode | run_as_nb_user tee "${ssh_dir}/id_rsa" >/dev/null || true
    run_as_nb_user chmod 600 "${ssh_dir}/id_rsa"
  fi
  if [[ -n "${SSH_PUBLIC_KEY:-}" ]]; then
    printf "%s\n" "${SSH_PUBLIC_KEY}" | run_as_nb_user tee "${ssh_dir}/id_rsa.pub" >/dev/null
    run_as_nb_user chmod 644 "${ssh_dir}/id_rsa.pub"
  fi
  if [[ -n "${SSH_KNOWN_HOSTS:-}" ]]; then
    printf "%s\n" "${SSH_KNOWN_HOSTS}" | run_as_nb_user tee "${ssh_dir}/known_hosts" >/dev/null
    run_as_nb_user chmod 644 "${ssh_dir}/known_hosts"
  fi
  unset SSH_PRIVATE_KEY_B64
}

configure_uv() {
  # Cache uv installs on scratch so toolchains persist between runs
  export UV_CACHE_DIR="${SCRATCH_HOME}/.cache/uv"
  export UV_PYTHON_INSTALL_DIR="${SCRATCH_HOME}/.uv"
  run_as_nb_user mkdir -p "${UV_CACHE_DIR}" "${UV_PYTHON_INSTALL_DIR}"
}

need_env
log "Ensuring POSIX user ${NB_USER} (${NB_UID}:${NB_GID})"
ensure_posix_user

umask 007
SCRATCH_HOME="${SCRATCH_HOME:-${SCRATCH_HOME_ROOT}/${NB_USER}}"
export SCRATCH_HOME
log "Ensuring scratch home ${SCRATCH_HOME}"
ensure_dir_with_owner "${SCRATCH_HOME}"
log "Ensuring working dir ${WORKING_DIR}"
ensure_dir_with_owner "${WORKING_DIR}"
export WORKING_DIR
log "Ensuring HF cache ${HF_HOME:-/mloscratch/hf_cache}"
ensure_dir_with_owner "${HF_HOME:-/mloscratch/hf_cache}"

# Everything after this point runs as the LDAP user inside the scratch-backed workspace
log "Setting up shell state"
setup_shell_state
log "Linking persistent items"
link_persistent_item ".zsh_history" "file"
link_persistent_item ".vscode" "dir"
link_persistent_item ".vscode-server" "dir"
link_persistent_item ".cursor" "dir"
link_persistent_item ".cursor-server" "dir"
log "Configuring git identity"
setup_git_identity
log "Installing SSH material"
setup_ssh
log "Configuring uv caches"
configure_uv

log "Handing over control to $*"
# Preserve the full environment (incl. variables injected by the runner) when switching user
exec sudo -n -E -H -u "${NB_USER}" -- /bin/bash -c 'cd "$1"; shift; exec "$@"' bash "${WORKING_DIR}" "$@"
