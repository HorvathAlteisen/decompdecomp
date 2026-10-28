# The smallest image VS Code fully supports for decompdecomp. Debian slim: VS Code Server needs glibc, libstdc++,
# ca-certificates and tar (code.visualstudio.com/docs/remote/linux), all already in python:slim. Alpine is smaller
# but musl: extensions with native code break there, and so do decompdecomp's pinned compilers (glibc builds).
FROM python:3.12-slim-trixie

COPY --from=ghcr.io/astral-sh/uv:0.11.32 /uv /usr/local/bin/uv

# A network that inspects TLS: put its root CA in .devcontainer/certs/ as a .crt (ignored by git), and Python, uv
# and git trust it. Without one this does nothing.
COPY certs/ /usr/local/share/ca-certificates/devcontainer/

# One layer. git: VS Code's source control, and decompdecomp clones public decomps; nothing else, the compilers and
# their 32-bit runtime come pinned through decompdecomp's own installer (toolchains.toml), not from apt. Then the
# network's root CA, and a user of your own (VS Code matches its uid to yours) with the folders the volumes in
# devcontainer.json keep.
RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && update-ca-certificates \
    && useradd -m -s /bin/bash -u 1000 vscode \
    && mkdir -p /home/vscode/Decomp-dev /home/vscode/.local/share/decompnet \
    && chown -R vscode:vscode /home/vscode \
    && rm -rf /var/lib/apt/lists/*

# the venv stays in the container, not in the workspace (a Windows checkout may have its own .venv there)
ENV UV_PROJECT_ENVIRONMENT=/home/vscode/.venv \
    UV_PYTHON_DOWNLOADS=never \
    UV_LINK_MODE=copy \
    UV_SYSTEM_CERTS=1 \
    SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt

USER vscode
