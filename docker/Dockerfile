# CUDA/PyTorch base image that matches EPFL GPUs
FROM --platform=linux/amd64 nvcr.io/nvidia/pytorch:24.02-py3
LABEL maintainer="Alexander Haegele <alexander.hagele@epfl.ch>"

# Allow non-interactive apt installs (no tz prompts)
ARG DEBIAN_FRONTEND=noninteractive
ARG LDAP_USERNAME=cluster
ARG LDAP_UID=1000
ARG LDAP_GROUPNAME=cluster
ARG LDAP_GID=1000

ENV LANG=en_US.UTF-8 \
    LC_ALL=en_US.UTF-8 \
    LANGUAGE=en_US:en \
    SHELL=/bin/zsh \
    TF_FORCE_GPU_ALLOW_GROWTH=true

# Basic tooling for interactive workflows plus sudo for entrypoint tricks
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    git \
    gnupg \
    htop \
    nvtop \
    jq \
    less \
    libssl-dev \
    locales \
    nano \
    openssh-client \
    pkg-config \
    python3-full \
    rsync \
    screen \
    sudo \
    tmux \
    unzip \
    vim \
    wget \
    zsh \
    && rm -rf /var/lib/apt/lists/*

# Generate UTF-8 locale for Python + shells
RUN locale-gen en_US.UTF-8

# Placeholder LDAP-like account; entrypoint will later mutate UID/GID
RUN groupadd -g ${LDAP_GID} ${LDAP_GROUPNAME} && \
    useradd -m -s /bin/zsh -g ${LDAP_GROUPNAME} -u ${LDAP_UID} ${LDAP_USERNAME}

# Seed account that already owns /mloscratch; entrypoint impersonates it
RUN useradd -m -s /bin/zsh -g ${LDAP_GROUPNAME} -u 177449 mljaggi-admin

# Pre-install Oh My Zsh once (later copied to scratch-backed homes)
RUN sh -c "$(curl -fsSL https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh)" "" --unattended && \
    chsh -s /bin/zsh root

# Install uv once at build time; per-user caches live on scratch
ENV UV_INSTALL_DIR=/usr/local/bin
RUN curl -LsSf https://astral.sh/uv/install.sh | sh

# Ship entrypoint + cached shell assets inside the image
RUN mkdir -p /docker
COPY entrypoint.sh /docker/entrypoint.sh
RUN chmod +x /docker/entrypoint.sh

# Copy root’s Oh My Zsh artifacts so entrypoint can clone them cheaply
RUN cp -r /root/.oh-my-zsh /docker/.oh-my-zsh && \
    cp /root/.zshrc /docker/.zshrc && \
    echo "umask 007" >> /docker/.zshrc

# Set root password only because some infra still demands it
RUN echo 'root:root' | chpasswd

WORKDIR /mloscratch/homes/
ENTRYPOINT ["/docker/entrypoint.sh"]
CMD ["/bin/zsh"]